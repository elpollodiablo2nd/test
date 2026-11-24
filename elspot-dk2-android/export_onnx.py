"""Export Timestral checkpoints to ONNX for on-device (Android/Pixel) inference.

The exported graph has FIXED shapes (context T=768 hourly steps, horizon H=168) so no
dynamic-axis massaging is needed; the app left-pads shorter history with NaN and slices
the 168-step output to the requested horizon (24..168 = up to 7 days).

Inputs:
  context          float32 (1, 1, 768)  hourly prices DKK/MWh, NaN = missing (left padding)
  known_covariates float32 (1, 13, 936) rows [wind, temp, solar, DE, SE3,
                                       de_windpw, de_wind10, de_solar, de_temp, de_cloud, de_pres,
                                       enc_hour, enc_weekday] over context+horizon (936 = 768 + 168);
                                       NaN = missing. The 6 de_* rows are N-Germany weather (wind-power
                                       proxy from wind100, wind10, solar, temp, cloud, pressure) — they
                                       help at day 3-7 on top of the ridge-filled DE/SE3 rows.
                                       DE/SE3 = neighbour-zone day-ahead prices DKK/MWh (the big
                                       zero-shot signal: full-year backtest 28M h24 MAE% 16.5 -> 4.3);
                                       beyond the published ~+36h the app fills them with an on-device
                                       ridge forecast (see index.html Core.buildNeighborFill).
                                       enc_* are the target-encoded categorical codes, computed
                                       exactly like TimestralForecaster._encode_categorical —
                                       the app replicates that in JS (see index.html Core).
Output:
  quantiles        float32 (1, 1, 168, 21) monotone quantiles 0.01..0.99 (median = index 10).
  NO non-negative clamp (clip_nonnegative=False): negative prices are predictable.

Run with the workflows venv:
  elspot-dk2-workflows/.venv/bin/python elspot-dk2-android/export_onnx.py --size 28M
"""

import argparse
import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import torch
from torch import nn

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
HF_CACHE = Path("/tmp/timestral-hf-cache")
T_CTX = 768  # context steps (multiple of patch_size 32); app pads/truncates to this
H = 168      # horizon steps exported (7 days; app slices 24..168)
PATCH = 32
WEATHER_VARS = ("wind_speed_10m", "temperature_2m", "shortwave_radiation")
WEATHER_LAT, WEATHER_LON = 55.6761, 12.5683
DE_WX_POINTS = ((54.79789, 9.445545), (54.024605, 10.465116), (53.60281, 10.0))  # Flensburg, Fehmarn area, Hamburg
DE_WX_VARS = ("wind_speed_100m", "wind_speed_10m", "shortwave_radiation", "temperature_2m", "cloud_cover", "surface_pressure")

def wind_power_proxy(w100):
    v = max(0.0, min(float(w100), 25.0) - 3.0)
    return v ** 3 / 22.0 ** 3
ENERGINET = "https://api.energidataservice.dk/dataset/DayAheadPrices"
OM_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
OM_FORECAST = "https://api.open-meteo.com/v1/forecast"


def http_json(url, tries=4):
    import time
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if "429" in str(e) and a < tries - 1:
                time.sleep(20)
            else:
                raise


def fetch_reference_points(days=34):
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M")
    params = urllib.parse.urlencode({
        "filter": json.dumps({"PriceArea": ["DK2"]}),
        "start": start, "sort": "TimeUTC asc", "limit": 4000,
    })
    try:
        data = http_json(ENERGINET + "?" + params)
        records = data.get("records", [])
    except Exception as e:
        print(f"Energinet reference fetch failed ({e}); using local snapshot")
        records = json.load(open(REPO / "elspot-dk2" / "assets" / "prices-dk2.json"))["records"]
    buckets = {}
    for rec in records:
        if not rec.get("TimeUTC") or rec.get("DayAheadPriceDKK") is None:
            continue
        d = datetime.fromisoformat(str(rec["TimeUTC"]).replace("Z", "+00:00")).astimezone(timezone.utc)
        hour = d.replace(minute=0, second=0, microsecond=0)
        buckets.setdefault(hour, []).append(float(rec["DayAheadPriceDKK"]))
    return sorted((h, sum(v) / len(v)) for h, v in buckets.items())


def fetch_neighbor_maps(days=34):
    """DE + SE3 day-ahead hourly prices (DKK/MWh) from Energinet, keyed by UTC hour."""
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M")
    params = urllib.parse.urlencode({
        "filter": json.dumps({"PriceArea": ["DE", "SE3"]}),
        "start": start, "sort": "TimeUTC asc", "limit": 9000,
    })
    try:
        data = http_json(ENERGINET + "?" + params)
        records = data.get("records", [])
    except Exception as e:
        print(f"Energinet neighbour fetch failed ({e}); using local snapshot")
        records = json.load(open(REPO / "elspot-dk2" / "assets" / "prices-neighbors.json"))["records"]
    out = {"DE": {}, "SE3": {}}
    for rec in records:
        if not rec.get("TimeUTC") or rec.get("DayAheadPriceDKK") is None:
            continue
        d = datetime.fromisoformat(str(rec["TimeUTC"]).replace("Z", "+00:00")).astimezone(timezone.utc)
        hour = d.replace(minute=0, second=0, microsecond=0)
        key = hour.strftime("%Y-%m-%dT%H:00")
        out.setdefault(rec["PriceArea"], {}).setdefault(key, []).append(float(rec["DayAheadPriceDKK"]))
    return {a: {k: sum(v) / len(v) for k, v in m.items()} for a, m in out.items()}


def _merge_payloads(payloads, variables):
    # payloads: archive + forecast; multi-location responses are lists of per-point objects -> average per hour
    acc = {}
    for payload in payloads:
        locs = payload if isinstance(payload, list) else [payload]
        for loc in locs:
            h = loc.get("hourly", {})
            times = h.get("time", [])
            cols = [h.get(v, []) for v in variables]
            for i, t in enumerate(times):
                key = datetime.fromisoformat(str(t)).strftime("%Y-%m-%dT%H:00")
                a = acc.setdefault(key, [0.0] * len(variables) + [0] * len(variables))
                for vi, c in enumerate(cols):
                    if i < len(c) and c[i] is not None:
                        a[vi] += float(c[i]); a[len(variables) + vi] += 1
    return {k: [a[vi] / a[len(variables) + vi] if a[len(variables) + vi] else float("nan")
                for vi in range(len(variables))] for k, a in acc.items()}


def fetch_weather_map(points):
    hours = [h for h, _ in points]
    start = hours[0].date()
    end = min((hours[-1] + timedelta(hours=H)).date(), datetime.now(timezone.utc).date())  # archive has no future
    dk_common = {"latitude": WEATHER_LAT, "longitude": WEATHER_LON, "timezone": "UTC", "hourly": ",".join(WEATHER_VARS)}
    de_common = {"latitude": ",".join(str(p[0]) for p in DE_WX_POINTS),
                 "longitude": ",".join(str(p[1]) for p in DE_WX_POINTS),
                 "timezone": "UTC", "hourly": ",".join(DE_WX_VARS)}
    weather = _merge_payloads([
        http_json(OM_ARCHIVE + "?" + urllib.parse.urlencode({**dk_common, "start_date": str(start), "end_date": str(end)})),
        http_json(OM_FORECAST + "?" + urllib.parse.urlencode({**dk_common, "forecast_days": 8})),
    ], WEATHER_VARS)
    de_weather = _merge_payloads([
        http_json(OM_ARCHIVE + "?" + urllib.parse.urlencode({**de_common, "start_date": str(start), "end_date": str(end)})),
        http_json(OM_FORECAST + "?" + urllib.parse.urlencode({**de_common, "forecast_days": 8})),
    ], DE_WX_VARS)
    return weather, de_weather


def build_inputs(points, weather, de_weather, neighbors):
    """Reference inputs mirroring the app: last T_CTX hours (NaN-padded), covariates over T_CTX+H."""
    hours = [h for h, _ in points][-T_CTX:]
    prices = [p for _, p in points][-T_CTX:]
    pad = T_CTX - len(hours)
    hours = [None] * pad + hours
    prices = [float("nan")] * pad + prices
    future = [hours[-1] + timedelta(hours=i + 1) for i in range(H)]
    all_hours = hours + future

    context = np.asarray(prices, dtype=np.float32)[None, None, :]
    cat = np.asarray([[h.hour if h else float("nan") for h in all_hours],
                      [h.weekday() if h else float("nan") for h in all_hours]], dtype=np.float64)[None, :, :]
    rows = []
    for i in range(3):  # wind, temp, solar
        rows.append([weather.get(h.strftime("%Y-%m-%dT%H:00"), [float("nan")] * 3)[i] if h else float("nan")
                     for h in all_hours])
    for area in ("DE", "SE3"):  # neighbour day-ahead prices (app fills a ridge forecast beyond ~+36h)
        nmap = neighbors.get(area, {})
        rows.append([nmap.get(h.strftime("%Y-%m-%dT%H:00"), float("nan")) if h else float("nan") for h in all_hours])
    for i, v in enumerate(DE_WX_VARS):  # N-Germany weather rows (row order matches the app)
        rows.append([(wind_power_proxy(de_weather.get(h.strftime("%Y-%m-%dT%H:00"), [float("nan")] * 6)[0]) if i == 0
                      else de_weather.get(h.strftime("%Y-%m-%dT%H:00"), [float("nan")] * 6)[i]) if h else float("nan")
                     for h in all_hours])
    known_w = np.asarray([rows], dtype=np.float64)
    return context, cat, known_w, all_hours


class OnnxWrapper(nn.Module):
    """forecast() with categorical covariates pre-encoded (so no numpy inside the graph)."""

    def __init__(self, forecaster, horizon):
        super().__init__()
        self.model = forecaster.model  # registered submodule -> weights export as shared initializers
        self.f = forecaster
        self.horizon = horizon

    def forward(self, context, known_covariates):
        # mirrors forecast(..., clip_nonnegative=False): symmetric averaging, NO clamp at 0
        # (negative day-ahead prices are real in high-wind hours and must be predictable)
        f = self.f
        inputs, mask = f._as_context(context, None)
        q = f._forecast_raw(inputs, mask, self.horizon, None, known_covariates)
        m = f._forecast_raw(-inputs, mask, self.horizon, None, -known_covariates)
        return 0.5 * (q + (-m).flip(-1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", default="28M", choices=["5M", "28M", "123M", "209M"])
    ap.add_argument("--outdir", default=str(HERE / "www" / "assets"))
    ap.add_argument("--quant", default="int8", choices=["fp32", "fp16", "int8"])
    args = ap.parse_args()

    from huggingface_hub import snapshot_download
    from timestral import TimestralForecaster

    print(f"loading mistralai/Timestral-{args.size} ...")
    snap = snapshot_download(f"mistralai/Timestral-{args.size}", cache_dir=str(HF_CACHE))
    forecaster = TimestralForecaster.from_pretrained(snap, device="cpu")
    model = forecaster.model
    model.eval()
    for p_ in model.parameters():
        p_.requires_grad_(False)

    print("fetching reference data (Energinet + Open-Meteo) ...")
    points = fetch_reference_points()
    weather, de_weather = fetch_weather_map(points)
    neighbors = fetch_neighbor_maps()
    context, cat, known_w, all_hours = build_inputs(points, weather, de_weather, neighbors)

    # torch reference via the public API (with categorical codes, target-encoded internally)
    with torch.inference_mode():
        ref = forecaster.forecast(
            torch.as_tensor(context, dtype=torch.float32),
            prediction_length=H,
            categorical_known_covariates=torch.as_tensor(cat),
            known_covariates=torch.as_tensor(known_w),
            clip_nonnegative=False,
        )
    q_ref = ref.quantiles[0, 0].numpy()  # (H, Q)
    levels = ref.quantile_levels
    print("reference quantiles:", q_ref.shape, "levels:", levels[:3], "...", levels[-1])

    # pre-encode categoricals exactly like the forecaster does, then build the (1,7,T+H) known tensor
    inputs, mask = forecaster._as_context(torch.as_tensor(context, dtype=torch.float32), None)
    target = forecaster._encoding_target(inputs, mask)
    enc = forecaster._encode_categorical(torch.as_tensor(cat), target)
    known_all = torch.cat([torch.as_tensor(known_w, dtype=torch.float32), enc], dim=1).contiguous()
    assert known_all.shape == (1, 13, T_CTX + H), known_all.shape

    wrapper = OnnxWrapper(forecaster, H)
    with torch.inference_mode():
        q_wrap = wrapper(torch.as_tensor(context, dtype=torch.float32), known_all)
    d = float((q_wrap - ref.quantiles).abs().max())
    print(f"wrapper vs public API max abs diff: {d:.3e}")
    assert d < 5e-3, "wrapper does not match the public forecast()"

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    raw = outdir / f"timestral-{args.size.lower()}.onnx"
    # ---- export-time patches: replace ops the ONNX opset-18 exporter cannot map ----
    import timestral.forecaster as _fc
    import timestral.masks as _mk
    import timestral.model as _md
    import timestral.scaler as _sc

    _saved = []
    def _patch(obj, name, fn):
        _saved.append((obj, name, getattr(obj, name)))
        setattr(obj, name, fn)

    _patch(torch.Tensor, "asinh", lambda self: torch.log(self + torch.sqrt(self * self + 1.0)))

    _orig_where = torch.where
    def _where(cond, a, b):
        if isinstance(a, torch.Tensor) and a.dtype == torch.bool and isinstance(b, torch.Tensor) and b.dtype == torch.bool:
            return (cond & a) | (~cond & b)  # ORT has no bool Where; use And/Or/Not
        return _orig_where(cond, a, b)
    torch.where = _where
    _saved.append((torch, "where", _orig_where))

    _orig_unique = torch.unique
    def _unique(x, return_inverse=False, **kw):
        if x.dim() == 1 and x.numel() > 0 and bool((x[1:] >= x[:-1]).all()):
            vals = torch.arange(int(x.max().item()) + 1, device=x.device, dtype=x.dtype)
            return (vals, x.to(torch.long)) if return_inverse else vals
        return _orig_unique(x, return_inverse=return_inverse, **kw)
    torch.unique = _unique
    _saved.append((torch, "unique", _orig_unique))

    _orig_eye = torch.eye
    def _eye(n, m=None, dtype=None, device=None, **kw):
        m = n if m is None else m
        e = torch.arange(n, device=device)[:, None] == torch.arange(m, device=device)[None, :]
        return e.to(dtype) if dtype is not None else e
    torch.eye = _eye
    _saved.append((torch, "eye", _orig_eye))
    _patch(torch.Tensor, "sinh", lambda self: (torch.exp(self) - torch.exp(-self)) / 2.0)

    _orig_ri_fn = torch.Tensor.repeat_interleave
    def _ri(self, repeats, dim=None):
        if not isinstance(repeats, int):
            return _orig_ri_fn(self, repeats, dim)
        if dim is None:
            self = self.flatten(); dim = 0
        if dim < 0:
            dim = self.dim() + dim
        s = list(self.shape)
        view = list(s); view.insert(dim + 1, repeats)
        out = list(s); out[dim] = s[dim] * repeats
        return self.unsqueeze(dim + 1).expand(*view).reshape(out)
    _patch(torch.Tensor, "repeat_interleave", _ri)

    def _ffill(inputs, mask):
        # exact when the mask is a left-padding pattern (False* True*), which the app guarantees
        if mask.all():
            return inputs
        first = mask.to(torch.float32).argmax(dim=-1, keepdim=True)
        head = torch.gather(inputs, -1, first)
        return torch.where(mask, inputs, head)
    _patch(_fc, "ffill_with_mask", _ffill)

    def _enc_key_valid(obs_per_patch, attend_missing):
        if not attend_missing:
            return obs_per_patch
        return obs_per_patch | (obs_per_patch.to(torch.float32).cumsum(dim=-1) > 0)
    _patch(_mk, "compute_enc_key_validity", _enc_key_valid)
    _patch(_md, "compute_enc_key_validity", _enc_key_valid)

    def _gfop(obs_per_patch, inverse, num_groups):
        r, n = obs_per_patch.shape
        onehot = (inverse[:, None] == torch.arange(num_groups, device=obs_per_patch.device)[None, :]).to(torch.float32).t()
        return ((onehot @ obs_per_patch.to(torch.float32)) > 0).to(torch.float32).argmax(dim=-1)
    _patch(_mk, "group_first_observed_patch", _gfop)
    _patch(_md, "group_first_observed_patch", _gfop)

    def _ccs(data, observation_mask, minimum_scale, stabilize_with_global, scale_factor_exponent=10.0):
        # stabilize_with_global is always False for this family (asserted in config)
        weights = torch.ones_like(data) * observation_mask
        x = data.to(torch.float64)
        w = weights.to(torch.float64)
        cum_w = torch.cumsum(w, dim=-1)
        cum_x = torch.cumsum(w * x, dim=-1)
        denominator = cum_w.clamp_min(1.0)
        means = cum_x / denominator
        shifted = torch.cat([torch.zeros_like(means[..., :1]), means[..., :-1]], dim=-1)
        increment = (x - shifted) * (x - means) * w
        m2 = torch.cumsum(increment, dim=-1)
        variance = m2 / torch.clamp(denominator - 1.0, min=1.0)
        scales = torch.sqrt(variance).clamp(min=minimum_scale)
        return means.to(data.dtype), scales.to(data.dtype)
    _patch(_sc, "compute_causal_statistics", _ccs)

    def _cpls(data, observation_mask, patch_size, minimum_scale, stabilize_with_global):
        means, scales = _ccs(data, observation_mask, minimum_scale, stabilize_with_global)
        t = data.shape[-1]
        pm = means.reshape(*means.shape[:-1], t // patch_size, patch_size)[..., -1]
        psc = scales.reshape(*scales.shape[:-1], t // patch_size, patch_size)[..., -1]
        return pm.repeat_interleave(patch_size, dim=-1), psc.repeat_interleave(patch_size, dim=-1)
    _patch(_sc, "causal_patch_loc_scale", _cpls)
    _patch(_md, "causal_patch_loc_scale", _cpls)
    _patch(_fc, "causal_patch_loc_scale", _cpls)

    def _refine_block(self, quantiles, context, mask, target_rows):
        ps = self.patch_size
        n_pred = quantiles.shape[1] // ps
        if n_pred <= 1:
            return quantiles
        _, loc, scale = self.model.scale(context, mask)
        loc0, scale0 = loc[:, -1], scale[:, -1]
        median = quantiles[..., self.median_index].unflatten(-1, (n_pred, ps)).to(torch.float64)
        sinh_median = (median - loc0[:, None, None]) / scale0[:, None, None]
        loc_j, scale_j = _sc.advancing_block_frames(context, mask, sinh_median, self.config.minimum_scale)
        first = (torch.arange(n_pred, device=loc_j.device) == 0).unsqueeze(0).expand(loc_j.shape)
        loc_j = torch.where(first, loc0[:, None], loc_j.to(quantiles.dtype)).repeat_interleave(ps, dim=-1)
        scale_j = torch.where(first, scale0[:, None], scale_j.to(quantiles.dtype)).repeat_interleave(ps, dim=-1)
        sinh_norm = (quantiles - loc0[:, None, None]) / scale0[:, None, None]
        refined = _sc.clamp_nonfinite(sinh_norm * scale_j[..., None] + loc_j[..., None])
        if target_rows is not None:
            refined = torch.where(target_rows[:, None, None], refined, quantiles)
        return refined
    _patch(type(forecaster), "_refine_block", _refine_block)

    try:
        with torch.no_grad():
            torch.onnx.export(
                wrapper,
                (torch.as_tensor(context, dtype=torch.float32), known_all),
                str(raw),
                input_names=["context", "known_covariates"],
                output_names=["quantiles"],
                opset_version=18,
                dynamo=False,
            )
    finally:
        for obj, name, fn in _saved:
            setattr(obj, name, fn)
    print("exported", raw, raw.stat().st_size / 1e6, "MB")

    import onnx
    import onnxruntime as ort

    m = onnx.load(str(raw))
    onnx.checker.check_model(m)
    sess = ort.InferenceSession(str(raw), providers=["CPUExecutionProvider"])
    q_onnx = sess.run(["quantiles"], {
        "context": context,
        "known_covariates": known_all.numpy(),
    })[0][0, 0]
    d2 = float(np.abs(q_onnx - q_ref).max())
    print(f"onnx vs torch max abs diff: {d2:.3e}")
    assert d2 < 1e-2, "onnx graph diverges from torch"

    final = raw
    if args.quant == "fp16":
        from onnxconverter_common import float16
        m16 = float16.convert_float_to_float16(onnx.load(str(raw)), keep_io_types=True)
        final = outdir / f"timestral-{args.size.lower()}-fp16.onnx"
        onnx.save(m16, str(final))
    elif args.quant == "int8":
        from onnxruntime.quantization import QuantType, quantize_dynamic
        final = outdir / f"timestral-{args.size.lower()}-int8.onnx"
        quantize_dynamic(str(raw), str(final), weight_type=QuantType.QInt8)
    if final != raw:
        print("quantized", final, final.stat().st_size / 1e6, "MB")
        sess2 = ort.InferenceSession(str(final), providers=["CPUExecutionProvider"])
        q_q = sess2.run(["quantiles"], {"context": context, "known_covariates": known_all.numpy()})[0][0, 0]
        d3 = float(np.abs(q_q - q_ref).max())
        rel = float(np.abs(q_q - q_ref).max() / (np.abs(q_ref).max() + 1e-9))
        print(f"quantized vs torch max abs diff: {d3:.3e} (rel {rel:.2e})")
        med = levels.index(0.5)
        mae_med = float(np.abs(q_q[:, med] - q_ref[:, med]).mean())
        print(f"median MAE quantized vs torch: {mae_med:.4f} DKK/MWh")

    ref_path = HERE / "test" / f"reference-{args.size.lower()}.json"
    ref_path.parent.mkdir(parents=True, exist_ok=True)

    def _no_nan(o):
        if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
            return None
        if isinstance(o, list):
            return [_no_nan(v) for v in o]
        return o

    ref_path.write_text(json.dumps({
        "size": args.size, "T": T_CTX, "H": H,
        "levels": list(levels),
        "context": _no_nan(context[0, 0].tolist()),
        "known_covariates": _no_nan(known_all[0].tolist()),
        "quantiles": _no_nan(q_ref.tolist()),
    }))
    print("reference saved to", ref_path)
    print("DONE", final)


if __name__ == "__main__":
    main()

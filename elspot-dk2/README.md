# elspot — Timestral price forecast (DK1/DK2)

A single-file, pixel-art web app that forecasts **day-ahead electricity prices in Denmark — East (DK2, default) or West (DK1), selectable in the app**
with Mistral's **Timestral** time-series foundation model, deployed as a managed workflow in this repo
(`elspot-dk2-workflows/`).

![style](https://img.shields.io/badge/style-Mistral%20pixel%20UI-FF8205) ![stack](https://img.shields.io/badge/stack-vanilla%20HTML%2FJS%2FSVG-FFD800) ![model](https://img.shields.io/badge/model-Timestral%201.0-FFAF00)

## Run it

Plain HTML — no build step. GitHub Pages serves this folder once the branch is merged, e.g.
`https://elpollodiablo2nd.github.io/test/elspot-dk2/`, or open `index.html` locally / serve the folder
(`python3 -m http.server 8000`).

## Use it

All prices are shown in **kr/kWh** — the source data is DKK/MWh, divided by 1000.

1. Prices load automatically on page open; **LOAD PRICES** retries them. It fetches the last
   35 days of hourly day-ahead prices (selected area) live from
   [Energi Data Service](https://www.energidataservice.dk/tso-electricity/DayAheadPrices)
   (`DayAheadPrices`, `PriceArea=DK1|DK2`; quarter-hourly since 2025-10-01, aggregated to hourly).
   Energinet occasionally answers **429 (rate limited)** or is unreachable from the device — the page
   retries up to 6 times, honoring `Retry-After` (capped at 60 s) with jittered backoff, and then falls
   back, in order, to the **remote Pages snapshot** (`elspot-dk2/assets/prices-dk1.json` /
   `prices-dk2.json`, refreshed every 3h by the GitHub Actions job
   `.github/workflows/refresh-elspot-snapshots.yml`, which itself falls back to the Nord Pool
   data-portal API when Energinet rate-limits the runner), the **cached copy** from the last
   successful load (`localStorage`, with timestamp; the freshest of the two is shown), and finally
   the **snapshot bundled in the APK** (refreshed at app build time). The banner always says which source was used.
   Day-ahead prices for tomorrow are published
   **once a day (~13:00 CET)**, and tomorrow usually tracks today: the chart always shows the
   **baseline** (tomorrow ≈ today — each forecast hour repeats the actual price 24h earlier). The HUD shows the cheapest hour and the EV window.
2. Press **RUN TIMESTRAL** — in the Android app (`elspot-dk2-android/app-debug.apk`) the
   ONNX-exported Timestral runs **on-device** (no API key): pick the checkpoint (5M bundled, 28M
   downloaded once in 4 parts) and the **horizon** (24–168h, up to 7 days — beyond 24h there is no published
   day-ahead price to check against and the q10–q90 band widens). In a plain browser the button
   explains that on-device ONNX needs the app. The server-side `dk2-elspot-forecast` workflow
   (`elspot-dk2-workflows/`) is still available via the Mistral API for anyone who wants it.
3. The chart shows **from the current hour only**: published day-ahead prices ahead of now (green),
   then the **Timestral median** (orange dashes) with its **q10–q90 band** (red) over the full
   horizon. The x-axis is adaptive — two-line labels with date **and** time of day (DK), with the
   finest tick step that fits the window (2h for a 24h view, up to 24h for multi-day views), with
   weekday + DD/MM date at each day boundary. The
   hourly grid below lists every hour from now (published + forecast) in kr/kWh with its q10–q90
   range, cheapest highlighted.
4. **EV charging**: the green shaded **EV window** on the chart marks the cheapest contiguous
   `EV 4/6/8h` run from now (over published + forecast), and the HUD stat `EV {n}H FROM …` gives its
   start time and average price.
5. **All-in price**: with **INCL. FEES+VAT** ticked (default), prices include the mandatory per-kWh
   fees from Energinet's `DatahubPricelist` — transmission + system tariff (Energinet), distribution
   `Nettarif C` (N1 A/S, Zealand — low at night 00–06, peak 17–21), electricity tax (elafgift) — plus
   25% VAT: all-in = (spot + fees) × 1.25. Untick for spot only. Tariffs are fetched live with
   retry, cached in `localStorage`, with built-in 2026 defaults as fallback.

No retraining is involved: Timestral is zero-shot — the price history is the inference context
(up to 32K steps), with hour-of-day/weekday passed as known-future covariates.

### Covariates, full-year backtest & error localization (DK2, Timestral-28M)

82 rolling origins every 5 days, 168h context, 72h horizon, 60/40 temporal split, test-set MAE% of mean actual.
**App-faithful**: neighbour day-ahead prices are only published up to ~+36h past each origin, so they are masked
(NaN) beyond that in these runs — the earlier h48/h72 numbers without masking were leakage-inflated.

| known covariates | h24 | h48 | h72 | q10–q90 coverage raw → conformal (h24/h48/h72) |
|---|---|---|---|---|
| spot only | 16.5 | 22.6 | 23.5 | 54% → 93% |
| + weather (Open-Meteo wind/temp/solar) | 14.1 | 19.9 | 20.5 | 72% → 93% |
| + DE/SE3 day-ahead neighbours | 4.13 | 9.11 | 13.27 | 86% → 94% |
| + weather + neighbours (shipped config) | **3.97** | **8.68** | **12.34** | 90/82/72% → 95/92/91% |
| + neighbours + wind/solar generation forecast (`Forecasts_Hour`) | 4.32 | 9.40 | 13.53 | worse — generation forecast adds nothing |

5M with weather+neighbours: 5.34 / 9.38 / 12.89%. DK1 (west) neighbours: 4.29 / 7.27 / 8.13% (unmasked h48/h72).

**Error localization** (per-hour analysis of the shipped config): MAE grows with horizon — rel 1–24: 69, 25–48: 197,
49–72: 335 DKK/MWh — and **every one of the top-20 errors is at rel ≥ 42 where DE/SE3 are NaN** (MAE 325 on
neighbour-NaN hours vs 82 when present). Errors also peak in the 16–19 UTC price peak. Gust events (3h price drop
>300 DKK/MWh with wind +8 m/s; 36 in the year) are forecast about as well as average when neighbours are published
(the German day-ahead moves with the same wind), and 92% of the 109 negative-price hours had wind10m > 15 m/s.
Negative-price hours: with the old non-negative clamp MAE was 32 DKK/MWh on those hours (unclamped 82 in that
run) — but the clamp also meant negative prices could never be *predicted*; the current export (v3) is unclamped
(`clip_nonnegative=False`), so high-wind negative hours are forecastable.
Skipped weather indicators: none — 0 of 936 app input hours missing (Open-Meteo 32d archive + 8d forecast covers the 768+168 window).

### 7-day horizon: neighbour-forecast ridge fill + no-clamp ONNX v3 export (H=168)

Neighbour day-ahead (DE/SE3) is only published to ~+36h, which is why error exploded beyond day 2 when the app
was capped at 72h. The app now **fills DE/SE3 beyond the published window with an on-device walk-forward ridge**
(38 features: intercept + 24 hour-of-day + 7 weekday dummies + 6 N-Germany weather features — wind-power proxy,
wind10, solar, temp, cloud, pressure — from 3 Open-Meteo points near the DK border, Flensburg/Fehmarn/Hamburg;
trained on published hours only at RUN time, solved as a 38×38 normal-equation system in JS, milliseconds on
device). The fill needs no ONNX change (the DE/SE3 rows already existed); the export was redone anyway at
**H=168 with 13 covariate rows** (T+H = 936, output `quantiles` (1,1,168,21)) with **`clip_nonnegative=False`**,
so the UI offers horizons 24…168h and negative prices are predictable. Extra-covariate ablation (same harness,
all variants with ridge fill): +6 DE-weather rows help at day 3–7 (e.g. day4 25.12 → 24.41, day7 27.75 → 26.87);
+DK wind100 adds nothing on top (27.58 day7 ≈ 27.65); day 1 is within noise (6.07 → 6.31).

7-month backtest (35 origins every 5 days, CTX=768, H=168, DK2, 28M, app-faithful +36h mask), MAE % of mean
actual per day ahead:

| day ahead | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| neighbours NaN beyond +36h (old app) | 6.16 | 16.77 | 31.65 | 32.41 | 40.51 | 45.11 | 39.78 |
| hour-of-week climatology fill | 6.13 | 21.83 | 35.85 | 34.50 | 49.25 | 54.75 | 39.00 |
| ridge fill DE+SE3 (7 covariate rows) | 6.07 | 16.01 | 28.60 | 25.12 | 26.49 | 29.00 | 27.75 |
| **ridge fill + 6 DE-weather rows (shipped, ONNX v4 = 13 rows)** | **6.31** | **15.95** | **27.65** | **24.41** | **26.12** | **28.26** | **26.87** |
| naive baseline (repeat yesterday) | 27.74 | 35.01 | 40.43 | 37.25 | 46.36 | 51.03 | 42.76 |

Per-day comparison against the other methods (DK2 spot, MAE %): elforbrug.nu / Spotprisprognose, 90-day repo
backtest: 18.7 / 25.0 / 25.0 / 24.4 / 25.4 / 24.5 (day 7 n/a — their forecast is only ~130 h); elpriser.dk,
published 30 d window (their day-1 is scored pre-auction, ours uses published DE/SE3 day-ahead):
15.1 / 16.4 / 16.7 / 18.8 / 21.8 / 21.1 / 22.5. We win day 1–2 decisively, match elpriser.dk on day 2, and with
the ridge fill beat elforbrug.nu from day 4 on; elpriser.dk's ECMWF→generation→quantile-regression pipeline
remains the strongest on days 3–7.

**ONNX contract v4**: `context` float32 (1,1,768) NaN-left-padded; `known_covariates` float32 (1,13,936), rows
`[wind, temp, solar, DE, SE3, de_windpw, de_wind10, de_solar, de_temp, de_cloud, de_pres, enc_hour, enc_weekday]`
over 768+168 (de_* = N-Germany weather at 3 points near the DK border; de_windpw = cubic wind-power proxy from
wind100); output `quantiles` float32 (1,1,168,21)
levels 0.01…0.99 (median idx 10, q10 idx 2, q90 idx 18); **no clamp at 0**. 5M bundled in the APK
(`www/assets/timestral-5m.onnx`); 28M served as 4 byte-parts on Pages (`models/timestral-28m.part0..3`,
concatenated then cached in CacheStorage under key `…28M.h168.onnx`). Export:
`elspot-dk2-android/export_onnx.py --size 28M --quant fp32` — wrapper vs public API (`clip_nonnegative=False`)
max diff 0.0, ONNX vs torch ≤ 3.1e-3, `test/ort-wasm-test.js <size> fp32` PASS.

## How it works

- **Data**: `GET https://api.energidataservice.dk/dataset/DayAheadPrices?filter={"PriceArea":["DK1 or DK2"]}&start=…&sort=TimeUTC asc`
  — keyless, CORS-enabled; bucketed to hourly UTC (DST-proof), labels shown in Europe/Copenhagen.
- **Fees**: `GET https://api.energidataservice.dk/dataset/DatahubPricelist?filter={"GLN_Number":[…],"Note":[…]}…`
  — keyless, CORS-enabled. Energinet GLN `5790000432752` provides `Transmissions nettarif`,
  `Systemtarif`, `Elafgift`; N1 A/S GLN `5790001089030` (Zealand/Copenhagen, DK2) provides the household distribution tariff `Nettarif C` for DK2;
  TREFOR El-net GLN `5790000392261` (Jutland) provides it for DK1. Records carry `ValidFrom`/`ValidTo` validity windows
  and `Price1..Price24` = local Danish hours 00–01 … 23–24 (flat charges set `Price1` only).
- **Model**: the managed workflow deployment `dk2-elspot-forecast` (source: `elspot-dk2-workflows/` in
  this repo) runs `TimestralForecaster.from_pretrained("mistralai/Timestral-<size>")` (open weights,
  Modified MIT, CPU-only) on the hourly DKK/MWh series and forecasts `horizon_hours` steps ahead
  (24/48/72 from the UI). Hour-of-day and
  weekday are passed as categorical known-future covariates, and the **weather forecast** (wind speed,
  temperature, solar radiation from [Open-Meteo](https://open-meteo.com/), keyless, for Zealand) as
  numeric known-future covariates over context + horizon — weather drives both generation and prices
  (`use_weather=false` disables it). The page also shows a next-24h weather line under the chart.
- **Baseline**: "tomorrow = today, same hour" (lag-1), scored against Timestral on a 7-day
  rolling-origin backtest — reported as MAE stats in both the workflow result and the HUD.
- Styled with the **Mistral pixel UI** skill (Press Start 2P / VT323, rainbow gradient, chunky
  borders, CRT scanlines); chart is an inline SVG with `shape-rendering: crispEdges`.

## Tests

```
node test.js                                    # pure-function tests of the embedded JS
cd elspot-dk2-workflows && uv run pytest apps/worker/tests   # workflow tests (mocked model)
```

## Files

- `index.html` — the whole app (markup + CSS + JS, no dependencies besides Google Fonts)
- `test.js` — Node tests for the pure chart/stat functions extracted from `index.html`
- `.nojekyll` — disables Jekyll processing on GitHub Pages

## Credits

- Prices: [Energi Data Service (Energinet)](https://www.energidataservice.dk/) — `DayAheadPrices`, DK1/DK2
- Weather: [Open-Meteo](https://open-meteo.com/) (ERA5 archive + forecast), Zealand (DK2) / Esbjerg-Jutland (DK1), keyless
- Model: [Mistral Timestral 1.0](https://docs.mistral.ai/models/timestral-1-0-28m) —
  [weights](https://huggingface.co/mistralai/Timestral-28M) (Modified MIT),
  [inference code](https://github.com/mistralai/timestral) (Apache 2.0)

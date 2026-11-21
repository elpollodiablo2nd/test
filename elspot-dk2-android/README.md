# Elspot DK2 — Android app (on-device ONNX Timestral)

Capacitor WebView app wrapping the `elspot-dk2/` page. The Timestral model runs
**on the phone** via `onnxruntime-web` (WASM, single-threaded — works in a plain
Android WebView, no NNAPI/CoreML needed): in the app pick **ON-DEVICE · ONNX (NO KEY)**
in RUN MODE and press RUN TIMESTRAL — no Mistral API key required. **SERVER · WORKFLOW**
mode (API key) also works and is the default in the browser.

## What's inside

- `www/` — built by `tools/sync-www.sh` from `../elspot-dk2/index.html` (the ORT loader
  `vendor/ort/ort.min.js` is injected before the app script) + `vendor/ort/` (wasm
  runtime) + `assets/timestral-5m.onnx` (bundled fp32 model, ~22 MB) + `assets/prices-dk2.json`
  (bundled price snapshot, refreshed by `tools/fetch_prices_snapshot.py` — the app's last-resort
  price source when Energinet rate-limits) + `icon.svg` (pixel lightning-bolt icon, also the
  Android launcher icon via `mipmap-*/ic_launcher*.png` generated from the same 8×8 grid).
- `models/timestral-28m.part{0..3}` — the 28M fp32 ONNX export (~113 MB) split into
  4 × ~28 MB parts so it can live in git and be served by GitHub Pages; the app
  downloads and reassembles it on first use (28M on-device). Split/join is plain
  byte concatenation (`tools/split-model` logic in `export_onnx.py --size 28M`).
- `export_onnx.py` — exports `mistralai/Timestral-{5M,28M}` to ONNX (fixed shapes:
  context T=768 hourly steps = 24 patches of 32, horizon H=96; the app left-pads
  shorter history with NaN and slices the 96-step output to 24/48/72h). The graph is
  the full `forecast()` including the clampsym mirrored pass and non-negative clip;
  categorical covariates (hour-of-day, weekday) are target-encoded **outside** the
  graph — `buildOnnxInputs`/`targetEncode` in `elspot-dk2/index.html` replicate
  `timestral.covariate_encoding.target_encode` exactly. Export-time patches rewrite
  ops ONNX opset-18 can't express (asinh/sinh, cummax, unique, bool-where, eye,
  repeat_interleave, index_put) into equivalent supported ops.
- `test/ort-wasm-test.js` — runs the exported model under onnxruntime-web WASM in
  Node against a PyTorch reference (`test/reference-*.json`).
- WebView fix: ORT 1.23 loads its glue via dynamic `import()`, so `wasmPaths` must be
  **absolute URLs** (`new URL("vendor/ort/", location.href)`) and pinned to the plain
  threaded build via `{ mjs, wasm }` (the default would be the jsep variant we don't ship).
- No remote execution: the UI has no API-key/server mode — RUN TIMESTRAL always runs the ONNX
  model on-device. Price loading fallback chain: live Energinet (6 retries, Retry-After aware)
  → `localStorage` cache → bundled `assets/prices-dk2.json` snapshot.

## Verified

- ONNX vs PyTorch (onnxruntime CPU): max abs diff 0.006 DKK/MWh (28M), 0.005 (5M).
- onnxruntime-web **WASM** vs PyTorch reference: 28M max abs diff 0.0059 DKK/MWh
  (load 1.1 s, run 1.8 s on a server CPU), 5M 0.0035 (run 0.23 s). fp16 models are
  NOT used: the wasm build has no fp16 kernels. int8 dynamic quant was inaccurate.
- `./gradlew assembleDebug` → `android/app/build/outputs/apk/debug/app-debug.apk`
  (~27 MB) with `assets/public/` = page + wasm + bundled 5M model.

## Build

```
npm install
./tools/sync-www.sh          # build www/ from ../elspot-dk2 + vendor runtime
npx cap add android          # once
npx cap sync android
cd android && ./gradlew assembleDebug     # JDK 21 + Android SDK 34
```

Re-export models (needs the workflows venv):
`../elspot-dk2-workflows/.venv/bin/python export_onnx.py --size 28M` (writes
`www/assets/timestral-28m.onnx` + `test/reference-28m.json`); re-split with the
4-part logic into `models/`.

## Notes

- On-device context is capped at 768 h (the export shape); history beyond that is dropped.
- Prices/weather still come from Energinet/Open-Meteo (keyless); cached prices work offline.
- 123M/209M are server-only (too big for a phone APK).

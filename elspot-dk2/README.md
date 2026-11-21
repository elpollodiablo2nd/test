# ELSPOT DK2 — Timestral Forecast

A single-file, pixel-art web app that forecasts **day-ahead electricity prices in East Denmark (DK2)**
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
   35 days of hourly DK2 day-ahead prices live from
   [Energi Data Service](https://www.energidataservice.dk/tso-electricity/DayAheadPrices)
   (`DayAheadPrices`, `PriceArea=DK2`; quarter-hourly since 2025-10-01, aggregated to hourly).
   Energinet occasionally answers **429 (rate limited)** or is unreachable from the device — the page
   retries up to 6 times, honoring `Retry-After` (capped at 60 s) with jittered backoff, and then falls
   back, in order, to the **cached copy** from the last successful load (`localStorage`, with timestamp)
   and to a **bundled snapshot** (`elspot-dk2-android/www/assets/prices-dk2.json`, refreshed at app
   build time by `tools/fetch_prices_snapshot.py`). The banner always says which source was used.
   Day-ahead prices for tomorrow are published
   **once a day (~13:00 CET)**, and tomorrow usually tracks today: the chart always shows the
   **lag-1 baseline** (tomorrow ≈ today), and the HUD shows the day-to-day correlation and the
   lag-1 backtest MAE.
2. Press **RUN TIMESTRAL** — in the Android app (`elspot-dk2-android/app-debug.apk`) the
   ONNX-exported Timestral runs **on-device** (no API key): pick the checkpoint (5M bundled, 28M
   downloaded once in 4 parts) and the **horizon** (24/48/72h — beyond 24h there is no published
   day-ahead price to check against and the q10–q90 band widens). In a plain browser the button
   explains that on-device ONNX needs the app. The server-side `dk2-elspot-forecast` workflow
   (`elspot-dk2-workflows/`) is still available via the Mistral API for anyone who wants it.
3. The chart shows **from the current hour only**: published day-ahead prices ahead of now (green),
   then the **Timestral median** (orange dashes) with its **q10–q90 band** (red) over the full
   horizon. The x-axis is adaptive — two-line labels with date **and** time of day (DK), with the
   finest tick step that fits the window (2h for a 24h view, up to 24h for multi-day views). The
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

## How it works

- **Data**: `GET https://api.energidataservice.dk/dataset/DayAheadPrices?filter={"PriceArea":["DK2"]}&start=…&sort=TimeUTC asc`
  — keyless, CORS-enabled; bucketed to hourly UTC (DST-proof), labels shown in Europe/Copenhagen.
- **Fees**: `GET https://api.energidataservice.dk/dataset/DatahubPricelist?filter={"GLN_Number":[…],"Note":[…]}…`
  — keyless, CORS-enabled. Energinet GLN `5790000432752` provides `Transmissions nettarif`,
  `Systemtarif`, `Elafgift`; N1 A/S GLN `5790001089030` (Zealand/Copenhagen, DK2) provides the
  household distribution tariff `Nettarif C`. Records carry `ValidFrom`/`ValidTo` validity windows
  and `Price1..Price24` = local Danish hours 00–01 … 23–24 (flat charges set `Price1` only).
- **Model**: the managed workflow deployment `dk2-elspot-forecast` (source: `elspot-dk2-workflows/` in
  this repo) runs `TimestralForecaster.from_pretrained("mistralai/Timestral-<size>")` (open weights,
  Modified MIT, CPU-only) on the hourly DKK/MWh series and forecasts `horizon_hours` steps ahead
  (24/48/72 from the UI). Hour-of-day and
  weekday are passed as categorical known-future covariates, and the **weather forecast** (wind speed,
  temperature, solar radiation from [Open-Meteo](https://open-meteo.com/), keyless, for Zealand) as
  numeric known-future covariates over context + horizon — weather drives both generation and prices
  (`use_weather=false` disables it). The page also shows a next-24h weather line under the chart.
- **Baseline**: lag-1 ("tomorrow = today, same hour"), scored against Timestral on a 7-day
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

- Prices: [Energi Data Service (Energinet)](https://www.energidataservice.dk/) — `DayAheadPrices`, DK2
- Weather: [Open-Meteo](https://open-meteo.com/) (ERA5 archive + forecast), Copenhagen/Zealand, keyless
- Model: [Mistral Timestral 1.0](https://docs.mistral.ai/models/timestral-1-0-28m) —
  [weights](https://huggingface.co/mistralai/Timestral-28M) (Modified MIT),
  [inference code](https://github.com/mistralai/timestral) (Apache 2.0)

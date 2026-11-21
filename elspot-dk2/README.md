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

1. Prices load automatically on page open; **LOAD PRICES** refreshes them. It fetches the last
   ~10 days of hourly DK2 day-ahead prices live from
   [Energi Data Service](https://www.energidataservice.dk/tso-electricity/DayAheadPrices)
   (`DayAheadPrices`, `PriceArea=DK2`; quarter-hourly since 2025-10-01, aggregated to hourly).
   Energinet occasionally answers **429 (rate limited)** or is unreachable from the browser — the page
   retries with backoff up to 4 times and then falls back, in order, to the **cached copy** from the
   last successful load (`localStorage`) and, if an API key is entered, to a **dry-run execution of
   the workflow itself** (`dry_run=true`, which fetches the prices server-side without loading the
   model). Either way the chart fills in; a successful RUN TIMESTRAL also adopts the server-side
   history from the result. Day-ahead prices for tomorrow are published
   **once a day (~13:00 CET)**, and tomorrow usually tracks today: the chart always shows the
   **lag-1 baseline** (tomorrow ≈ today), and the HUD shows the day-to-day correlation and the
   lag-1 backtest MAE.
2. Paste your **Mistral API key** (stored only in `localStorage`, sent only to `api.mistral.ai`),
   pick the **horizon** (24/48/72h — beyond 24h there is no published day-ahead price to check
   against and the q10–q90 band widens) and press **RUN TIMESTRAL** — the page starts an async
   execution of the deployed `dk2-elspot-forecast` workflow
   (`POST /v1/workflows/dk2-elspot-forecast/execute` with `wait_for_result:false`, then polls
   `GET /v1/workflows/executions/{id}` every 3 s, showing progress in the banner), which runs
   Timestral (default 28M checkpoint; 5M/123M/209M selectable) on the last 30 days and returns the
   forecast with q10–q90 quantiles plus a rolling backtest of Timestral vs the lag-1 baseline.
3. The chart then overlays the **Timestral median** (orange dashes) and its **q10–q90 band** (red)
   over the full horizon, and the hourly grid below lists every forecast hour in kr/kWh with its
   q10–q90 range, cheapest highlighted.
4. **EV charging**: the HUD stat `EV {4/6/8}H FROM …` (window length selectable) shows the cheapest
   contiguous charging window in the forecast and its average price in kr/kWh.

No retraining is involved: Timestral is zero-shot — the price history is the inference context
(up to 32K steps), with hour-of-day/weekday passed as known-future covariates.

## How it works

- **Data**: `GET https://api.energidataservice.dk/dataset/DayAheadPrices?filter={"PriceArea":["DK2"]}&start=…&sort=TimeUTC asc`
  — keyless, CORS-enabled; bucketed to hourly UTC (DST-proof), labels shown in Europe/Copenhagen.
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

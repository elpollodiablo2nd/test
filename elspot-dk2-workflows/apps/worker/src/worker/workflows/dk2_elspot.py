"""Forecast DK2 (East Denmark) day-ahead electricity prices with Mistral's Timestral model.

Day-ahead ("elspot") prices for tomorrow are published once a day by Energinet, and tomorrow's
profile is usually close to today's, so the workflow reports the lag-1 baseline ("tomorrow ~=
today") next to the Timestral forecast and scores both on a recent backtest.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pydantic

import mistralai.workflows as workflows

ENERGINET_DAY_AHEAD_URL = "https://api.energidataservice.dk/dataset/DayAheadPrices"
PRICE_AREA = "DK2"  # East Denmark: Zealand, Copenhagen and the islands
DK_TZ = ZoneInfo("Europe/Copenhagen")
TIMESTRAL_REPO_TEMPLATE = "mistralai/Timestral-{size}"
VALID_MODEL_SIZES = ("5M", "28M", "123M", "209M")
DEFAULT_MODEL_SIZE = "28M"
HOURS_PER_DAY = 24
MIN_CONTEXT_DAYS = 7
HF_CACHE_DIR = "/tmp/timestral-hf-cache"


class Dk2ElspotInput(pydantic.BaseModel):
    days: int = 30
    horizon_hours: int = 24
    model_size: str = DEFAULT_MODEL_SIZE
    backtest_days: int = 7
    dry_run: bool = False


class HourlyPoint(pydantic.BaseModel):
    hour_utc: str
    hour_dk: str
    price_dkk: float


class ForecastHour(pydantic.BaseModel):
    hour_utc: str
    hour_dk: str
    median: float
    q10: float
    q90: float
    lag1: float


class Dk2ForecastPayload(pydantic.BaseModel):
    forecast: list[ForecastHour]
    stats: dict[str, float | int | bool | None]


class Dk2ElspotResult(pydantic.BaseModel):
    price_area: str
    model: str
    generated_at: str
    history: list[HourlyPoint]
    forecast: list[ForecastHour]
    stats: dict[str, float | int | bool | None]


def parse_hour_utc(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def hour_dk_label(hour_utc: datetime) -> str:
    return hour_utc.astimezone(DK_TZ).strftime("%Y-%m-%d %H:00")


def aggregate_hourly_utc(records: list[dict]) -> list[tuple[datetime, float]]:
    """Average DayAheadPriceDKK per UTC hour; the dataset is quarter-hourly since 2025-10-01
    and hourly before that, so bucketing by UTC hour gives one clean hourly series."""
    buckets: dict[datetime, list[float]] = {}
    for record in records:
        raw_time = record.get("TimeUTC")
        price = record.get("DayAheadPriceDKK")
        if not raw_time or price is None:
            continue
        hour = parse_hour_utc(str(raw_time)).replace(minute=0, second=0, microsecond=0)
        buckets.setdefault(hour, []).append(float(price))
    return sorted((hour, sum(values) / len(values)) for hour, values in buckets.items())


def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return num / den if den else 0.0


def lag1_pairs(points: list[tuple[datetime, float]]) -> list[tuple[float, float]]:
    prices = [price for _, price in points]
    return [
        (prices[i], prices[i + HOURS_PER_DAY])
        for i in range(len(prices) - HOURS_PER_DAY)
    ]


def corr_lag1(points: list[tuple[datetime, float]]) -> float:
    """Correlation between each day's hourly prices and the next day's, same hour."""
    pairs = lag1_pairs(points)
    if not pairs:
        return 0.0
    return pearson([a for a, _ in pairs], [b for _, b in pairs])


def lag1_forecast(points: list[tuple[datetime, float]], horizon: int) -> list[float]:
    """Naive baseline: tomorrow's hour h equals today's hour h."""
    prices = [price for _, price in points]
    return [prices[-HOURS_PER_DAY + (h % HOURS_PER_DAY)] for h in range(horizon)]


def mae(predictions: list[float], actuals: list[float]) -> float:
    errors = [abs(p - a) for p, a in zip(predictions, actuals)]
    return sum(errors) / len(errors) if errors else 0.0


def backtest_mae(
    points: list[tuple[datetime, float]],
    predict_fn,
    backtest_days: int,
    horizon: int,
) -> float | None:
    """Rolling-origin backtest: for each of the last `backtest_days` days, predict the next
    `horizon` hours from the history before it and score against the actuals."""
    prices = [price for _, price in points]
    errors: list[float] = []
    for i in range(1, backtest_days + 1):
        context_end = len(prices) - horizon * i
        if context_end < MIN_CONTEXT_DAYS * HOURS_PER_DAY:
            break
        context = points[:context_end]
        actual = prices[context_end : context_end + horizon]
        predicted = predict_fn(context, horizon)
        errors.extend(abs(p - a) for p, a in zip(predicted, actual))
    if not errors:
        return None
    return sum(errors) / len(errors)


_FORECASTER_CACHE: dict[str, object] = {}


def _load_forecaster(model_size: str) -> object:
    if model_size not in _FORECASTER_CACHE:
        from timestral import TimestralForecaster

        repo_id = TIMESTRAL_REPO_TEMPLATE.format(size=model_size)
        _FORECASTER_CACHE[model_size] = TimestralForecaster.from_pretrained(
            repo_id, device="cpu", cache_dir=HF_CACHE_DIR
        )
    return _FORECASTER_CACHE[model_size]


def _known_covariates(points: list[tuple[datetime, float]], horizon: int):
    """Hour-of-day and weekday as categorical known-future covariates over context + horizon."""
    import numpy as np

    hours = [hour for hour, _ in points]
    future = [hours[-1] + timedelta(hours=i + 1) for i in range(horizon)]
    all_hours = hours + future
    hour_of_day = [h.hour for h in all_hours]
    weekday = [h.weekday() for h in all_hours]
    return np.asarray([hour_of_day, weekday], dtype=np.float64)[None, :, :]


def timestral_predict(
    points: list[tuple[datetime, float]], horizon: int, model_size: str
) -> tuple[list[float], list[float], list[float]]:
    """Return (median, q10, q90) for the `horizon` hours after the last point."""
    import numpy as np

    forecaster = _load_forecaster(model_size)
    context = np.asarray([price for _, price in points], dtype=np.float64)[None, None, :]
    kwargs: dict = {}
    if getattr(forecaster, "supports_known_covariates", False):
        kwargs["categorical_known_covariates"] = _known_covariates(points, horizon)
    forecast = forecaster.forecast(context, prediction_length=horizon, **kwargs)
    median = [float(v) for v in np.asarray(forecast.median)[0, 0]]
    q10 = [float(v) for v in np.asarray(forecast.quantile(0.1))[0, 0]]
    q90 = [float(v) for v in np.asarray(forecast.quantile(0.9))[0, 0]]
    return median, q10, q90


@workflows.activity(
    name="fetch-dk2-day-ahead-prices",
    start_to_close_timeout=timedelta(seconds=120),
    retry_policy_max_attempts=3,
)
async def fetch_dk2_day_ahead_prices(days: int) -> list[HourlyPoint]:
    import httpx

    start = (datetime.now(timezone.utc) - timedelta(days=days + 2)).strftime("%Y-%m-%dT%H:%M")
    limit = min(100_000, (days + 2) * 96 + 200)
    params = {
        "filter": json.dumps({"PriceArea": [PRICE_AREA]}),
        "start": start,
        "sort": "TimeUTC asc",
        "limit": limit,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(ENERGINET_DAY_AHEAD_URL, params=params)
        response.raise_for_status()
        records = response.json().get("records", [])
    points = aggregate_hourly_utc(records)
    needed = MIN_CONTEXT_DAYS * HOURS_PER_DAY
    if len(points) < needed:
        raise RuntimeError(
            f"Energinet returned {len(points)} hourly {PRICE_AREA} prices, need at least {needed}"
        )
    return [
        HourlyPoint(
            hour_utc=hour.strftime("%Y-%m-%dT%H:00:00"),
            hour_dk=hour_dk_label(hour),
            price_dkk=round(price, 2),
        )
        for hour, price in points
    ]


@workflows.activity(
    name="timestral-dk2-forecast",
    start_to_close_timeout=timedelta(minutes=15),
    retry_policy_max_attempts=2,
)
async def timestral_dk2_forecast(
    history: list[HourlyPoint],
    horizon_hours: int,
    model_size: str,
    backtest_days: int,
    dry_run: bool,
) -> Dk2ForecastPayload:
    points = [(parse_hour_utc(h.hour_utc), h.price_dkk) for h in history]
    corr = corr_lag1(points)
    lag1_full = lag1_forecast(points, horizon_hours)
    mae_lag1 = backtest_mae(
        points, lambda ctx, h: lag1_forecast(ctx, h), backtest_days, horizon_hours
    )
    if dry_run:
        median = q10 = q90 = lag1_full
        mae_timestral = None
    else:
        def predict(ctx: list[tuple[datetime, float]], h: int) -> list[float]:
            m, _, _ = timestral_predict(ctx, h, model_size)
            return m

        mae_timestral = backtest_mae(points, predict, backtest_days, horizon_hours)
        median, q10, q90 = timestral_predict(points, horizon_hours, model_size)
    future_hours = [
        points[-1][0] + timedelta(hours=i + 1) for i in range(horizon_hours)
    ]
    forecast = [
        ForecastHour(
            hour_utc=future.strftime("%Y-%m-%dT%H:00:00"),
            hour_dk=hour_dk_label(future),
            median=round(m, 2),
            q10=round(lo, 2),
            q90=round(hi, 2),
            lag1=round(lag, 2),
        )
        for future, m, lo, hi, lag in zip(future_hours, median, q10, q90, lag1_full)
    ]
    stats: dict[str, float | int | bool | None] = {
        "corr_lag1": round(corr, 4),
        "mae_lag1_dkk": None if mae_lag1 is None else round(mae_lag1, 2),
        "mae_timestral_dkk": None if mae_timestral is None else round(mae_timestral, 2),
        "backtest_days": backtest_days,
        "context_hours": len(points),
        "dry_run": dry_run,
    }
    return Dk2ForecastPayload(forecast=forecast, stats=stats)


@workflows.workflow.define(
    name="dk2-elspot-forecast",
    workflow_display_name="DK2 Elspot Forecast",
    workflow_description=(
        "Fetches East Denmark (DK2) day-ahead electricity prices from Energinet and forecasts "
        "the next 24 hours with Mistral's Timestral time-series foundation model, alongside the "
        "lag-1 baseline (tomorrow ~ today) and a rolling backtest of both. No schedule; start it "
        "manually or from the elspot-dk2 page."
    ),
)
class Dk2ElspotForecastWorkflow:
    @workflows.workflow.entrypoint
    async def run(self, input: Dk2ElspotInput) -> Dk2ElspotResult:
        if input.model_size not in VALID_MODEL_SIZES:
            raise ValueError(
                f"model_size must be one of {VALID_MODEL_SIZES}, got {input.model_size!r}"
            )
        if input.horizon_hours < 1 or input.horizon_hours > 96:
            raise ValueError("horizon_hours must be between 1 and 96")
        history = await fetch_dk2_day_ahead_prices(input.days)
        payload = await timestral_dk2_forecast(
            history,
            input.horizon_hours,
            input.model_size,
            input.backtest_days,
            input.dry_run,
        )
        return Dk2ElspotResult(
            price_area=PRICE_AREA,
            model=f"timestral-1.0-{input.model_size.lower()}",
            generated_at=workflows.workflow.now().isoformat(),
            history=history,
            forecast=payload.forecast,
            stats=payload.stats,
        )

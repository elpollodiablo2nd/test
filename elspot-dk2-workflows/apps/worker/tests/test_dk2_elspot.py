import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import mistralai.workflows as workflows
import numpy as np
from mistralai.workflows.testing import create_test_worker

from worker.workflows.dk2_elspot import (
    Dk2ElspotInput,
    Dk2ElspotResult,
    Dk2ElspotForecastWorkflow,
    Dk2ForecastPayload,
    ForecastHour,
    HourlyPoint,
    WEATHER_HOUR_KEY,
    aggregate_hourly_utc,
    backtest_mae,
    corr_lag1,
    fetch_dk2_day_ahead_prices,
    hour_dk_label,
    lag1_forecast,
    mae,
    parse_hour_utc,
    parse_open_meteo_hourly,
    summarize_weather_next_hours,
    timestral_dk2_forecast,
    timestral_predict,
)

WORKFLOW_EXECUTION_TIMEOUT = timedelta(seconds=30)


def make_points(days: int = 10, base: float = 500.0) -> list[tuple[datetime, float]]:
    start = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)
    return [
        (start + timedelta(hours=i), base + 100.0 * ((i % 24) // 6) + (i % 7))
        for i in range(days * 24)
    ]


def make_history(days: int = 10) -> list[HourlyPoint]:
    return [
        HourlyPoint(
            hour_utc=hour.strftime("%Y-%m-%dT%H:00:00"),
            hour_dk=hour_dk_label(hour),
            price_dkk=round(price, 2),
        )
        for hour, price in make_points(days)
    ]


def test_aggregate_hourly_utc_averages_subhourly_records():
    records = [
        {"TimeUTC": "2026-11-20T10:15:00", "DayAheadPriceDKK": 100.0},
        {"TimeUTC": "2026-11-20T10:45:00", "DayAheadPriceDKK": 200.0},
        {"TimeUTC": "2026-11-20T11:00:00", "DayAheadPriceDKK": 300.0},
        {"TimeUTC": "2026-11-20T10:30:00", "DayAheadPriceDKK": None},
        {"TimeUTC": None, "DayAheadPriceDKK": 999.0},
    ]
    points = aggregate_hourly_utc(records)
    assert points == [
        (parse_hour_utc("2026-11-20T10:00:00"), 150.0),
        (parse_hour_utc("2026-11-20T11:00:00"), 300.0),
    ]


def test_hour_dk_label_converts_utc_to_copenhagen():
    # November: CET = UTC+1
    assert hour_dk_label(parse_hour_utc("2026-11-20T22:00:00")) == "2026-11-20 23:00"
    # July: CEST = UTC+2
    assert hour_dk_label(parse_hour_utc("2026-07-20T22:00:00")) == "2026-07-21 00:00"


def test_corr_lag1_is_one_when_tomorrow_equals_today():
    day = [300.0 + 50.0 * h for h in range(24)]
    points = [(datetime(2026, 11, 1, tzinfo=timezone.utc) + timedelta(hours=i), p)
              for i, p in enumerate(day + day + day)]
    assert corr_lag1(points) == 1.0


def test_corr_lag1_handles_short_series():
    points = make_points(days=1)
    assert corr_lag1(points) == 0.0


def test_lag1_forecast_repeats_today():
    points = make_points(days=3)
    forecast = lag1_forecast(points, 24)
    assert forecast == [price for _, price in points[-24:]]


def test_mae():
    assert mae([1.0, 2.0], [1.0, 4.0]) == 1.0
    assert mae([], []) == 0.0


def test_backtest_mae_scores_rolling_days():
    points = make_points(days=10)
    result = backtest_mae(
        points, lambda ctx, h: lag1_forecast(ctx, h), backtest_days=3, horizon=24
    )
    # the synthetic series has a weekly component (i % 7), so lag-1 is not perfect
    assert result is not None and result > 0
    perfect = [(datetime(2026, 11, 1, tzinfo=timezone.utc) + timedelta(hours=i), 400.0)
               for i in range(10 * 24)]
    assert backtest_mae(perfect, lambda ctx, h: lag1_forecast(ctx, h), 3, 24) == 0.0


def test_backtest_mae_returns_none_without_enough_context():
    points = make_points(days=7)
    assert backtest_mae(points, lambda ctx, h: [0.0] * h, backtest_days=5, horizon=24) is None


class FakeForecast:
    def __init__(self, base: float, horizon: int):
        self.median = np.full((1, 1, horizon), base)
        self._q = {
            0.1: np.full((1, 1, horizon), base - 10.0),
            0.9: np.full((1, 1, horizon), base + 10.0),
        }

    def quantile(self, level: float):
        return self._q[level]


class FakeForecaster:
    supports_known_covariates = True
    calls: list[tuple[int, int, int]] = []
    known_calls: list = []

    def forecast(self, context, prediction_length: int, **kwargs):
        cov = kwargs.get("categorical_known_covariates")
        assert cov is not None
        assert cov.shape == (1, 2, context.shape[2] + prediction_length)
        FakeForecaster.calls.append((context.shape[2], prediction_length, cov.shape[2]))
        if "known_covariates" in kwargs:
            FakeForecaster.known_calls.append(kwargs["known_covariates"])
        return FakeForecast(500.0, prediction_length)


def test_timestral_predict_shapes_and_covariates():
    points = make_points(days=5)
    with patch("worker.workflows.dk2_elspot._load_forecaster", return_value=FakeForecaster()):
        median, q10, q90 = timestral_predict(points, 24, "28M")
    assert len(median) == len(q10) == len(q90) == 24
    assert median == [500.0] * 24
    assert q10 == [490.0] * 24
    assert q90 == [510.0] * 24
    assert FakeForecaster.calls[-1] == (5 * 24, 24, 5 * 24 + 24)
    assert not FakeForecaster.known_calls


def test_timestral_predict_passes_weather_known_covariates():
    points = make_points(days=5)
    weather = {}
    hours = [h for h, _ in points]
    from datetime import timedelta
    for h in hours + [hours[-1] + timedelta(hours=i + 1) for i in range(24)]:
        weather[h.strftime(WEATHER_HOUR_KEY)] = [8.0, 4.0, 100.0]
    weather[hours[-1].strftime(WEATHER_HOUR_KEY)] = [float("nan"), 4.0, 0.0]  # missing wind -> NaN
    FakeForecaster.known_calls.clear()
    with patch("worker.workflows.dk2_elspot._load_forecaster", return_value=FakeForecaster()):
        timestral_predict(points, 24, "28M", weather=weather)
    known = FakeForecaster.known_calls[-1]
    assert known.shape == (1, 3, 5 * 24 + 24)
    assert known[0, 0, -1] == 8.0 and known[0, 1, -1] == 4.0 and known[0, 2, -1] == 100.0
    assert np.isnan(known[0, 0, 5 * 24 - 1])


def test_parse_open_meteo_hourly():
    payload = {
        "hourly": {
            "time": ["2026-11-21T00:00", "2026-11-21T01:00"],
            "wind_speed_10m": [8.1, None],
            "temperature_2m": [3.5, 3.0],
            "shortwave_radiation": [0.0, 0.0],
        }
    }
    weather = parse_open_meteo_hourly(payload)
    assert set(weather) == {"2026-11-21T00:00", "2026-11-21T01:00"}
    assert weather["2026-11-21T00:00"] == [8.1, 3.5, 0.0]
    assert np.isnan(weather["2026-11-21T01:00"][0])
    assert weather["2026-11-21T01:00"][1] == 3.0
    assert parse_open_meteo_hourly({}) == {}


def test_summarize_weather_next_hours():
    last = parse_hour_utc("2026-11-21T22:00:00")
    weather = {}
    for i in range(1, 25):
        weather[(last + timedelta(hours=i)).strftime(WEATHER_HOUR_KEY)] = [10.0 + i * 0.1, 2.0 + i * 0.1, 50.0 * i]
    summary = summarize_weather_next_hours(last, 24, weather)
    assert summary["wind_avg_ms"] == round(sum(10.0 + i * 0.1 for i in range(1, 25)) / 24, 1)
    assert summary["temp_min_c"] == 2.1 and summary["temp_max_c"] == 4.4
    assert summary["solar_peak_wm2"] == 1200.0
    assert summarize_weather_next_hours(last, 24, {}) == {
        "wind_avg_ms": None, "temp_min_c": None, "temp_max_c": None, "solar_peak_wm2": None,
    }


async def test_timestral_dk2_forecast_dry_run_returns_baseline():
    payload = await timestral_dk2_forecast(make_history(10), 24, "28M", 3, dry_run=True,
                                            use_weather=False, weather={})
    assert len(payload.forecast) == 24
    assert all(f.median == f.q10 == f.q90 == f.lag1 for f in payload.forecast)
    assert payload.stats["dry_run"] is True
    assert payload.stats["mae_timestral_dkk"] is None
    assert payload.stats["mae_lag1_dkk"] is not None
    assert 0.0 <= payload.stats["corr_lag1"] <= 1.0
    last = parse_hour_utc(payload.forecast[0].hour_utc)
    assert last == parse_hour_utc(make_history(10)[-1].hour_utc) + timedelta(hours=1)


async def test_timestral_dk2_forecast_with_fake_model():
    weather = {}
    points = make_points(10)
    for h, _ in points:
        weather[h.strftime(WEATHER_HOUR_KEY)] = [7.0, 3.0, 10.0]
    for i in range(1, 25):  # forecast window hours
        weather[(points[-1][0] + timedelta(hours=i)).strftime(WEATHER_HOUR_KEY)] = [7.0, 3.0, 10.0]
    FakeForecaster.known_calls.clear()
    with patch("worker.workflows.dk2_elspot._load_forecaster", return_value=FakeForecaster()):
        payload = await timestral_dk2_forecast(make_history(10), 24, "28M", 2, dry_run=False,
                                                use_weather=True, weather=weather)
    assert all(f.median == 500.0 and f.q10 == 490.0 and f.q90 == 510.0 for f in payload.forecast)
    assert payload.stats["mae_timestral_dkk"] is not None
    assert payload.stats["use_weather"] is True
    assert payload.stats["wind_avg_ms"] == 7.0
    assert FakeForecaster.known_calls  # weather was passed as known covariates


async def test_timestral_dk2_forecast_without_weather():
    with patch("worker.workflows.dk2_elspot._load_forecaster", return_value=FakeForecaster()):
        payload = await timestral_dk2_forecast(make_history(10), 24, "28M", 2, dry_run=False,
                                                use_weather=False, weather={})
    assert payload.stats["use_weather"] is False
    assert "wind_avg_ms" not in payload.stats


def test_input_defaults():
    model = Dk2ElspotInput()
    assert model.days == 30
    assert model.horizon_hours == 24
    assert model.model_size == "28M"
    assert model.use_weather is True
    assert model.dry_run is False


@workflows.activity(name="fetch-dk2-day-ahead-prices")
async def mock_fetch_dk2_day_ahead_prices(days: int) -> list[HourlyPoint]:
    return make_history(days=10)


@workflows.activity(name="fetch-dk2-weather")
async def mock_fetch_dk2_weather(days: int) -> dict:
    return {}


@workflows.activity(name="timestral-dk2-forecast")
async def mock_timestral_dk2_forecast(
    history: list[HourlyPoint],
    horizon_hours: int,
    model_size: str,
    backtest_days: int,
    dry_run: bool,
    use_weather: bool,
    weather: dict,
) -> Dk2ForecastPayload:
    forecast = [
        ForecastHour(
            hour_utc=f"2026-11-11T{i:02d}:00:00",
            hour_dk=f"2026-11-11 {i:02d}:00",
            median=500.0,
            q10=490.0,
            q90=510.0,
            lag1=480.0,
        )
        for i in range(horizon_hours)
    ]
    return Dk2ForecastPayload(
        forecast=forecast,
        stats={"corr_lag1": 0.9, "mae_lag1_dkk": 40.0, "mae_timestral_dkk": 35.0,
               "backtest_days": backtest_days, "context_hours": len(history),
               "use_weather": use_weather, "dry_run": dry_run},
    )


async def test_workflow_end_to_end_with_mocked_activities(temporal_env) -> None:
    async with create_test_worker(
        temporal_env,
        workflows=[Dk2ElspotForecastWorkflow],
        activities=[mock_fetch_dk2_day_ahead_prices, mock_fetch_dk2_weather, mock_timestral_dk2_forecast],
    ):
        handle = await temporal_env.client.start_workflow(
            "dk2-elspot-forecast",
            {"days": 10, "horizon_hours": 24, "dry_run": True, "use_weather": True},
            id="test-dk2-elspot",
            task_queue="test-task-queue",
            execution_timeout=WORKFLOW_EXECUTION_TIMEOUT,
        )
        result = await asyncio.wait_for(handle.result(), timeout=45)
        assert result["price_area"] == "DK2"
        assert result["model"] == "timestral-1.0-28m"
        assert len(result["history"]) == 10 * 24
        assert len(result["forecast"]) == 24
        assert result["forecast"][0]["median"] == 500.0
        assert result["stats"]["corr_lag1"] == 0.9
        assert result["stats"]["use_weather"] is True
        assert result["stats"]["dry_run"] is True


async def test_workflow_rejects_bad_model_size(temporal_env) -> None:
    async with create_test_worker(
        temporal_env,
        workflows=[Dk2ElspotForecastWorkflow],
        activities=[mock_fetch_dk2_day_ahead_prices, mock_fetch_dk2_weather, mock_timestral_dk2_forecast],
    ):
        handle = await temporal_env.client.start_workflow(
            "dk2-elspot-forecast",
            {"model_size": "7B"},
            id="test-dk2-elspot-bad-size",
            task_queue="test-task-queue",
            execution_timeout=WORKFLOW_EXECUTION_TIMEOUT,
        )
        try:
            await asyncio.wait_for(handle.result(), timeout=45)
        except Exception:
            pass
        else:
            raise AssertionError("expected the workflow to fail on an invalid model_size")

"""수도 시계열의 객관적인 특징값을 계산하는 순수 함수."""

from collections import defaultdict
from datetime import date, datetime, timedelta
from itertools import pairwise
from statistics import median
from typing import Any

from app.schemas.water_usage import NormalizedWaterUsage, WaterMeasurement


def _sum_since(measurements: tuple[WaterMeasurement, ...], start: datetime, end: datetime) -> float:
    """[start, end) 범위의 사용량을 더한다."""
    return sum(item.usage_liter for item in measurements if start <= item.timestamp < end)


def calculate_features(data: NormalizedWaterUsage) -> dict[str, Any]:
    """GPT가 산술 추론하지 않도록 모든 요구 특징을 로컬에서 계산한다."""
    measurements = data.measurements
    start = measurements[0].timestamp
    end = measurements[-1].timestamp
    deltas = [
        (right.timestamp - left.timestamp).total_seconds() / 60
        for left, right in pairwise(measurements)
    ]
    interval = float(median(deltas)) if deltas else 60.0
    recent_24 = _sum_since(measurements, end - timedelta(hours=24), end + timedelta(microseconds=1))
    previous_24 = _sum_since(measurements, end - timedelta(hours=48), end - timedelta(hours=24))
    recent_7d = _sum_since(measurements, end - timedelta(days=7), end + timedelta(microseconds=1))
    duration_days = max((end - start).total_seconds() / 86400, interval / 1440)
    average_daily = sum(item.usage_liter for item in measurements) / duration_days
    positive = [item for item in measurements if item.usage_liter > 0]
    last_usage = positive[-1].timestamp if positive else None
    hours_since = (end - last_usage).total_seconds() / 3600 if last_usage else duration_days * 24

    expected_count = round((end - start).total_seconds() / 60 / interval) + 1
    missing_ratio = max(0.0, 1 - len(measurements) / max(expected_count, 1))
    drop_rate = max(0.0, min(1.0, (previous_24 - recent_24) / previous_24)) if previous_24 else 0.0

    hourly: dict[int, list[float]] = defaultdict(list)
    for item in measurements:
        hourly[item.timestamp.hour].append(item.usage_liter)
    hourly_averages = {str(hour): sum(values) / len(values) for hour, values in hourly.items()}
    same_hour_deviation = {
        str(hour): values[-1] - hourly_averages[str(hour)] for hour, values in hourly.items()
    }

    days: dict[date, list[WaterMeasurement]] = defaultdict(list)
    for item in measurements:
        days[item.timestamp.date()].append(item)
    first_uses = [
        min(item.timestamp for item in items if item.usage_liter > 0)
        for items in days.values()
        if any(item.usage_liter > 0 for item in items)
    ]
    typical_first_minutes = (
        median(item.hour * 60 + item.minute for item in first_uses[:-1] or first_uses)
        if first_uses
        else None
    )
    today_uses = [item for item in days[end.date()] if item.usage_liter > 0]
    first_use = min((item.timestamp for item in today_uses), default=None)
    first_use_delay = (
        first_use.hour * 60 + first_use.minute - typical_first_minutes
        if first_use and typical_first_minutes is not None
        else None
    )
    return {
        "measurement_start": start.isoformat(),
        "measurement_end": end.isoformat(),
        "interval_minutes": interval,
        "usage_last_24h_liter": round(recent_24, 3),
        "usage_previous_24h_liter": round(previous_24, 3),
        "usage_last_7d_liter": round(recent_7d, 3),
        "average_daily_usage_liter": round(average_daily, 3),
        "last_positive_usage_at": last_usage.isoformat() if last_usage else None,
        "hours_since_last_usage": round(hours_since, 3),
        "zero_usage_streak_hours": round(hours_since, 3),
        "usage_drop_rate": round(drop_rate, 4),
        "hourly_average_usage_liter": hourly_averages,
        "same_hour_deviation_liter": same_hour_deviation,
        "first_use_at": first_use.isoformat() if first_use else None,
        "typical_first_use_minutes": typical_first_minutes,
        "first_use_delay_minutes": first_use_delay,
        "missing_ratio": round(missing_ratio, 4),
        "meter_status": data.meter_status,
        "expected_absence": data.expected_absence,
        "baseline_days": round(duration_days, 2),
    }

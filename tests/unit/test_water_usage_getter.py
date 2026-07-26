"""WaterUsageGetter 검증 계약 테스트."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.exceptions import InputValidationError
from app.modules.getter.water_usage_getter import WaterUsageGetter
from app.schemas.water_usage import WaterMeasurement


def test_normal_and_sorted(request_factory) -> None:
    request = request_factory()
    request.measurements.reverse()
    result = WaterUsageGetter().normalize(request, now=datetime(2026, 7, 21, tzinfo=UTC))
    assert len(result.measurements) == 72
    assert list(result.measurements) == sorted(result.measurements, key=lambda item: item.timestamp)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda r: setattr(r, "household_id", "이름 홍길동"), "household_id"),
        (lambda r: setattr(r, "measurements", r.measurements[:23]), "최소 24"),
        (
            lambda r: setattr(
                r,
                "measurements",
                [
                    WaterMeasurement(
                        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=i),
                        usage_liter=0,
                    )
                    for i in range(5001)
                ],
            ),
            "최대 5,000",
        ),
    ],
)
def test_domain_rejections(request_factory, mutate, message: str) -> None:
    request = request_factory()
    mutate(request)
    with pytest.raises(InputValidationError, match=message):
        WaterUsageGetter().normalize(request, now=datetime(2026, 7, 21, tzinfo=UTC))


def test_duplicate_timestamp_rejected(request_factory) -> None:
    request = request_factory()
    request.measurements[1].timestamp = request.measurements[0].timestamp
    with pytest.raises(InputValidationError, match="중복"):
        WaterUsageGetter().normalize(request, now=datetime(2026, 7, 21, tzinfo=UTC))


def test_naive_timestamp_rejected(request_factory) -> None:
    request = request_factory()
    request.measurements[0].timestamp = request.measurements[0].timestamp.replace(tzinfo=None)
    with pytest.raises(InputValidationError, match="timezone"):
        WaterUsageGetter().normalize(request, now=datetime(2026, 7, 21, tzinfo=UTC))


def test_negative_usage_rejected_by_schema(request_factory) -> None:
    request = request_factory().model_dump()
    request["measurements"][0]["usage_liter"] = -1
    from pydantic import ValidationError

    from app.schemas.water_usage import WaterUsageAnalysisRequest

    with pytest.raises(ValidationError):
        WaterUsageAnalysisRequest.model_validate(request)

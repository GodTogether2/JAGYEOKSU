"""외부 수도 사용량을 안전한 내부 구조체로 변환한다.

담당: 홍성표
"""

import re
from datetime import UTC, datetime

from app.core.exceptions import InputValidationError
from app.schemas.water_usage import NormalizedWaterUsage, WaterUsageAnalysisRequest

HOUSEHOLD_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class WaterUsageGetter:
    """검증·정렬·정규화만 담당하며 분석이나 프롬프트 생성은 하지 않는다."""

    def normalize(
        self,
        request: WaterUsageAnalysisRequest,
        *,
        now: datetime | None = None,
    ) -> NormalizedWaterUsage:
        """FastAPI 입력을 검증한 뒤 시간순 불변 튜플 구조체로 만든다."""
        current = (now or datetime.now(UTC)).astimezone(UTC)
        if not HOUSEHOLD_ID_PATTERN.fullmatch(request.household_id):
            raise InputValidationError("household_id는 영문, 숫자, 하이픈, 밑줄만 허용합니다.")
        count = len(request.measurements)
        if count < 24:
            raise InputValidationError("측정값은 최소 24개 이상이어야 합니다.")
        if count > 5_000:
            raise InputValidationError("측정값은 최대 5,000개까지 허용합니다.")

        timestamps: set[datetime] = set()
        for measurement in request.measurements:
            timestamp = measurement.timestamp
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise InputValidationError("모든 timestamp에는 timezone 정보가 필요합니다.")
            utc_timestamp = timestamp.astimezone(UTC)
            if utc_timestamp > current:
                raise InputValidationError("미래 시각의 측정값은 허용하지 않습니다.")
            if utc_timestamp in timestamps:
                raise InputValidationError("동일한 timestamp가 중복됐습니다.")
            timestamps.add(utc_timestamp)

        ordered = tuple(sorted(request.measurements, key=lambda item: item.timestamp))
        return NormalizedWaterUsage(
            request_id=request.request_id,
            household_id=request.household_id,
            meter_status=request.meter_status,
            expected_absence=request.expected_absence,
            measurements=ordered,
            normalized_at=current,
        )

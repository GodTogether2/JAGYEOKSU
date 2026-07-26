"""수도 사용량 입력 및 정규화 스키마."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MeterStatus = Literal["ONLINE", "OFFLINE", "UNKNOWN"]


class WaterMeasurement(BaseModel):
    """단일 수도 계량 측정값."""

    model_config = ConfigDict(extra="forbid")
    timestamp: datetime
    usage_liter: float = Field(ge=0, allow_inf_nan=False)


class WaterUsageAnalysisRequest(BaseModel):
    """개인정보 필드를 허용하지 않는 외부 분석 요청."""

    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1, max_length=100)
    household_id: str = Field(min_length=1, max_length=100)
    meter_status: MeterStatus
    expected_absence: bool = False
    measurements: list[WaterMeasurement]


class NormalizedWaterUsage(BaseModel):
    """WaterUsageGetter가 만드는 내부 공통 구조체."""

    request_id: str
    household_id: str
    meter_status: MeterStatus
    expected_absence: bool
    measurements: tuple[WaterMeasurement, ...]
    normalized_at: datetime

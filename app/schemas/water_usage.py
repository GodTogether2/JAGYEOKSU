"""이전 import 경로를 지원하는 공용 수도 사용 모델 호환 모듈."""

from app.common.models.water_usage import (
    MeterStatus,
    NormalizedWaterUsage,
    WaterMeasurement,
    WaterUsageAnalysisRequest,
)

__all__ = [
    "MeterStatus",
    "NormalizedWaterUsage",
    "WaterMeasurement",
    "WaterUsageAnalysisRequest",
]

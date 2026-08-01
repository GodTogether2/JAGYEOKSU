"""수도 사용 이상징후 분석 라우터."""

import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_anomaly_analysis_service, get_water_usage_getter
from app.common.models.anomaly import AnomalyAnalysisResponse
from app.common.models.water_usage import WaterUsageAnalysisRequest
from app.core.exceptions import InputValidationError
from app.core.logging import log_event, mask_household_id
from app.modules.detector.anomaly_analysis_service import AnomalyAnalysisService
from app.modules.getter.water_usage_getter import WaterUsageGetter

router = APIRouter(prefix="/api/v1/anomalies", tags=["anomalies"])
logger = logging.getLogger(__name__)


@router.post("/analyze", response_model=AnomalyAnalysisResponse)
async def analyze_anomaly(
    request: WaterUsageAnalysisRequest,
    getter: Annotated[WaterUsageGetter, Depends(get_water_usage_getter)],
    service: Annotated[AnomalyAnalysisService, Depends(get_anomaly_analysis_service)],
) -> AnomalyAnalysisResponse:
    """라우터는 핵심 세 클래스의 흐름만 연결하고 계산하지 않는다."""
    started = time.perf_counter()
    try:
        normalized = getter.normalize(request)
    except InputValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = await service.analyze(normalized)
    log_event(
        logger,
        "analysis_completed",
        request_id=request.request_id,
        household_id=mask_household_id(request.household_id),
        path="/api/v1/anomalies/analyze",
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
        status=result.status,
        llm_success=result.model_provider == "ollama",
    )
    return result

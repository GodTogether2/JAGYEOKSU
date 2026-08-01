"""서비스 상태 라우터."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.common.models.common import HealthResponse
from app.core.config import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    """비밀값 없이 LLM 설정 여부만 알려준다."""
    return HealthResponse(
        status="UP",
        service="caresignal-api",
        llm_configured=settings.llm_configured,
    )

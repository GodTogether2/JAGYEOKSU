"""공통 응답 스키마."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """서비스 상태 응답."""

    status: str
    service: str
    openai_configured: bool


class ErrorResponse(BaseModel):
    """내부 상세를 숨긴 표준 오류 응답."""

    detail: str

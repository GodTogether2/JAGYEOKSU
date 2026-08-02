"""서비스 상태와 오류에 사용하는 공용 응답 구조체."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """서비스 상태 응답."""

    status: str
    service: str
    llm_configured: bool


class ErrorResponse(BaseModel):
    """내부 상세를 숨긴 표준 오류 응답."""

    detail: str

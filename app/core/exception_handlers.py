"""예외를 민감정보 없는 HTTP 응답으로 변환한다."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    InvalidLLMResponseError,
    OpenAIAuthError,
    OpenAIRateLimitError,
    OpenAIServiceError,
    OpenAITimeoutError,
)

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """외부 장애 유형별 요구 상태 코드를 등록한다."""

    @app.exception_handler(OpenAITimeoutError)
    async def timeout_handler(_: Request, __: OpenAITimeoutError) -> JSONResponse:
        return JSONResponse(
            status_code=504, content={"detail": "AI 분석 요청 시간이 초과됐습니다."}
        )

    @app.exception_handler(OpenAIRateLimitError)
    async def rate_limit_handler(_: Request, __: OpenAIRateLimitError) -> JSONResponse:
        return JSONResponse(
            status_code=503, content={"detail": "AI 분석 서비스가 일시적으로 혼잡합니다."}
        )

    @app.exception_handler(OpenAIAuthError)
    async def auth_handler(_: Request, __: OpenAIAuthError) -> JSONResponse:
        return JSONResponse(
            status_code=502, content={"detail": "AI 분석 서비스를 사용할 수 없습니다."}
        )

    @app.exception_handler(InvalidLLMResponseError)
    async def invalid_handler(_: Request, __: InvalidLLMResponseError) -> JSONResponse:
        return JSONResponse(
            status_code=502, content={"detail": "AI 분석 결과를 검증할 수 없습니다."}
        )

    @app.exception_handler(OpenAIServiceError)
    async def service_handler(_: Request, __: OpenAIServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=502, content={"detail": "AI 분석 서비스 호출에 실패했습니다."}
        )

    @app.exception_handler(Exception)
    async def unexpected_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unexpected_server_error", exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "서버 내부 오류가 발생했습니다."})

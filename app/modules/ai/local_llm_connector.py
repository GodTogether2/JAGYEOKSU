"""Ollama 기반 로컬 LLM Structured Outputs 어댑터.

담당: 문범석
"""

import json
from collections.abc import Awaitable, Callable
from typing import Protocol

import httpx
import ollama
from pydantic import ValidationError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.common.models.anomaly import AnomalyLLMResult
from app.core.config import Settings
from app.core.exceptions import (
    InvalidLLMResponseError,
    LLMConnectionError,
    LLMServiceError,
    LLMTimeoutError,
)


class AnalysisConnector(Protocol):
    """Service와 Connector가 독립 개발할 수 있게 고정한 호출 계약."""

    async def analyze(
        self, system_prompt: str, user_payload: dict[str, object]
    ) -> AnomalyLLMResult:
        """프롬프트와 특징 JSON을 구조화 결과로 변환한다."""
        raise AssertionError("프로토콜 선언은 직접 호출할 수 없습니다.")


class _RetryableLLMError(Exception):
    """Ollama 서버 연결 실패에만 적용하는 내부 재시도 신호."""


class LocalLLMConnector:
    """Ollama 서버 연결, 요청, 재시도 및 오류 번역만 담당한다."""

    def __init__(
        self,
        settings: Settings,
        client: ollama.AsyncClient | None = None,
        request_callable: Callable[..., Awaitable[object]] | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or ollama.AsyncClient(
            host=settings.llm_base_url,
            timeout=settings.llm_timeout_seconds,
        )
        self._request_callable = request_callable

    async def analyze(
        self,
        system_prompt: str,
        user_payload: dict[str, object],
    ) -> AnomalyLLMResult:
        """시스템 프롬프트와 JSON payload를 함께 Ollama에 전달한다."""
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.settings.llm_max_retries + 1),
                wait=wait_exponential(multiplier=0.25, min=0.25, max=2),
                retry=retry_if_exception_type(_RetryableLLMError),
                reraise=True,
            ):
                with attempt:
                    return await self._call_once(system_prompt, user_payload)
        except _RetryableLLMError as exc:
            raise LLMConnectionError("Ollama 서버에 연결할 수 없습니다.") from exc
        raise LLMServiceError("LLM 호출이 완료되지 않았습니다.")

    async def _call_once(
        self, system_prompt: str, user_payload: dict[str, object]
    ) -> AnomalyLLMResult:
        """Ollama의 스키마 강제 디코딩으로 자유 텍스트 json.loads 파싱을 피한다."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, default=str)},
        ]
        try:
            if self._request_callable is not None:
                response = await self._request_callable(
                    model=self.settings.llm_model,
                    messages=messages,
                    format=AnomalyLLMResult.model_json_schema(),
                    think=False,
                )
            else:
                response = await self.client.chat(
                    model=self.settings.llm_model,
                    messages=messages,
                    format=AnomalyLLMResult.model_json_schema(),
                    think=False,
                )
            content = getattr(getattr(response, "message", None), "content", None)
            if not isinstance(content, str) or not content:
                raise InvalidLLMResponseError("구조화 출력이 비어 있거나 형식이 올바르지 않습니다.")
            return AnomalyLLMResult.model_validate_json(content)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("LLM 응답 시간이 초과됐습니다.") from exc
        except ConnectionError as exc:
            raise _RetryableLLMError from exc
        except ollama.ResponseError as exc:
            raise LLMServiceError(f"Ollama 오류: {exc}") from exc
        except ValidationError as exc:
            raise InvalidLLMResponseError("LLM 구조화 출력 검증 실패") from exc

"""OpenAI Responses API Structured Outputs 어댑터.

담당: 문범석
"""

import json
from collections.abc import Awaitable, Callable
from typing import Protocol

import openai
from openai import AsyncOpenAI
from pydantic import ValidationError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.common.models.anomaly import AnomalyLLMResult
from app.core.config import Settings
from app.core.exceptions import (
    InvalidLLMResponseError,
    OpenAIAuthError,
    OpenAIBadRequestError,
    OpenAIRateLimitError,
    OpenAIServiceError,
    OpenAITimeoutError,
)


class AnalysisConnector(Protocol):
    """Service와 Connector가 독립 개발할 수 있게 고정한 호출 계약."""

    async def analyze(
        self, system_prompt: str, user_payload: dict[str, object]
    ) -> AnomalyLLMResult:
        """프롬프트와 특징 JSON을 구조화 결과로 변환한다."""
        raise AssertionError("프로토콜 선언은 직접 호출할 수 없습니다.")


class _RetryableOpenAIError(Exception):
    """네트워크·서버 장애에만 적용하는 내부 재시도 신호."""


class OpenAIConnector:
    """SDK 초기화, 요청, 재시도 및 오류 번역만 담당한다."""

    def __init__(
        self,
        settings: Settings,
        client: AsyncOpenAI | None = None,
        request_callable: Callable[..., Awaitable[object]] | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or AsyncOpenAI(
            api_key=settings.openai_api_key or "not-configured",
            timeout=settings.openai_timeout_seconds,
            max_retries=0,  # 재시도 횟수는 tenacity 한 곳에서만 통제한다.
        )
        self._request_callable = request_callable

    async def analyze(
        self,
        system_prompt: str,
        user_payload: dict[str, object],
    ) -> AnomalyLLMResult:
        """시스템 프롬프트와 JSON payload를 함께 Responses API에 전달한다."""
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.settings.openai_max_retries + 1),
                wait=wait_exponential(multiplier=0.25, min=0.25, max=2),
                retry=retry_if_exception_type(_RetryableOpenAIError),
                reraise=True,
            ):
                with attempt:
                    return await self._call_once(system_prompt, user_payload)
        except _RetryableOpenAIError as exc:
            raise OpenAIServiceError("OpenAI 네트워크 또는 서버 장애") from exc
        raise OpenAIServiceError("OpenAI 호출이 완료되지 않았습니다.")

    async def _call_once(
        self, system_prompt: str, user_payload: dict[str, object]
    ) -> AnomalyLLMResult:
        """SDK parse 기능으로 자유 텍스트 json.loads 파싱을 피한다."""
        try:
            if self._request_callable is not None:
                response = await self._request_callable(
                    model=self.settings.openai_model,
                    instructions=system_prompt,
                    input=[
                        {
                            "role": "user",
                            "content": json.dumps(user_payload, ensure_ascii=False, default=str),
                        }
                    ],
                    text_format=AnomalyLLMResult,
                    store=False,
                )
            else:
                response = await self.client.responses.parse(
                    model=self.settings.openai_model,
                    instructions=system_prompt,
                    input=[
                        {
                            "role": "user",
                            "content": json.dumps(user_payload, ensure_ascii=False, default=str),
                        }
                    ],
                    text_format=AnomalyLLMResult,
                    store=False,
                )
            parsed = getattr(response, "output_parsed", None)
            if not isinstance(parsed, AnomalyLLMResult):
                raise InvalidLLMResponseError("구조화 출력이 없거나 스키마가 다릅니다.")
            return AnomalyLLMResult.model_validate(parsed)
        except openai.APITimeoutError as exc:
            raise OpenAITimeoutError("OpenAI timeout") from exc
        except openai.RateLimitError as exc:
            raise OpenAIRateLimitError("OpenAI rate limit") from exc
        except openai.AuthenticationError as exc:
            raise OpenAIAuthError("OpenAI authentication failed") from exc
        except openai.BadRequestError as exc:
            raise OpenAIBadRequestError("OpenAI bad request") from exc
        except (openai.APIConnectionError, openai.InternalServerError) as exc:
            raise _RetryableOpenAIError from exc
        except ValidationError as exc:
            raise InvalidLLMResponseError("OpenAI structured output validation failed") from exc

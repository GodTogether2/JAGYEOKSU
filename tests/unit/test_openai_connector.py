"""OpenAIConnector의 구조화 출력과 오류 변환 테스트."""

from types import SimpleNamespace

import httpx
import openai
import pytest

from app.core.config import Settings
from app.core.exceptions import (
    InvalidLLMResponseError,
    OpenAIAuthError,
    OpenAIRateLimitError,
    OpenAIServiceError,
    OpenAITimeoutError,
)
from app.modules.ai.openai_connector import OpenAIConnector
from tests.conftest import FakeOpenAIConnector


@pytest.mark.asyncio
async def test_structured_response() -> None:
    expected = FakeOpenAIConnector().result

    async def request(**kwargs):
        assert kwargs["store"] is False
        assert kwargs["instructions"] == "system"
        return SimpleNamespace(output_parsed=expected)

    result = await OpenAIConnector(Settings(), request_callable=request).analyze("system", {"a": 1})
    assert result == expected


def api_request() -> httpx.Request:
    return httpx.Request("POST", "https://api.openai.com/v1/responses")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_factory", "expected"),
    [
        (lambda: openai.APITimeoutError(api_request()), OpenAITimeoutError),
        (
            lambda: openai.RateLimitError(
                "rate", response=httpx.Response(429, request=api_request()), body=None
            ),
            OpenAIRateLimitError,
        ),
        (
            lambda: openai.AuthenticationError(
                "auth", response=httpx.Response(401, request=api_request()), body=None
            ),
            OpenAIAuthError,
        ),
    ],
)
async def test_error_mapping(error_factory, expected) -> None:
    async def request(**kwargs):
        raise error_factory()

    with pytest.raises(expected):
        await OpenAIConnector(Settings(), request_callable=request).analyze("system", {})


@pytest.mark.asyncio
async def test_invalid_structured_output() -> None:
    async def request(**kwargs):
        return SimpleNamespace(output_parsed=None)

    with pytest.raises(InvalidLLMResponseError):
        await OpenAIConnector(Settings(), request_callable=request).analyze("system", {})


@pytest.mark.asyncio
async def test_network_retry_count() -> None:
    calls = 0

    async def request(**kwargs):
        nonlocal calls
        calls += 1
        raise openai.APIConnectionError(request=api_request())

    with pytest.raises(OpenAIServiceError):
        await OpenAIConnector(Settings(openai_max_retries=2), request_callable=request).analyze(
            "system", {}
        )
    assert calls == 3

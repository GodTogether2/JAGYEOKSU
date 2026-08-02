"""LocalLLMConnector의 구조화 출력과 오류 변환 테스트."""

from types import SimpleNamespace

import httpx
import ollama
import pytest

from app.core.config import Settings
from app.core.exceptions import (
    InvalidLLMResponseError,
    LLMConnectionError,
    LLMServiceError,
    LLMTimeoutError,
)
from app.modules.ai.local_llm_connector import LocalLLMConnector
from tests.conftest import FakeLLMConnector


def _response(content: str | None) -> SimpleNamespace:
    return SimpleNamespace(message=SimpleNamespace(content=content))


@pytest.mark.asyncio
async def test_structured_response() -> None:
    expected = FakeLLMConnector().result

    async def request(**kwargs):
        assert kwargs["model"] == "qwen3:8b"
        assert kwargs["messages"][0] == {"role": "system", "content": "system"}
        assert kwargs["messages"][1]["role"] == "user"
        assert "format" in kwargs
        assert kwargs["think"] is False
        assert kwargs["options"] == {"temperature": 0.7, "top_p": 0.8, "top_k": 20}
        return _response(expected.model_dump_json())

    result = await LocalLLMConnector(Settings(), request_callable=request).analyze(
        "system", {"a": 1}
    )
    assert result == expected


@pytest.mark.asyncio
async def test_timeout_mapping() -> None:
    async def request(**kwargs):
        raise httpx.TimeoutException("timeout")

    with pytest.raises(LLMTimeoutError):
        await LocalLLMConnector(Settings(), request_callable=request).analyze("system", {})


@pytest.mark.asyncio
async def test_response_error_mapping() -> None:
    async def request(**kwargs):
        raise ollama.ResponseError("model not found", 404)

    with pytest.raises(LLMServiceError):
        await LocalLLMConnector(Settings(), request_callable=request).analyze("system", {})


@pytest.mark.asyncio
async def test_empty_structured_output() -> None:
    async def request(**kwargs):
        return _response(None)

    with pytest.raises(InvalidLLMResponseError):
        await LocalLLMConnector(Settings(), request_callable=request).analyze("system", {})


@pytest.mark.asyncio
async def test_invalid_structured_output_schema() -> None:
    async def request(**kwargs):
        return _response('{"status": "NOT_A_VALID_STATUS"}')

    with pytest.raises(InvalidLLMResponseError):
        await LocalLLMConnector(Settings(), request_callable=request).analyze("system", {})


@pytest.mark.asyncio
async def test_connection_retry_count() -> None:
    calls = 0

    async def request(**kwargs):
        nonlocal calls
        calls += 1
        raise ConnectionError("Failed to connect to Ollama")

    with pytest.raises(LLMConnectionError):
        await LocalLLMConnector(Settings(llm_max_retries=2), request_callable=request).analyze(
            "system", {}
        )
    assert calls == 3

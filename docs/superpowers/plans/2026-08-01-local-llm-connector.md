# LocalLLMConnector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `OpenAIConnector` (hosted OpenAI API) with `LocalLLMConnector`, which calls a locally-running Ollama server hosting Qwen3 8B, so CareSignal complies with the competition's open-weight/independently-operable AI model rule (제9조), while keeping the `AnalysisConnector` protocol and every other module unchanged.

**Architecture:** `LocalLLMConnector` implements the same `AnalysisConnector.analyze(system_prompt, user_payload) -> AnomalyLLMResult` contract as the old connector, but calls `ollama.AsyncClient.chat(..., format=AnomalyLLMResult.model_json_schema())` instead of `AsyncOpenAI.responses.parse(...)`. Settings and exceptions that were OpenAI-specific are renamed/trimmed to match local-server semantics (no API key, no rate limits, no auth — but a new connection-refused case that didn't exist before).

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, `ollama` (official Python client) replacing `openai`, `httpx`, `tenacity`, pytest/pytest-asyncio.

**Reference spec:** [docs/superpowers/specs/2026-08-01-local-llm-connector-design.md](../specs/2026-08-01-local-llm-connector-design.md)

---

## Before you start

This plan assumes Ollama is already installed on the machine (`winget install Ollama.Ollama` on Windows). Pulling the actual `qwen3:8b` model weights (~5GB) is **not** part of this plan — see the "Manual post-implementation step" at the end. All automated tasks below use an injected `request_callable` so no task requires a running Ollama server or a downloaded model.

**Important ordering note:** Tasks 1–4 are foundational renames. Between Task 3 and Task 7, running the *whole* test suite (`pytest` with no path) or whole-project `mypy app`/`ruff check .` will show pre-existing failures in files not yet updated (`tests/unit/test_openai_connector.py`, `app/api/dependencies.py`, etc.) — this is expected. Each task's own verify step only targets the files that task touches. The suite is only guaranteed green as a whole after Task 7.

---

### Task 1: Swap `openai` dependency for `ollama`

**Files:**
- Modify: `pyproject.toml:12-20`

- [ ] **Step 1: Edit the dependency list**

In `pyproject.toml`, replace:

```toml
dependencies = [
  "fastapi>=0.115,<1",
  "uvicorn[standard]>=0.34,<1",
  "pydantic>=2.10,<3",
  "pydantic-settings>=2.7,<3",
  "openai>=1.68,<2",
  "httpx>=0.28,<1",
  "tenacity>=9,<10",
]
```

with:

```toml
dependencies = [
  "fastapi>=0.115,<1",
  "uvicorn[standard]>=0.34,<1",
  "pydantic>=2.10,<3",
  "pydantic-settings>=2.7,<3",
  "ollama>=0.6,<1",
  "httpx>=0.28,<1",
  "tenacity>=9,<10",
]
```

- [ ] **Step 2: Reinstall the package to pick up the new dependency**

Run: `pip install -e ".[dev]"`
Expected: install succeeds, `ollama` appears in the output, `openai` is no longer required (it may still be present in the environment until you restart the venv — that's fine, it's just not a declared dependency anymore).

- [ ] **Step 3: Verify `ollama` importable**

Run: `python -c "import ollama; print(ollama.AsyncClient, ollama.ResponseError)"`
Expected: prints the two class objects, no error. (`ollama.__version__` is not exposed at the top level — use `importlib.metadata.version('ollama')` if you need the installed version string.)

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: replace openai dependency with ollama"
```

---

### Task 2: Rework `Settings` for local LLM config

**Files:**
- Modify: `app/core/config.py`

- [ ] **Step 1: Replace the whole file**

```python
"""환경변수 기반 애플리케이션 설정."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """민감정보를 코드와 분리하고 환경변수에서만 읽는다."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    log_level: str = "INFO"
    llm_model: str = "qwen3:8b"
    llm_base_url: str = "http://localhost:11434"
    llm_timeout_seconds: float = Field(default=180, gt=0)
    llm_max_retries: int = Field(default=2, ge=0, le=2)
    missing_ratio_threshold: float = Field(default=0.2, ge=0, le=1)
    cors_origins: str = ""

    @property
    def llm_configured(self) -> bool:
        """LLM 모델명이 설정되어 있는지 여부만 공개한다."""
        return bool(self.llm_model.strip())


@lru_cache
def get_settings() -> Settings:
    """프로세스 내에서 설정 객체를 재사용한다."""
    return Settings()
```

- [ ] **Step 2: Verify the new fields**

Run:
```bash
python -c "from app.core.config import Settings; s = Settings(); assert s.llm_model == 'qwen3:8b'; assert s.llm_base_url == 'http://localhost:11434'; assert s.llm_timeout_seconds == 180; assert s.llm_max_retries == 2; assert s.llm_configured is True; print('ok')"
```
Expected: prints `ok`, no `AttributeError`.

- [ ] **Step 3: Commit**

```bash
git add app/core/config.py
git commit -m "refactor: replace OpenAI settings with local LLM settings"
```

---

### Task 3: Rework exception taxonomy for a local server

**Files:**
- Modify: `app/core/exceptions.py`
- Modify: `app/core/exception_handlers.py`

- [ ] **Step 1: Replace `app/core/exceptions.py`**

```python
"""외부 서비스 및 입력 오류를 분리하는 프로젝트 공통 예외."""


class CareSignalError(Exception):
    """모든 프로젝트 예외의 기반 클래스."""


class InputValidationError(CareSignalError):
    """Getter 단계의 도메인 입력 오류."""


class LLMServiceError(CareSignalError):
    """로컬 LLM 일반 장애."""


class LLMTimeoutError(LLMServiceError):
    """로컬 LLM 응답 제한시간 초과."""


class LLMConnectionError(LLMServiceError):
    """Ollama 서버에 연결할 수 없음(미실행 또는 모델 미다운로드)."""


class InvalidLLMResponseError(LLMServiceError):
    """스키마 또는 안전 정책을 만족하지 않는 모델 응답."""
```

Removed: `OpenAIServiceError` (→ renamed `LLMServiceError`), `OpenAITimeoutError` (→ renamed `LLMTimeoutError`), `OpenAIRateLimitError` and `OpenAIAuthError` and `OpenAIBadRequestError` (deleted — a single local Ollama server has no auth or per-caller rate limiting). Added: `LLMConnectionError` for "server not running / model not pulled".

- [ ] **Step 2: Replace `app/core/exception_handlers.py`**

```python
"""예외를 민감정보 없는 HTTP 응답으로 변환한다."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    InvalidLLMResponseError,
    LLMConnectionError,
    LLMServiceError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """외부 장애 유형별 요구 상태 코드를 등록한다."""

    @app.exception_handler(LLMTimeoutError)
    async def timeout_handler(_: Request, __: LLMTimeoutError) -> JSONResponse:
        return JSONResponse(
            status_code=504, content={"detail": "AI 분석 요청 시간이 초과됐습니다."}
        )

    @app.exception_handler(LLMConnectionError)
    async def connection_handler(_: Request, __: LLMConnectionError) -> JSONResponse:
        return JSONResponse(
            status_code=503, content={"detail": "AI 분석 서비스가 일시적으로 연결되지 않습니다."}
        )

    @app.exception_handler(InvalidLLMResponseError)
    async def invalid_handler(_: Request, __: InvalidLLMResponseError) -> JSONResponse:
        return JSONResponse(
            status_code=502, content={"detail": "AI 분석 결과를 검증할 수 없습니다."}
        )

    @app.exception_handler(LLMServiceError)
    async def service_handler(_: Request, __: LLMServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=502, content={"detail": "AI 분석 서비스 호출에 실패했습니다."}
        )

    @app.exception_handler(Exception)
    async def unexpected_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unexpected_server_error", exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "서버 내부 오류가 발생했습니다."})
```

- [ ] **Step 3: Verify the module imports cleanly**

Run: `python -c "import app.core.exceptions, app.core.exception_handlers; print('ok')"`
Expected: prints `ok`. (This does not run the full app, so it won't yet catch the still-outdated imports in `openai_connector.py` — that's expected, it gets deleted in Task 6.)

- [ ] **Step 4: Commit**

```bash
git add app/core/exceptions.py app/core/exception_handlers.py
git commit -m "refactor: rename OpenAI exceptions to LLM exceptions for local server semantics"
```

---

### Task 4: Rename `HealthResponse.openai_configured` → `llm_configured`

**Files:**
- Modify: `app/common/models/common.py`
- Modify: `app/api/routes/health.py`

- [ ] **Step 1: Update `app/common/models/common.py`**

Replace:
```python
class HealthResponse(BaseModel):
    """서비스 상태 응답."""

    status: str
    service: str
    openai_configured: bool
```

with:
```python
class HealthResponse(BaseModel):
    """서비스 상태 응답."""

    status: str
    service: str
    llm_configured: bool
```

- [ ] **Step 2: Update `app/api/routes/health.py`**

Replace:
```python
@router.get("/health", response_model=HealthResponse)
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    """비밀값 없이 OpenAI 설정 여부만 알려준다."""
    return HealthResponse(
        status="UP",
        service="caresignal-api",
        openai_configured=settings.openai_configured,
    )
```

with:
```python
@router.get("/health", response_model=HealthResponse)
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    """비밀값 없이 LLM 설정 여부만 알려준다."""
    return HealthResponse(
        status="UP",
        service="caresignal-api",
        llm_configured=settings.llm_configured,
    )
```

- [ ] **Step 3: Verify**

Run: `python -c "from app.common.models.common import HealthResponse; HealthResponse(status='UP', service='x', llm_configured=True); print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add app/common/models/common.py app/api/routes/health.py
git commit -m "refactor: rename health field openai_configured to llm_configured"
```

(The integration test asserting on this field is fixed together with the other test-file updates in Task 7, since that same file also imports things that don't exist until Task 6.)

---

### Task 5: Write failing tests for `LocalLLMConnector` (TDD red)

**Files:**
- Create: `tests/unit/test_local_llm_connector.py`

This new connector doesn't exist yet — these tests establish its contract before it's written. They use dependency injection (`request_callable`) so no real Ollama server is needed, matching CLAUDE.md's rule that tests never hit a real external service.

- [ ] **Step 1: Write the test file**

```python
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
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `pytest tests/unit/test_local_llm_connector.py -v`
Expected: `ModuleNotFoundError: No module named 'app.modules.ai.local_llm_connector'` (or `ImportError: cannot import name 'FakeLLMConnector'` — whichever import fails first). Either failure is expected at this point.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_local_llm_connector.py
git commit -m "test: add failing tests for LocalLLMConnector"
```

---

### Task 6: Implement `LocalLLMConnector` (TDD green)

**Files:**
- Create: `app/modules/ai/local_llm_connector.py`
- Delete: `app/modules/ai/openai_connector.py`
- Modify: `tests/conftest.py`

The test file from Task 5 also needs `FakeLLMConnector` (renamed from `FakeOpenAIConnector`) to exist in `tests/conftest.py`, so that rename happens here too — it's a pure rename with no behavior change.

- [ ] **Step 1: Rename `FakeOpenAIConnector` → `FakeLLMConnector` in `tests/conftest.py`**

Replace:
```python
"""실제 OpenAI 호출 없이 공통 합성 입력과 Fake를 제공한다."""
```
with:
```python
"""실제 LLM 호출 없이 공통 합성 입력과 Fake를 제공한다."""
```

Replace:
```python
class FakeOpenAIConnector:
    """담당 모듈 사이의 계약을 구현하는 테스트 대역."""
```
with:
```python
class FakeLLMConnector:
    """담당 모듈 사이의 계약을 구현하는 테스트 대역."""
```

(The rest of the class body is unchanged — only the class name and the module docstring change here.)

- [ ] **Step 2: Create `app/modules/ai/local_llm_connector.py`**

```python
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
                )
            else:
                response = await self.client.chat(
                    model=self.settings.llm_model,
                    messages=messages,
                    format=AnomalyLLMResult.model_json_schema(),
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
```

- [ ] **Step 3: Delete the old connector**

```bash
git rm app/modules/ai/openai_connector.py
```

- [ ] **Step 4: Run the Task 5 tests to verify they pass**

Run: `pytest tests/unit/test_local_llm_connector.py -v`
Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/modules/ai/local_llm_connector.py tests/conftest.py
git commit -m "feat: implement LocalLLMConnector backed by Ollama, remove OpenAIConnector"
```

---

### Task 7: Cutover — wire the rest of the app to `LocalLLMConnector`

**Files:**
- Modify: `app/api/dependencies.py`
- Modify: `app/modules/detector/anomaly_analysis_service.py:20,80-81`
- Modify: `app/api/routes/anomalies.py:42`
- Modify: `app/modules/ai/__init__.py`
- Modify: `tests/unit/test_anomaly_analysis_service.py`
- Modify: `tests/integration/test_anomaly_api.py`
- Delete: `tests/unit/test_openai_connector.py`

This is the task where everything that still points at `OpenAIConnector`/`FakeOpenAIConnector`/`openai_configured` gets updated together, because they're all interdependent (the integration test imports from `dependencies.py`, which imports the connector module). After this task, the full test suite must be green.

- [ ] **Step 1: Update `app/api/dependencies.py`**

Replace the whole file:
```python
"""세 핵심 클래스를 조립하는 의존성 주입 구성."""

from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.modules.ai.local_llm_connector import LocalLLMConnector
from app.modules.detector.anomaly_analysis_service import AnomalyAnalysisService
from app.modules.getter.water_usage_getter import WaterUsageGetter


def get_water_usage_getter() -> WaterUsageGetter:
    """상태가 없는 Getter를 생성한다."""
    return WaterUsageGetter()


def get_local_llm_connector(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LocalLLMConnector:
    """환경설정을 한 곳에서 주입해 모델명과 서버 주소의 중복을 막는다."""
    return LocalLLMConnector(settings)


def get_anomaly_analysis_service(
    connector: Annotated[LocalLLMConnector, Depends(get_local_llm_connector)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnomalyAnalysisService:
    """테스트가 Connector 의존성을 override할 수 있게 조립한다."""
    return AnomalyAnalysisService(connector, settings)
```

- [ ] **Step 2: Update `app/modules/detector/anomaly_analysis_service.py`**

Replace:
```python
from app.modules.ai.openai_connector import AnalysisConnector
```
with:
```python
from app.modules.ai.local_llm_connector import AnalysisConnector
```

Replace:
```python
        return AnomalyAnalysisResponse(
            **validated.model_dump(exclude={"limitations"}),
            request_id=data.request_id,
            household_id=data.household_id,
            limitations=list(dict.fromkeys(limitations))[:5],
            model_provider="openai",
            model_name=self.settings.openai_model,
            analyzed_at=utc_now(),
        )
```
with:
```python
        return AnomalyAnalysisResponse(
            **validated.model_dump(exclude={"limitations"}),
            request_id=data.request_id,
            household_id=data.household_id,
            limitations=list(dict.fromkeys(limitations))[:5],
            model_provider="ollama",
            model_name=self.settings.llm_model,
            analyzed_at=utc_now(),
        )
```

- [ ] **Step 3: Update `app/api/routes/anomalies.py`**

Replace:
```python
        openai_success=result.model_provider == "openai",
```
with:
```python
        llm_success=result.model_provider == "ollama",
```

- [ ] **Step 4: Update `app/modules/ai/__init__.py`**

Replace:
```python
"""OpenAI 연결 모듈."""
```
with:
```python
"""로컬 LLM 연결 모듈."""
```

- [ ] **Step 5: Update `tests/unit/test_anomaly_analysis_service.py`**

Replace:
```python
from tests.conftest import FakeOpenAIConnector
```
with:
```python
from tests.conftest import FakeLLMConnector
```

Replace all three occurrences of `FakeOpenAIConnector()` with `FakeLLMConnector()` (in `test_offline_skips_gpt` and `test_absence_and_72_hours_payload`).

- [ ] **Step 6: Update `tests/integration/test_anomaly_api.py`**

Replace the whole file:
```python
"""FastAPI 전 구간 통합 테스트."""

from fastapi.testclient import TestClient

from app.api.dependencies import get_local_llm_connector
from app.main import app
from tests.conftest import FakeLLMConnector


def test_health_and_swagger() -> None:
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert "llm_configured" in client.get("/health").json()
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").json()["info"]["title"] == "CareSignal API"


def test_normal_analysis_with_fake(request_factory) -> None:
    app.dependency_overrides[get_local_llm_connector] = lambda: FakeLLMConnector()
    try:
        response = TestClient(app).post(
            "/api/v1/anomalies/analyze", json=request_factory().model_dump(mode="json")
        )
        assert response.status_code == 200
        assert response.json()["status"] == "NORMAL"
    finally:
        app.dependency_overrides.clear()


def test_input_422(request_factory) -> None:
    payload = request_factory().model_dump(mode="json")
    payload["household_id"] = "실명"
    assert TestClient(app).post("/api/v1/anomalies/analyze", json=payload).status_code == 422


def test_offline_without_llm_call(request_factory) -> None:
    payload = request_factory(meter_status="OFFLINE").model_dump(mode="json")
    response = TestClient(app).post("/api/v1/anomalies/analyze", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "DATA_ERROR"
```

- [ ] **Step 7: Delete the old connector test file**

```bash
git rm tests/unit/test_openai_connector.py
```

- [ ] **Step 8: Run the full test suite**

Run: `pytest -v`
Expected: all tests pass, no collection errors.

- [ ] **Step 9: Run the remaining quality gates**

Run: `ruff check .`
Expected: `All checks passed!`

Run: `ruff format --check .`
Expected: no output / exit code 0 (if it reports files needing formatting, run `ruff format .` then re-check).

Run: `mypy app`
Expected: `Success: no issues found in N source files`.

- [ ] **Step 10: Commit**

```bash
git add app/api/dependencies.py app/modules/detector/anomaly_analysis_service.py app/api/routes/anomalies.py app/modules/ai/__init__.py tests/unit/test_anomaly_analysis_service.py tests/integration/test_anomaly_api.py
git commit -m "refactor: wire LocalLLMConnector through dependencies, routes, and tests"
```

---

### Task 8: Update documentation

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `app/modules/ai/README.md`

- [ ] **Step 1: Replace `.env.example`**

```env
APP_ENV=development
LOG_LEVEL=INFO
LLM_MODEL=qwen3:8b
LLM_BASE_URL=http://localhost:11434
LLM_TIMEOUT_SECONDS=180
LLM_MAX_RETRIES=2
MISSING_RATIO_THRESHOLD=0.20
CORS_ORIGINS=
```

- [ ] **Step 2: Replace `app/modules/ai/README.md`**

```markdown
# AI Connector 모듈

담당자는 문범석입니다. `LocalLLMConnector`는 로컬에 설치된 Ollama 서버(`ollama` 공식 Python 클라이언트, `AsyncClient`)를 통해 오픈웨이트 모델(Qwen3 8B)을 호출하고, 스키마 강제 디코딩(`format=AnomalyLLMResult.model_json_schema()`)으로 구조화 출력을 받습니다.

Service와의 계약은 `AnalysisConnector.analyze(system_prompt, user_payload) -> AnomalyLLMResult`입니다. 전달받은 시스템 프롬프트와 JSON payload를 모두 요청에 포함하며 비즈니스 특징은 계산하지 않습니다. 변경 후 `pytest tests/unit/test_local_llm_connector.py`를 실행합니다.
```

- [ ] **Step 3: Update `README.md`**

Replace the owner table row:
```markdown
| 문범석 | `OpenAIConnector` | AsyncOpenAI, Responses API, Structured Outputs, timeout·재시도·오류 변환 | 특징 계산, 비즈니스 프롬프트 작성 | `pytest tests/unit/test_openai_connector.py` |
```
with:
```markdown
| 문범석 | `LocalLLMConnector` | Ollama(로컬 Qwen3 8B), 구조화 출력(JSON Schema), timeout·재시도·오류 변환 | 특징 계산, 비즈니스 프롬프트 작성 | `pytest tests/unit/test_local_llm_connector.py` |
```

Replace the 문범석 개발 계약 block:
```markdown
문범석 개발 계약:

- 공개 인터페이스는 `analyze(system_prompt, user_payload) -> AnomalyLLMResult`입니다.
- Service가 만든 시스템 프롬프트와 사용자 payload를 모두 호출에 붙입니다.
- `responses.parse(..., text_format=AnomalyLLMResult, store=False)`를 유지합니다.
- 인증·잘못된 요청은 재시도하지 않고, 연결·서버 장애만 `OPENAI_MAX_RETRIES` 횟수만큼 재시도합니다.
- 테스트의 `request_callable` 주입 지점을 사용하면 실제 API 호출 없이 작업할 수 있습니다.
```
with:
```markdown
문범석 개발 계약:

- 공개 인터페이스는 `analyze(system_prompt, user_payload) -> AnomalyLLMResult`입니다.
- Service가 만든 시스템 프롬프트와 사용자 payload를 모두 호출에 붙입니다.
- Ollama의 `format=AnomalyLLMResult.model_json_schema()` 스키마 강제 디코딩을 유지합니다.
- 서버 연결 실패에만 `LLM_MAX_RETRIES` 횟수만큼 재시도합니다(인증·요청 한도 개념은 로컬 서버엔 없습니다).
- 테스트의 `request_callable` 주입 지점을 사용하면 실제 Ollama 서버 없이 작업할 수 있습니다.
```

Replace the env block:
```markdown
```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
OPENAI_TIMEOUT_SECONDS=30
OPENAI_MAX_RETRIES=2
OPENAI_STORE=false
```

`OPENAI_STORE` 설정과 무관하게 요청은 개인정보 보호 원칙에 따라 `store=False`입니다.
```
with:
```markdown
```env
LLM_MODEL=qwen3:8b
LLM_BASE_URL=http://localhost:11434
LLM_TIMEOUT_SECONDS=180
LLM_MAX_RETRIES=2
```

로컬 Ollama 서버(`LLM_BASE_URL`)가 실행 중이어야 하며, 모델은 `ollama pull qwen3:8b`로 미리 받아둬야 합니다.
```

Replace the debugging section's connector step and closing paragraph:
```markdown
4. `app/modules/ai/openai_connector.py`의 `analyze`와 `_call_once`
```
with:
```markdown
4. `app/modules/ai/local_llm_connector.py`의 `analyze`와 `_call_once`
```

Replace:
```markdown
실제 Connector까지 추적하려면 `.env`에 `OPENAI_API_KEY`와 `OPENAI_MODEL`을 설정하고 정상 샘플을 호출합니다. 키 없이 전 과정을 재현하려면 `전체 테스트 디버그` 구성으로 `tests/integration/test_anomaly_api.py::test_normal_analysis_with_fake`를 실행합니다. OFFLINE 안전 게이트는 실제 HTTP 호출로도 키 없이 확인할 수 있습니다.
```
with:
```markdown
실제 Connector까지 추적하려면 Ollama 서버를 실행하고 `qwen3:8b` 모델을 받아둔 뒤 정상 샘플을 호출합니다. Ollama 없이 전 과정을 재현하려면 `전체 테스트 디버그` 구성으로 `tests/integration/test_anomaly_api.py::test_normal_analysis_with_fake`를 실행합니다. OFFLINE 안전 게이트는 Ollama 없이도 확인할 수 있습니다.
```

- [ ] **Step 4: Update `CLAUDE.md`**

Replace the `OpenAIConnector` bullet under Architecture:
```markdown
- **`OpenAIConnector`** ([app/modules/ai/openai_connector.py](app/modules/ai/openai_connector.py)) — the only class that talks to `AsyncOpenAI`. Uses `responses.parse(..., text_format=AnomalyLLMResult, store=False)`, never free-text `json.loads`. Public contract is `analyze(system_prompt, user_payload) -> AnomalyLLMResult`, implementing the `AnalysisConnector` Protocol. Does not compute features or write business prompts. Auth/bad-request errors are never retried; only connection/server errors retry up to `OPENAI_MAX_RETRIES` times via `tenacity` (retries are centralized here — the SDK client itself is constructed with `max_retries=0`). A `request_callable` injection point exists for tests to avoid real API calls.
```
with:
```markdown
- **`LocalLLMConnector`** ([app/modules/ai/local_llm_connector.py](app/modules/ai/local_llm_connector.py)) — the only class that talks to Ollama (a locally-installed server hosting Qwen3 8B, an open-weight model — required by the competition's 제9조, see below). Uses `ollama.AsyncClient.chat(..., format=AnomalyLLMResult.model_json_schema())` for schema-constrained decoding, never free-text `json.loads`. Public contract is `analyze(system_prompt, user_payload) -> AnomalyLLMResult`, implementing the `AnalysisConnector` Protocol. Does not compute features or write business prompts. Only connection failures (Ollama server not running) are retried, up to `LLM_MAX_RETRIES` times via `tenacity`. A `request_callable` injection point exists for tests to avoid needing a real Ollama server.
```

Replace the owner table row:
```markdown
| 문범석 | `OpenAIConnector` | AsyncOpenAI, Responses API, structured outputs, timeout/retry/error translation | feature calc, business prompt authoring |
```
with:
```markdown
| 문범석 | `LocalLLMConnector` | Ollama client, structured outputs, timeout/retry/error translation | feature calc, business prompt authoring |
```

Replace the single-module test command:
```markdown
pytest tests/unit/test_openai_connector.py
```
with:
```markdown
pytest tests/unit/test_local_llm_connector.py
```

Replace the Configuration section's closing sentence:
```markdown
Never read `os.environ` directly elsewhere — inject `Settings` through FastAPI `Depends`. `settings.openai_configured` exposes only whether a key is present, never the key itself.
```
with:
```markdown
Never read `os.environ` directly elsewhere — inject `Settings` through FastAPI `Depends`. `settings.llm_configured` exposes only whether an LLM model name is set.
```

Add a new subsection right after "Project" (before "Do not input real personal data..."):
```markdown
## Competition constraint

CareSignal is submitted to the 2026 오픈소스 개발자대회 (osscontest.kr). 운영규정 제9조 requires every AI model embedded in the submission to be open-weight and independently operable (runnable on a local/self-hosted server) — hosted-API-only models like OpenAI's GPT are not allowed for the submission's core functionality. This is why the anomaly-judgment LLM is `LocalLLMConnector` (Ollama + Qwen3, Apache 2.0) rather than an OpenAI connector. Don't reintroduce a hosted-commercial-API-only model as the core connector without checking this constraint first. Submission deadline: 2026-08-27 18:00 KST.
```

- [ ] **Step 5: Commit**

```bash
git add .env.example README.md CLAUDE.md app/modules/ai/README.md
git commit -m "docs: update docs for LocalLLMConnector"
```

---

### Task 9: Final quality gate

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest`
Expected: all tests pass.

- [ ] **Step 2: Run lint**

Run: `ruff check .`
Expected: `All checks passed!`

- [ ] **Step 3: Run format check**

Run: `ruff format --check .`
Expected: no output, exit code 0.

- [ ] **Step 4: Run type check**

Run: `mypy app`
Expected: `Success: no issues found in N source files`.

- [ ] **Step 5: Confirm no leftover references**

Run: `grep -rni "openai" --include="*.py" --include="*.md" --include="*.env*" . | grep -v ".venv"`
Expected: no output (or only incidental matches you've reviewed and are fine with, e.g. historical git log text — there should be none in tracked source/docs files).

If Step 5 finds anything, fix it and re-run Steps 1–4, then commit the fix.

---

## Manual post-implementation step (not part of this plan's automated tasks)

The plan above never requires a running Ollama server or a downloaded model — everything is verified through `request_callable` injection. Before actually using the feature end-to-end, a human needs to:

1. Confirm the Ollama server is running (it was installed via `winget install Ollama.Ollama`; it typically starts automatically as a background service — check with `ollama list` in a terminal).
2. Pull the model: `ollama pull qwen3:8b` (~5GB download — this needs explicit user confirmation before running, same as the earlier Ollama app install).
3. Run the server and do one real end-to-end smoke test:
   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```
   In another terminal:
   ```bash
   curl -X POST "http://127.0.0.1:8000/api/v1/anomalies/analyze" -H "Content-Type: application/json" --data-binary "@samples/normal_request.json"
   ```
   Expect a `200` response with `"model_provider": "ollama"`. On CPU this may take tens of seconds — that's expected (see [design doc risks](../specs/2026-08-01-local-llm-connector-design.md#리스크-및-열린-질문)).

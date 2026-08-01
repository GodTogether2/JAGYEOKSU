# LocalLLMConnector 설계 (OpenAIConnector → 로컬 오픈웨이트 모델 전환)

## 배경

CareSignal API는 2026 오픈소스 개발자대회(osscontest.kr) 출품작이다. 대회 운영규정 제9조(AI 모델 활용의 기준)는 출품작에 탑재·적용되는 모든 AI 모델이 최소 오픈웨이트 이상으로 공개되고, 로컬/자체 서버 환경에서 직접 구동 가능("독립 구동 가능성")해야 한다고 규정한다(https://osscontest.kr/notice/36). 상용 API 호출로만 동작하는 모델(OpenAI GPT 등)은 이 요건을 충족하지 못해 출품작에 사용할 수 없다. 예외는 (a) MCP/AI 에이전트 프레임워크 자체를 개발하는 경우의 연동 테스트, (b) 개발 중 코드 작성·디버깅 보조용 상용 AI 사용 — 둘 다 CareSignal의 핵심 기능(이상징후 판단)에는 해당하지 않는다.

현재 `OpenAIConnector`([app/modules/ai/openai_connector.py](../../../app/modules/ai/openai_connector.py))는 `AsyncOpenAI.responses.parse()`로 OpenAI 호스팅 API를 직접 호출하고 있어 규정 위반 상태다. 이를 로컬에서 구동 가능한 오픈웨이트 모델로 교체한다.

제출 마감: 2026-08-27(목) 18:00.

## 목표

- `AnalysisConnector` 프로토콜(`analyze(system_prompt, user_payload) -> AnomalyLLMResult`)을 만족하는 로컬 LLM 기반 Connector 구현
- 오픈웨이트 + Apache 2.0 라이선스 모델(Qwen3 8B) 사용, 대회 규정 충족
- CPU 전용 환경에서 동작 (팀 하드웨어 제약)
- `Getter`/`Service` 모듈은 변경 없음 — 프로토콜 경계만 유지하면 됨

## 비목표

- OpenAI API를 다시 쓸 수 있는 provider 스위치/추상화 계층은 만들지 않는다 (YAGNI, CLAUDE.md 방침: 백워드 호환 훅 지양)
- GPU 가속, vLLM/프로덕션급 서빙 스택은 다루지 않는다 (현재 하드웨어가 CPU 전용)
- summary/message/limitations를 규칙 기반 템플릿으로 대체하는 방안은 이번 스코프에서 제외 (LLM 기반 유지로 확정)

## 모델 및 서빙 스택

| 항목 | 선택 | 이유 |
|---|---|---|
| 모델 | Qwen3 8B | Apache 2.0(라이선스 리스크 없음), 구조화 출력 툴링 성숙, 한국어 처리 가능한 수준 |
| 서빙 | Ollama | Windows/CPU 환경에서 설치·운용이 가장 간단, 구조화 출력(`format` + JSON Schema, grammar-constrained decoding)을 네이티브로 지원 |
| 클라이언트 | 공식 `ollama` Python 패키지 (`AsyncClient`) | OpenAI 호환 레이어(`/v1/chat/completions`)의 `json_schema` 처리가 모델별로 불안정하다는 이슈가 보고돼 있어 배제. 네이티브 API가 이 프로젝트의 핵심 안전장치(`AnomalyLLMResult` 스키마 강제)에 더 적합 |

Ollama 서버는 PC에 별도 설치되는 프로그램(`winget install Ollama.Ollama`)이고, `ollama` pip 패키지는 그 서버(`localhost:11434`)에 요청을 보내는 클라이언트일 뿐이다. 서버가 실행 중이지 않으면 클라이언트 연결이 실패하며, 이는 재시도 대상 오류로 처리한다.

## 아키텍처

```
AnomalyAnalysisService
   │  analyze(system_prompt, user_payload)
   ▼
LocalLLMConnector (AnalysisConnector 구현체)
   │  ollama.AsyncClient.chat(model, messages, format=AnomalyLLMResult.model_json_schema())
   ▼
Ollama 서버 (localhost:11434) ── Qwen3 8B 모델 구동
   │  response.message.content (JSON 문자열)
   ▼
AnomalyLLMResult.model_validate_json(...)
```

`AnalysisConnector` 프로토콜 자체는 변경하지 않는다. Service는 여전히 `self.connector.analyze(system_prompt, payload)` 한 줄만 알면 된다.

### `LocalLLMConnector` 핵심 로직

```python
class LocalLLMConnector:
    def __init__(
        self,
        settings: Settings,
        client: ollama.AsyncClient | None = None,
        request_callable: Callable[..., Awaitable[object]] | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or ollama.AsyncClient(host=settings.llm_base_url)
        self._request_callable = request_callable

    async def analyze(self, system_prompt, user_payload) -> AnomalyLLMResult:
        # 연결 실패에만 tenacity 재시도 (settings.llm_max_retries)
        # 그 외 예외는 예외 타입별로 즉시 변환 후 raise
        ...

    async def _call_once(self, system_prompt, user_payload) -> AnomalyLLMResult:
        response = await (self._request_callable or self.client.chat)(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, default=str)},
            ],
            format=AnomalyLLMResult.model_json_schema(),
        )
        content = response.message.content  # 혹은 request_callable이 반환하는 동등 구조
        return AnomalyLLMResult.model_validate_json(content)
```

기존 `OpenAIConnector`와 동일하게 `request_callable` 주입 지점을 유지해 테스트에서 실제 Ollama 서버 없이도 검증 가능하게 한다(CI 환경엔 Ollama가 없을 것이므로 기존 "실제 API 호출 금지" 규칙을 그대로 적용).

## 설정 변경 (`app/core/config.py`)

| 기존 | 변경 후 | 비고 |
|---|---|---|
| `openai_api_key` | 삭제 | 로컬 서버는 API 키 불필요 |
| `openai_configured` (property) | 삭제 | 위와 동일한 이유 |
| `openai_store` | 삭제 | OpenAI Responses API 전용 옵션, 대응 개념 없음 |
| `openai_model` (기본 `gpt-4.1-mini`) | `llm_model` (기본 `qwen3:8b`) | |
| `openai_timeout_seconds` (기본 30) | `llm_timeout_seconds` (기본 **180**) | CPU 추론 시간 고려해 상향 |
| `openai_max_retries` (기본 2) | `llm_max_retries` (기본 2, 그대로) | |
| (없음) | `llm_base_url` (기본 `http://localhost:11434`) | Ollama 서버 주소 |

`.env.example`도 `OPENAI_*` → `LLM_*`로 갱신.

## 예외 체계 변경 (`app/core/exceptions.py`, `app/core/exception_handlers.py`)

| 기존 | 변경 후 | 비고 |
|---|---|---|
| `OpenAIAuthError` | 삭제 | 로컬 서버는 인증 개념 없음 |
| `OpenAIRateLimitError` | 삭제 | 단일 로컬 서버는 요청 한도 개념 없음 |
| `OpenAIBadRequestError` | 삭제 | 스키마가 코드로 고정되어 있어 발생 시나리오 없음 |
| `OpenAIServiceError` | `LLMServiceError` | 이름만 변경, 재시도 실패 시 최종 예외 |
| `OpenAITimeoutError` | `LLMTimeoutError` | 이름만 변경 |
| (없음) | `LLMConnectionError` | Ollama 서버 미실행/모델 미다운로드 — 재시도 대상 |
| `InvalidLLMResponseError` | 그대로 유지 | 이미 이름이 범용적 |

`exception_handlers.py`의 핸들러 등록도 위 표에 맞춰 정리 (Auth/RateLimit 전용 핸들러 제거, `LLMConnectionError` → 502 매핑 추가).

## 파일 변경 범위

- `pyproject.toml`: `openai` 의존성 제거, `ollama` 추가
- `app/modules/ai/openai_connector.py` → `app/modules/ai/local_llm_connector.py` (클래스명 `LocalLLMConnector`)
- `app/api/dependencies.py`: `get_openai_connector` → `get_local_llm_connector`
- `tests/unit/test_openai_connector.py` → `tests/unit/test_local_llm_connector.py`
- `tests/conftest.py`: `FakeOpenAIConnector` → `FakeLLMConnector` (다른 테스트 파일의 import도 동일 변경)
- `.env.example`, `README.md`, `CLAUDE.md`: 담당자 표의 "OpenAIConnector" 표기, 환경변수 목록 갱신
- `app/modules/ai/README.md`: 모듈 설명 갱신

## 테스트 전략

기존 `test_openai_connector.py` 구조를 그대로 계승한다 (구조화 응답 성공 케이스, 오류 매핑별 케이스, 잘못된 구조화 출력 케이스, 재시도 횟수 케이스). `request_callable`로 실제 Ollama 서버 호출 없이 전부 검증한다. 오류 매핑 케이스는 `OpenAIAuthError`/`RateLimitError` 대신 `LLMConnectionError`(연결 거부) 시나리오로 대체한다.

## 리스크 및 열린 질문

- CPU 추론 속도: 8B 모델 기준 요청당 수십 초가 걸릴 수 있음. 타임아웃 기본값을 180초로 넉넉히 잡았으나, 실제 하드웨어에서 측정 후 조정 필요.
- Qwen3의 구조화 출력이 `AnomalyLLMResult`의 모든 필드 제약(길이, enum, 금지어 등)을 항상 만족하는지는 실제 연동 테스트로 검증 필요 — `AnomalyLLMResult.model_validate()`가 이미 이 안전망 역할을 하므로 실패 시 `InvalidLLMResponseError`로 처리됨.

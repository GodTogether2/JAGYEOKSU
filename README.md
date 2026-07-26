# CareSignal API

CareSignal API는 합성·시뮬레이션 수도 사용량을 가구별 과거 패턴과 비교하고, 복지 담당자의 전화 확인 또는 수동 검토 우선순위를 보조하는 오픈소스 FastAPI 프로젝트입니다. 고독사 여부, 사망 확률, 생존 여부, 질병 또는 응급상황을 예측하거나 진단하지 않습니다.

실제 개인정보는 입력하지 마세요. 이름, 주소, 전화번호, 주민등록번호는 스키마가 거부하며 `household_id`에는 영문·숫자·하이픈·밑줄로 된 익명 식별자만 허용합니다.

## 담당자와 모듈별 개발 가이드

세 모듈은 고정된 Pydantic 구조와 `AnalysisConnector` 프로토콜로 분리되어 각 담당자가 독립 개발할 수 있습니다.

| 담당 | 모듈 | 책임 | 하지 않는 일 | 단독 테스트 |
|---|---|---|---|---|
| 홍성표 | `WaterUsageGetter` | API 입력 검증, 정렬, `NormalizedWaterUsage` 생성 | 특징 계산, 프롬프트, AI 호출 | `pytest tests/unit/test_water_usage_getter.py` |
| 문범석 | `OpenAIConnector` | AsyncOpenAI, Responses API, Structured Outputs, timeout·재시도·오류 변환 | 특징 계산, 비즈니스 프롬프트 작성 | `pytest tests/unit/test_openai_connector.py` |
| 최지욱 | `AnomalyAnalysisService` | 특징 계산, payload·프롬프트 로드, 안전 게이트, 최종 응답 조립 | SDK 초기화, HTTP 라우팅 | `pytest tests/unit/test_anomaly_analysis_service.py` |

문범석 개발 계약:

- 공개 인터페이스는 `analyze(system_prompt, user_payload) -> AnomalyLLMResult`입니다.
- Service가 만든 시스템 프롬프트와 사용자 payload를 모두 호출에 붙입니다.
- `responses.parse(..., text_format=AnomalyLLMResult, store=False)`를 유지합니다.
- 인증·잘못된 요청은 재시도하지 않고, 연결·서버 장애만 `OPENAI_MAX_RETRIES` 횟수만큼 재시도합니다.
- 테스트의 `request_callable` 주입 지점을 사용하면 실제 API 호출 없이 작업할 수 있습니다.

최지욱 개발 계약:

- 입력은 오직 `NormalizedWaterUsage`, AI 의존성은 `AnalysisConnector` 프로토콜입니다.
- `tests.conftest.FakeOpenAIConnector`를 주입하면 문범석 모듈 없이 기능을 개발할 수 있습니다.
- 프롬프트는 `app/prompts/anomaly_system_prompt.txt`에서 읽으며 코드에 긴 문자열을 넣지 않습니다.
- 최근 72시간만 AI에 전달하고 OFFLINE·누락률 초과는 AI 호출 전에 처리합니다.
- 예정된 부재와 30일 미만 기준선 한계를 최종 `limitations`에 보존합니다.

공동 변경 규칙:

- 스키마 계약 변경은 `app/schemas/`와 양쪽 테스트를 같은 PR에서 수정합니다.
- 원본 시계열, 전체 프롬프트·응답, API 키를 로그에 추가하지 않습니다.
- 각 담당자는 위 단독 테스트와 `ruff check .`, `mypy app`을 통과시킨 뒤 통합합니다.

## 요청 흐름

`FastAPI Router → WaterUsageGetter → AnomalyAnalysisService → OpenAIConnector → AnomalyAnalysisService → AnomalyAnalysisResponse`

라우터는 의존성 연결만 담당합니다. Getter는 API 입력을 내부 구조체로 정규화하고, Service는 Python에서 특징값을 계산합니다. Connector는 비동기 Structured Outputs 호출만 담당합니다.

## 프로젝트 구조

```text
app/api          라우터와 의존성 주입
app/core         환경설정, 예외, 구조화 로그
app/schemas      외부·내부·LLM Pydantic v2 구조
app/modules      Getter, Connector, Service
app/prompts      한국어 안전 시스템 프롬프트
app/utils        날짜 및 특징 계산
tests            실제 OpenAI를 쓰지 않는 단위·통합 테스트
scripts          합성 샘플 생성기
samples          생성된 요청과 호출 클라이언트
docs             설계·흐름·한계 문서
```

## 설치

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

`.env.example`을 `.env`로 복사하고 필요한 환경변수를 설정합니다. 키가 없어도 서버, `/health`, OFFLINE 로컬 분석과 테스트가 동작합니다.

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
OPENAI_TIMEOUT_SECONDS=30
OPENAI_MAX_RETRIES=2
OPENAI_STORE=false
```

`OPENAI_STORE` 설정과 무관하게 요청은 개인정보 보호 원칙에 따라 `store=False`입니다.

## 실행과 API 호출

```bash
python scripts/generate_sample_data.py
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger는 http://127.0.0.1:8000/docs 에서 확인합니다.

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/anomalies/analyze" \
  -H "Content-Type: application/json" \
  --data-binary "@samples/no_usage_request.json"
```

Python 클라이언트는 `python samples/call_api.py`로 실행합니다.

## 로컬 전 과정 디버깅

VS Code에서 프로젝트 루트를 열고 Python 및 Ruff 확장을 설치한 뒤 `.vscode/launch.json`의 `CareSignal API 서버`를 실행합니다. 다음 위치에 순서대로 중단점을 두면 요청 전체를 추적할 수 있습니다.

1. `app/api/routes/anomalies.py`의 `analyze_anomaly`
2. `app/modules/getter/water_usage_getter.py`의 `normalize`
3. `app/modules/detector/anomaly_analysis_service.py`의 `analyze`와 `build_user_payload`
4. `app/modules/ai/openai_connector.py`의 `analyze`와 `_call_once`
5. 다시 Service의 최종 `AnomalyAnalysisResponse` 생성부

실제 Connector까지 추적하려면 `.env`에 `OPENAI_API_KEY`와 `OPENAI_MODEL`을 설정하고 정상 샘플을 호출합니다. 키 없이 전 과정을 재현하려면 `전체 테스트 디버그` 구성으로 `tests/integration/test_anomaly_api.py::test_normal_analysis_with_fake`를 실행합니다. OFFLINE 안전 게이트는 실제 HTTP 호출로도 키 없이 확인할 수 있습니다.

## 품질 검사

```bash
pytest
ruff check .
ruff format --check .
mypy app
```

모든 테스트는 Fake 또는 주입된 callable을 사용해 실제 OpenAI API를 호출하지 않습니다.

## Docker

```bash
cp .env.example .env
docker compose up --build
```

컨테이너는 비루트 사용자로 실행되고 기본 CORS는 꺼져 있습니다. 개발환경에서만 `CORS_ORIGINS`를 명시할 수 있습니다.

## 개인정보와 알려진 한계

- 실제 개인 데이터가 아닌 합성 데이터를 기본 대상으로 합니다.
- 수도 사용량만으로 사람의 건강·안전 상태를 판단할 수 없습니다.
- 외출, 입원, 계량기 장애처럼 등록되지 않은 맥락이 있을 수 있습니다.
- 30일 미만 데이터는 장기 기준선이 부족하다고 표시합니다.
- 결과는 자동 집행 근거가 아니라 전화 확인·수동 검토를 위한 참고정보입니다.
- 높은 누락률은 생활 이상보다 데이터 품질 오류로 우선 처리합니다.

## 라이선스

Apache License 2.0. 자세한 내용은 `LICENSE`를 확인하세요.

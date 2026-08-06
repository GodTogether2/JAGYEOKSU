# CareSignal API

CareSignal API는 합성 수도 사용량을 기반으로 복지 담당자의 전화 확인 또는 수동 검토 우선순위를 보조하는 FastAPI 프로젝트입니다. 고독사 여부, 사망 확률, 생존 여부, 질병 또는 응급상황을 예측하거나 진단하지 않습니다.

실제 개인정보는 입력하지 마세요. 이름, 주소, 전화번호, 주민등록번호는 스키마가 거부하며 `household_id`에는 영문·숫자·하이픈·밑줄로 된 익명 식별자만 허용합니다.

## 기능별 계약

세 기능의 경계는 입력 정규화, AI 분석, 결과 전달로 나뉩니다.

| 기능 | 모듈 | 책임 | 하지 않는 일 | 단독 테스트 |
|---|---|---|---|---|
| 입력 정규화 | `WaterUsageGetter` | API 요청 검증, 정렬, `NormalizedWaterUsage` 생성 | 특징 계산, AI 호출, 결과 전달 | `pytest tests/unit/test_water_usage_getter.py` |
| AI 분석 | `LocalLLMConnector` | 로컬 Ollama 서버(Kanana 1.5 8B) 호출, 구조화 출력(JSON Schema) 강제, timeout·재시도·오류 변환 | 특징 계산, 비즈니스 프롬프트 작성, 외부 결과 엔드포인트로 전달 | `pytest tests/unit/test_local_llm_connector.py` |
| 결과 전달 | `AnomalyAnalysisService` | 특징 계산, 안전 게이트, 최종 응답 조립, AI 분석 결과를 원 요청 포맷에 `analysis_result` 키로 추가해 다른 엔드포인트로 POST | SDK 초기화, HTTP 라우팅, 입력 정규화 | `pytest tests/unit/test_anomaly_analysis_service.py` |

결과 전달 기능의 핵심 출력 포맷은 다음처럼 **초기 요청 포맷 + 키-밸류 하나**입니다.

```json
{
  "request_id": "req-test-001",
  "household_id": "demo_house-001",
  "meter_status": "ONLINE",
  "expected_absence": false,
  "measurements": [
    {
      "timestamp": "2026-07-19T01:00:00Z",
      "usage_liter": 1.0
    }
  ],
  "analysis_result": {
    "status": "NORMAL",
    "anomaly_score": 10,
    "confidence": 0.8,
    "summary": "평소 수도 사용 패턴과 유사합니다.",
    "evidence": [],
    "recommended_action": "NONE",
    "limitations": []
  }
}
```

## 요청 흐름

```text
FastAPI Router
→ WaterUsageGetter.normalize()
→ AnomalyAnalysisService.analyze()
→ LocalLLMConnector.analyze()
→ AnomalyAnalysisService.forward_analysis_result()
→ RESULT_FORWARD_ENDPOINT_URL
→ AnomalyAnalysisResponse
```

라우터는 의존성 연결만 담당합니다. Getter는 입력을 내부 구조체로 정규화합니다. Connector는 로컬 Ollama 호출만 담당합니다. Service는 특징값을 계산하고 AI 분석 결과를 받은 뒤, 원 요청 형태를 재구성해 `analysis_result`만 추가해 외부 엔드포인트로 전송합니다.

`RESULT_FORWARD_ENDPOINT_URL`이 비어 있으면 로컬 개발과 테스트를 위해 외부 전송을 생략합니다.

Downstream 수신 endpoint를 개발하는 쪽은 [Downstream 전달 payload 수신 개발 가이드](docs/downstream-forwarding-usage.md)만 보면 됩니다.

## 프로젝트 구조

```text
app/api          라우터와 의존성 주입
app/core         환경설정, 예외, 구조화 로그
app/schemas      외부·내부·LLM Pydantic v2 구조
app/modules      Getter, Connector, Service
app/prompts      한국어 안전 시스템 프롬프트
app/utils        날짜 및 특징 계산
tests            실제 Ollama 서버와 외부 결과 endpoint를 쓰지 않는 단위·통합 테스트
scripts          합성 샘플 생성기
samples          생성된 요청과 호출 클라이언트
docs             설계·흐름·한계 문서
```

## 환경변수

```env
LLM_MODEL=coolsoon/kanana-1.5-8b
LLM_BASE_URL=http://localhost:11434
LLM_TIMEOUT_SECONDS=420
LLM_MAX_RETRIES=2
RESULT_FORWARD_ENDPOINT_URL=
RESULT_FORWARD_TIMEOUT_SECONDS=10
MISSING_RATIO_THRESHOLD=0.20
CORS_ORIGINS=
```

`RESULT_FORWARD_ENDPOINT_URL`이 비어 있으면 결과 전달을 생략합니다.

## 설치

bash가 있는 환경(macOS/Linux, Windows Git Bash 등)이라면 아래 스크립트로 venv 생성부터 `.env` 설정, Ollama·LLM 모델 자동 설치, 샘플 데이터 생성까지 한 번에 끝낼 수 있습니다. 이미 되어 있는 단계는 건너뜁니다.

```bash
bash scripts/setup.sh
```

완료 후 서버는 아래로 실행합니다(이후에는 이 명령만 실행하면 됩니다).

```bash
bash scripts/run_server.sh
```

각 단계를 직접 실행하고 싶다면 아래를 그대로 따라 해도 됩니다.

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

`.env.example`을 `.env`로 복사하고 필요한 환경변수를 설정합니다. 아래 스크립트를 실행하면 Ollama가 없을 때 자동으로 설치하고(Windows: winget, macOS/Linux: 공식 설치 스크립트), `LLM_MODEL`에 설정된 모델(기본 `coolsoon/kanana-1.5-8b`)을 없으면 자동으로 받아옵니다. 이미 설치·다운로드돼 있으면 건너뜁니다.

```bash
python scripts/setup_local_llm.py
```

CPU 환경에서는 요청당 4~6분 정도 걸릴 수 있어 `LLM_TIMEOUT_SECONDS`를 넉넉히(기본 420초) 잡았습니다. `RESULT_FORWARD_ENDPOINT_URL`이 없어도 서버, `/health`, OFFLINE 로컬 분석과 테스트는 동작합니다.

## 실행과 API 호출

`bash scripts/setup.sh`로 설치했다면 `bash scripts/run_server.sh`만 실행하면 됩니다. 직접 실행하려면:

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

## Docker

```bash
cp .env.example .env
docker compose up --build
```

`ollama` 서비스가 뜨고, `model-init` 서비스가 `LLM_MODEL`에 설정된 모델을 자동으로 pull한 뒤 종료되면 그때 `api` 서비스가 시작됩니다. 최초 실행 시 모델 다운로드 때문에 몇 분 걸릴 수 있습니다. 모델은 `ollama_data` 볼륨에 저장되므로 `docker compose down` 후 다시 올려도 재다운로드하지 않습니다(볼륨을 지우지 않는 한).

## 로컬 디버깅 순서

1. `app/api/routes/anomalies.py`의 `analyze_anomaly`
2. `app/modules/getter/water_usage_getter.py`의 `normalize`
3. `app/modules/detector/anomaly_analysis_service.py`의 `analyze`와 `build_user_payload`
4. `app/modules/ai/local_llm_connector.py`의 `analyze`와 `_call_once`
5. `app/modules/detector/anomaly_analysis_service.py`의 `forward_analysis_result`

실제 Connector까지 추적하려면 Ollama 서버를 실행하고 `coolsoon/kanana-1.5-8b` 모델을 받아둔 뒤 정상 샘플을 호출합니다. Ollama와 외부 endpoint 없이 전 과정을 재현하려면 `전체 테스트 디버그` 구성으로 `tests/integration/test_anomaly_api.py::test_normal_analysis_with_fake`를 실행하거나, `forward_callable` 테스트 대역을 주입합니다. OFFLINE 안전 게이트는 Ollama 없이도 확인할 수 있습니다.

## 품질 검사

```bash
pytest
ruff check .
ruff format --check .
mypy app
```

모든 테스트는 Fake 또는 주입된 callable을 사용해 실제 Ollama 서버와 외부 결과 endpoint를 호출하지 않습니다.

## 개인정보와 한계

- 실제 개인 데이터가 아닌 합성 데이터를 기본 대상으로 합니다.
- 수도 사용량만으로 사람의 건강·안전 상태를 판단할 수 없습니다.
- 외출, 입원, 계량기 장애처럼 등록되지 않은 맥락이 있을 수 있습니다.
- 30일 미만 데이터는 장기 기준선이 부족하다고 표시합니다.
- 결과는 자동 집행 근거가 아니라 전화 확인·수동 검토를 위한 참고정보입니다.
- 높은 누락률은 생활 이상보다 데이터 품질 오류로 우선 처리합니다.

## 라이선스

Apache License 2.0. 자세한 내용은 `LICENSE`를 확인하세요.

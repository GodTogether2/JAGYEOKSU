# CareSignal API

CareSignal API는 합성 수도 사용량을 기반으로 복지 담당자의 전화 확인 또는 수동 검토 우선순위를 보조하는 FastAPI 프로젝트입니다. 고독사 여부, 사망 확률, 생존 여부, 질병 또는 응급상황을 예측하거나 진단하지 않습니다.

실제 개인정보는 입력하지 마세요. 이름, 주소, 전화번호, 주민등록번호는 스키마가 거부하며 `household_id`에는 영문·숫자·하이픈·밑줄로 된 익명 식별자만 허용합니다.

## 담당자와 실제 계약

세 담당자의 경계는 입력 정규화, AI 분석, 결과 전달로 나뉩니다.

| 담당 | 모듈 | 책임 | 하지 않는 일 | 단독 테스트 |
|---|---|---|---|---|
| 홍성표 | `WaterUsageGetter` | API 요청 검증, 정렬, `NormalizedWaterUsage` 생성 | AI 호출, 결과 전달 | `pytest tests/unit/test_water_usage_getter.py` |
| 문범석 | `OpenAIConnector` | 시스템 프롬프트와 사용자 payload를 받아 `AnomalyLLMResult` 반환 | 외부 결과 엔드포인트로 전달 | `pytest tests/unit/test_openai_connector.py` |
| 최지욱 | `AnomalyAnalysisService` | 문범석 결과를 원 요청 포맷에 `analysis_result` 키로 추가해 다른 엔드포인트로 POST | SDK 초기화, HTTP 라우팅, 입력 정규화 | `pytest tests/unit/test_anomaly_analysis_service.py` |

최지욱 파트의 핵심 출력 포맷은 다음처럼 **홍성표가 처음 받는 요청 포맷 + 키-밸류 하나**입니다.

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
→ OpenAIConnector.analyze()
→ AnomalyAnalysisService.forward_analysis_result()
→ RESULT_FORWARD_ENDPOINT_URL
→ AnomalyAnalysisResponse
```

라우터는 의존성 연결만 담당합니다. Getter는 입력을 내부 구조체로 정규화합니다. Connector는 OpenAI 호출만 담당합니다. Service는 문범석 결과를 받은 뒤 원 요청 형태를 재구성하고 `analysis_result`만 추가해 외부 엔드포인트로 전송합니다.

`RESULT_FORWARD_ENDPOINT_URL`이 비어 있으면 로컬 개발과 테스트를 위해 외부 전송을 생략합니다.

## 환경변수

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
OPENAI_TIMEOUT_SECONDS=30
OPENAI_MAX_RETRIES=2
OPENAI_STORE=false
RESULT_FORWARD_ENDPOINT_URL=
RESULT_FORWARD_TIMEOUT_SECONDS=10
MISSING_RATIO_THRESHOLD=0.20
CORS_ORIGINS=
```

`OPENAI_STORE` 설정과 무관하게 OpenAI 요청은 개인정보 보호 원칙에 따라 `store=False`입니다.

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

## 로컬 디버깅 순서

1. `app/api/routes/anomalies.py`의 `analyze_anomaly`
2. `app/modules/getter/water_usage_getter.py`의 `normalize`
3. `app/modules/detector/anomaly_analysis_service.py`의 `analyze`
4. `app/modules/ai/openai_connector.py`의 `analyze`
5. `app/modules/detector/anomaly_analysis_service.py`의 `forward_analysis_result`

문범석 모듈 없이 최지욱 파트를 개발할 때는 `tests.conftest.FakeOpenAIConnector`를 주입합니다. 외부 endpoint 호출 없이 검증할 때는 `forward_callable` 테스트 대역을 주입합니다.

## 품질 검사

```bash
pytest
ruff check .
ruff format --check .
mypy app
```

모든 테스트는 Fake 또는 주입된 callable을 사용해 실제 OpenAI API와 외부 결과 endpoint를 호출하지 않습니다.

## 개인정보와 한계

- 실제 개인 데이터가 아닌 합성 데이터를 기본 대상으로 합니다.
- 수도 사용량만으로 사람의 건강·안전 상태를 판단할 수 없습니다.
- 외출, 입원, 계량기 장애처럼 등록되지 않은 맥락이 있을 수 있습니다.
- 30일 미만 데이터는 장기 기준선이 부족하다고 표시합니다.
- 결과는 자동 집행 근거가 아니라 전화 확인·수동 검토를 위한 참고정보입니다.
- 높은 누락률은 생활 이상보다 데이터 품질 오류로 우선 처리합니다.

## 라이선스

Apache License 2.0. 자세한 내용은 `LICENSE`를 확인하세요.

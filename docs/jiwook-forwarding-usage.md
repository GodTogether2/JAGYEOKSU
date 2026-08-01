# 최지욱 파트 사용법

최지욱 파트는 문범석 `OpenAIConnector`가 만든 `AnomalyLLMResult`를 받아서, 홍성표가 처음 받는 요청 JSON에 `analysis_result` 키 하나를 추가한 뒤 다른 endpoint로 POST한다.

## 받는 사람이 받는 포맷

```json
{
  "request_id": "req-normal-001",
  "household_id": "demo-normal-001",
  "meter_status": "ONLINE",
  "expected_absence": false,
  "measurements": [
    {
      "timestamp": "2026-07-19T01:00:00+00:00",
      "usage_liter": 0.15
    }
  ],
  "analysis_result": {
    "status": "NORMAL",
    "anomaly_score": 12,
    "confidence": 0.86,
    "summary": "평소 수도 사용 패턴과 유사합니다.",
    "evidence": [],
    "recommended_action": "NONE",
    "limitations": []
  }
}
```

기존 요청 필드는 그대로 유지한다. 추가 필드는 `analysis_result` 하나다.

## 환경변수 설정

`.env`에 downstream endpoint를 넣는다.

```env
RESULT_FORWARD_ENDPOINT_URL=https://example.com/receive-analysis
RESULT_FORWARD_TIMEOUT_SECONDS=10
```

`RESULT_FORWARD_ENDPOINT_URL`이 비어 있으면 POST하지 않는다. 로컬 테스트와 CI에서는 이 값이 비어 있어도 된다.

## 서버 실행

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

분석 요청을 넣으면 내부 흐름은 다음 순서로 돈다.

```text
POST /api/v1/anomalies/analyze
→ WaterUsageGetter.normalize()
→ OpenAIConnector.analyze()
→ AnomalyAnalysisService.forward_analysis_result()
→ RESULT_FORWARD_ENDPOINT_URL
```

## 더미 payload로 받는 쪽 테스트

받는 사람이 자기 endpoint를 열어둔 뒤 아래처럼 바로 테스트하면 된다.

```bash
curl -X POST "https://example.com/receive-analysis" \
  -H "Content-Type: application/json" \
  --data-binary "@samples/forward_normal_payload.json"
```

케이스별 샘플:

- `samples/forward_normal_payload.json`
- `samples/forward_observe_payload.json`
- `samples/forward_check_required_payload.json`
- `samples/forward_data_error_payload.json`

샘플을 다시 만들 때:

```bash
python scripts/generate_sample_data.py
```

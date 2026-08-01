# Detector 모듈

`AnomalyAnalysisService`는 AI Connector가 반환한 `AnomalyLLMResult`를 받아, 최초 요청인 `WaterUsageAnalysisRequest` 포맷에 `analysis_result` 키 하나를 추가한 뒤 `RESULT_FORWARD_ENDPOINT_URL`로 POST합니다.

결과 전달 기능에서 유지해야 하는 계약:

- 외부 전송 payload는 기존 요청 필드 `request_id`, `household_id`, `meter_status`, `expected_absence`, `measurements`를 그대로 유지합니다.
- 추가 필드는 `analysis_result` 하나입니다.
- `analysis_result` 값은 AI Connector가 반환한 `AnomalyLLMResult.model_dump(mode="json")`입니다.
- `RESULT_FORWARD_ENDPOINT_URL`이 비어 있으면 로컬 개발과 테스트를 위해 전송하지 않습니다.
- SDK 초기화와 실제 OpenAI 호출 세부 구현은 AI Connector 책임입니다.

실제 AI Connector 없이 개발할 때는 `tests.conftest.FakeOpenAIConnector`를 주입합니다. 외부 endpoint 없이 전송 payload만 검증할 때는 `forward_callable` 테스트 대역을 주입합니다.

변경 후 실행:

```bash
pytest tests/unit/test_anomaly_analysis_service.py
```

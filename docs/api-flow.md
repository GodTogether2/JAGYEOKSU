# API 흐름

1. FastAPI가 외부 JSON을 엄격한 요청 스키마로 검증한다.
2. WaterUsageGetter가 익명 식별자, timezone, 개수, 중복, 미래 시각을 검사하고 정렬한다.
3. AnomalyAnalysisService가 OpenAIConnector 호출에 필요한 내부 특징 payload를 만든다.
4. OFFLINE 또는 누락률 초과는 결정적 로컬 응답을 만들고 외부 전송을 하지 않는다.
5. 나머지는 OpenAIConnector가 `AnomalyLLMResult`를 반환한다.
6. AnomalyAnalysisService가 원 요청 포맷에 `analysis_result` 키 하나를 추가한다.
7. `RESULT_FORWARD_ENDPOINT_URL`이 설정되어 있으면 해당 payload를 다른 endpoint로 POST한다.
8. 클라이언트에는 검증된 `AnomalyAnalysisResponse`를 반환한다.

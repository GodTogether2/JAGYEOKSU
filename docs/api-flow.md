# API 흐름

1. FastAPI가 외부 JSON을 엄격한 요청 스키마로 검증한다.
2. WaterUsageGetter가 익명 식별자, timezone, 개수, 중복, 미래 시각을 검사하고 정렬한다.
3. AnomalyAnalysisService가 모든 객관 특징을 Python으로 계산한다.
4. OFFLINE 또는 누락률 초과는 결정적 로컬 응답을 만든다.
5. 나머지는 최근 72시간과 특징값만 LocalLLMConnector에 전달한다.
6. Structured Outputs를 다시 검증하고 기준선·부재 한계를 추가해 응답한다.


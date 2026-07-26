# AI Connector 모듈

담당자는 문범석입니다. `OpenAIConnector`는 환경변수 기반 `AsyncOpenAI`, Responses API Structured Outputs, `store=False`, timeout, 선택적 지수 백오프와 공통 예외 변환을 담당합니다.

Service와의 계약은 `AnalysisConnector.analyze(system_prompt, user_payload) -> AnomalyLLMResult`입니다. 전달받은 시스템 프롬프트와 JSON payload를 모두 요청에 포함하며 비즈니스 특징은 계산하지 않습니다. 변경 후 `pytest tests/unit/test_openai_connector.py`를 실행합니다.


# AI Connector 모듈

담당자는 문범석입니다. `LocalLLMConnector`는 로컬에 설치된 Ollama 서버(`ollama` 공식 Python 클라이언트, `AsyncClient`)를 통해 오픈웨이트 모델(Qwen3 8B)을 호출하고, 스키마 강제 디코딩(`format=AnomalyLLMResult.model_json_schema()`)으로 구조화 출력을 받습니다.

Service와의 계약은 `AnalysisConnector.analyze(system_prompt, user_payload) -> AnomalyLLMResult`입니다. 전달받은 시스템 프롬프트와 JSON payload를 모두 요청에 포함하며 비즈니스 특징은 계산하지 않습니다. 변경 후 `pytest tests/unit/test_local_llm_connector.py`를 실행합니다.

# Detector 모듈

담당자는 최지욱입니다. `AnomalyAnalysisService`는 정규화 입력에서 객관 특징을 계산하고, 분리된 시스템 프롬프트와 최근 72시간 payload를 Connector에 전달하며, 안전 정책 및 최종 응답을 검증합니다.

문범석 담당 모듈 없이 개발할 때는 `tests.conftest.FakeLLMConnector`를 주입합니다. OFFLINE과 누락률 초과는 Connector를 호출하지 않습니다. 변경 후 `pytest tests/unit/test_anomaly_analysis_service.py`를 실행합니다.


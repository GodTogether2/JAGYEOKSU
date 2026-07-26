# Getter 모듈

담당자는 홍성표입니다. `WaterUsageGetter.normalize()`은 FastAPI가 검증한 요청을 받아 익명 식별자, timezone, 미래 시각, 중복, 측정 개수를 검사한 후 `NormalizedWaterUsage` 구조체로 정렬합니다.

이 모듈은 특징 계산, 이상 판단, 프롬프트 생성 및 외부 호출을 하지 않습니다. 변경 후 `pytest tests/unit/test_water_usage_getter.py`를 실행합니다.


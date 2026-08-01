# Getter 모듈

`WaterUsageGetter.normalize()`은 FastAPI가 검증한 요청을 받아 익명 식별자, timezone, 미래 시각, 중복, 측정 개수를 검사한 후 `NormalizedWaterUsage` 구조체로 정렬합니다.

이 모듈은 특징 계산, 이상 판단, 프롬프트 생성 및 외부 호출을 하지 않습니다. 변경 후 `pytest tests/unit/test_water_usage_getter.py`를 실행합니다.

## 먼저 읽을 문서

- [API 입력 및 필드 명세](./INPUT_SPEC.md): API 주소, 전체 필드, 타입, 필수 여부, 허용값, 422 조건, 입력·정규화 예시
- [공용 입력 구조체](../../common/models/water_usage.py): 실제 코드 기준 요청 및 내부 구조체
- [Getter 구현](./water_usage_getter.py): 검증, 정렬, 정규화 구현
- [Getter 단위 테스트](../../../tests/unit/test_water_usage_getter.py): 정상 및 오류 입력 예시

## Getter 호출 위치

Getter는 서버 시작 시 실행되지 않습니다. 다음 API 요청이 들어올 때 FastAPI 의존성 주입으로 생성되고 라우터에서 실행됩니다.

```text
POST /api/v1/anomalies/analyze
→ WaterUsageAnalysisRequest
→ get_water_usage_getter()
→ WaterUsageGetter()
→ getter.normalize(request)
→ NormalizedWaterUsage
```

실제 호출 코드는 `app/api/routes/anomalies.py`의 다음 부분입니다.

```python
normalized = getter.normalize(request)
```

## 빠른 테스트

서버 실행:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

별도 터미널에서 Getter부터 로컬 안전 처리까지 확인:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/anomalies/analyze" \
  -H "Content-Type: application/json" \
  --data-binary "@samples/meter_offline_request.json"
```

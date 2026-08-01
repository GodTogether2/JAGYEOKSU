# WaterUsageGetter API 입력 및 필드 명세

이 문서는 `WaterUsageGetter`가 어떤 API 입력을 받고, 각 필드를 어떻게 검증하며, 어떤 내부 구조체로 변환하는지 정의합니다. 실제 공용 구조체는 `app/common/models/water_usage.py`에 정의되어 모든 모듈이 같은 계약을 import합니다.

## API 기본 정보

| 항목 | 값 |
|---|---|
| HTTP Method | `POST` |
| Path | `/api/v1/anomalies/analyze` |
| Content-Type | `application/json` |
| 성공 상태 코드 | `200 OK` |
| 입력 검증 실패 | `422 Unprocessable Entity` |
| 입력 스키마 | `WaterUsageAnalysisRequest` |
| 정규화 결과 | `NormalizedWaterUsage` |

이 API는 이름, 주소, 전화번호, 주민등록번호 등 실제 개인정보를 받지 않습니다. 정의되지 않은 필드를 추가하면 Pydantic의 `extra="forbid"` 설정에 의해 422로 거부됩니다.

## 최상위 요청 필드

| 필드 | JSON 타입 | 필수 | 예시 | 설명 및 제약 |
|---|---|---:|---|---|
| `request_id` | string | 필수 | `req-demo-001` | 요청 추적용 식별자입니다. 1~100자입니다. 개인정보를 넣지 않습니다. |
| `household_id` | string | 필수 | `demo-household-001` | 익명화된 가구 식별자입니다. 영문 대소문자, 숫자, 하이픈, 밑줄만 허용합니다. |
| `meter_status` | string | 필수 | `ONLINE` | 계량기 상태입니다. `ONLINE`, `OFFLINE`, `UNKNOWN` 중 하나만 허용합니다. |
| `expected_absence` | boolean | 선택 | `false` | 여행 등 예정된 부재가 등록됐는지 나타냅니다. 생략하면 `false`입니다. |
| `measurements` | array | 필수 | 아래 참고 | 수도 사용 측정값 배열입니다. 최소 24개, 최대 5,000개입니다. |

## measurements 요소 필드

각 배열 요소는 `WaterMeasurement` 구조입니다.

| 필드 | JSON 타입 | 필수 | 예시 | 설명 및 제약 |
|---|---|---:|---|---|
| `timestamp` | ISO 8601 string | 필수 | `2026-07-20T00:00:00+09:00` | 측정 시각입니다. `Z` 또는 `+09:00` 같은 timezone이 반드시 있어야 합니다. 미래 시각과 중복 시각은 허용하지 않습니다. |
| `usage_liter` | number | 필수 | `0.4` | 해당 측정 구간의 수도 사용량(리터)입니다. 0 이상인 유한 숫자만 허용합니다. |

`timestamp` 예시:

| 값 | 결과 | 이유 |
|---|---|---|
| `2026-07-20T00:00:00+09:00` | 허용 | UTC offset 포함 |
| `2026-07-19T15:00:00Z` | 허용 | UTC timezone 포함 |
| `2026-07-20T00:00:00` | 거부 | timezone 없음 |
| 동일 timestamp 두 건 | 거부 | 중복 측정 |
| 현재보다 미래 timestamp | 거부 | 미래 데이터 |

## 전체 요청 예시

실제 요청에는 측정값이 최소 24개 있어야 합니다. 아래는 구조 설명을 위해 일부만 표시한 예시이며, 바로 실행 가능한 전체 요청은 `samples/normal_request.json` 또는 `samples/meter_offline_request.json`을 사용합니다.

```json
{
  "request_id": "req-demo-001",
  "household_id": "demo-household-001",
  "meter_status": "ONLINE",
  "expected_absence": false,
  "measurements": [
    {
      "timestamp": "2026-07-20T00:00:00+09:00",
      "usage_liter": 0.4
    },
    {
      "timestamp": "2026-07-20T01:00:00+09:00",
      "usage_liter": 0.0
    }
  ]
}
```

## FastAPI에서 Getter까지 전달되는 구조

클라이언트가 보낸 JSON은 라우터 함수가 실행되기 전에 FastAPI와 Pydantic에 의해 다음 객체로 변환됩니다.

```python
WaterUsageAnalysisRequest(
    request_id="req-demo-001",
    household_id="demo-household-001",
    meter_status="ONLINE",
    expected_absence=False,
    measurements=[
        WaterMeasurement(
            timestamp=datetime(...),
            usage_liter=0.4,
        ),
    ],
)
```

따라서 Getter의 `request` 매개변수는 원시 `dict`가 아니라 `WaterUsageAnalysisRequest` 객체입니다.

## Getter 정규화 결과

Getter는 입력을 검증하고 `measurements`를 timestamp 오름차순으로 정렬한 뒤 다음 내부 공통 구조체를 반환합니다.

| 내부 필드 | 타입 | 생성 방식 |
|---|---|---|
| `request_id` | `str` | 요청값 유지 |
| `household_id` | `str` | 검증된 익명 식별자 유지 |
| `meter_status` | `ONLINE \| OFFLINE \| UNKNOWN` | 요청값 유지 |
| `expected_absence` | `bool` | 요청값 또는 기본값 유지 |
| `measurements` | `tuple[WaterMeasurement, ...]` | timestamp 오름차순 정렬 후 불변 tuple로 변환 |
| `normalized_at` | timezone-aware `datetime` | Getter가 정규화를 완료한 UTC 시각 |

예시:

```python
NormalizedWaterUsage(
    request_id="req-demo-001",
    household_id="demo-household-001",
    meter_status="ONLINE",
    expected_absence=False,
    measurements=(...시간순으로 정렬된 측정값...),
    normalized_at=datetime(..., tzinfo=UTC),
)
```

Getter는 프롬프트를 만들거나 LLM을 호출하지 않으며 이상 여부도 판단하지 않습니다.

## 422 오류 조건

다음 입력은 422 응답을 반환합니다.

- `measurements`가 없거나 24개 미만
- `measurements`가 5,000개 초과
- `usage_liter`가 음수, NaN 또는 무한대
- 동일한 timestamp가 두 번 존재
- timezone 없는 timestamp
- 미래 timestamp
- 허용 문자 외 문자가 포함된 `household_id`
- `ONLINE`, `OFFLINE`, `UNKNOWN` 이외의 meter 상태
- 정의되지 않은 개인정보 또는 기타 필드

오류 응답 예:

```json
{
  "detail": "동일한 timestamp가 중복됐습니다."
}
```

Pydantic 스키마 단계의 오류는 문제가 발생한 필드 위치와 오류 유형이 배열로 반환될 수 있습니다.

## 실행 가능한 cURL

Ollama 없이 Getter와 OFFLINE 로컬 처리 확인:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/anomalies/analyze" \
  -H "Content-Type: application/json" \
  --data-binary "@samples/meter_offline_request.json"
```

Getter와 Service를 통과해 LocalLLMConnector까지 확인:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/anomalies/analyze" \
  -H "Content-Type: application/json" \
  --data-binary "@samples/normal_request.json"
```

두 번째 요청은 로컬에 Ollama 서버가 실행 중이고 `qwen3:8b` 모델이 받아져 있어야 합니다.

## 디버깅 중 확인할 변수

다음 순서로 중단점을 설정합니다.

1. `app/api/routes/anomalies.py`의 `analyze_anomaly`
2. `app/api/dependencies.py`의 `get_water_usage_getter`
3. `app/api/routes/anomalies.py`의 `getter.normalize(request)`
4. `app/modules/getter/water_usage_getter.py`의 `normalize`
5. `NormalizedWaterUsage` 반환 직전

디버거에서 주요 확인값:

```python
request.model_dump()
request.measurements[0]
request.measurements[0].timestamp.tzinfo
ordered[0]
ordered[-1]
normalized.model_dump()
```

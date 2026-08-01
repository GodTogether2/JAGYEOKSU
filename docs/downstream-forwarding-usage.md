# Downstream 전달 payload 수신 개발 가이드

이 문서 하나만 읽으면 CareSignal이 보내는 downstream payload를 받는 endpoint를 만들 수 있다.

## 한 줄 계약

CareSignal은 최초 수도 사용량 요청 JSON에 `analysis_result` 키 하나를 추가해서 `RESULT_FORWARD_ENDPOINT_URL`로 `POST application/json` 요청을 보낸다.

## HTTP 계약

| 항목 | 값 |
|---|---|
| Method | `POST` |
| Content-Type | `application/json` |
| 인증 | 현재 계약 없음 |
| 성공 응답 | `2xx` |
| 실패 응답 | 잘못된 payload는 `400` 또는 `422` |
| 재시도 | 현재 송신 쪽 재시도 없음 |

송신 URL은 CareSignal `.env`의 `RESULT_FORWARD_ENDPOINT_URL`에 넣는다.

```env
RESULT_FORWARD_ENDPOINT_URL=https://receiver.example.com/water-analysis
RESULT_FORWARD_TIMEOUT_SECONDS=10
```

## Payload 형태

최상위 구조:

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
    "evidence": [
      {
        "code": "STABLE_DAILY_PATTERN",
        "message": "최근 사용량이 기준선 범위 안에 있습니다.",
        "observed_value": 41.2,
        "baseline_value": 43.0
      }
    ],
    "recommended_action": "NONE",
    "limitations": ["수도 사용량만을 분석한 참고정보입니다."]
  }
}
```

## 최상위 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `request_id` | string | 예 | 요청 ID |
| `household_id` | string | 예 | 익명 가구 ID |
| `meter_status` | `ONLINE` \| `OFFLINE` \| `UNKNOWN` | 예 | 계량기 상태 |
| `expected_absence` | boolean | 예 | 예정 부재 여부 |
| `measurements` | array | 예 | 수도 사용량 시계열 |
| `analysis_result` | object | 예 | AI 분석 결과 |

`measurements` 항목:

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `timestamp` | ISO-8601 string | 예 | timezone 포함 측정 시각 |
| `usage_liter` | number | 예 | 사용량 리터 |

## `analysis_result` 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `status` | `NORMAL` \| `OBSERVE` \| `CHECK_REQUIRED` \| `DATA_ERROR` | 예 | 분석 상태 |
| `anomaly_score` | integer | 예 | 0-100 점수 |
| `confidence` | number | 예 | 0.0-1.0 신뢰도 |
| `summary` | string | 예 | 요약 |
| `evidence` | array | 예 | 근거 목록, 최대 5개 |
| `recommended_action` | `NONE` \| `RECHECK_LATER` \| `AUTO_CHECK_IN` \| `PHONE_CHECK` \| `CHECK_DEVICE` \| `MANUAL_REVIEW` | 예 | 권장 조치 |
| `limitations` | array | 예 | 한계 문구, 최대 5개 |

`evidence` 항목:

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `code` | string | 예 | 근거 코드 |
| `message` | string | 예 | 근거 설명 |
| `observed_value` | string \| number \| null | 예 | 관측값 |
| `baseline_value` | string \| number \| null | 예 | 기준값 |

## 케이스별 처리 기준

| `analysis_result.status` | 권장 처리 |
|---|---|
| `NORMAL` | 별도 조치 없음. 저장 또는 완료 처리 |
| `OBSERVE` | 추후 재확인 큐 또는 관찰 상태로 저장 |
| `CHECK_REQUIRED` | 전화 확인, 알림, 담당자 확인 큐 생성 |
| `DATA_ERROR` | 계량기 또는 데이터 품질 확인 큐 생성 |

`recommended_action`은 실제 액션을 고를 때 우선 참고한다. `status`는 큰 분류, `recommended_action`은 구체 조치다.

## 더미 데이터

아래 네 파일로 수신 endpoint를 테스트한다.

| 파일 | 케이스 |
|---|---|
| `samples/forward_normal_payload.json` | 정상 |
| `samples/forward_observe_payload.json` | 관찰 필요 |
| `samples/forward_check_required_payload.json` | 확인 필요 |
| `samples/forward_data_error_payload.json` | 데이터 품질 문제 |

예시:

```bash
curl -X POST "http://localhost:8080/water-analysis" \
  -H "Content-Type: application/json" \
  --data-binary "@samples/forward_check_required_payload.json"
```

샘플 재생성:

```bash
python scripts/generate_sample_data.py
```

## 받는 쪽 구현 체크리스트

- `POST` endpoint를 만든다.
- `Content-Type: application/json`을 받는다.
- 위 payload schema를 검증한다.
- `measurements[*].timestamp`는 timezone 포함 ISO-8601 문자열로 파싱한다.
- `analysis_result.status` 네 케이스를 모두 처리한다.
- 성공하면 `2xx`를 반환한다.
- payload가 잘못되면 `400` 또는 `422`를 반환한다.
- 네 개 더미 JSON을 모두 테스트에 사용한다.

## LLM에게 줄 지시문

아래 내용을 그대로 붙여 넣으면 된다.

```text
이 repo에서 CareSignal downstream payload를 받는 endpoint를 개발해라.

반드시 먼저 이 파일들을 읽어라:
- docs/downstream-forwarding-usage.md
- samples/forward_normal_payload.json
- samples/forward_observe_payload.json
- samples/forward_check_required_payload.json
- samples/forward_data_error_payload.json

구현 요구사항:
- POST JSON endpoint를 만든다.
- payload는 최초 수도 사용량 요청 포맷에 analysis_result 키 하나가 추가된 형태다.
- request_id, household_id, meter_status, expected_absence, measurements, analysis_result를 검증한다.
- analysis_result.status는 NORMAL, OBSERVE, CHECK_REQUIRED, DATA_ERROR만 허용한다.
- analysis_result.recommended_action은 NONE, RECHECK_LATER, AUTO_CHECK_IN, PHONE_CHECK, CHECK_DEVICE, MANUAL_REVIEW만 허용한다.
- status와 recommended_action 기준으로 케이스별 처리를 구현한다.
- 제공된 더미 JSON 4개를 이용한 테스트를 작성한다.
- 잘못된 payload는 400 또는 422로 거부한다.
- 성공 시 2xx를 반환한다.
```

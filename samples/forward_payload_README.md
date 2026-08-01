# Downstream 전달 payload

`AnomalyAnalysisService`가 `RESULT_FORWARD_ENDPOINT_URL`로 POST하는 JSON은 초기 입력 포맷에 AI 분석 결과를 `analysis_result` 키로 하나 더 붙인 형태입니다.

## 최상위 필드

| 필드 | 타입 | 설명 |
|---|---|---|
| `request_id` | string | 기존 요청 ID |
| `household_id` | string | 기존 익명 가구 ID |
| `meter_status` | `ONLINE` \| `OFFLINE` \| `UNKNOWN` | 기존 계량기 상태 |
| `expected_absence` | boolean | 기존 예정 부재 여부 |
| `measurements` | array | 기존 수도 사용량 시계열 |
| `analysis_result` | object | AI 분석 결과 `AnomalyLLMResult` |

`measurements` 항목:

| 필드 | 타입 | 설명 |
|---|---|---|
| `timestamp` | ISO-8601 string | timezone 포함 측정 시각 |
| `usage_liter` | number | 사용량 리터 |

`analysis_result` 필드:

| 필드 | 타입 | 설명 |
|---|---|---|
| `status` | `NORMAL` \| `OBSERVE` \| `CHECK_REQUIRED` \| `DATA_ERROR` | 분석 상태 |
| `anomaly_score` | integer | 0-100 점수 |
| `confidence` | number | 0.0-1.0 신뢰도 |
| `summary` | string | 요약 |
| `evidence` | array | 근거 목록, 최대 5개 |
| `recommended_action` | `NONE` \| `RECHECK_LATER` \| `AUTO_CHECK_IN` \| `PHONE_CHECK` \| `CHECK_DEVICE` \| `MANUAL_REVIEW` | 권장 조치 |
| `limitations` | array | 한계 문구, 최대 5개 |

## 케이스별 더미

- `forward_normal_payload.json`: 정상 패턴
- `forward_observe_payload.json`: 관찰 필요
- `forward_check_required_payload.json`: 확인 필요
- `forward_data_error_payload.json`: 데이터 품질 확인 필요

예시 전송:

```bash
curl -X POST "$RESULT_FORWARD_ENDPOINT_URL" \
  -H "Content-Type: application/json" \
  --data-binary "@samples/forward_check_required_payload.json"
```

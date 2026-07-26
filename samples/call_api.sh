#!/usr/bin/env sh
# 최근 무사용 합성 샘플을 로컬 API에 전송한다.
curl -X POST "http://127.0.0.1:8000/api/v1/anomalies/analyze" \
  -H "Content-Type: application/json" \
  --data-binary "@samples/no_usage_request.json"


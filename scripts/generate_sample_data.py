"""현실적인 합성 수도 사용량 시나리오를 재현 가능하게 생성한다."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
END = datetime(2026, 7, 20, 0, tzinfo=UTC)


def usage_for_hour(hour: int, index: int) -> float:
    """아침·저녁에 사용량이 집중되는 결정적 합성 패턴."""
    if 6 <= hour <= 8:
        return round(2.2 + (index % 4) * 0.4, 2)
    if 18 <= hour <= 21:
        return round(2.8 + (index % 3) * 0.5, 2)
    return round(0.15 if index % 5 == 0 else 0.0, 2)


def build(name: str, *, hours: int = 24 * 30, expected: bool = False) -> dict[str, object]:
    """시나리오별 상태 변화만 적용하고 개인정보 없는 요청을 만든다."""
    measurements: list[dict[str, object]] = []
    start = END - timedelta(hours=hours - 1)
    for index in range(hours):
        timestamp = start + timedelta(hours=index)
        usage = usage_for_hour(timestamp.hour, index)
        if name in {"no_usage", "expected_absence"} and index >= hours - 27:
            usage = 0.0
        if name == "continuous_small":
            usage = 0.12
        if name == "missing" and index % 4 == 0:
            continue
        measurements.append({"timestamp": timestamp.isoformat(), "usage_liter": usage})
    return {
        "request_id": f"req-{name}-001",
        "household_id": f"demo-{name.replace('_', '-')}-001",
        "meter_status": "OFFLINE" if name == "meter_offline" else "ONLINE",
        "expected_absence": expected,
        "measurements": measurements,
    }


def analysis_result(status: str) -> dict[str, object]:
    """downstream 전달 payload에 붙일 문범석 결과 더미."""
    cases: dict[str, dict[str, object]] = {
        "NORMAL": {
            "anomaly_score": 12,
            "confidence": 0.86,
            "summary": "평소 수도 사용 패턴과 유사합니다.",
            "evidence": [
                {
                    "code": "STABLE_DAILY_PATTERN",
                    "message": "최근 사용량이 기준선 범위 안에 있습니다.",
                    "observed_value": 41.2,
                    "baseline_value": 43.0,
                }
            ],
            "recommended_action": "NONE",
            "limitations": ["수도 사용량만을 분석한 참고정보입니다."],
        },
        "OBSERVE": {
            "anomaly_score": 42,
            "confidence": 0.72,
            "summary": "최근 사용량 감소가 있어 추이를 더 확인하는 것이 좋습니다.",
            "evidence": [
                {
                    "code": "LOW_RECENT_USAGE",
                    "message": "최근 24시간 사용량이 평소보다 낮습니다.",
                    "observed_value": 5.4,
                    "baseline_value": 18.7,
                }
            ],
            "recommended_action": "RECHECK_LATER",
            "limitations": ["예정된 외출 정보가 있으면 해석이 달라질 수 있습니다."],
        },
        "CHECK_REQUIRED": {
            "anomaly_score": 78,
            "confidence": 0.81,
            "summary": "장시간 사용량 변화가 없어 전화 확인이 필요합니다.",
            "evidence": [
                {
                    "code": "ZERO_USAGE_STREAK",
                    "message": "최근 30시간 동안 의미 있는 사용량이 없습니다.",
                    "observed_value": 30,
                    "baseline_value": 6,
                }
            ],
            "recommended_action": "PHONE_CHECK",
            "limitations": ["수도 사용 외 생활 정보는 포함되지 않았습니다."],
        },
        "DATA_ERROR": {
            "anomaly_score": 0,
            "confidence": 1.0,
            "summary": "측정 데이터 품질 확인이 우선입니다.",
            "evidence": [
                {
                    "code": "METER_OR_DATA_QUALITY",
                    "message": "측정값 누락 또는 계량기 상태 확인이 필요합니다.",
                    "observed_value": "UNKNOWN",
                    "baseline_value": None,
                }
            ],
            "recommended_action": "CHECK_DEVICE",
            "limitations": ["데이터 품질 문제는 생활패턴으로 해석하지 않습니다."],
        },
    }
    return {"status": status, **cases[status]}


def build_forward_payload(
    request_name: str, status: str, *, expected: bool = False
) -> dict[str, object]:
    """홍성표 입력 포맷에 문범석 결과 키 하나만 추가한다."""
    return {
        **build(request_name, hours=24, expected=expected),
        "analysis_result": analysis_result(status),
    }


def main() -> None:
    """요구된 여섯 시나리오와 대표 별칭 파일을 생성한다."""
    scenarios = {
        "normal_request.json": build("normal"),
        "no_usage_request.json": build("no_usage"),
        "expected_absence_request.json": build("expected_absence", expected=True),
        "meter_offline_request.json": build("meter_offline"),
        "continuous_small_request.json": build("continuous_small"),
        "missing_data_request.json": build("missing"),
        "forward_normal_payload.json": build_forward_payload("normal", "NORMAL"),
        "forward_observe_payload.json": build_forward_payload(
            "expected_absence", "OBSERVE", expected=True
        ),
        "forward_check_required_payload.json": build_forward_payload("no_usage", "CHECK_REQUIRED"),
        "forward_data_error_payload.json": build_forward_payload("missing", "DATA_ERROR"),
    }
    SAMPLES.mkdir(exist_ok=True)
    for filename, payload in scenarios.items():
        (SAMPLES / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    main()

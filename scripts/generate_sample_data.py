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


def main() -> None:
    """요구된 여섯 시나리오와 대표 별칭 파일을 생성한다."""
    scenarios = {
        "normal_request.json": build("normal"),
        "no_usage_request.json": build("no_usage"),
        "expected_absence_request.json": build("expected_absence", expected=True),
        "meter_offline_request.json": build("meter_offline"),
        "continuous_small_request.json": build("continuous_small"),
        "missing_data_request.json": build("missing"),
    }
    SAMPLES.mkdir(exist_ok=True)
    for filename, payload in scenarios.items():
        (SAMPLES / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    main()

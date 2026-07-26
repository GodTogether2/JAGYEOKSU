"""실제 OpenAI 호출 없이 공통 합성 입력과 Fake를 제공한다."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.schemas.anomaly import AnomalyEvidence, AnomalyLLMResult
from app.schemas.water_usage import WaterMeasurement, WaterUsageAnalysisRequest


class FakeOpenAIConnector:
    """담당 모듈 사이의 계약을 구현하는 테스트 대역."""

    def __init__(self, result: AnomalyLLMResult | None = None) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.result = result or AnomalyLLMResult(
            status="NORMAL",
            anomaly_score=10,
            confidence=0.8,
            summary="평소 수도 사용 패턴과 유사합니다.",
            evidence=[
                AnomalyEvidence(
                    code="STABLE_USAGE",
                    message="최근 사용량이 기준선과 유사합니다.",
                    observed_value=10,
                    baseline_value=11,
                )
            ],
            recommended_action="NONE",
            limitations=["수도 사용량만을 분석한 참고정보입니다."],
        )

    async def analyze(
        self, system_prompt: str, user_payload: dict[str, object]
    ) -> AnomalyLLMResult:
        self.calls.append((system_prompt, user_payload))
        return self.result


@pytest.fixture
def request_factory() -> Any:
    """시간 수와 상태를 바꿀 수 있는 합성 요청 팩토리."""

    def factory(
        hours: int = 72,
        *,
        meter_status: str = "ONLINE",
        expected_absence: bool = False,
        end: datetime = datetime(2026, 7, 20, tzinfo=UTC),
    ) -> WaterUsageAnalysisRequest:
        start = end - timedelta(hours=hours - 1)
        return WaterUsageAnalysisRequest(
            request_id="req-test-001",
            household_id="demo_house-001",
            meter_status=meter_status,
            expected_absence=expected_absence,
            measurements=[
                WaterMeasurement(
                    timestamp=start + timedelta(hours=index),
                    usage_liter=1.0 if index < hours - 27 else 0.0,
                )
                for index in range(hours)
            ],
        )

    return factory

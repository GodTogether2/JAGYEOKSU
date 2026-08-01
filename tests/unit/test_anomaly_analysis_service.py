"""AnomalyAnalysisService 안전장치와 downstream 전달 테스트."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.modules.detector.anomaly_analysis_service import AnomalyAnalysisService
from app.modules.getter.water_usage_getter import WaterUsageGetter
from app.schemas.anomaly import AnomalyLLMResult
from app.utils.feature_utils import calculate_features
from tests.conftest import FakeOpenAIConnector


def normalized(request_factory, **kwargs):
    request = request_factory(**kwargs)
    return WaterUsageGetter().normalize(request, now=request.measurements[-1].timestamp)


def test_features(request_factory) -> None:
    features = calculate_features(normalized(request_factory))
    assert features["usage_last_24h_liter"] == 0
    assert features["hours_since_last_usage"] == pytest.approx(27)
    assert features["zero_usage_streak_hours"] == pytest.approx(27)
    assert features["usage_drop_rate"] == pytest.approx(1)


@pytest.mark.asyncio
async def test_offline_skips_gpt(request_factory) -> None:
    fake = FakeOpenAIConnector()
    result = await AnomalyAnalysisService(fake, Settings()).analyze(
        normalized(request_factory, meter_status="OFFLINE")
    )
    assert result.status == "DATA_ERROR"
    assert result.recommended_action == "CHECK_DEVICE"
    assert fake.calls == []


@pytest.mark.asyncio
async def test_absence_and_72_hours_payload(request_factory) -> None:
    fake = FakeOpenAIConnector()
    data = normalized(request_factory, hours=24 * 30, expected_absence=True)
    result = await AnomalyAnalysisService(fake, Settings()).analyze(data)
    payload = fake.calls[0][1]
    assert payload["expected_absence"] is True
    assert len(payload["recent_measurements"]) <= 73
    assert any("예정된 외출" in item for item in result.limitations)


@pytest.mark.asyncio
async def test_forwards_original_request_shape_with_llm_result(request_factory) -> None:
    fake = FakeOpenAIConnector()
    forwarded: list[tuple[str, dict[str, object]]] = []

    async def forward(url: str, payload: dict[str, object]) -> None:
        forwarded.append((url, payload))

    request = request_factory(hours=24)
    data = WaterUsageGetter().normalize(request, now=request.measurements[-1].timestamp)

    await AnomalyAnalysisService(
        fake,
        Settings(result_forward_endpoint_url="https://example.test/results"),
        forward_callable=forward,
    ).analyze(data)

    assert forwarded == [
        (
            "https://example.test/results",
            {
                **request.model_dump(mode="json"),
                "analysis_result": fake.result.model_dump(mode="json"),
            },
        )
    ]


def test_invalid_score_and_forbidden_language_rejected() -> None:
    base = {
        "status": "NORMAL",
        "confidence": 1,
        "summary": "평소와 유사합니다.",
        "evidence": [],
        "recommended_action": "NONE",
        "limitations": [],
    }
    with pytest.raises(ValidationError):
        AnomalyLLMResult(anomaly_score=101, **base)
    with pytest.raises(ValidationError):
        AnomalyLLMResult(anomaly_score=1, **{**base, "summary": "사망 확률을 계산했습니다."})

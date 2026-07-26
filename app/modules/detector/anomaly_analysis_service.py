"""특징 계산과 안전한 분석 흐름을 조정한다.

담당: 최지욱
"""

from datetime import timedelta
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.common.models.anomaly import (
    AnomalyAnalysisResponse,
    AnomalyEvidence,
    AnomalyLLMResult,
)
from app.common.models.water_usage import NormalizedWaterUsage
from app.core.config import Settings
from app.core.exceptions import InvalidLLMResponseError
from app.modules.ai.openai_connector import AnalysisConnector
from app.utils.datetime_utils import utc_now
from app.utils.feature_utils import calculate_features

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "anomaly_system_prompt.txt"


class AnomalyAnalysisService:
    """로컬 안전장치를 적용하고 Connector를 호출해 최종 응답을 조립한다."""

    def __init__(self, connector: AnalysisConnector, settings: Settings) -> None:
        self.connector = connector
        self.settings = settings

    async def analyze(self, data: NormalizedWaterUsage) -> AnomalyAnalysisResponse:
        """오프라인·품질 오류를 우선 처리하고 그 외에만 GPT를 호출한다."""
        features = calculate_features(data)
        if data.meter_status == "OFFLINE":
            return self._local_response(
                data,
                status="DATA_ERROR",
                summary="계량기가 오프라인 상태여서 생활패턴을 판단할 수 없습니다.",
                action="CHECK_DEVICE",
                limitations=["계량기 상태를 먼저 확인해야 합니다."],
            )
        if features["missing_ratio"] >= self.settings.missing_ratio_threshold:
            return self._local_response(
                data,
                status="DATA_ERROR",
                summary="측정값 누락이 많아 생활패턴보다 데이터 품질 확인이 우선입니다.",
                action="CHECK_DEVICE",
                limitations=[f"측정값 누락률 {features['missing_ratio']:.1%}가 기준 이상입니다."],
            )

        payload = self.build_user_payload(data, features)
        system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
        try:
            result = await self.connector.analyze(system_prompt, payload)
            validated = AnomalyLLMResult.model_validate(result)
        except ValidationError as exc:
            raise InvalidLLMResponseError("LLM 결과 검증 실패") from exc

        limitations = list(validated.limitations)
        if features["baseline_days"] < 30:
            limitations.append("30일 미만 데이터로 장기 기준선이 부족합니다.")
        if data.expected_absence:
            limitations.append("예정된 외출 정보를 분석에 반영했습니다.")
            if validated.status == "CHECK_REQUIRED":
                validated = validated.model_copy(
                    update={
                        "status": "OBSERVE",
                        "recommended_action": "RECHECK_LATER",
                        "anomaly_score": min(validated.anomaly_score, 49),
                    }
                )
        return AnomalyAnalysisResponse(
            **validated.model_dump(exclude={"limitations"}),
            request_id=data.request_id,
            household_id=data.household_id,
            limitations=list(dict.fromkeys(limitations))[:5],
            model_provider="openai",
            model_name=self.settings.openai_model,
            analyzed_at=utc_now(),
        )

    def build_user_payload(
        self, data: NormalizedWaterUsage, features: dict[str, Any]
    ) -> dict[str, object]:
        """최근 72시간만 포함한 Connector 독립형 JSON 계약을 만든다."""
        cutoff = data.measurements[-1].timestamp - timedelta(hours=72)
        recent = [
            {"timestamp": item.timestamp.isoformat(), "usage_liter": item.usage_liter}
            for item in data.measurements
            if item.timestamp >= cutoff
        ]
        return {
            "task": "water_usage_anomaly_triage",
            "household_id": data.household_id,
            "meter_status": data.meter_status,
            "expected_absence": data.expected_absence,
            "data_quality": {
                "measurement_count": len(data.measurements),
                "missing_ratio": features["missing_ratio"],
                "interval_minutes": features["interval_minutes"],
            },
            "features": features,
            "recent_measurements": recent,
        }

    def _local_response(
        self,
        data: NormalizedWaterUsage,
        *,
        status: str,
        summary: str,
        action: str,
        limitations: list[str],
    ) -> AnomalyAnalysisResponse:
        """GPT를 호출하지 않는 결정적 로컬 응답을 생성한다."""
        return AnomalyAnalysisResponse(
            request_id=data.request_id,
            household_id=data.household_id,
            status=status,
            anomaly_score=0,
            confidence=1.0,
            summary=summary,
            evidence=[
                AnomalyEvidence(
                    code="METER_OR_DATA_QUALITY",
                    message=summary,
                    observed_value=data.meter_status,
                    baseline_value=None,
                )
            ],
            recommended_action=action,
            limitations=limitations,
            model_provider="local",
            model_name="rule-based-safety-gate",
            analyzed_at=utc_now(),
        )

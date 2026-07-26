"""LLM 구조화 출력과 최종 API 응답 스키마."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Status = Literal["NORMAL", "OBSERVE", "CHECK_REQUIRED", "DATA_ERROR"]
Action = Literal[
    "NONE", "RECHECK_LATER", "AUTO_CHECK_IN", "PHONE_CHECK", "CHECK_DEVICE", "MANUAL_REVIEW"
]
FORBIDDEN_TERMS = (
    "고독사",
    "사망 확률",
    "사망확률",
    "생존 여부",
    "응급환자",
    "질병 진단",
    "진단 확률",
)


class AnomalyEvidence(BaseModel):
    """판단을 뒷받침하는 최대 다섯 개의 수치 근거."""

    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=60)
    message: str = Field(min_length=1, max_length=300)
    observed_value: str | float | int | None
    baseline_value: str | float | int | None


class AnomalyLLMResult(BaseModel):
    """Responses API Structured Outputs가 반드시 만족해야 하는 스키마."""

    model_config = ConfigDict(extra="forbid")
    status: Status
    anomaly_score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = Field(min_length=1, max_length=500)
    evidence: list[AnomalyEvidence] = Field(max_length=5)
    recommended_action: Action
    limitations: list[str] = Field(max_length=5)

    @field_validator("summary", "limitations", mode="after")
    @classmethod
    def reject_unsafe_or_markdown(cls, value: str | list[str]) -> str | list[str]:
        """금지된 진단 표현과 Markdown/코드블록을 거부한다."""
        texts = [value] if isinstance(value, str) else value
        if any(term in text for text in texts for term in FORBIDDEN_TERMS):
            raise ValueError("허용되지 않는 진단 또는 사망 관련 표현입니다.")
        if any(token in text for text in texts for token in ("```", "**", "# ")):
            raise ValueError("Markdown 문법은 허용되지 않습니다.")
        return value

    @field_validator("evidence")
    @classmethod
    def validate_evidence_language(cls, value: list[AnomalyEvidence]) -> list[AnomalyEvidence]:
        """근거 메시지에도 안전 표현 정책을 동일하게 적용한다."""
        if any(term in item.message for item in value for term in FORBIDDEN_TERMS):
            raise ValueError("근거에 허용되지 않는 표현이 포함됐습니다.")
        return value


class AnomalyAnalysisResponse(AnomalyLLMResult):
    """클라이언트에 반환하는 완전한 분석 응답."""

    request_id: str
    household_id: str
    model_provider: str
    model_name: str
    analyzed_at: datetime

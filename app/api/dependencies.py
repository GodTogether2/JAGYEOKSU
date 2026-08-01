"""세 핵심 클래스를 조립하는 의존성 주입 구성."""

from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.modules.ai.local_llm_connector import LocalLLMConnector
from app.modules.detector.anomaly_analysis_service import AnomalyAnalysisService
from app.modules.getter.water_usage_getter import WaterUsageGetter


def get_water_usage_getter() -> WaterUsageGetter:
    """상태가 없는 Getter를 생성한다."""
    return WaterUsageGetter()


def get_local_llm_connector(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LocalLLMConnector:
    """환경설정을 한 곳에서 주입해 모델명과 서버 주소의 중복을 막는다."""
    return LocalLLMConnector(settings)


def get_anomaly_analysis_service(
    connector: Annotated[LocalLLMConnector, Depends(get_local_llm_connector)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnomalyAnalysisService:
    """테스트가 Connector 의존성을 override할 수 있게 조립한다."""
    return AnomalyAnalysisService(connector, settings)

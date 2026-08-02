"""환경변수 기반 애플리케이션 설정."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """민감정보를 코드와 분리하고 환경변수에서만 읽는다."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    log_level: str = "INFO"
    llm_model: str = "coolsoon/kanana-1.5-8b"
    llm_base_url: str = "http://localhost:11434"
    llm_timeout_seconds: float = Field(default=420, gt=0)
    llm_max_retries: int = Field(default=2, ge=0, le=2)
    result_forward_endpoint_url: str = ""
    result_forward_timeout_seconds: float = Field(default=10, gt=0)
    missing_ratio_threshold: float = Field(default=0.2, ge=0, le=1)
    cors_origins: str = ""

    @property
    def llm_configured(self) -> bool:
        """LLM 모델명이 설정되어 있는지 여부만 공개한다."""
        return bool(self.llm_model.strip())


@lru_cache
def get_settings() -> Settings:
    """프로세스 내에서 설정 객체를 재사용한다."""
    return Settings()

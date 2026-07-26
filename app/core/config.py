"""환경변수 기반 애플리케이션 설정."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """민감정보를 코드와 분리하고 환경변수에서만 읽는다."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    log_level: str = "INFO"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    openai_timeout_seconds: float = Field(default=30, gt=0)
    openai_max_retries: int = Field(default=2, ge=0, le=2)
    openai_store: bool = False
    missing_ratio_threshold: float = Field(default=0.2, ge=0, le=1)
    cors_origins: str = ""

    @property
    def openai_configured(self) -> bool:
        """키 존재 여부만 공개하고 실제 값은 노출하지 않는다."""
        return bool(self.openai_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    """프로세스 내에서 설정 객체를 재사용한다."""
    return Settings()

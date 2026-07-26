"""CareSignal API 애플리케이션 진입점."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import anomalies, health
from app.core.config import get_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title="CareSignal API",
    version="0.1.0",
    description="합성 수도 사용 패턴과 개인 기준선의 차이를 분석하는 복지 업무 참고 API",
)
if settings.app_env == "development" and settings.cors_origins.strip():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[item.strip() for item in settings.cors_origins.split(",")],
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(health.router)
app.include_router(anomalies.router)
register_exception_handlers(app)

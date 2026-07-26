"""원본 시계열과 비밀값을 기록하지 않는 JSON 구조화 로깅."""

import json
import logging
from typing import Any


def mask_household_id(value: str) -> str:
    """상관관계 확인에 필요한 최소 부분만 남긴다."""
    return f"{value[:3]}***{value[-3:]}" if len(value) > 6 else "***"


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """허용된 메타데이터만 한 줄 JSON으로 기록한다."""
    logger.info(json.dumps({"event": event, **fields}, ensure_ascii=False, default=str))


def configure_logging(level: str) -> None:
    """애플리케이션 공통 로그 형식을 설정한다."""
    logging.basicConfig(level=level.upper(), format="%(message)s")

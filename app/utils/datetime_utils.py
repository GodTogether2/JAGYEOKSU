"""시간대 안전한 날짜/시간 처리."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """테스트에서 대체하기 쉬운 UTC 현재 시각 함수."""
    return datetime.now(UTC)


def hours_between(start: datetime, end: datetime) -> float:
    """서로 다른 timezone을 UTC 기준 시간 차로 계산한다."""
    return max(0.0, (end.astimezone(UTC) - start.astimezone(UTC)).total_seconds() / 3600)

"""외부 서비스 및 입력 오류를 분리하는 프로젝트 공통 예외."""


class CareSignalError(Exception):
    """모든 프로젝트 예외의 기반 클래스."""


class InputValidationError(CareSignalError):
    """Getter 단계의 도메인 입력 오류."""


class LLMServiceError(CareSignalError):
    """로컬 LLM 일반 장애."""


class LLMTimeoutError(LLMServiceError):
    """로컬 LLM 응답 제한시간 초과."""


class LLMConnectionError(LLMServiceError):
    """Ollama 서버에 연결할 수 없음(미실행 또는 모델 미다운로드)."""


class InvalidLLMResponseError(LLMServiceError):
    """스키마 또는 안전 정책을 만족하지 않는 모델 응답."""

"""외부 서비스 및 입력 오류를 분리하는 프로젝트 공통 예외."""


class CareSignalError(Exception):
    """모든 프로젝트 예외의 기반 클래스."""


class InputValidationError(CareSignalError):
    """Getter 단계의 도메인 입력 오류."""


class OpenAIServiceError(CareSignalError):
    """OpenAI 일반 장애."""


class OpenAITimeoutError(OpenAIServiceError):
    """OpenAI 제한시간 초과."""


class OpenAIRateLimitError(OpenAIServiceError):
    """OpenAI 요청 한도 초과."""


class OpenAIAuthError(OpenAIServiceError):
    """OpenAI 인증 실패."""


class OpenAIBadRequestError(OpenAIServiceError):
    """재시도하면 안 되는 잘못된 OpenAI 요청."""


class InvalidLLMResponseError(OpenAIServiceError):
    """스키마 또는 안전 정책을 만족하지 않는 모델 응답."""

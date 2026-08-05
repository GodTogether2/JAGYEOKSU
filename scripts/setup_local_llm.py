"""Ollama 서버 설치와 로컬 LLM 모델 다운로드를 자동화한다."""

INSTALL_COMMANDS: dict[str, str] = {
    "Windows": (
        "winget install --id Ollama.Ollama --accept-package-agreements "
        "--accept-source-agreements --silent"
    ),
    "Darwin": "curl -fsSL https://ollama.com/install.sh | sh",
    "Linux": "curl -fsSL https://ollama.com/install.sh | sh",
}


def get_install_command(system: str) -> str | None:
    """OS 이름(platform.system() 결과)에 맞는 공식 Ollama 설치 명령을 돌려준다.

    지원하지 않는 OS는 None을 돌려준다.
    """
    return INSTALL_COMMANDS.get(system)

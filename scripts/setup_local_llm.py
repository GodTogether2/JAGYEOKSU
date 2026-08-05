"""Ollama 서버 설치와 로컬 LLM 모델 다운로드를 자동화한다."""

import shutil
import time
from collections.abc import Callable

import httpx

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


def is_ollama_installed() -> bool:
    """ollama 실행 파일이 PATH에 있는지 확인한다."""
    return shutil.which("ollama") is not None


def wait_for_server(
    base_url: str,
    timeout_seconds: float = 30,
    get_callable: Callable[..., object] = httpx.get,
    sleep_callable: Callable[[float], None] = time.sleep,
) -> bool:
    """Ollama 서버가 응답할 때까지 짧게 폴링한다."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            get_callable(base_url, timeout=2)
            return True
        except httpx.HTTPError:
            sleep_callable(1)
    return False

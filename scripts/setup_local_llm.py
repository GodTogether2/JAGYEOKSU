"""Ollama 서버 설치와 로컬 LLM 모델 다운로드를 자동화한다."""

import platform
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from typing import Protocol

import httpx
import ollama

from app.core.config import get_settings

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


class _OllamaClientLike(Protocol):
    def list(self) -> object: ...

    def pull(self, model: str, *, stream: bool = True) -> object: ...


def is_model_pulled(client: _OllamaClientLike, model: str) -> bool:
    """모델이 이미 로컬에 받아져 있는지 확인한다."""
    return any(item.model == model for item in client.list().models)  # type: ignore


def pull_model(client: _OllamaClientLike, model: str) -> None:
    """모델을 다운로드하며 진행률을 stdout에 스트리밍한다."""
    for progress in client.pull(model, stream=True):  # type: ignore
        if progress.total and progress.completed:
            percent = progress.completed / progress.total * 100
            print(f"{progress.status}: {percent:.1f}%")
        else:
            print(progress.status)


def main() -> int:
    settings = get_settings()
    system = platform.system()

    if is_ollama_installed():
        print("Ollama가 이미 설치되어 있습니다.")
    else:
        command = get_install_command(system)
        if command is None:
            print(
                f"지원하지 않는 OS입니다: {system}. "
                "https://ollama.com/download 에서 직접 설치하세요."
            )
            return 1
        print(f"Ollama 설치 중: {command}")
        subprocess.run(command, shell=True, check=True)

    print("Ollama 서버 응답 대기 중...")
    if not wait_for_server(settings.llm_base_url):
        print(
            "Ollama 설치는 됐지만 서버가 응답하지 않습니다. "
            "직접 실행한 뒤 이 스크립트를 다시 실행하세요."
        )
        return 1

    client = ollama.Client(host=settings.llm_base_url)
    if is_model_pulled(client, settings.llm_model):  # type: ignore
        print(f"모델이 이미 받아져 있습니다: {settings.llm_model}")
        return 0

    print(f"모델 다운로드 중: {settings.llm_model} (수 GB, 몇 분 걸릴 수 있습니다)")
    pull_model(client, settings.llm_model)  # type: ignore
    print("완료.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

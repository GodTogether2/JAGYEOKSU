"""scripts/setup_local_llm.py의 순수 로직 단위 테스트."""

import shutil

import httpx

from scripts.setup_local_llm import get_install_command, is_ollama_installed, wait_for_server


def test_get_install_command_windows() -> None:
    assert get_install_command("Windows") == (
        "winget install --id Ollama.Ollama --accept-package-agreements "
        "--accept-source-agreements --silent"
    )


def test_get_install_command_mac_and_linux_share_curl_script() -> None:
    expected = "curl -fsSL https://ollama.com/install.sh | sh"
    assert get_install_command("Darwin") == expected
    assert get_install_command("Linux") == expected


def test_get_install_command_unknown_returns_none() -> None:
    assert get_install_command("Plan9") is None


def test_is_ollama_installed_true(monkeypatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/ollama")
    assert is_ollama_installed() is True


def test_is_ollama_installed_false(monkeypatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert is_ollama_installed() is False


def test_wait_for_server_retries_until_success() -> None:
    calls: list[str] = []

    def get_callable(url: str, timeout: float) -> None:
        calls.append(url)
        if len(calls) < 3:
            raise httpx.ConnectError("no")

    result = wait_for_server(
        "http://x", timeout_seconds=5, get_callable=get_callable, sleep_callable=lambda s: None
    )
    assert result is True
    assert len(calls) == 3


def test_wait_for_server_times_out() -> None:
    def get_callable(url: str, timeout: float) -> None:
        raise httpx.ConnectError("no")

    result = wait_for_server(
        "http://x", timeout_seconds=0.05, get_callable=get_callable, sleep_callable=lambda s: None
    )
    assert result is False

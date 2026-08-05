"""scripts/setup_local_llm.py의 순수 로직 단위 테스트."""

from scripts.setup_local_llm import get_install_command


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

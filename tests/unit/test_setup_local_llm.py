"""scripts/setup_local_llm.py의 순수 로직 단위 테스트."""

import shutil
from types import SimpleNamespace

import httpx

from scripts.setup_local_llm import (
    get_install_command,
    is_model_pulled,
    is_ollama_installed,
    pull_model,
    wait_for_server,
)


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


def test_is_model_pulled_true() -> None:
    class FakeClient:
        def list(self) -> SimpleNamespace:
            return SimpleNamespace(models=[SimpleNamespace(model="coolsoon/kanana-1.5-8b")])

    assert is_model_pulled(FakeClient(), "coolsoon/kanana-1.5-8b") is True


def test_is_model_pulled_false() -> None:
    class FakeClient:
        def list(self) -> SimpleNamespace:
            return SimpleNamespace(models=[])

    assert is_model_pulled(FakeClient(), "coolsoon/kanana-1.5-8b") is False


def test_is_model_pulled_true_when_server_returns_default_tag() -> None:
    """실제 Ollama 서버는 태그 없는 모델명도 ':latest' 태그를 붙여 돌려준다."""

    class FakeClient:
        def list(self) -> SimpleNamespace:
            return SimpleNamespace(models=[SimpleNamespace(model="coolsoon/kanana-1.5-8b:latest")])

    assert is_model_pulled(FakeClient(), "coolsoon/kanana-1.5-8b") is True


def test_is_model_pulled_ignores_entries_with_no_model_name() -> None:
    """model이 None인 항목이 있어도 TypeError 없이 무시하고 계속 비교한다."""

    class FakeClient:
        def list(self) -> SimpleNamespace:
            return SimpleNamespace(
                models=[
                    SimpleNamespace(model=None),
                    SimpleNamespace(model="coolsoon/kanana-1.5-8b:latest"),
                ]
            )

    assert is_model_pulled(FakeClient(), "coolsoon/kanana-1.5-8b") is True


def test_is_model_pulled_false_when_only_entry_has_no_model_name() -> None:
    class FakeClient:
        def list(self) -> SimpleNamespace:
            return SimpleNamespace(models=[SimpleNamespace(model=None)])

    assert is_model_pulled(FakeClient(), "coolsoon/kanana-1.5-8b") is False


def test_pull_model_streams_progress(capsys) -> None:
    class FakeClient:
        def pull(self, model: str, *, stream: bool = True) -> list[SimpleNamespace]:
            assert model == "coolsoon/kanana-1.5-8b"
            assert stream is True
            return [
                SimpleNamespace(status="pulling manifest", completed=None, total=None),
                SimpleNamespace(status="downloading", completed=50, total=100),
                SimpleNamespace(status="success", completed=100, total=100),
            ]

    pull_model(FakeClient(), "coolsoon/kanana-1.5-8b")
    captured = capsys.readouterr()
    assert "downloading" in captured.out
    assert "success" in captured.out

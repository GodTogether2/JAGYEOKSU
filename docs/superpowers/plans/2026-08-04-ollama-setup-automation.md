# Ollama·Kanana 자동 설치 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 프로젝트를 처음 clone한 사람이 네이티브 환경에서는 스크립트 한 번, Docker 환경에서는 `docker compose up` 한 번으로 Ollama 설치와 Kanana 모델 다운로드까지 자동으로 끝나게 만든다.

**Architecture:** 새 `scripts/setup_local_llm.py`가 OS를 감지해 공식 설치 명령을 실행하고, 이미 설치된 `ollama` 파이썬 패키지의 동기 `Client`로 서버 응답을 확인한 뒤 모델을 pull한다. Docker 쪽은 `docker-compose.yml`에 `ollama` 서비스(공식 이미지)와 모델을 한 번만 받는 `model-init` 1회성 서비스를 추가하고, `api` 서비스가 그 뒤에 뜨도록 `depends_on`으로 순서를 강제한다.

**Tech Stack:** Python 3.12, `ollama` 패키지(동기 `Client`), `httpx`, `subprocess`, Docker Compose(`ollama/ollama` 공식 이미지).

**Reference spec:** [docs/superpowers/specs/2026-08-04-ollama-setup-automation-design.md](../specs/2026-08-04-ollama-setup-automation-design.md)

---

## Before you start

이 계획은 실제로 winget/curl 설치나 5GB 모델 다운로드를 실행하는 테스트는 만들지 않는다 — `main()`을 뺀 모든 핵심 로직은 fake/주입 가능한 콜러블로 단위 테스트하고, 실제 설치/다운로드 동작은 마지막에 딱 한 번 수동으로 확인한다(이미 이 개발 머신엔 Ollama와 모델이 있으므로 "이미 설치됨" 경로가 정상 동작하는지 확인하는 형태가 됨). Docker Compose 검증은 이 머신에 Docker가 없어서 실행할 수 없다 — 파일 내용까지만 작성하고, 실제 실행 확인은 Docker가 있는 환경에서 별도로 하도록 안내를 남긴다.

---

### Task 1: `scripts`를 import 가능한 패키지로 등록

**Files:**
- Create: `scripts/__init__.py`
- Modify: `pyproject.toml:34-35`

- [ ] **Step 1: 빈 `__init__.py` 생성**

```python
```

(빈 파일로 `scripts/__init__.py` 생성)

- [ ] **Step 2: `pyproject.toml`의 packages-find에 `scripts` 추가**

Replace:
```toml
[tool.setuptools.packages.find]
include = ["app*"]
```
with:
```toml
[tool.setuptools.packages.find]
include = ["app*", "scripts*"]
```

- [ ] **Step 3: 재설치해서 import 가능한지 확인**

Run: `pip install -e ".[dev]"`
Run: `python -c "import scripts; print('ok')"`
Expected: `ok` 출력, 에러 없음.

- [ ] **Step 4: Commit**

```bash
git add scripts/__init__.py pyproject.toml
git commit -m "build: scripts 디렉터리를 import 가능한 패키지로 등록"
```

---

### Task 2: `get_install_command()` — OS별 설치 명령 (TDD)

**Files:**
- Create: `scripts/setup_local_llm.py`
- Test: `tests/unit/test_setup_local_llm.py`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/unit/test_setup_local_llm.py -v`
Expected: `ModuleNotFoundError: No module named 'scripts.setup_local_llm'`

- [ ] **Step 3: 최소 구현 작성**

```python
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
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/unit/test_setup_local_llm.py -v`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/setup_local_llm.py tests/unit/test_setup_local_llm.py
git commit -m "feat: OS별 Ollama 설치 명령 결정 로직 추가"
```

---

### Task 3: `is_ollama_installed()` / `wait_for_server()` (TDD)

**Files:**
- Modify: `scripts/setup_local_llm.py`
- Modify: `tests/unit/test_setup_local_llm.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/unit/test_setup_local_llm.py` 상단 import를 아래로 바꾸고, 파일 끝에 테스트를 추가한다.

Replace:
```python
from scripts.setup_local_llm import get_install_command
```
with:
```python
import shutil

import httpx

from scripts.setup_local_llm import get_install_command, is_ollama_installed, wait_for_server
```

파일 끝에 추가:
```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/unit/test_setup_local_llm.py -v`
Expected: `ImportError: cannot import name 'is_ollama_installed'`

- [ ] **Step 3: 구현 추가**

`scripts/setup_local_llm.py`의 docstring 줄을 아래로 교체(import 추가):

Replace:
```python
"""Ollama 서버 설치와 로컬 LLM 모델 다운로드를 자동화한다."""

INSTALL_COMMANDS: dict[str, str] = {
```
with:
```python
"""Ollama 서버 설치와 로컬 LLM 모델 다운로드를 자동화한다."""

import shutil
import time
from collections.abc import Callable

import httpx

INSTALL_COMMANDS: dict[str, str] = {
```

`INSTALL_COMMANDS`/`get_install_command` 뒤에 추가:

```python
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
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/unit/test_setup_local_llm.py -v`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/setup_local_llm.py tests/unit/test_setup_local_llm.py
git commit -m "feat: Ollama 설치 여부·서버 응답 대기 로직 추가"
```

---

### Task 4: `is_model_pulled()` / `pull_model()` (TDD)

**Files:**
- Modify: `scripts/setup_local_llm.py`
- Modify: `tests/unit/test_setup_local_llm.py`

- [ ] **Step 1: 실패하는 테스트 작성**

Import 줄 교체:
```python
import shutil

import httpx

from scripts.setup_local_llm import get_install_command, is_ollama_installed, wait_for_server
```
→
```python
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
```

파일 끝에 추가:
```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/unit/test_setup_local_llm.py -v`
Expected: `ImportError: cannot import name 'is_model_pulled'`

- [ ] **Step 3: 구현 추가**

`scripts/setup_local_llm.py`의 import에 `Protocol` 추가:

Replace:
```python
import shutil
import time
from collections.abc import Callable

import httpx
```
with:
```python
import shutil
import time
from collections.abc import Callable
from typing import Protocol

import httpx
```

`wait_for_server` 뒤에 클라이언트 타입 힌트용 프로토콜 정의(테스트의 `FakeClient`가 실제 `ollama.Client`를 흉내내므로, 타입은 구조적으로만 맞으면 됨)와 두 함수를 추가:

```python
class _OllamaClientLike(Protocol):
    def list(self) -> object: ...

    def pull(self, model: str, *, stream: bool = True) -> object: ...
```

(`stream`을 키워드 전용으로 선언 — 실제 `ollama.Client.pull(self, model, *, insecure=False, stream=False)`도 키워드 전용이라 구조적 타입 호환을 맞춘다.)

`wait_for_server` 뒤에 추가:

```python
def is_model_pulled(client: _OllamaClientLike, model: str) -> bool:
    """모델이 이미 로컬에 받아져 있는지 확인한다."""
    return any(item.model == model for item in client.list().models)  # type: ignore[attr-defined]


def pull_model(client: _OllamaClientLike, model: str) -> None:
    """모델을 다운로드하며 진행률을 stdout에 스트리밍한다."""
    for progress in client.pull(model, stream=True):  # type: ignore[union-attr]
        if progress.total and progress.completed:
            percent = progress.completed / progress.total * 100
            print(f"{progress.status}: {percent:.1f}%")
        else:
            print(progress.status)
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/unit/test_setup_local_llm.py -v`
Expected: `10 passed`

- [ ] **Step 5: `ruff`/`mypy` 확인**

Run: `ruff check scripts/ tests/unit/test_setup_local_llm.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add scripts/setup_local_llm.py tests/unit/test_setup_local_llm.py
git commit -m "feat: 모델 다운로드 여부 확인과 pull 진행률 출력 추가"
```

---

### Task 5: `main()` 오케스트레이션

**Files:**
- Modify: `scripts/setup_local_llm.py`

이 단계는 실제 subprocess 실행과 `sys.exit`을 포함해 단위 테스트로 깔끔하게 감싸기 어렵다 — Task 1-4에서 만든 순수 로직만 조합하고, 실제 동작은 Task 9에서 수동으로 확인한다.

- [ ] **Step 1: `main()` 구현**

`scripts/setup_local_llm.py`의 import를 교체:

Replace:
```python
import shutil
import time
from collections.abc import Callable
from typing import Protocol

import httpx
```
with:
```python
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
```

파일 맨 아래에 추가:

```python
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
    if is_model_pulled(client, settings.llm_model):
        print(f"모델이 이미 받아져 있습니다: {settings.llm_model}")
        return 0

    print(f"모델 다운로드 중: {settings.llm_model} (수 GB, 몇 분 걸릴 수 있습니다)")
    pull_model(client, settings.llm_model)
    print("완료.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 전체 테스트 재확인 (기존 로직 안 깨졌는지)**

Run: `pytest tests/unit/test_setup_local_llm.py -v`
Expected: `10 passed`

- [ ] **Step 3: `ruff`/`mypy` 확인**

Run: `ruff check scripts/`
Expected: `All checks passed!`

Run: `mypy scripts`
Expected: `Success` (참고: `CLAUDE.md`의 기존 `mypy app` 명령 범위엔 포함 안 되지만, 새 코드이므로 직접 확인)

- [ ] **Step 4: Commit**

```bash
git add scripts/setup_local_llm.py
git commit -m "feat: Ollama 설치·모델 다운로드 오케스트레이션 스크립트 완성"
```

---

### Task 6: README — 네이티브 설치 단계에 스크립트 추가

**Files:**
- Modify: `README.md:109`

- [ ] **Step 1: 안내 문장 뒤에 실행 단계 추가**

Replace:
```markdown
`.env.example`을 `.env`로 복사하고 필요한 환경변수를 설정합니다. 로컬 Ollama 서버(`LLM_BASE_URL`)가 실행 중이어야 하며, 모델은 `ollama pull coolsoon/kanana-1.5-8b`로 미리 받아둬야 합니다. CPU 환경에서는 요청당 4~6분 정도 걸릴 수 있어 `LLM_TIMEOUT_SECONDS`를 넉넉히(기본 420초) 잡았습니다. `RESULT_FORWARD_ENDPOINT_URL`이 없어도 서버, `/health`, OFFLINE 로컬 분석과 테스트는 동작합니다.
```
with:
```markdown
`.env.example`을 `.env`로 복사하고 필요한 환경변수를 설정합니다. 아래 스크립트를 실행하면 Ollama가 없을 때 자동으로 설치하고(Windows: winget, macOS/Linux: 공식 설치 스크립트), `LLM_MODEL`에 설정된 모델(기본 `coolsoon/kanana-1.5-8b`)을 없으면 자동으로 받아옵니다. 이미 설치·다운로드돼 있으면 건너뜁니다.

```bash
python scripts/setup_local_llm.py
```

CPU 환경에서는 요청당 4~6분 정도 걸릴 수 있어 `LLM_TIMEOUT_SECONDS`를 넉넉히(기본 420초) 잡았습니다. `RESULT_FORWARD_ENDPOINT_URL`이 없어도 서버, `/health`, OFFLINE 로컬 분석과 테스트는 동작합니다.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README에 Ollama 자동 설치 스크립트 안내 추가"
```

---

### Task 7: `docker-compose.yml` — Ollama 서비스와 모델 자동 다운로드

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: 전체 파일 교체**

Replace the whole file:
```yaml
services:
  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama_data:/root/.ollama
    ports:
      - "127.0.0.1:11434:11434"
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 5s
      timeout: 5s
      retries: 20
    restart: unless-stopped

  model-init:
    image: ollama/ollama:latest
    depends_on:
      ollama:
        condition: service_healthy
    entrypoint: ["ollama", "pull", "${LLM_MODEL:-coolsoon/kanana-1.5-8b}"]
    environment:
      - OLLAMA_HOST=http://ollama:11434

  api:
    build: .
    env_file:
      - .env
    environment:
      - LLM_BASE_URL=http://ollama:11434
    depends_on:
      model-init:
        condition: service_completed_successfully
    ports:
      - "127.0.0.1:8000:8000"
    restart: unless-stopped

volumes:
  ollama_data:
```

- [ ] **Step 2: YAML 문법만 검증(Docker 없이도 가능)**

Run: `python -c "import yaml; yaml.safe_load(open('docker-compose.yml', encoding='utf-8')); print('valid yaml')"`
Expected: `valid yaml`
(만약 `yaml` 모듈이 없으면 `pip install pyyaml`로 임시 설치 후 확인해도 되고, 최종적으로 실제 `docker compose config` 검증은 Task 9에서 Docker가 있는 환경에 안내)

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: docker-compose에 Ollama 서비스와 모델 자동 다운로드 추가"
```

---

### Task 8: README — Docker 섹션 추가

**Files:**
- Modify: `README.md`

지금 README엔 Docker 관련 섹션이 아예 없다. "실행과 API 호출" 섹션 뒤, "로컬 디버깅 순서" 섹션 앞에 새로 추가한다.

- [ ] **Step 1: 새 섹션 삽입**

Replace:
```markdown
Swagger는 http://127.0.0.1:8000/docs 에서 확인합니다.

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/anomalies/analyze" \
  -H "Content-Type: application/json" \
  --data-binary "@samples/no_usage_request.json"
```

## 로컬 디버깅 순서
```
with:
```markdown
Swagger는 http://127.0.0.1:8000/docs 에서 확인합니다.

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/anomalies/analyze" \
  -H "Content-Type: application/json" \
  --data-binary "@samples/no_usage_request.json"
```

## Docker

```bash
cp .env.example .env
docker compose up --build
```

`ollama` 서비스가 뜨고, `model-init` 서비스가 `LLM_MODEL`에 설정된 모델을 자동으로 pull한 뒤 종료되면 그때 `api` 서비스가 시작됩니다. 최초 실행 시 모델 다운로드 때문에 몇 분 걸릴 수 있습니다. 모델은 `ollama_data` 볼륨에 저장되므로 `docker compose down` 후 다시 올려도 재다운로드하지 않습니다(볼륨을 지우지 않는 한).

## 로컬 디버깅 순서
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README에 Docker 실행 섹션 추가"
```

---

### Task 9: 최종 검증

**Files:** 없음(검증만)

- [ ] **Step 1: 전체 테스트**

Run: `pytest`
Expected: 전부 통과 (기존 22개 + 새로 추가된 10개 = 32 passed 근처)

- [ ] **Step 2: 린트/포맷/타입**

Run: `ruff check .`
Expected: `All checks passed!`

Run: `ruff format --check .`
Expected: 포맷 문제 없음

Run: `mypy app`
Expected: `Success: no issues found in N source files`

- [ ] **Step 3: 네이티브 스크립트 실제 실행 (수동 확인)**

Run: `python scripts/setup_local_llm.py`
Expected: 이 개발 머신엔 이미 Ollama와 `coolsoon/kanana-1.5-8b`가 있으므로 "Ollama가 이미 설치되어 있습니다."와 "모델이 이미 받아져 있습니다: coolsoon/kanana-1.5-8b" 출력, 종료 코드 0. (새 환경에서의 실제 설치 경로는 이 머신에서 검증 불가 — 리스크로 남김)

- [ ] **Step 4: Docker Compose 검증 (Docker 있는 환경에서만 가능)**

이 개발 머신엔 Docker가 없어 직접 실행할 수 없다. Docker가 설치된 환경에서 다음을 확인한다:

```bash
docker compose config
docker compose up --build
```

Expected: `ollama` → `model-init`(모델 pull 후 종료) → `api` 순서로 뜨고, `curl http://127.0.0.1:8000/health`가 `{"status":"UP",...}`를 반환.

- [ ] **Step 5: 최종 Commit (필요 시)**

이전 단계에서 발견된 문제를 고쳤다면:

```bash
git add -A
git commit -m "fix: 최종 검증 중 발견된 문제 수정"
```

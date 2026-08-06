# Ollama + Kanana 자동 설치 설계

## 배경

CareSignal API는 로컬 Ollama 서버(Kanana 1.5 8B 모델)에 의존한다. 지금까지는 개발자가 직접 `winget install Ollama.Ollama`, `ollama pull coolsoon/kanana-1.5-8b` 같은 명령을 수동으로 실행해야 했다. 프로젝트를 처음 clone하는 사람(팀원, 대회 심사자)이 이 과정을 자동으로 거치도록 만든다.

범위는 두 가지다: (1) 네이티브(venv) 개발 환경, (2) Docker 환경. 둘 다 지금은 Ollama 설치·모델 준비가 수동이거나(네이티브), 아예 연결이 깨져 있다(Docker — 컨테이너가 호스트의 `localhost:11434`에 도달할 수 없음).

## 목표

- 네이티브 환경: 새 스크립트 실행 한 번으로 Ollama 설치 + Kanana 모델 다운로드까지 끝남
- Docker 환경: `docker compose up` 한 번으로 Ollama 컨테이너가 뜨고 모델까지 자동으로 받아진 뒤 API가 기동됨
- 이미 설치·다운로드된 경우 중복 작업 없이 스킵(멱등성)
- Windows/macOS/Linux 크로스플랫폼 지원

## 비목표

- GPU 가속 설정은 다루지 않는다(현재 CPU 전용 전제 유지)
- Ollama 자체의 업데이트/버전 관리는 다루지 않는다(최초 설치만)
- CI 파이프라인 구성은 다루지 않는다(로컬 개발 환경 한정)

## 1. 네이티브 설치 스크립트 (`scripts/setup_local_llm.py`)

### 흐름

```
1. platform.system()으로 OS 판별 (Windows / Darwin / Linux)
2. shutil.which("ollama")로 설치 여부 확인
   → 있으면 2번 생략
3. 없으면 OS별 공식 설치 명령 실행:
   - Windows: winget install --id Ollama.Ollama --accept-package-agreements --accept-source-agreements --silent
   - macOS: brew가 있으면 `brew install ollama`, 없으면 공식 curl 스크립트로 폴백
   - Linux: curl -fsSL https://ollama.com/install.sh | sh
4. http://localhost:11434 에 짧은 간격으로 폴링(예: 최대 30초) → 응답 없으면
   "Ollama 설치는 됐지만 서버가 응답하지 않습니다. 직접 실행 후 스크립트를 다시 실행하세요"
   안내 후 종료 코드 1
5. app.core.config.get_settings().llm_model 값을 읽어 `ollama list`에 이미 있는지 확인
   → 있으면 6번 생략
6. `ollama pull <model>`을 subprocess로 실행하며 stdout/stderr를 그대로 스트리밍(진행률 표시)
```

### 오류 처리

- winget/brew/curl 명령 자체가 없는 환경(예: winget 없는 구버전 Windows, Homebrew 없고 curl도 없는 극단적 macOS)에서는 설치를 시도하지 않고, 공식 다운로드 페이지 링크(https://ollama.com/download)를 안내하고 종료 코드 1로 종료한다.
- 설치·다운로드 도중 실패(네트워크 오류 등)는 예외를 그대로 노출하지 않고, 어떤 단계에서 실패했는지와 재시도 방법(스크립트 재실행)을 안내한다.

### 이 스크립트가 하지 않는 일

- `pip install -e ".[dev]"`에 자동으로 엮이지 않는다. README에 별도 단계로 안내되는 명시적 실행 스크립트다.
- 기존 `Settings`/`.env` 로직을 변경하지 않는다. 오직 `llm_model` 값을 읽기만 한다.

## 2. Docker 환경 (`docker-compose.yml`)

### 서비스 구성

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama_data:/root/.ollama
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

### 핵심 포인트

- `ollama_data` 볼륨으로 모델을 영구 저장 — `docker compose down && docker compose up`을 반복해도 재다운로드하지 않는다(볼륨을 지우지 않는 한).
- `model-init`은 모델을 받기만 하고 종료되는 1회성 컨테이너다. `api`는 이게 성공적으로 끝난 뒤에만 뜬다(`service_completed_successfully`는 Compose v2.20+ 필요 — 이미 현재 환경에서 쓰는 Compose 버전이 이를 지원하는지 구현 단계에서 확인).
- `api`의 `LLM_BASE_URL`은 `.env`에 뭐라고 적혀있든(`localhost` 등) `environment:`가 우선하므로 항상 `http://ollama:11434`로 강제된다. 네이티브용 `.env`를 Docker용으로 따로 관리할 필요가 없다.
- `LLM_MODEL` 환경변수가 `.env`에 설정돼 있으면 `model-init`도 같은 값을 pull한다(기본값은 현재 코드 기본값과 동일한 `coolsoon/kanana-1.5-8b`로 맞춤).

## 3. README 갱신

- "설치" 섹션에 `python scripts/setup_local_llm.py` 실행 단계 추가(venv 활성화 이후, 서버 실행 이전)
- "Docker" 섹션에 "Ollama와 모델 다운로드가 `docker compose up` 한 번으로 자동 처리됨" 안내 추가, 최초 실행 시 모델 다운로드로 몇 분 걸릴 수 있다는 점 명시

## 리스크 및 확인 필요 사항

- Compose의 `service_completed_successfully` 조건은 비교적 최근 기능이라, 구현 단계에서 실제 설치된 Docker Compose 버전이 지원하는지 확인이 필요하다. 지원 안 하면 `depends_on: condition: service_healthy` + `api` 쪽에서 연결 재시도로 대체해야 한다.
- macOS의 Ollama 공식 설치 방법(Homebrew 공식 지원 여부, curl 스크립트가 macOS도 커버하는지)은 이 문서 작성 시점에 확실히 검증되지 않았다 — 구현 단계에서 공식 문서로 재확인 필요.

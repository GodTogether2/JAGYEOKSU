#!/usr/bin/env bash
# 가상환경을 활성화하고 개발 서버를 실행한다.
# 처음 설정할 때는 먼저 scripts/setup.sh를 실행해야 한다.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
    echo "'.venv'가 없습니다. 먼저 다음을 실행하세요: bash scripts/setup.sh"
    exit 1
fi

source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate

uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

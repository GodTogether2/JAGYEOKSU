#!/usr/bin/env bash
# 저장소를 처음 clone한 사람을 위한 전체 초기 설정 스크립트.
# venv 생성 -> 의존성 설치 -> .env 설정 -> Ollama/LLM 모델 자동 설치 -> 샘플 데이터 생성까지 수행한다.
# 서버는 실행하지 않는다 -- 서버 실행은 scripts/run_server.sh를 사용한다.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[1/5] Python 가상환경 준비..."
if [ ! -d ".venv" ]; then
    python -m venv .venv
else
    echo "  .venv가 이미 있어 건너뜁니다."
fi

echo "[2/5] 가상환경 활성화 및 의존성 설치..."
source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate
pip install -e ".[dev]"

echo "[3/5] .env 파일 준비..."
if [ ! -f ".env" ]; then
    cp .env.example .env
else
    echo "  .env가 이미 있어 건너뜁니다."
fi

echo "[4/5] Ollama 및 LLM 모델 자동 설치 (없을 때만 설치·다운로드합니다)..."
python scripts/setup_local_llm.py

echo "[5/5] 샘플 요청 데이터 생성..."
python scripts/generate_sample_data.py

echo ""
echo "설정 완료. 서버를 실행하려면 다음을 실행하세요:"
echo "  bash scripts/run_server.sh"

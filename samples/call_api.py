"""샘플 JSON을 httpx로 전송하는 비동기 클라이언트."""

import asyncio
import json
from pathlib import Path

import httpx


async def main() -> None:
    """27시간 무사용 합성 샘플을 로컬 API에 전송한다."""
    sample = json.loads((Path(__file__).parent / "no_usage_request.json").read_text())
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post("http://127.0.0.1:8000/api/v1/anomalies/analyze", json=sample)
        response.raise_for_status()
        print(json.dumps(response.json(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

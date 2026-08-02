"""FastAPI 전 구간 통합 테스트."""

from fastapi.testclient import TestClient

from app.api.dependencies import get_local_llm_connector
from app.main import app
from tests.conftest import FakeLLMConnector


def test_health_and_swagger() -> None:
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert "llm_configured" in client.get("/health").json()
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").json()["info"]["title"] == "CareSignal API"


def test_normal_analysis_with_fake(request_factory) -> None:
    app.dependency_overrides[get_local_llm_connector] = lambda: FakeLLMConnector()
    try:
        response = TestClient(app).post(
            "/api/v1/anomalies/analyze", json=request_factory().model_dump(mode="json")
        )
        assert response.status_code == 200
        assert response.json()["status"] == "NORMAL"
    finally:
        app.dependency_overrides.clear()


def test_input_422(request_factory) -> None:
    payload = request_factory().model_dump(mode="json")
    payload["household_id"] = "실명"
    assert TestClient(app).post("/api/v1/anomalies/analyze", json=payload).status_code == 422


def test_offline_without_llm_call(request_factory) -> None:
    payload = request_factory(meter_status="OFFLINE").model_dump(mode="json")
    response = TestClient(app).post("/api/v1/anomalies/analyze", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "DATA_ERROR"

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_health_reports_api_status():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "FraudLens", "model_status": "unavailable"}


def test_local_frontend_cors():
    response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_other_origin_is_not_allowed():
    response = client.get("/api/health", headers={"Origin": "https://example.com"})
    assert "access-control-allow-origin" not in response.headers

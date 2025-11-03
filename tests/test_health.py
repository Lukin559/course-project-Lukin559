from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "task-tracker"
    assert "correlation_id" in body
    # Also check header
    assert "X-Correlation-ID" in r.headers

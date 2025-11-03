from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_not_found_item():
    r = client.get("/items/999")
    assert r.status_code == 404
    body = r.json()
    # RFC 7807 format
    assert "type" in body and "not_found" in body["type"]
    assert body["status"] == 404
    assert body["detail"] == "item not found"
    assert "correlation_id" in body


def test_validation_error():
    r = client.post("/items", json={"name": ""})
    assert r.status_code == 422
    body = r.json()
    # RFC 7807 format
    assert "type" in body and "validation" in body["type"].lower()
    assert body["status"] == 422
    assert "correlation_id" in body

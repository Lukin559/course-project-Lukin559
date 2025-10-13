from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_rate_limiting_health_endpoint():
    """Test rate limiting on health endpoint"""
    # Make requests up to the limit
    for i in range(100):
        response = client.get("/health")
        assert response.status_code == 200

    # This request should be rate limited
    response = client.get("/health")
    assert response.status_code == 429  # Too Many Requests


def test_rate_limiting_create_item():
    """Test rate limiting on create item endpoint"""
    # Make requests up to the limit
    for i in range(200):
        response = client.post("/items", params={"name": f"Task {i}"})
        assert response.status_code == 201

    # This request should be rate limited
    response = client.post("/items", params={"name": "Rate Limited Task"})
    assert response.status_code == 429  # Too Many Requests


def test_rate_limiting_get_item():
    """Test rate limiting on get item endpoint"""
    # First create an item
    create_response = client.post("/items", params={"name": "Test Task"})
    item_id = create_response.json()["id"]

    # Make requests up to the limit
    for i in range(300):
        response = client.get(f"/items/{item_id}")
        assert response.status_code == 200

    # This request should be rate limited
    response = client.get(f"/items/{item_id}")
    assert response.status_code == 429  # Too Many Requests


def test_rate_limiting_different_endpoints():
    """Test that rate limiting is per endpoint"""
    # Exhaust health endpoint limit
    for i in range(100):
        response = client.get("/health")
        assert response.status_code == 200

    # Health should be rate limited
    response = client.get("/health")
    assert response.status_code == 429

    # But create item should still work
    response = client.post("/items", params={"name": "Still Working"})
    assert response.status_code == 201


def test_rate_limiting_error_response():
    """Test that rate limiting returns proper error response"""
    # Exhaust the limit
    for i in range(100):
        response = client.get("/health")
        assert response.status_code == 200

    # Check rate limit error response
    response = client.get("/health")
    assert response.status_code == 429
    assert "detail" in response.json()
    assert "rate limit" in response.json()["detail"].lower()

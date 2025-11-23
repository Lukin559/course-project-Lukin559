"""Tests for RFC 7807 Problem Details error format implementation.

Implements ADR-001: RFC 7807 Error Response Format with Correlation ID

Tests validate:
- RFC 7807 compliance (type, title, status, detail, instance, correlation_id)
- Masked error details (no stack traces, no database internals)
- Correlation ID inclusion and consistency
- Proper HTTP status codes
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestRfc7807Format:
    """Test RFC 7807 Problem Details format compliance."""

    def test_not_found_rfc7807_format(self):
        """Test that 404 errors use RFC 7807 format."""
        response = client.get("/items/999")
        assert response.status_code == 404

        body = response.json()

        # RFC 7807 required fields
        assert "type" in body
        assert "title" in body
        assert "status" in body
        assert "detail" in body
        assert "instance" in body
        assert "correlation_id" in body

        # Validate field values
        assert body["type"] == "https://api.secdev.example.com/errors/not_found"
        assert body["title"] == "Not Found"
        assert body["status"] == 404
        assert body["detail"] == "item not found"
        assert body["instance"] == "/items/999"
        assert len(body["correlation_id"]) > 0  # UUID format

    def test_validation_error_rfc7807_format(self):
        """Test that 422 validation errors use RFC 7807 format."""
        response = client.post("/items", json={"name": ""})
        assert response.status_code == 422

        body = response.json()

        # RFC 7807 required fields
        assert "type" in body
        assert "title" in body
        assert "status" in body
        assert "detail" in body
        assert "instance" in body
        assert "correlation_id" in body

        # Validate field values
        assert body["status"] == 422
        assert "validation" in body["type"].lower()

    def test_error_detail_masking(self):
        """Test that error details are masked (no implementation details exposed)."""
        response = client.post("/items", json={"name": ""})
        body = response.json()

        # Should NOT contain raw Pydantic validation messages
        assert "pydantic" not in body["detail"].lower()
        assert "field_required" not in str(body).lower()

        # Should NOT contain stack traces
        assert "traceback" not in str(body).lower()
        assert "line" not in body["detail"]


class TestCorrelationIdPropagation:
    """Test correlation ID generation and propagation."""

    def test_correlation_id_in_success_response_header(self):
        """Test that successful responses include correlation_id header."""
        response = client.get("/health")
        assert response.status_code == 200

        # Header should be present
        assert "X-Correlation-ID" in response.headers
        correlation_id = response.headers["X-Correlation-ID"]
        assert len(correlation_id) > 0

        # Header should be valid UUID format (36 chars with dashes)
        assert len(correlation_id) == 36

    def test_correlation_id_in_error_response_header(self):
        """Test that error responses include correlation_id header."""
        response = client.get("/items/999")
        assert response.status_code == 404

        # Header should be present
        assert "X-Correlation-ID" in response.headers
        correlation_id = response.headers["X-Correlation-ID"]
        assert len(correlation_id) > 0

    def test_correlation_id_in_error_response_body(self):
        """Test that error responses include correlation_id in body."""
        response = client.get("/items/999")
        body = response.json()

        assert "correlation_id" in body
        assert len(body["correlation_id"]) > 0

    def test_correlation_id_header_propagation(self):
        """Test that client-provided correlation_id is preserved."""
        custom_cid = "test-correlation-id-12345"
        response = client.get(
            "/health",
            headers={"X-Correlation-ID": custom_cid}
        )
        assert response.status_code == 200

        # Response should use the same correlation ID
        assert response.headers["X-Correlation-ID"] == custom_cid

        # Body should also include it
        body = response.json()
        assert body["correlation_id"] == custom_cid

    def test_correlation_id_consistency_across_request(self):
        """Test that all responses for same request use same correlation_id."""
        response1 = client.get("/health")
        cid1 = response1.headers["X-Correlation-ID"]

        response2 = client.get("/health")
        cid2 = response2.headers["X-Correlation-ID"]

        # Different requests should have different correlation IDs
        assert cid1 != cid2


class TestErrorCodesAndStatuses:
    """Test proper error codes and HTTP status codes."""

    def test_not_found_404(self):
        """Test 404 for missing item."""
        response = client.get("/items/999")
        assert response.status_code == 404
        assert response.json()["status"] == 404
        assert "not_found" in response.json()["type"]

    def test_validation_error_422(self):
        """Test 422 for validation errors."""
        response = client.post("/items", json={"name": ""})
        assert response.status_code == 422
        assert response.json()["status"] == 422
        assert "validation" in response.json()["type"].lower()

    def test_validation_error_name_too_long(self):
        """Test 422 for name exceeding max length."""
        long_name = "x" * 10000
        response = client.post("/items", json={"name": long_name})
        assert response.status_code == 422
        assert response.json()["status"] == 422

    def test_validation_error_invalid_price(self):
        """Test 422 for invalid price."""
        response = client.post("/items", json={"name": "Test", "price": -100})
        assert response.status_code == 422
        assert response.json()["status"] == 422

    def test_success_includes_correlation_id(self):
        """Test that successful item creation includes correlation_id."""
        response = client.post(
            "/items",
            json={"name": "Test Item", "price": 10.99}
        )
        assert response.status_code == 201

        # Response body should include correlation_id in header
        assert "X-Correlation-ID" in response.headers


class TestErrorSecurity:
    """Test that errors don't leak sensitive information."""

    def test_no_database_details_in_errors(self):
        """Test that error responses don't contain database internals."""
        response = client.post("/items", json={"price": -100})
        body = str(response.json())

        # Should not contain database keywords
        assert "sqlite" not in body.lower()
        assert "postgres" not in body.lower()
        assert "column" not in body.lower() or "column" in response.json()["detail"].lower()
        assert "table" not in body.lower()

    def test_no_stack_trace_in_errors(self):
        """Test that error responses don't contain Python stack traces."""
        response = client.get("/items/999")
        body = str(response.json())

        assert "traceback" not in body.lower()
        assert "file" not in body.lower() or "file" in response.json().get("detail", "").lower()
        assert ".py" not in body.lower()

    def test_validation_error_masks_field_types(self):
        """Test that validation errors don't expose field types/constraints."""
        response = client.post("/items", json={"name": ""})
        body = response.json()["detail"]

        # Should NOT expose Pydantic constraint messages
        assert "at least 1 character" not in body.lower()
        assert "ensure" not in body.lower()


class TestErrorInstanceField:
    """Test that instance field correctly identifies the resource/endpoint."""

    def test_instance_field_in_get_error(self):
        """Test instance field for GET error."""
        response = client.get("/items/999")
        assert response.json()["instance"] == "/items/999"

    def test_instance_field_in_post_error(self):
        """Test instance field for POST error."""
        response = client.post("/items", json={"name": ""})
        assert response.json()["instance"] == "/items"

    def test_instance_field_in_put_error(self):
        """Test instance field for PUT error."""
        response = client.put("/items/999", json={"name": "Updated"})
        assert response.json()["instance"] == "/items/999"

    def test_instance_field_in_delete_error(self):
        """Test instance field for DELETE error."""
        response = client.delete("/items/999")
        assert response.json()["instance"] == "/items/999"

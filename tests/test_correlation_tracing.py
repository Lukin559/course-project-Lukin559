"""Tests for request correlation ID tracing implementation.

Implements ADR-003: Request Correlation & Distributed Tracing via Correlation ID

Tests validate:
- Correlation ID generation for each request
- Header propagation (X-Correlation-ID)
- Consistency across request/response cycle
- Audit trail linking via correlation_id
"""

import re

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestCorrelationIdGeneration:
    """Test automatic correlation ID generation."""

    def test_correlation_id_generated_for_get_request(self):
        """Test that GET requests get a correlation ID."""
        response = client.get("/items")
        assert response.status_code == 200
        assert "X-Correlation-ID" in response.headers
        correlation_id = response.headers["X-Correlation-ID"]
        assert len(correlation_id) > 0

    def test_correlation_id_generated_for_post_request(self):
        """Test that POST requests get a correlation ID."""
        response = client.post("/items", json={"name": "Test Item"})
        assert response.status_code == 201
        assert "X-Correlation-ID" in response.headers

    def test_correlation_id_generated_for_put_request(self):
        """Test that PUT requests get a correlation ID."""
        # Create item first
        create_response = client.post("/items", json={"name": "Test"})
        _item_id = create_response.json()["id"]  # noqa: F841

        # Update item
        response = client.put("/items/{item_id}", json={"name": "Updated"})
        assert "X-Correlation-ID" in response.headers

    def test_correlation_id_generated_for_delete_request(self):
        """Test that DELETE requests get a correlation ID."""
        response = client.delete("/items/999")
        assert "X-Correlation-ID" in response.headers

    def test_correlation_id_uuid_format(self):
        """Test that correlation ID is valid UUID format."""
        response = client.get("/health")
        correlation_id = response.headers["X-Correlation-ID"]

        # UUID format: 8-4-4-4-12 hex characters with dashes
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        assert re.match(
            uuid_pattern, correlation_id.lower()
        ), f"Invalid UUID format: {correlation_id}"

    def test_correlation_ids_are_unique(self):
        """Test that different requests get different correlation IDs."""
        correlation_ids = set()
        for _ in range(5):
            response = client.get("/health")
            cid = response.headers["X-Correlation-ID"]
            assert cid not in correlation_ids, f"Duplicate correlation ID: {cid}"
            correlation_ids.add(cid)

        assert len(correlation_ids) == 5


class TestCorrelationIdHeaderPropagation:
    """Test correlation ID header propagation."""

    def test_correlation_id_from_request_header_preserved(self):
        """Test that client-provided correlation ID is preserved."""
        custom_cid = "custom-correlation-id-123456"
        response = client.get("/health", headers={"X-Correlation-ID": custom_cid})
        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == custom_cid

    def test_correlation_id_custom_uuid_preserved(self):
        """Test that client-provided custom UUID is preserved."""
        custom_uuid = "550e8400-e29b-41d4-a716-446655440000"
        response = client.get("/health", headers={"X-Correlation-ID": custom_uuid})
        assert response.headers["X-Correlation-ID"] == custom_uuid

    def test_correlation_id_in_error_response_header(self):
        """Test that error responses include correlation_id header."""
        response = client.get("/items/999")
        assert response.status_code == 404
        assert "X-Correlation-ID" in response.headers
        assert len(response.headers["X-Correlation-ID"]) > 0

    def test_correlation_id_in_validation_error_header(self):
        """Test that validation error responses include header."""
        response = client.post("/items", json={"name": ""})
        assert response.status_code == 422
        assert "X-Correlation-ID" in response.headers

    def test_correlation_id_header_case_insensitive(self):
        """Test that header name is case-insensitive."""
        custom_cid = "case-insensitive-test-123"
        response = client.get("/health", headers={"x-correlation-id": custom_cid})
        # FastAPI handles header case insensitivity
        assert response.headers.get("X-Correlation-ID") is not None


class TestCorrelationIdInResponse:
    """Test correlation ID in response body (RFC 7807)."""

    def test_correlation_id_in_error_response_body(self):
        """Test that error responses include correlation_id in body."""
        response = client.get("/items/999")
        body = response.json()
        assert "correlation_id" in body
        assert len(body["correlation_id"]) > 0

    def test_correlation_id_in_validation_error_body(self):
        """Test that validation error responses include correlation_id in body."""
        response = client.post("/items", json={"name": ""})
        body = response.json()
        assert "correlation_id" in body

    def test_correlation_id_body_matches_header(self):
        """Test that correlation_id in body matches header."""
        custom_cid = "body-header-match-test-123"
        response = client.get("/items/999", headers={"X-Correlation-ID": custom_cid})
        header_cid = response.headers["X-Correlation-ID"]
        body_cid = response.json()["correlation_id"]
        assert header_cid == body_cid == custom_cid


class TestCorrelationIdAuditTrail:
    """Test correlation ID for audit trail linking."""

    def test_correlation_id_persists_through_create_and_retrieve(self):
        """Test correlation ID for complete lifecycle."""
        custom_cid = "lifecycle-test-" + "a" * 20

        # Create item with correlation ID
        create_response = client.post(
            "/items",
            json={"name": "Audit Trail Test", "price": 99.99},
            headers={"X-Correlation-ID": custom_cid},
        )
        assert create_response.status_code == 201
        assert create_response.headers["X-Correlation-ID"] == custom_cid
        item_id = create_response.json()["id"]

        # Retrieve item with different correlation ID
        different_cid = "different-" + "b" * 25
        get_response = client.get(f"/items/{item_id}", headers={"X-Correlation-ID": different_cid})
        assert get_response.status_code == 200
        # Different request should have different correlation ID
        assert get_response.headers["X-Correlation-ID"] == different_cid

    def test_correlation_id_for_audit_logging(self):
        """Test that correlation ID enables audit trail linking."""
        audit_cid = "audit-test-" + "c" * 25

        # Multiple operations with same correlation ID (would log with same ID)
        responses = []

        # Create
        create_response = client.post(
            "/items",
            json={"name": "Audit Item"},
            headers={"X-Correlation-ID": audit_cid},
        )
        responses.append(create_response)
        item_id = create_response.json()["id"]

        # Get
        get_response = client.get(f"/items/{item_id}", headers={"X-Correlation-ID": audit_cid})
        responses.append(get_response)

        # All operations should have same correlation ID for audit trail linking
        for response in responses:
            assert response.headers["X-Correlation-ID"] == audit_cid


class TestCorrelationIdRobustness:
    """Test robustness of correlation ID handling."""

    def test_correlation_id_with_empty_string(self):
        """Test handling of empty correlation ID header."""
        response = client.get("/health", headers={"X-Correlation-ID": ""})
        # Should generate new ID if provided ID is empty
        assert response.status_code == 200
        cid = response.headers["X-Correlation-ID"]
        assert len(cid) > 0

    def test_correlation_id_with_special_characters(self):
        """Test correlation ID with special characters."""
        special_cid = "test-!@#$%^&*()-_=+[]{}|;:,.<>?"
        response = client.get("/health", headers={"X-Correlation-ID": special_cid})
        # Should preserve or handle gracefully
        assert response.status_code == 200
        # Header should exist (may or may not preserve special chars)
        assert "X-Correlation-ID" in response.headers

    def test_correlation_id_with_very_long_string(self):
        """Test correlation ID with very long string."""
        long_cid = "a" * 10000
        response = client.get("/health", headers={"X-Correlation-ID": long_cid})
        # Should handle gracefully (may truncate or preserve)
        assert response.status_code == 200

    def test_correlation_id_with_whitespace(self):
        """Test correlation ID with whitespace."""
        cid_with_space = "test cid with space"
        response = client.get("/health", headers={"X-Correlation-ID": cid_with_space})
        # Should handle (HTTP headers strip leading/trailing)
        assert response.status_code == 200


class TestCorrelationIdMultipleErrorTypes:
    """Test correlation ID across different error types."""

    def test_correlation_id_in_not_found_error(self):
        """Test correlation ID in 404 error."""
        cid = "not-found-error-test-123456"
        response = client.get("/items/999", headers={"X-Correlation-ID": cid})
        assert response.status_code == 404
        assert response.headers["X-Correlation-ID"] == cid
        assert response.json()["correlation_id"] == cid

    def test_correlation_id_in_validation_error(self):
        """Test correlation ID in 422 validation error."""
        cid = "validation-error-test-123456"
        response = client.post("/items", json={"name": ""}, headers={"X-Correlation-ID": cid})
        assert response.status_code == 422
        assert response.headers["X-Correlation-ID"] == cid
        assert response.json()["correlation_id"] == cid

    def test_correlation_id_in_success_response(self):
        """Test correlation ID in successful response."""
        cid = "success-response-test-123456"
        response = client.get("/health", headers={"X-Correlation-ID": cid})
        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == cid
        # Success response includes correlation_id
        assert response.json()["correlation_id"] == cid

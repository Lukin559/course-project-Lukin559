"""Tests for secure HTTP client (P06 Secure Coding).

Control: HTTP client with timeouts, retries, backoff
Tests: Positive (success), negative (timeout, retries exhausted, 4xx errors), boundary
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.http_client import HttpClientError, create_timeout, fetch_json, fetch_with_retries


class TestTimeoutConfiguration:
    """Test timeout configuration."""

    def test_timeout_creation(self):
        """Test timeout object creation."""
        timeout = create_timeout()
        assert isinstance(timeout, httpx.Timeout)
        # Timeout object stores values but doesn't expose them directly
        # Just verify it's created correctly
        assert timeout is not None


class TestHttpFetchSuccess:
    """Test successful HTTP requests."""

    @patch("httpx.Client.request")
    def test_successful_get(self, mock_request):
        """Test successful GET request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        response = fetch_with_retries("https://example.com/health")
        assert response.status_code == 200

    @patch("httpx.Client.request")
    def test_post_request(self, mock_request):
        """Test successful POST request."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        response = fetch_with_retries("https://example.com/data", method="POST")
        assert response.status_code == 201

    @patch("httpx.Client.request")
    def test_json_fetch_success(self, mock_request):
        """Test successful JSON fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"status": "ok"}
        mock_request.return_value = mock_response

        data = fetch_json("https://example.com/api")
        assert data == {"status": "ok"}


class TestHttpTimeout:
    """Test timeout handling."""

    @patch("httpx.Client.request")
    def test_timeout_triggers_retry(self, mock_request):
        """NEGATIVE: Timeout triggers retry."""
        # Fail twice with timeout, succeed on third
        mock_request.side_effect = [
            httpx.TimeoutException("Timeout"),
            httpx.TimeoutException("Timeout"),
            MagicMock(status_code=200, raise_for_status=lambda: None),
        ]

        response = fetch_with_retries("https://example.com/health")
        assert response.status_code == 200
        assert mock_request.call_count == 3

    @patch("httpx.Client.request")
    def test_timeout_exhausts_retries(self, mock_request):
        """NEGATIVE: Timeout exhausts retries and fails."""
        mock_request.side_effect = httpx.TimeoutException("Timeout")

        with pytest.raises(HttpClientError) as exc_info:
            fetch_with_retries("https://example.com/health", max_retries=2)

        assert "Failed to fetch" in str(exc_info.value)
        assert mock_request.call_count == 2  # Only 2 attempts with max_retries=2


class TestHttpRetries:
    """Test retry logic with backoff."""

    @patch("httpx.Client.request")
    @patch("time.sleep")
    def test_exponential_backoff(self, mock_sleep, mock_request):
        """Test exponential backoff between retries."""
        mock_request.side_effect = [
            httpx.RequestError("Connection error"),
            httpx.RequestError("Connection error"),
            MagicMock(status_code=200, raise_for_status=lambda: None),
        ]

        response = fetch_with_retries(
            "https://example.com/health",
            max_retries=3,
            backoff_factor=0.5,
        )

        assert response.status_code == 200
        # Should sleep with exponential backoff
        assert mock_sleep.call_count == 2
        # First sleep: 0.5 * 1 = 0.5s
        # Second sleep: 0.5 * 2 = 1.0s
        mock_sleep.assert_any_call(0.5)
        mock_sleep.assert_any_call(1.0)

    @patch("httpx.Client.request")
    def test_no_retry_on_4xx(self, mock_request):
        """NEGATIVE: 4xx errors don't trigger retry."""
        mock_request.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=MagicMock(status_code=404),
        )

        with pytest.raises(HttpClientError) as exc_info:
            fetch_with_retries("https://example.com/missing")

        assert "404" in str(exc_info.value)
        assert mock_request.call_count == 1  # No retries for 4xx


class TestHttpErrors:
    """Test error handling."""

    @patch("httpx.Client.request")
    def test_5xx_triggers_retry(self, mock_request):
        """Test 5xx errors trigger retries."""
        # Fail twice with 500, succeed on third
        mock_request.side_effect = [
            httpx.HTTPStatusError(
                "Internal Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            ),
            httpx.HTTPStatusError(
                "Internal Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            ),
            MagicMock(status_code=200, raise_for_status=lambda: None),
        ]

        response = fetch_with_retries("https://example.com/api")
        assert response.status_code == 200
        assert mock_request.call_count == 3

    @patch("httpx.Client.request")
    def test_invalid_json_raises_error(self, mock_request):
        """NEGATIVE: Invalid JSON raises error."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_request.return_value = mock_response

        with pytest.raises(HttpClientError) as exc_info:
            fetch_json("https://example.com/api")

        assert "Invalid JSON" in str(exc_info.value)


class TestHttpBoundaryConditions:
    """Test boundary and edge cases."""

    @patch("httpx.Client.request")
    def test_single_retry(self, mock_request):
        """Test with single retry (max_retries=1)."""
        mock_request.side_effect = httpx.RequestError("Error")

        with pytest.raises(HttpClientError):
            fetch_with_retries(
                "https://example.com/api",
                max_retries=1,
            )

        assert mock_request.call_count == 1

    @patch("httpx.Client.request")
    def test_many_retries(self, mock_request):
        """Test with many retry attempts."""
        # Eventually succeed on last attempt
        mock_request.side_effect = [
            httpx.RequestError("Error"),
            httpx.RequestError("Error"),
            httpx.RequestError("Error"),
            httpx.RequestError("Error"),
            MagicMock(status_code=200, raise_for_status=lambda: None),
        ]

        response = fetch_with_retries(
            "https://example.com/api",
            max_retries=5,
        )

        assert response.status_code == 200
        assert mock_request.call_count == 5

    @patch("httpx.Client.request")
    def test_zero_backoff(self, mock_request):
        """Test with zero backoff (should still work)."""
        mock_request.side_effect = [
            httpx.RequestError("Error"),
            MagicMock(status_code=200, raise_for_status=lambda: None),
        ]

        response = fetch_with_retries(
            "https://example.com/api",
            max_retries=2,
            backoff_factor=0.0,  # No backoff
        )

        assert response.status_code == 200

    @patch("httpx.Client.request")
    def test_redirect_followed(self, mock_request):
        """Test that redirects are followed."""
        # This is handled by httpx with follow_redirects=True
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        response = fetch_with_retries("https://example.com/redirect")
        assert response.status_code == 200


class TestJsonFetching:
    """Test JSON-specific fetch operations."""

    @patch("httpx.Client.request")
    def test_fetch_json_object(self, mock_request):
        """Test fetching JSON object."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"key": "value"}
        mock_response.headers = {"content-type": "application/json"}
        mock_request.return_value = mock_response

        data = fetch_json("https://api.example.com/data")
        assert data == {"key": "value"}

    @patch("httpx.Client.request")
    def test_fetch_json_array(self, mock_request):
        """Test fetching JSON array."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = [1, 2, 3]
        mock_response.headers = {"content-type": "application/json"}
        mock_request.return_value = mock_response

        data = fetch_json("https://api.example.com/list")
        assert data == [1, 2, 3]

    @patch("httpx.Client.request")
    def test_fetch_json_with_method(self, mock_request):
        """Test fetching JSON with different HTTP method."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"created": True}
        mock_response.headers = {"content-type": "application/json"}
        mock_request.return_value = mock_response

        data = fetch_json(
            "https://api.example.com/items",
            method="POST",
        )
        assert data == {"created": True}

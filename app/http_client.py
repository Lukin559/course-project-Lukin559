"""Secure HTTP client with timeouts and retries (P06 Secure Coding).

Control: Безопасный HTTP-клиент (таймауты, ретраи, лимиты)
Related: NFR-001 (performance), R002 (DoS prevention)
"""

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Security settings
CONNECT_TIMEOUT = 3.0  # Connection timeout
READ_TIMEOUT = 5.0  # Read timeout
WRITE_TIMEOUT = 5.0  # Write timeout
POOL_TIMEOUT = 2.0  # Connection pool timeout

MAX_RETRIES = 3
RETRY_BACKOFF = 0.5  # Exponential backoff: 0.5s, 1.0s, 1.5s


class HttpClientError(Exception):
    """HTTP client error (safe for logging)."""

    pass


def create_timeout() -> httpx.Timeout:
    """Create timeout configuration for HTTP requests.

    Security: Prevents indefinite hangs and resource exhaustion.
    """
    return httpx.Timeout(
        timeout=READ_TIMEOUT,
        connect=CONNECT_TIMEOUT,
        write=WRITE_TIMEOUT,
        pool=POOL_TIMEOUT,
    )


def fetch_with_retries(
    url: str,
    method: str = "GET",
    max_retries: int = MAX_RETRIES,
    backoff_factor: float = RETRY_BACKOFF,
    **kwargs,
) -> httpx.Response:
    """Fetch URL with automatic retries and exponential backoff.

    Args:
        url: URL to fetch
        method: HTTP method (GET, POST, etc.)
        max_retries: Maximum retry attempts
        backoff_factor: Exponential backoff multiplier
        **kwargs: Additional httpx.Client arguments

    Returns:
        Response object

    Raises:
        HttpClientError: If all retries exhausted

    Security:
        - Timeout prevents hanging
        - Exponential backoff prevents thundering herd
        - Maximum retries prevents infinite loops
    """
    timeout = create_timeout()
    last_exception = None

    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=timeout, **kwargs) as client:
                logger.debug(f"HTTP {method} request", extra={"url": url, "attempt": attempt + 1})

                response = client.request(
                    method=method,
                    url=url,
                    follow_redirects=True,
                )

                # Raise on 4xx/5xx
                response.raise_for_status()

                logger.info(
                    f"HTTP {method} success",
                    extra={"url": url, "status": response.status_code},
                )
                return response

        except httpx.TimeoutException as e:
            last_exception = e
            logger.warning(
                f"HTTP timeout (attempt {attempt + 1}/{max_retries})",
                extra={"url": url, "error": "timeout"},
            )

        except httpx.HTTPStatusError as e:
            # Don't retry on 4xx (client errors)
            if 400 <= e.response.status_code < 500:
                logger.error(
                    f"HTTP {e.response.status_code} error",
                    extra={"url": url, "status": e.response.status_code},
                )
                raise HttpClientError(f"HTTP {e.response.status_code}") from e

            # Retry on 5xx
            last_exception = e
            logger.warning(
                f"HTTP {e.response.status_code} (attempt {attempt + 1}/{max_retries})",
                extra={"url": url, "status": e.response.status_code},
            )

        except httpx.RequestError as e:
            last_exception = e
            logger.warning(
                f"HTTP request failed (attempt {attempt + 1}/{max_retries})",
                extra={"url": url, "error": str(e)[:100]},  # Truncate for logs
            )

        # Exponential backoff
        if attempt < max_retries - 1:
            wait_time = backoff_factor * (attempt + 1)
            logger.debug(f"Retrying in {wait_time}s...")
            time.sleep(wait_time)

    # All retries exhausted
    error_msg = f"Failed to fetch {url} after {max_retries} attempts"
    logger.error(error_msg, extra={"url": url, "max_retries": max_retries})
    raise HttpClientError(error_msg) from last_exception


def fetch_json(
    url: str,
    method: str = "GET",
    **kwargs,
) -> Any:
    """Fetch JSON from URL with retries.

    Args:
        url: URL to fetch
        method: HTTP method
        **kwargs: Additional arguments for fetch_with_retries

    Returns:
        Parsed JSON data

    Raises:
        HttpClientError: If fetch or parse fails
    """
    try:
        response = fetch_with_retries(url, method=method, **kwargs)
        data = response.json()
        logger.debug(
            "JSON parsed successfully",
            extra={"url": url, "content_type": response.headers.get("content-type")},
        )
        return data
    except ValueError as e:
        logger.error("JSON parse failed", extra={"url": url, "error": "invalid_json"})
        raise HttpClientError(f"Invalid JSON from {url}") from e

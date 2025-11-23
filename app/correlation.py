"""Request correlation context management for distributed tracing."""

import contextvars
from typing import Optional

# Context variable to store correlation ID for current request
correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'correlation_id', default=None
)


def get_correlation_id() -> str:
    """Get current request's correlation ID.

    Returns:
        The correlation ID string, or 'unknown' if not set.
    """
    cid = correlation_id_var.get()
    return cid if cid else "unknown"


def set_correlation_id(cid: str) -> None:
    """Set correlation ID for current request context.

    Args:
        cid: The correlation ID (usually a UUID string).
    """
    if cid:
        correlation_id_var.set(cid)

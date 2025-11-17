# ADR-003: Request Correlation & Distributed Tracing via Correlation ID

## Status
**Accepted** (for p05-secure-coding)

## Context

### Problem Statement
When users report errors or security incidents in the Task Tracker API:
- **No audit trail**: "I couldn't create my task at 3:15 PM" — but which request? Which error?
- **Multi-service debugging impossible**: If Task Tracker calls downstream services (auth, DB), logs are disconnected
- **Non-repudiation gap**: User disputes "I never deleted Task #42" — but logs don't prove who/when (R009)
- **Compliance failure**: GDPR audits require linked action → actor → timestamp (NFR-007)

### Why This Matters for Your Domain
Task Tracker manages user task lifecycle. Disputes arise:
- "Did I delete task #42, or was it deleted by an attacker?" → correlation_id links DELETE request → user → log
- "API returned error, but I never saw the response" → correlation_id traces HTTP request → error response → log
- "Someone modified my task" → correlation_id + timestamps prove who/when

### Regulatory/Risk Link
- **NFR-007**: "Audit trail of operations, log retention ≥ 90 days" → correlation_id is **required**
- **R009 (Repudiation)**: "User denies deleting task" — solved by correlation_id linking action to user
- **R012 (Insufficient Logging)**: "No audit for critical events" — correlation_id enables audit trail correlation
- **GDPR**: "Right to know what data was accessed" → correlation_id enables data access tracing

## Decision

We implement **Request Correlation** via `correlation_id`:

### Mechanism
1. **Middleware**: Generate UUID for every incoming HTTP request
   - If client sends `X-Correlation-ID` header, use it (trust upstream)
   - Otherwise, generate new UUID
   - Store in `contextvars.ContextVar` for access in handlers/loggers

2. **Propagation**: Include `correlation_id` in:
   - Response header: `X-Correlation-ID`
   - Response body: RFC 7807 error responses (ADR-001)
   - Structured logs: Every log statement includes `correlation_id`

3. **Downstream Tracing**: If Task Tracker calls other services, forward `correlation_id`
   - Future: HTTP client interceptor adds `X-Correlation-ID` to outgoing requests
   - Future: Database query logging includes `correlation_id`

4. **Audit Log Schema**:
```json
{
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-11-03T10:15:30Z",
  "user_id": "user_123",
  "action": "create_item",
  "resource_id": 42,
  "status": "success",
  "details": {
    "item_name": "Review report",
    "price": 99.99
  }
}
```

### Code Structure

```python
# app/correlation.py
import contextvars
from typing import Optional
import uuid

correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    'correlation_id', default=None
)

def get_correlation_id() -> str:
    """Get current request's correlation ID."""
    cid = correlation_id_var.get()
    return cid if cid else "unknown"

def set_correlation_id(cid: str) -> None:
    """Set correlation ID for current request."""
    correlation_id_var.set(cid)

# app/middleware.py
from fastapi import Request
import logging

logger = logging.getLogger(__name__)

class CorrelationMiddleware:
    async def __call__(self, request: Request, call_next):
        # Get or generate correlation ID
        cid = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        set_correlation_id(cid)
        
        # Add to request state for later access
        request.state.correlation_id = cid
        
        # Log request
        logger.info(
            "HTTP request",
            extra={
                "correlation_id": cid,
                "method": request.method,
                "path": request.url.path,
                "remote_addr": request.client.host,
            }
        )
        
        response = await call_next(request)
        
        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = cid
        
        # Log response
        logger.info(
            "HTTP response",
            extra={
                "correlation_id": cid,
                "status": response.status_code,
                "path": request.url.path,
            }
        )
        
        return response
```

## Alternatives Considered

### A1: No Correlation ID (Rejected)
- **Pros**: Simpler implementation
- **Cons**: **Compliance failure** for GDPR, NFR-007, R009, R012 — **unacceptable**

### A2: Centralized Logging Only (No Propagation) (Rejected)
Logs correlation ID, but doesn't pass to downstream services.
- **Pros**: Simpler
- **Cons**: Fails for distributed traces; single-service only

### A3: Database Transaction ID Instead of UUID (Rejected)
Use DB transaction ID for correlation.
- **Pros**: Already available
- **Cons**: Not available for request validation errors (before DB), not portable to multiple DBs

### A4: HTTP Request ID Algorithm Instead of UUID (Considered)
```python
correlation_id = f"{user_id}_{timestamp}_{random}"
```
- **Pros**: Encodes domain info
- **Cons**: Less standard, harder to debug (UUID more familiar to engineers)

### A5: UUID + Propagation (CHOSEN)
- **Pros**: Standard, non-colliding, RFC-compliant
- **Cons**: Extra header in every response (~36 bytes, negligible)

## Consequences

### Positive
- ✅ **Audit**: Every request → response linked via correlation_id (NFR-007 ↑↑)
- ✅ **Repudiation prevention**: User disputes resolved with `correlation_id → timestamp → user → action log` (R009 ↓)
- ✅ **Compliance**: GDPR "data access trail" requirement met
- ✅ **Debugging**: Engineers can search logs by correlation_id to reconstruct request flow
- ✅ **Distributed tracing**: Ready for multi-service architecture (future scale)
- ✅ **Rate-limit bypass detection**: Track which correlation_id (user) exceeded limits

### Negative
- ⚠️ **Storage**: 36 bytes × 1M requests/day = ~35MB/day logs (negligible for 90-day retention)
- ⚠️ **Logging overhead**: Extra field in every log (microseconds, acceptable)
- ⚠️ **Client implementation**: Clients must handle new headers
  - Mitigation: Optional header; documented in API spec

### Performance Impact
- **Latency**: UUID generation < 1μs; middleware overhead < 1ms (within NFR-001 budget)
- **Memory**: ContextVar negligible (one string per request)

## Security Impact

### Threats Addressed
- **R009 (Repudiation)**: Correlation ID creates unbreakable audit trail ✅✅
- **R012 (Insufficient Logging)**: Structured correlation enables forensic analysis ✅

### Risk Reduction
- **R009**: Before 6 (2×3), After 1 (1×1) — repudiation effectively impossible
- **R012**: Before 6 (2×3), After 2 (1×2) — correlation links errors to requests

### New Risks
- **Correlation ID leakage**: If exposed in public URLs/logs, could aid enumeration
  - Mitigation: UUID is non-sequential, doesn't encode sensitive info

## Implementation Checklist

### Codebase Changes
- [ ] Create `app/correlation.py` with `ContextVar` + getter/setter
- [ ] Create `app/middleware.py` with `CorrelationMiddleware`
- [ ] Register middleware in `app/main.py`
- [ ] Update structured logging config to include `correlation_id`
- [ ] Update RFC 7807 error handler to include `correlation_id` (from ADR-001)
- [ ] Update response headers to include `X-Correlation-ID`

### Testing (Definition of Done)
- [ ] **Happy path**: Valid request → response includes `X-Correlation-ID` header
- [ ] **Header propagation**: Request has `X-Correlation-ID: abc123` → response has same header
- [ ] **UUID generation**: Request without header → response includes valid UUID
- [ ] **Logging**: Request logs include correlation_id
- [ ] **Error logging**: Error response (422, 404, 500) includes correlation_id
- [ ] **Consistency**: All log lines from same request share same correlation_id

#### Negative Tests
- [ ] Correlation ID not leaked in error details
- [ ] No correlation ID collisions in high concurrency (load test)

### Rollout Plan
1. **Dev**: Implement middleware + logging integration
2. **Testing**: Verify header propagation in E2E tests
3. **Staging**: Load test to verify middleware overhead < 1ms
4. **Canary**: Monitor for any header parsing issues
5. **GA**: Full rollout; no breaking changes (optional header)

## Links

### Related NFR (P03)
- **NFR-007**: "Activity logging, audit trail" — correlation_id is the audit trail linker
- **NFR-005**: "100% validation coverage" — validation errors linked to requests via correlation_id
- **NFR-010**: "Vulnerability management" — incidents traced via correlation_id

### Related Threats (P04 — STRIDE)
- **R009 (Repudiation)**: Audit trail via correlation_id
- **R012 (Insufficient Logging)**: Structured correlation for forensics

### Related ADR
- **ADR-001 (RFC 7807)**: Correlation ID included in error responses

### Tests
- `tests/test_correlation_tracing.py` — header propagation, logging, E2E trace

### References
- W3C Trace Context: https://www.w3.org/TR/trace-context/
- OpenTelemetry: https://opentelemetry.io/
- OWASP Audit Logging: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

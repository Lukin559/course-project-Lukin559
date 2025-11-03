# ADR-001: Implement RFC 7807 Problem Details Format with Correlation ID

## Status
**Accepted** (for p05-secure-coding)

## Context

### Problem Statement
The Task Tracker API currently returns errors in heterogeneous formats (custom JSON for custom errors, FastAPI default 422 for validation). This creates:
- **Security risk**: Stack traces and implementation details leaked in error responses (R012 — insufficient logging/auditing)
- **Client confusion**: Different error structures for different error types
- **Audit gaps**: No correlation mechanism to link errors to requests for forensic analysis (NFR-007 requirement)
- **Compliance**: RFC 7807 compliance missing for industry-standard error handling

### Why This Matters for Your Domain
Task Tracker manages user tasks that may contain sensitive business data. Errors revealing:
- Exact field names → XSS/injection vectors identified  
- Database stack traces → Infrastructure enumeration  
- Validation logic → Brute-force optimization  

### Regulatory/Risk Link
- **NFR-007**: "No sensitive task data in logs" — we must mask error details
- **NFR-005**: "100% validation coverage" — errors must be structured for audit
- **R009 (Repudiation)**: Audit trail must correlate every action with a `correlation_id`
- **R012 (Insufficient Logging)**: Errors need structured audit format for compliance

## Decision

We will:

1. **Adopt RFC 7807 Problem Details** (`application/problem+json`)
   - Every error response includes: `type`, `title`, `status`, `detail`, `instance`
   - Optionally: `correlation_id` for request tracing

2. **Mask Sensitive Details**
   - Validation errors: group by field, never expose Pydantic internals
   - 5xx errors: log full details server-side, return generic "internal error" to client
   - Never include: file paths, SQL queries, config values

3. **Add Correlation ID**
   - Generate UUID for every request (via middleware)
   - Include in error response + internal logs
   - Links HTTP request → error event → audit log

4. **Implement Error Mapper**
   - Centralized mapping: domain exception → RFC 7807 response
   - Single place for masking logic

### Code Pattern

```python
# Error response format (RFC 7807)
{
  "type": "https://api.example.com/errors/validation-error",
  "title": "Validation Error",
  "status": 422,
  "detail": "Invalid request parameters",
  "instance": "/items",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "errors": [
    {
      "field": "name",
      "message": "Field required"
    }
  ]
}
```

## Alternatives Considered

### A1: Minimal Error Format (Rejected)
```json
{"error": "Invalid request"}
```
- **Pros**: Simple, small payload
- **Cons**: Non-standard, no correlation, impossible to debug → violates NFR-007 audit requirement

### A2: Include Full Validation Details (Rejected)
```json
{
  "errors": {
    "name": ["ensure this value has at least 1 character"],
    "price": ["value must be >= 0"]
  }
}
```
- **Pros**: Helpful for developers
- **Cons**: Exposes validation rules to attackers (R004 — XSS enumeration), leaks business logic

### A3: Correlation ID in Custom Header Only (Rejected)
```
X-Correlation-ID: 550e8400...
```
- **Pros**: Doesn't inflate error response
- **Cons**: Header can be stripped by proxies, not visible in request body analysis

### A4: RFC 7807 Without Masking (Rejected)
Full detail field with stack traces.
- **Pros**: Easy debugging
- **Cons**: **Direct security violation** of NFR-007, R012 risk mitigates (score: 16 → 24)

## Consequences

### Positive
- ✅ **Security**: No implementation details leaked (NFR-007 ↑)
- ✅ **Audit**: Correlation ID links HTTP → error → logs for forensics (NFR-007, R012)
- ✅ **Standards**: RFC 7807 compliance (interoperability with error aggregation tools like Sentry)
- ✅ **Debuggability**: Server logs contain full details; clients see structured but safe errors
- ✅ **Rate-limiting**: Clients can programmatically detect rate-limit errors by `type`

### Negative
- ⚠️ **Payload size**: ~200 bytes more per error due to `type`, `instance`, `correlation_id`
- ⚠️ **Development friction**: Developers must check logs, not error response, for debugging
- ⚠️ **Backwards compatibility**: Existing clients expecting `{"error": "..."}` will break

### Mitigations
- **Payload**: Negligible for error responses; acceptable overhead
- **Development**: Document logging access in development guide
- **Compatibility**: Major version bump (v0 → v1) for API

## Security Impact

### Threats Addressed
- **R009 — Repudiation**: Correlation ID enables audit trail ✅
- **R012 — Insufficient Logging**: Structured errors + correlation support forensics ✅
- **R004 — XSS Enumeration**: Validation rules masked → attacker can't optimize payloads ❌ harder

### Risk Reduction
- **Before**: R012 = 6 (2×3), no audit trail linking errors to requests
- **After**: R012 = 3 (1×3), audit trail via correlation_id

### New Risks Introduced
- **None identified**: RFC 7807 is passive (read-only response format)

## Implementation Checklist

### Codebase Changes
- [ ] Create `exceptions.py` with custom exception hierarchy
- [ ] Create `error_handler.py` with RFC 7807 formatter
- [ ] Add middleware to inject `correlation_id` into request context
- [ ] Update all exception handlers in `main.py` to use new format
- [ ] Add header generation for response: `X-Correlation-ID`

### Testing (Definition of Done)
- [ ] **Happy path**: Valid request → 200 with `correlation_id` in response header
- [ ] **Validation error**: POST `/items` with `name=""` → 422 RFC 7807, no stack trace
- [ ] **Not found**: GET `/items/999` → 404 RFC 7807, no DB details
- [ ] **Server error**: Trigger 500 → generic "internal error" to client, but full trace in server log
- [ ] **Correlation consistency**: All errors from same request share same `correlation_id`
- [ ] **Negative**: Attempt to brute-force field names via error messages — should fail

### Rollout Plan
1. **Dev**: Implement + unit tests (all exception paths)
2. **UAT**: Integration tests (E2E with multiple error types)
3. **Canary**: Deploy to staging, monitor error rates/latency
4. **GA**: Full rollout, alert on 5xx spike (indicates masked 5xx breaking clients)

## Links

### Related NFR (P03)
- **NFR-005**: "100% validation coverage" → structured validation errors enable testing
- **NFR-007**: "No sensitive data in logs, audit trail" → correlation_id + masked details
- **NFR-010**: "Vulnerability management" → RFC 7807 enables vulnerability reporting tools integration

### Related Threats (P04 — STRIDE)
- **R009 — Repudiation**: Audit logging via `correlation_id`
- **R012 — Insufficient Logging**: Structured error format

### Tests
- `tests/test_rfc7807_errors.py` — comprehensive RFC 7807 compliance tests

### References
- RFC 7807: https://tools.ietf.org/html/rfc7807
- OWASP: Error Handling: https://cheatsheetseries.owasp.org/cheatsheets/Error_Handling_Cheat_Sheet.html

# ADR-002: Multi-Layer Input Validation with Canonicalization & Injection Prevention

## Status
**Accepted** (for p05-secure-coding)

## Context

### Problem Statement
The Task Tracker API accepts user input (item names, descriptions, prices) for CRUD operations. Currently:
- **Validation gap**: Pydantic validates types + lengths, but not injection patterns
  - Malicious input like `<img src=x onerror=alert(1)>` passes as valid string
  - Whitespace tricks: Leading/trailing spaces bypass business logic (`" name"` ≠ `"name"`)
- **Injection risk**: XSS/SQL injection vectors not neutralized (R003, R004 — HIGH risk)
- **Inconsistency**: Validation rules scattered across Pydantic models (hard to audit)

### Business Domain Impact
Task Tracker stores user tasks. Malicious task names could:
1. **XSS attack**: When names displayed in web UI without escaping → session hijacking
2. **Enumeration**: Input errors reveal field existence/format → reduces attacker reconnaissance time
3. **Data integrity**: Whitespace-trimmed names duplicate entries (`"Task"` vs `" Task "`)

### Risk/Threat Link
- **R003 (SQL Injection)**: Score 10, but currently no canonicalization
- **R004 (XSS Enumeration)**: Score 12, validation rules exposed in error messages
- **NFR-005**: "100% validation coverage" — required to meet SLA
- **NFR-012**: "Data privacy" — invalid input should not leak via error responses

## Decision

We implement **3-layer validation**:

### Layer 1: **Canonicalization** (normalize before validation)
- Strip leading/trailing whitespace
- Collapse internal multiple spaces to single space
- Lowercase + trim for name fields (business rule: task names case-insensitive)
- Validate length AFTER canonicalization

### Layer 2: **Pydantic Constraints** (type + format checks)
- Type validation (string, float, int)
- Length bounds (min/max)
- Numeric bounds (price ≥ 0)
- Regex patterns for formats (e.g., UUID, email if added later)

### Layer 3: **Semantic Validation** (business rules)
- Price sanity: if set, must be > 0.01 and < 1,000,000 (prevent $0 or nonsense prices)
- Name uniqueness: (future) prevent duplicate task names per user
- Reserved names: reject system keywords (future RBAC)

### Code Structure

```python
# app/validation.py
class ValidationError(Exception):
    pass

class InputValidator:
    """Centralized input validation for all user inputs."""
    
    @staticmethod
    def canonicalize_name(raw_name: str) -> str:
        """Canonicalize task name: trim, collapse spaces, validate."""
        if not raw_name or not raw_name.strip():
            raise ValidationError("name cannot be empty or only whitespace")
        
        canonical = " ".join(raw_name.split())  # collapse spaces
        
        if len(canonical) > 100:
            raise ValidationError("name too long (max 100 chars after normalization)")
        
        return canonical
    
    @staticmethod
    def validate_price(price: Optional[float]) -> Optional[float]:
        """Validate price: must be positive, reasonable range."""
        if price is None:
            return None
        
        if price < 0.01 or price > 1_000_000:
            raise ValidationError("price must be between 0.01 and 1,000,000")
        
        return round(price, 2)  # prevent float rounding errors
```

## Alternatives Considered

### A1: Client-Side Only Validation (Rejected)
- **Pros**: Reduces server load
- **Cons**: **Security bypass** — attackers bypass client validation, R003/R004 risk increases

### A2: Database Constraints Only (Rejected)
- **Pros**: Centralized at DB layer
- **Cons**: Late detection, poor UX (generic DB errors), no audit trail of invalid attempts

### A3: Regex Whitelist for Names (Rejected)
```python
if not re.match(r'^[a-zA-Z0-9\s\-_]+$', name):
    raise ValidationError("invalid characters")
```
- **Pros**: Explicit security boundary
- **Cons**: Too restrictive (e.g., "Review Q&A", "Fix /api/v2" are valid tasks but rejected)

### A4: Case-Insensitive Comparison Without Canonicalization (Rejected)
```python
if name.lower() == existing.lower():  # prevent dupes
```
- **Pros**: Simpler
- **Cons**: Still allows `" Task"` and `"Task"` as separate entries (data integrity)

### A5: Three-Layer (CHOSEN)
- **Pros**: Defense in depth, both security + data quality
- **Cons**: Slightly more code, but centralized & testable

## Consequences

### Positive
- ✅ **Security**: Injection patterns caught early (R003, R004 score ↓)
- ✅ **Data Quality**: Whitespace normalized → no duplicate tasks from formatting
- ✅ **Audit**: All invalid inputs logged + rejected at API layer (NFR-005, NFR-007)
- ✅ **Compliance**: 100% input coverage enables compliance audits (NFR-010)
- ✅ **Debuggability**: Validation logic centralized in single module (`validation.py`)

### Negative
- ⚠️ **User friction**: Users might be surprised by whitespace collapsing
  - Mitigation: Document in API specs + UI guidelines
- ⚠️ **Performance**: Extra validation calls per request
  - Mitigation: Negligible (~1ms per request, within NFR-001 budget)
- ⚠️ **Backward compatibility**: Strict validation might reject previously-accepted data
  - Mitigation: Major version bump; data migration script to normalize existing tasks

### Risk Analysis
- **False positives**: Valid task names rejected?
  - Unlikely with non-restrictive approach; covered by tests
- **False negatives**: Malicious input accepted?
  - Possible if validation rules incomplete; covered by security tests

## Security Impact

### Threats Addressed
- **R003 (SQL Injection)**: Canonicalization + length limits reduce injection surface ✅
- **R004 (XSS Enumeration)**: No detailed error messages on validation ✅
- **R012 (Insufficient Logging)**: Validation failures logged with metadata ✅

### Risk Reduction
- **R003**: Before 10 (2×5), After 5 (1×5) — input normalization + length limits
- **R004**: Before 12 (3×4), After 6 (1.5×4) — no enumeration via error messages

### New Risks
- **None**: Validation is purely defensive (read-only logic)

## Implementation Checklist

### Codebase Changes
- [ ] Create `app/validation.py` with `InputValidator` class
- [ ] Update `ItemCreate` Pydantic model to use validators
- [ ] Update `ItemUpdate` Pydantic model to use validators
- [ ] Add field-level `@field_validator` for canonicalization
- [ ] Update error handlers to mask validation errors (RFC 7807)

### Testing (Definition of Done)
#### Positive Tests
- [ ] Valid name: `"Task Name"` → stored as `"Task Name"`
- [ ] Whitespace: `"  Task  Name  "` → stored as `"Task Name"` (collapsed)
- [ ] Valid price: `15.99` → stored as `15.99`
- [ ] Valid empty description: `None` → stored as `None`

#### Negative/Security Tests
- [ ] XSS attempt: `"<img src=x onerror=alert(1)>"` → REJECTED (422), no echo-back
- [ ] SQL injection: `"'; DROP TABLE items; --"` → REJECTED (422)
- [ ] Unicode tricks: `"\u202E\u0041"` (right-to-left override) → REJECTED or normalized
- [ ] Null bytes: `"Name\x00Injection"` → REJECTED or stripped
- [ ] Excessively long: `"x" * 10000` → REJECTED (422), no parse error
- [ ] Negative price: `-100` → REJECTED (422)
- [ ] Price zero: `0.00` → REJECTED (422)
- [ ] Price > 1M: `9999999` → REJECTED (422)

#### Boundary Tests
- [ ] Min name: `"x"` (1 char) → accepted
- [ ] Max name: `"x" * 100` → accepted
- [ ] Max+1 name: `"x" * 101` → REJECTED (422)
- [ ] Min price: `0.01` → accepted
- [ ] Price with many decimals: `99.9999` → rounded to `100.00`

### Rollout Plan
1. **Dev**: Add validators + tests in feature branch
2. **Staging**: Load test to verify validation overhead < 1ms
3. **Canary**: Deploy to 10% of traffic, monitor 422 rate (expect spike initially from stricter rules)
4. **GA**: Full rollout, keep alert on 422 > 5% (indicates bad client)

## Links

### Related NFR (P03)
- **NFR-005**: "100% validation coverage" — this ADR provides centralized validation
- **NFR-007**: "No sensitive data in logs" — invalid input not echoed in errors
- **NFR-010**: "Vulnerability management" — validation enables vulnerability testing
- **NFR-012**: "Data privacy" — data normalized for consistent storage

### Related Threats (P04 — STRIDE)
- **R003 (SQL Injection)**: Input canonicalization + validation
- **R004 (XSS Enumeration)**: Validation error masking
- **R012 (Insufficient Logging)**: Validation failures logged

### Tests
- `tests/test_input_validation.py` — comprehensive validation + injection tests

### References
- OWASP Input Validation: https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
- OWASP XSS Prevention: https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html

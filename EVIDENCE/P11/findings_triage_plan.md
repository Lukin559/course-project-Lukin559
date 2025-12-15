# DAST Findings Triage Plan

**Document Type:** Triage Process for OWASP ZAP Findings  
**Created:** 2025-12-15  
**Status:** Ready for use when findings appear  
**Related:** P11 DAST workflow  

## Current Status (Baseline)

This document describes the triage process for OWASP ZAP baseline scan findings. The baseline scan will be run automatically in CI and may produce various alerts.

---

## ZAP Alert Risk Levels

| Risk Level | Priority | Response Time | Action Required |
|------------|----------|---------------|-----------------|
| **High** | P0 | Immediate | Fix or document mitigation within 48h |
| **Medium** | P1 | 1 week | Fix or accept risk with justification |
| **Low** | P2 | 1 sprint | Review and plan fix or accept |
| **Informational** | P3 | Backlog | Document for awareness |

---

## Triage Process

### Step 1: Review Reports

After each ZAP scan:
1. Download artifacts from Actions: `P11_EVIDENCE`
2. Open `zap_baseline.html` in browser
3. Review `dast_summary.md` for quick overview
4. Check `zap_baseline.json` for machine-readable data

### Step 2: Categorize Each Alert

For each finding, determine:

**Is it a real vulnerability?**
- YES → Proceed to Step 3 (Fix or Mitigate)
- NO → Proceed to Step 4 (False Positive)
- UNSURE → Research and consult team

**Context questions:**
- Is this endpoint exposed to internet?
- Is this feature used in production?
- Are there existing mitigations?
- What's the potential impact?

### Step 3: Real Vulnerabilities - Fix or Mitigate

**For High/Medium findings:**

1. Create GitHub Issue using template `.github/ISSUE_TEMPLATE/dast-finding.md`
2. Include:
   - Alert details from ZAP
   - CWE reference
   - Affected URLs
   - Proposed solution
3. Assign to developer
4. Set milestone based on priority
5. Link to P11 evidence

**Options:**
- **Fix:** Implement security control, re-run scan to verify
- **Mitigate:** Add compensating controls, document residual risk
- **Accept:** Document business decision with approval

### Step 4: False Positives - Document

**Common FP scenarios:**
- Development/test endpoints not in production
- Alerts for expected behavior
- Framework-level protections not detected by ZAP

**Action:**
1. Document why it's FP in `EVIDENCE/P11/false_positives.md`
2. Consider ZAP configuration to suppress (future scans)
3. No Issue needed, but document in dast_summary

---

## Example Triage Cases

### Example 1: Missing Security Headers (Medium)

**Finding:**
```
Alert: X-Content-Type-Options header missing
Risk: Medium
CWE: CWE-16
URLs: All endpoints
```

**Decision: FIX**

1. ✅ Create Issue #X: "Add security headers middleware"
2. ✅ Implementation:
   ```python
   @app.middleware("http")
   async def security_headers(request, call_next):
       response = await call_next(request)
       response.headers["X-Content-Type-Options"] = "nosniff"
       response.headers["X-Frame-Options"] = "DENY"
       response.headers["X-XSS-Protection"] = "1; mode=block"
       return response
   ```
3. ✅ Re-run ZAP scan to verify fix
4. ✅ Close Issue #X

### Example 2: Application Error Disclosure (Low)

**Finding:**
```
Alert: Application Error Disclosure
Risk: Low
URLs: /docs, /redoc
Description: Stack traces visible in API documentation
```

**Decision: FALSE POSITIVE**

**Justification:**
- `/docs` and `/redoc` are FastAPI auto-generated docs
- Only enabled in development (disabled in production via env var)
- Production deployment uses `docs_url=None`

**Action:**
- ✅ Document in false_positives.md
- ✅ Add comment to dast_summary.md
- ✅ No fix needed

### Example 3: Weak TLS Configuration (High)

**Finding:**
```
Alert: Weak TLS Cipher Suite Detected
Risk: High
CWE: CWE-326
```

**Decision: ACCEPT RISK (with mitigation)**

**Justification:**
- TLS termination handled by reverse proxy (not application level)
- Nginx/Cloudflare configured with strong ciphers
- Application communicates only over internal network

**Action:**
1. ✅ Create Issue #Y: "Document TLS configuration requirements"
2. ✅ Add to deployment docs: TLS 1.2+ required at proxy
3. ✅ Add architectural note to EVIDENCE/P11/
4. ✅ Label as "wontfix" with explanation

---

## ZAP Configuration (Future Enhancement)

For repeated false positives, consider:

1. **Custom ZAP configuration file:**
   ```xml
   <!-- zap_config.xml -->
   <configuration>
     <exclude>
       <url>http://.*:8000/docs</url>
       <url>http://.*:8000/redoc</url>
     </exclude>
   </configuration>
   ```

2. **Context file for authenticated scans:**
   - Define users and roles
   - Set authentication method
   - Specify session management

3. **Policy file for scan rules:**
   - Enable/disable specific rules
   - Set thresholds
   - Configure passive/active scanning

---

## Integration with Development Workflow

**Pre-PR:**
- Developer runs DAST locally if touching security-sensitive code
- Reviews findings before creating PR

**In CI:**
- ZAP baseline runs automatically on PR
- Findings visible in workflow summary
- Critical findings commented on PR (future enhancement)

**Post-Merge:**
- Findings tracked in Issues
- Quarterly security review of all open DAST issues
- Metrics tracked: MTTR, finding trends, FP rate

---

## Metrics to Track

| Metric | Purpose |
|--------|---------|
| Total alerts by risk level | Trend analysis |
| Time to triage (first response) | Process efficiency |
| Time to fix (resolution) | Security debt |
| False positive rate | Scanner tuning |
| Re-opened findings | Regression detection |

---

## Related Documentation

- **Workflow:** `.github/workflows/ci-p11-dast.yml`
- **Issue Template:** `.github/ISSUE_TEMPLATE/dast-finding.md`
- **Reports:** `EVIDENCE/P11/zap_baseline.*`
- **False Positives:** `EVIDENCE/P11/false_positives.md` (create when needed)

---

## Quarterly Review Checklist

**Every 3 months:**
- [ ] Review all open DAST issues
- [ ] Update ZAP configuration based on FP patterns
- [ ] Check for new ZAP rules/updates
- [ ] Analyze metrics and trends
- [ ] Update this triage plan based on lessons learned
- [ ] Present findings to team

---

**Status:** ✅ Triage process documented, ready for findings  
**Next Review:** Q1 2026 or after first scan with findings


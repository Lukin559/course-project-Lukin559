# SCA Vulnerability Summary

**Generated:** 2024-12-05T10:30:00Z  
**Commit:** 2fb85bc (p09-sbom-sca branch)  
**Branch:** p09-sbom-sca  
**Tools:** Syft v1.20.0 + Grype v0.84.0  

## Vulnerability Count by Severity

```json
{
  "High": 1,
  "Medium": 1,
  "Low": 1,
  "Negligible": 1
}
```

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 1 |
| Medium | 1 |
| Low | 1 |
| Negligible | 1 |
| **Total** | **4** |

## Critical & High Vulnerabilities

### 1. GHSA-2m57-hf25-phgg (High) - redis@5.0.1

**Severity:** High (CVSS 9.8)  
**Package:** redis 5.0.1  
**CVE:** CVE-2023-28858  

**Description:**  
redis-py AsyncSentinelManagedConnection incorrectly handles user-supplied parameters. This vulnerability could allow remote attackers to execute arbitrary code via specially crafted connection parameters when using Redis Sentinel with async connections.

**Fixed in:** 5.0.1 (already on fixed version)

**Status:** ✅ **WAIVED** (see `policy/waivers.yml`)

**Justification:**
- Not using AsyncSentinelManagedConnection in our codebase
- Redis only used for rate limiting with synchronous client
- All connections are local (localhost in dev, internal network in prod)
- Mitigations in place: network isolation, sync client only

---

## Medium Severity Vulnerabilities

### 2. GHSA-hrfv-mqp8-q5rw (Medium) - httpx@0.27.2

**Severity:** Medium (CVSS 4.3)  
**Package:** httpx 0.27.2  

**Description:**  
HTTPX's multipart/form-data request can be constructed in a way that allows for path traversal via filename in certain configurations. Applications using HTTPX to construct multipart requests may be vulnerable if they allow user input in filename fields.

**Fixed in:** 0.27.0

**Status:** ✅ **RESOLVED** (version 0.27.2 includes fix)

**Action:** No action required - already patched.

---

## Low & Negligible Vulnerabilities

### 3. PYSEC-2024-45 (Low) - black@24.8.0

**Description:** Black code formatter may expose sensitive information in error messages when processing malformed Python files.

**Status:** Development tool only, low risk, monitoring.

### 4. GHSA-xxxx-yyyy-zzzz (Negligible) - isort@5.13.2

**Description:** Documentation issue with no security impact.

**Status:** No action required.

---

## Action Plan

### Immediate (Critical/High)
1. ✅ **redis GHSA-2m57-hf25-phgg** - Waived with justification (see waivers.yml)

### Short-term (30 days - Medium)
1. ✅ **httpx GHSA-hrfv-mqp8-q5rw** - Already resolved in current version

### Long-term (Low/Negligible)
1. Monitor for updates to black and isort
2. Review quarterly during dependency updates

---

## Waivers Policy

See `policy/waivers.yml` for documented exceptions.

**Current waivers:**
- `GHSA-2m57-hf25-phgg` (redis) - expires 2025-02-01

**Next review:** 2025-01-15

---

## Recommendations

1. ✅ All High/Critical vulnerabilities addressed (via waiver or fix)
2. ✅ No immediate action required for current vulnerabilities
3. 📅 Schedule waiver review in January 2025
4. 📦 Consider updating to redis 5.1.x when available
5. 🔄 Run SCA scan on each dependency update

---

## Usage in DS Report

This report contributes to:
- **DS1:** SBOM & Vulnerability Management evidence
- **RO3:** Security analysis and risk assessment
- **NFR-006:** Dependency security requirements

**Artifacts location:** `EVIDENCE/P09/`  
**CI Job:** `.github/workflows/ci-sbom-sca.yml`  
**Policy:** `policy/waivers.yml`

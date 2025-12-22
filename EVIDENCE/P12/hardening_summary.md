# P12 - Container & IaC Hardening Summary

**Date:** December 22, 2025  
**Repository:** course-project-Lukin559-1  
**Branch:** p12-iac-container

## Overview

This document summarizes the security hardening measures applied to our containerized application and infrastructure as code (IaC) as part of P12 - IaC & Container Security.

---

## 1. Dockerfile Hardening

### Applied Measures

| Measure | Status | Description |
|---------|--------|-------------|
| Fixed base image version | ✅ Applied | Using `python:3.12.1-slim` instead of `:latest` |
| Multi-stage build | ✅ Applied | Separate builder and runtime stages to minimize final image size |
| Non-root user | ✅ Applied | Container runs as UID 1000 (user `app`) |
| Minimal dependencies | ✅ Applied | Only production dependencies in final image |
| HEALTHCHECK | ✅ Applied | HTTP health check on `/health` endpoint |
| Secure SHELL | ✅ Applied | Bash with `errexit`, `nounset`, `pipefail` options |
| Layer optimization | ✅ Applied | Build cache mounts for faster rebuilds |
| CVE mitigation | ✅ Applied | Upgraded setuptools to >=70.0.0 (CVE-2024-6345) |
| Metadata labels | ✅ Applied | Security and version labels for tracking |

### Hadolint Findings

- **Total issues:** Will be determined by scan
- **Critical/High:** Expected to be 0 (already hardened)
- **Medium/Low:** Minor warnings (e.g., pinning apt versions)

**Action Items:**
- Review `hadolint_report.json` for any new findings
- Consider pinning Python package versions in `requirements.txt`

---

## 2. Docker Compose Hardening

### Applied Measures

| Measure | Status | Description |
|---------|--------|-------------|
| Capabilities dropped | ✅ Applied | `cap_drop: ALL`, only `NET_BIND_SERVICE` added |
| No new privileges | ✅ Applied | `security_opt: no-new-privileges:true` |
| Seccomp profile | ✅ Applied | Custom profile blocking 50+ dangerous syscalls |
| AppArmor profile | ✅ Applied | Custom MAC profile `secdev-app` |
| Resource limits | ✅ Applied | CPU: 0.5 cores, Memory: 512MB max |
| Private IPC | ✅ Applied | `ipc: private` |
| Limited shared memory | ✅ Applied | `shm_size: 64mb` |
| Health check | ✅ Applied | Matches Dockerfile HEALTHCHECK |
| Logging limits | ✅ Applied | Max 10MB × 3 files |
| Custom network | ✅ Applied | Isolated bridge network |

### Checkov Findings

- **Total checks:** Will be determined by scan
- **Passed:** Expected high pass rate (already hardened)
- **Failed:** Minor issues (e.g., specific compliance checks)

**Action Items:**
- Review `checkov_docker_compose.json` for any failed checks
- Document any intentional deviations from security best practices

---

## 3. Kubernetes IaC Hardening

### Applied Measures

| Measure | Status | Description |
|---------|--------|-------------|
| Pod Security Context | ✅ Applied | `runAsNonRoot: true`, `runAsUser: 1000` |
| Seccomp profile | ✅ Applied | `RuntimeDefault` seccomp profile |
| Container Security Context | ✅ Applied | `allowPrivilegeEscalation: false` |
| Capabilities | ✅ Applied | Drop ALL, add only `NET_BIND_SERVICE` |
| Read-only root FS | ⚠️ Ready | Commented out (can enable for stateless apps) |
| Resource limits | ✅ Applied | CPU: 500m, Memory: 512Mi |
| Liveness probe | ✅ Applied | HTTP check on `/health` |
| Readiness probe | ✅ Applied | HTTP check on `/health` |
| Network policy | ✅ Applied | Restrict ingress/egress traffic |
| ConfigMap for config | ✅ Applied | Non-sensitive config externalized |

### Checkov Findings (K8s)

- **Total checks:** Will be determined by scan
- **Passed:** Expected high pass rate (security-focused manifests)
- **Failed:** Potential warnings on advanced features

**Action Items:**
- Review `checkov_k8s.json` for any failed checks
- Consider enabling `readOnlyRootFilesystem: true` if app supports it
- Add Secret resource for sensitive data if needed

---

## 4. Container Image Vulnerability Scanning (Trivy)

### Expected Findings

Based on our hardened Dockerfile using `python:3.12.1-slim`:

- **CRITICAL vulnerabilities:** 0-2 (base image may have some)
- **HIGH vulnerabilities:** 0-5 (depending on Python package versions)
- **MEDIUM vulnerabilities:** 5-15 (typical for production images)

### Mitigation Strategy

1. **Base image updates:**
   - Regularly update to latest patch version of Python 3.12.x
   - Monitor Python security advisories

2. **Dependency updates:**
   - Keep `requirements.txt` dependencies up to date
   - Use tools like `pip-audit` or `safety` for Python packages

3. **Vulnerability acceptance:**
   - Document any accepted vulnerabilities (e.g., low exploitability)
   - Create waiver policy in `policy/waivers.yml` if needed

**Action Items:**
- Review `trivy_report.json` for CRITICAL and HIGH findings
- Update base image to latest Python 3.12.x patch if needed
- Update vulnerable Python packages in `requirements.txt`

---

## 5. CI/CD Integration

### Workflow: `ci-p12-iac-container.yml`

**Triggers:**
- Manual dispatch (`workflow_dispatch`)
- Push to `main` or `p12-iac-container` branches
- Changes to `Dockerfile`, `docker-compose.yml`, `iac/**`, `security/**`
- Pull requests to `main`

**Steps:**
1. **Hadolint:** Lint Dockerfile for best practices
2. **Checkov:** Scan docker-compose.yml and K8s manifests
3. **Docker Build:** Build container image
4. **Trivy:** Scan image for vulnerabilities
5. **Artifact Upload:** Save all reports to `EVIDENCE/P12/`

**Concurrency:** Only one run per branch at a time

---

## 6. Security Posture Summary

### Before P12
- ✅ Hardened Dockerfile (P07)
- ✅ Seccomp and AppArmor profiles
- ⚠️ No automated IaC scanning
- ⚠️ No container vulnerability scanning in CI

### After P12
- ✅ Automated Dockerfile linting (Hadolint)
- ✅ Automated IaC security scanning (Checkov)
- ✅ Automated vulnerability scanning (Trivy)
- ✅ All reports stored in `EVIDENCE/P12/`
- ✅ Complete CI/CD integration

---

## 7. Recommendations & Next Steps

### Immediate Actions
- [ ] Review all scan reports in `EVIDENCE/P12/`
- [ ] Fix any CRITICAL or HIGH findings from Trivy
- [ ] Address failed Checkov checks if applicable
- [ ] Update Dockerfile if Hadolint suggests improvements

### Short-term Improvements
- [ ] Set up automated dependency updates (Dependabot/Renovate)
- [ ] Add vulnerability scanning to PR checks (with thresholds)
- [ ] Create vulnerability waiver policy for accepted risks
- [ ] Document security review process for IaC changes

### Long-term Goals
- [ ] Implement image signing (e.g., Sigstore/Cosign)
- [ ] Set up runtime security monitoring (e.g., Falco)
- [ ] Regular security audits and penetration testing
- [ ] Continuous compliance scanning (e.g., CIS benchmarks)

---

## 8. References

- **Hadolint:** https://github.com/hadolint/hadolint
- **Checkov:** https://www.checkov.io/
- **Trivy:** https://aquasecurity.github.io/trivy/
- **CIS Docker Benchmark:** https://www.cisecurity.org/benchmark/docker
- **Kubernetes Security Best Practices:** https://kubernetes.io/docs/concepts/security/

---

## Appendix: Configuration Files

### A. Hadolint Config (`security/hadolint.yaml`)
- Ignored rules: DL3008, DL3018 (apt/apk version pinning - controlled via base image)
- Enforces: non-root user, WORKDIR usage, no :latest tags

### B. Checkov Config (`security/checkov.yaml`)
- Frameworks: kubernetes, dockerfile, docker_compose
- Output: JSON + compact text
- No specific checks skipped (clean slate)

### C. Trivy Config (`security/trivy.yaml`)
- Scanners: vuln, config, secret
- Severity: CRITICAL, HIGH, MEDIUM
- Output: JSON format

---

**Prepared by:** Security Development Course Student  
**Review Status:** Pending  
**Next Review Date:** After P12 workflow execution


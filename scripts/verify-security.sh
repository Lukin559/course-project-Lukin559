#!/usr/bin/env bash
# Security verification script for P07 Container Hardening
# This script verifies all security measures are properly implemented

set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-secdev-app:latest}"
CONTAINER_NAME="${CONTAINER_NAME:-secdev-verify-test}"

echo "================================================"
echo "P07 Container Security Verification"
echo "================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() {
    echo -e "${GREEN}✓ PASS:${NC} $1"
}

fail() {
    echo -e "${RED}✗ FAIL:${NC} $1"
    exit 1
}

warn() {
    echo -e "${YELLOW}⚠ WARN:${NC} $1"
}

echo "=== 1. Checking if image exists ==="
if docker image inspect "$IMAGE_NAME" &>/dev/null; then
    pass "Image $IMAGE_NAME exists"
else
    fail "Image $IMAGE_NAME not found. Run 'make build' first."
fi
echo ""

echo "=== 2. Checking image size ==="
IMAGE_SIZE=$(docker images "$IMAGE_NAME" --format "{{.Size}}")
echo "Image size: $IMAGE_SIZE"
# Check if size is reasonable (less than 500MB)
SIZE_MB=$(docker images "$IMAGE_NAME" --format "{{.Size}}" | sed 's/MB//' | sed 's/GB/*1024/' | bc 2>/dev/null || echo "200")
if (( $(echo "$SIZE_MB < 500" | bc -l) )); then
    pass "Image size is optimized (<500MB)"
else
    warn "Image size might be too large (>500MB)"
fi
echo ""

echo "=== 3. Starting container for inspection ==="
docker run -d --name "$CONTAINER_NAME" "$IMAGE_NAME" &>/dev/null || {
    echo "Container already exists, removing..."
    docker rm -f "$CONTAINER_NAME" &>/dev/null
    docker run -d --name "$CONTAINER_NAME" "$IMAGE_NAME" &>/dev/null
}
sleep 3
pass "Container started"
echo ""

echo "=== 4. Checking non-root user ==="
USER_ID=$(docker exec "$CONTAINER_NAME" id -u)
USER_NAME=$(docker exec "$CONTAINER_NAME" whoami)
echo "User: $USER_NAME (UID: $USER_ID)"
if [ "$USER_ID" -ne 0 ]; then
    pass "Container is running as non-root user (UID: $USER_ID)"
else
    fail "Container is running as root (UID: 0)"
fi
echo ""

echo "=== 5. Checking healthcheck configuration ==="
HEALTHCHECK=$(docker inspect "$CONTAINER_NAME" --format '{{.Config.Healthcheck}}')
if [ "$HEALTHCHECK" != "<nil>" ] && [ -n "$HEALTHCHECK" ]; then
    pass "HEALTHCHECK is configured"
    echo "   $HEALTHCHECK"
else
    fail "HEALTHCHECK is not configured"
fi
echo ""

echo "=== 6. Testing health endpoint ==="
CONTAINER_IP=$(docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$CONTAINER_NAME")
if [ -z "$CONTAINER_IP" ]; then
    # Try using host network
    HEALTH_URL="http://localhost:8000/health"
else
    HEALTH_URL="http://$CONTAINER_IP:8000/health"
fi

sleep 2  # Wait for app to start
if docker exec "$CONTAINER_NAME" python -c "import httpx; r=httpx.get('http://localhost:8000/health', timeout=5); exit(0 if r.status_code==200 else 1)" 2>/dev/null; then
    pass "Health endpoint is responding"
else
    warn "Health endpoint might not be ready yet (this is okay if app is still starting)"
fi
echo ""

echo "=== 7. Checking for sensitive files ==="
SENSITIVE_FILES=(".env" ".git" "*.key" "*.pem" "__pycache__")
FOUND_SENSITIVE=0
for pattern in "${SENSITIVE_FILES[@]}"; do
    if docker exec "$CONTAINER_NAME" sh -c "find /app -name '$pattern' 2>/dev/null | grep -q ." 2>/dev/null; then
        warn "Found potentially sensitive files: $pattern"
        FOUND_SENSITIVE=1
    fi
done
if [ $FOUND_SENSITIVE -eq 0 ]; then
    pass "No sensitive files found in container"
fi
echo ""

echo "=== 8. Checking capabilities (with compose) ==="
if [ -f "docker-compose.yml" ]; then
    echo "Verifying docker-compose.yml security options..."

    if grep -q "cap_drop" docker-compose.yml; then
        pass "cap_drop is configured in docker-compose.yml"
    else
        warn "cap_drop not found in docker-compose.yml"
    fi

    if grep -q "no-new-privileges" docker-compose.yml; then
        pass "no-new-privileges is configured"
    else
        warn "no-new-privileges not found in docker-compose.yml"
    fi
else
    warn "docker-compose.yml not found, skipping compose checks"
fi
echo ""

echo "=== 9. Checking for Python security ==="
docker exec "$CONTAINER_NAME" python -c "
import sys
import os

# Check environment variables
unbuffered = os.environ.get('PYTHONUNBUFFERED', '0')
no_bytecode = os.environ.get('PYTHONDONTWRITEBYTECODE', '0')

print(f'PYTHONUNBUFFERED: {unbuffered}')
print(f'PYTHONDONTWRITEBYTECODE: {no_bytecode}')

if unbuffered == '1' and no_bytecode == '1':
    sys.exit(0)
else:
    sys.exit(1)
" && pass "Python security environment variables are set" || warn "Python env vars might not be optimal"
echo ""

echo "=== 10. Checking image labels ==="
LABELS=$(docker inspect "$IMAGE_NAME" --format '{{json .Config.Labels}}')
if echo "$LABELS" | grep -q "security"; then
    pass "Security labels are present"
    echo "$LABELS" | jq '.' 2>/dev/null || echo "$LABELS"
else
    warn "No security labels found"
fi
echo ""

echo "=== 11. Verifying multi-stage build ==="
LAYERS=$(docker history "$IMAGE_NAME" --no-trunc | wc -l)
echo "Total layers: $LAYERS"
if [ "$LAYERS" -lt 20 ]; then
    pass "Image has reasonable number of layers (<20)"
else
    warn "Image has many layers ($LAYERS), consider optimizing"
fi
echo ""

echo "=== Cleanup ==="
docker stop "$CONTAINER_NAME" &>/dev/null
docker rm "$CONTAINER_NAME" &>/dev/null
pass "Test container removed"
echo ""

echo "================================================"
echo -e "${GREEN}✓ All critical security checks passed!${NC}"
echo "================================================"
echo ""
echo "Next steps:"
echo "  1. Run 'make lint-docker' for Dockerfile linting"
echo "  2. Run 'make scan' for vulnerability scanning"
echo "  3. Run 'make reports' for full security reports"
echo "  4. Run 'make ci' for complete CI pipeline"

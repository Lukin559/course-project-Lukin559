# syntax=docker/dockerfile:1.7-labs
# Multi-stage Dockerfile for FastAPI application (P07 Container Hardening)
# Security: non-root user, minimal image, explicit versions, hardened base
# Performance: multi-stage build, layer caching, no dev tools in final image

# ============= Stage 1: Builder =============
FROM python:3.12.1-slim AS builder

WORKDIR /build

# Copy requirements
COPY requirements*.txt ./

# Build wheel cache (layers) 
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip==24.0 setuptools==68.2.2 wheel==0.42.0 && \
    pip wheel --no-cache-dir --wheel-dir=/wheels -r requirements.txt

# ============= Stage 2: Runtime =============
FROM python:3.12.1-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Create non-root user (security hardening)
RUN groupadd -r app && \
    useradd -r -g app -u 1000 app && \
    mkdir -p /app && \
    chown -R app:app /app

# Install dependencies from builder
COPY --from=builder --chown=app:app /wheels /wheels

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir /wheels/* && \
    rm -rf /wheels

COPY --chown=app:app app/ ./app/

# Switch to non-root user BEFORE ENTRYPOINT
USER app

# Health check (verify service is responding)
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=2)" || exit 1

# Explicit port
EXPOSE 8000

# Explicit command (python as entrypoint via CMD)
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Labels for metadata
LABEL maintainer="Security Development Course" \
      version="0.1.0" \
      description="SecDev Course App - Hardened Container" \
      security.non-root="true" \
      security.healthcheck="true"

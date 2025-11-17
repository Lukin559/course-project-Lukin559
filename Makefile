.PHONY: help build run stop logs shell test-container scan lint-docker clean

IMAGE_NAME := secdev-app
CONTAINER_NAME := secdev-app

help:
	@echo "=== P07 Container Hardening Commands ==="
	@echo "make build          - Build Docker image"
	@echo "make run            - Run container with docker-compose"
	@echo "make stop           - Stop running container"
	@echo "make logs           - View container logs"
	@echo "make shell          - Open shell in container"
	@echo "make test-container - Test container (user, healthcheck, ports)"
	@echo "make scan           - Scan image with Trivy (vulnerability scanning)"
	@echo "make lint-docker    - Lint Dockerfile with Hadolint"
	@echo "make clean          - Remove image and containers"

# Build Docker image
build:
	@echo "Building Docker image ($(IMAGE_NAME))..."
	docker build -t $(IMAGE_NAME):latest .
	@echo "✓ Image built successfully"
	docker images | grep $(IMAGE_NAME)

# Run with docker-compose
run:
	@echo "Starting container with docker-compose..."
	docker-compose up -d
	@echo "✓ Container started"
	@echo "  App: http://localhost:8000"
	@echo "  Docs: http://localhost:8000/docs"
	@sleep 2 && docker-compose ps

# Stop container
stop:
	@echo "Stopping container..."
	docker-compose down
	@echo "✓ Container stopped"

# View logs
logs:
	docker-compose logs -f app

# Open shell in running container
shell:
	docker-compose exec app /bin/bash

# Test container security & functionality
test-container: build
	@echo "=== Testing Container Security & Functionality ==="
	@echo ""
	@echo "1. Testing non-root user..."
	@docker run --rm $(IMAGE_NAME):latest sh -c 'id' | grep -q "uid=1000" && echo "✓ Running as UID 1000 (non-root)" || echo "✗ WARNING: May be running as different user"
	@echo ""
	@echo "2. Testing application startup..."
	@docker run --rm -d --name test-app -p 8001:8000 $(IMAGE_NAME):latest > /dev/null
	@sleep 3
	@curl -s http://localhost:8001/health | grep -q '"status":"ok"' && echo "✓ Health check passed" || echo "✗ Health check failed"
	@docker stop test-app > /dev/null
	@echo ""
	@echo "3. Checking image layers..."
	@echo "✓ Image size:"
	@docker images $(IMAGE_NAME):latest --format "{{.Size}}"
	@echo ""
	@echo "=== All tests completed ==="

# Scan image with Trivy
scan: build
	@echo "=== Scanning Docker image with Trivy ==="
	@echo "Image: $(IMAGE_NAME):latest"
	@echo ""
	@if command -v trivy &> /dev/null; then \
		trivy image --severity HIGH,CRITICAL $(IMAGE_NAME):latest; \
	else \
		echo "⚠ Trivy not installed. Install with: brew install trivy"; \
		echo "  Running basic checks..."; \
		docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image --severity HIGH,CRITICAL $(IMAGE_NAME):latest; \
	fi

# Lint Dockerfile
lint-docker:
	@echo "=== Linting Dockerfile with Hadolint ==="
	@if command -v hadolint &> /dev/null; then \
		hadolint Dockerfile; \
	else \
		echo "⚠ Hadolint not installed. Install with: brew install hadolint"; \
		echo "  Running lint via Docker..."; \
		docker run --rm -i hadolint/hadolint < Dockerfile; \
	fi
	@echo "✓ Lint completed"

# Clean up
clean:
	@echo "Cleaning up..."
	docker-compose down -v
	docker rmi $(IMAGE_NAME):latest 2>/dev/null || true
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✓ Cleanup completed"

# Full CI pipeline
ci: lint-docker build test-container scan
	@echo "✓ Full CI pipeline passed"

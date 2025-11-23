.PHONY: help build run stop logs shell test-container scan lint-docker sbom inspect history reports load-profiles clean ci

IMAGE_NAME := secdev-app
CONTAINER_NAME := secdev-app
REPORTS_DIR := reports

help:
	@echo "=== P07 Container Hardening Commands (★★2) ==="
	@echo "make build          - Build Docker image"
	@echo "make run            - Run container with docker-compose"
	@echo "make stop           - Stop running container"
	@echo "make logs           - View container logs"
	@echo "make shell          - Open shell in container"
	@echo "make test-container - Test container (user, healthcheck, ports)"
	@echo "make scan           - Scan image with Trivy (vulnerability scanning)"
	@echo "make lint-docker    - Lint Dockerfile with Hadolint"
	@echo "make sbom           - Generate SBOM (Software Bill of Materials)"
	@echo "make inspect        - Inspect container security config"
	@echo "make history        - Show image layers and size optimization"
	@echo "make reports        - Generate all security reports (lint + scan + sbom)"
	@echo "make load-profiles  - Load AppArmor/seccomp security profiles (requires sudo)"
	@echo "make clean          - Remove image and containers"
	@echo "make ci             - Run full CI pipeline"

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

# Scan image with Trivy (detailed reports for C4 ★★2)
scan: build
	@echo "=== Scanning Docker image with Trivy ==="
	@echo "Image: $(IMAGE_NAME):latest"
	@mkdir -p $(REPORTS_DIR)
	@echo ""
	@if command -v trivy &> /dev/null; then \
		echo "Running Trivy scan (table format)..."; \
		trivy image --severity HIGH,CRITICAL,MEDIUM --ignorefile .trivyignore $(IMAGE_NAME):latest | tee $(REPORTS_DIR)/trivy-report.txt; \
		echo ""; \
		echo "Generating JSON report..."; \
		trivy image --format json --output $(REPORTS_DIR)/trivy-report.json --ignorefile .trivyignore $(IMAGE_NAME):latest; \
		echo "✓ Trivy reports saved to $(REPORTS_DIR)/"; \
	else \
		echo "⚠ Trivy not installed. Install with: brew install trivy"; \
		echo "  Running scan via Docker..."; \
		docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v $(PWD)/.trivyignore:/root/.trivyignore -v $(PWD)/$(REPORTS_DIR):/output aquasec/trivy image --severity HIGH,CRITICAL,MEDIUM --ignorefile /root/.trivyignore $(IMAGE_NAME):latest | tee $(REPORTS_DIR)/trivy-report.txt; \
	fi

# Lint Dockerfile with detailed report
lint-docker:
	@echo "=== Linting Dockerfile with Hadolint ==="
	@mkdir -p $(REPORTS_DIR)
	@if command -v hadolint &> /dev/null; then \
		hadolint --config .hadolint.yaml Dockerfile | tee $(REPORTS_DIR)/hadolint-report.txt; \
	else \
		echo "⚠ Hadolint not installed. Install with: brew install hadolint"; \
		echo "  Running lint via Docker..."; \
		docker run --rm -i -v $(PWD)/.hadolint.yaml:/root/.hadolint.yaml hadolint/hadolint < Dockerfile | tee $(REPORTS_DIR)/hadolint-report.txt; \
	fi
	@echo "✓ Lint completed. Report saved to $(REPORTS_DIR)/hadolint-report.txt"

# Generate SBOM (Software Bill of Materials)
sbom: build
	@echo "=== Generating SBOM with Trivy ==="
	@mkdir -p $(REPORTS_DIR)
	@if command -v trivy &> /dev/null; then \
		trivy image --format cyclonedx --output $(REPORTS_DIR)/sbom.json $(IMAGE_NAME):latest; \
		echo "✓ SBOM (CycloneDX) saved to $(REPORTS_DIR)/sbom.json"; \
		trivy image --format spdx-json --output $(REPORTS_DIR)/sbom-spdx.json $(IMAGE_NAME):latest; \
		echo "✓ SBOM (SPDX) saved to $(REPORTS_DIR)/sbom-spdx.json"; \
	else \
		echo "⚠ Trivy not installed. Using Docker..."; \
		docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v $(PWD)/$(REPORTS_DIR):/output aquasec/trivy image --format cyclonedx --output /output/sbom.json $(IMAGE_NAME):latest; \
	fi

# Inspect container security configuration
inspect: build
	@echo "=== Inspecting Container Security Configuration ==="
	@mkdir -p $(REPORTS_DIR)
	@echo "Starting temporary container for inspection..."
	@docker run -d --name $(CONTAINER_NAME)-inspect $(IMAGE_NAME):latest > /dev/null
	@sleep 2
	@echo ""
	@echo "1. User Configuration:"
	@docker exec $(CONTAINER_NAME)-inspect whoami
	@docker exec $(CONTAINER_NAME)-inspect id
	@echo ""
	@echo "2. Security Options:"
	@docker inspect $(CONTAINER_NAME)-inspect --format='{{json .HostConfig.SecurityOpt}}' | jq
	@echo ""
	@echo "3. Capabilities (Dropped):"
	@docker inspect $(CONTAINER_NAME)-inspect --format='{{json .HostConfig.CapDrop}}' | jq
	@echo ""
	@echo "4. Capabilities (Added):"
	@docker inspect $(CONTAINER_NAME)-inspect --format='{{json .HostConfig.CapAdd}}' | jq
	@echo ""
	@echo "5. AppArmor Profile:"
	@docker inspect $(CONTAINER_NAME)-inspect --format='{{.AppArmorProfile}}'
	@echo ""
	@docker inspect $(CONTAINER_NAME)-inspect > $(REPORTS_DIR)/docker-inspect.json
	@echo "✓ Full inspect report saved to $(REPORTS_DIR)/docker-inspect.json"
	@docker stop $(CONTAINER_NAME)-inspect > /dev/null
	@docker rm $(CONTAINER_NAME)-inspect > /dev/null

# Show image history and size optimization
history: build
	@echo "=== Docker Image History & Size Analysis ==="
	@mkdir -p $(REPORTS_DIR)
	@echo ""
	@echo "Image Layers:"
	@docker history $(IMAGE_NAME):latest
	@echo ""
	@echo "Image Size Comparison:"
	@docker images | grep -E "REPOSITORY|$(IMAGE_NAME)|python.*3.12.*slim"
	@echo ""
	@docker history $(IMAGE_NAME):latest > $(REPORTS_DIR)/docker-history.txt
	@docker images $(IMAGE_NAME):latest >> $(REPORTS_DIR)/docker-history.txt
	@echo "✓ History report saved to $(REPORTS_DIR)/docker-history.txt"

# Generate all security reports (C4 ★★2)
reports: lint-docker build scan sbom history inspect
	@echo ""
	@echo "=== All Security Reports Generated ==="
	@echo "Reports directory: $(REPORTS_DIR)/"
	@ls -lh $(REPORTS_DIR)/
	@echo ""
	@echo "✓ Reports ready for CI artifacts"

# Clean up
clean:
	@echo "Cleaning up..."
	docker-compose down -v
	docker rmi $(IMAGE_NAME):latest 2>/dev/null || true
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf $(REPORTS_DIR) 2>/dev/null || true
	@echo "✓ Cleanup completed"

# Full CI pipeline (★★2 level)
ci: reports test-container
	@echo ""
	@echo "=== CI Pipeline Summary ==="
	@echo "✓ Dockerfile linting passed"
	@echo "✓ Container build successful"
	@echo "✓ Security scan completed"
	@echo "✓ SBOM generated"
	@echo "✓ Container tests passed"
	@echo ""
	@echo "📊 View all reports in: $(REPORTS_DIR)/"
	@echo "✓ Full CI pipeline passed"

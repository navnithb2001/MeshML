# Makefile for MeshML Development

.PHONY: help install test lint format clean docker-up docker-down db-init

help:  ## Show this help message
	@echo "MeshML Development Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies
	@echo "Installing dependencies..."
	./scripts/setup/install_deps.sh

test: ## Run all tests
	@echo "Running Python tests..."
	@for service in services/*/; do \
		if [ -f "$$service/requirements.txt" ]; then \
			echo "Testing $$service"; \
			cd $$service && source venv/bin/activate && pytest tests/ && cd ../..; \
		fi \
	done

lint: ## Run all linters
	@echo "Running linters..."
	pre-commit run --all-files

format: ## Format all code
	@echo "Formatting Python..."
	black services/ shared/
	isort services/ shared/
	@echo "Formatting JavaScript..."
	cd dashboard && npm run format
	cd workers/js-worker && npm run format

clean: ## Clean build artifacts
	@echo "Cleaning..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete

docker-up: ## Start all Docker services
	./scripts/dev/start_services.sh

docker-down: ## Stop all Docker services
	./scripts/dev/stop_services.sh

db-init: ## Initialize database
	./scripts/setup/init_db.sh

db-reset: ## Reset database (⚠️ destroys data)
	./scripts/dev/reset_db.sh

pre-commit-install: ## Install pre-commit hooks
	pip install pre-commit
	pre-commit install

pre-commit-run: ## Run pre-commit on all files
	pre-commit run --all-files

ci-local: ## Run CI checks locally
	@echo "Running local CI checks..."
	@make lint
	@make test
	@echo "✅ All checks passed!"

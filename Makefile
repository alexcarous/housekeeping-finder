.PHONY: setup test cov lint format run clean help

# Use uv as the modern 2026 standard if available, otherwise fallback to python
PYTHON := $(shell which uv > /dev/null && echo "uv run" || echo "python3")
PIP := $(shell which uv > /dev/null && echo "uv pip" || echo "pip")

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## Setup environment and install dependencies
	@echo "Setting up environment..."
	@which uv > /dev/null && uv sync --all-extras || $(PIP) install -e ".[dev]"
	@if [ ! -f .env ]; then cp .env.example .env && echo "Created default .env"; fi

test: ## Run tests
	@echo "Running tests..."
	$(PYTHON) -m pytest --cov=beneat --cov-report=term-missing tests/

cov: ## Run tests and open HTML coverage report in browser
	@echo "Generating coverage report..."
	$(PYTHON) -m pytest --cov=beneat --cov-report=html tests/
	@which xdg-open > /dev/null && xdg-open htmlcov/index.html || \
	 which open > /dev/null && open htmlcov/index.html || \
	 echo "Open htmlcov/index.html in your browser to view report."

lint: ## Run linter (Ruff) and type checker (Mypy)
	@echo "Running code quality checks..."
	$(PYTHON) -m ruff check .
	$(PYTHON) -m mypy src/

format: ## Auto-format code (Ruff)
	@echo "Formatting code..."
	$(PYTHON) -m ruff format .

run: ## Run the application
	@echo "Running application..."
	PYTHONPATH=src $(PYTHON) -m beneat.main

clean: ## Clean up cache and build artifacts
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov/ build/ dist/

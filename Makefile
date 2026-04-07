# ============================================================
# Energy Saver AI — Makefile
# ============================================================
# Prerequisites: Python 3.10+, pip, GNU Make (or NMAKE on Windows)
#
# Usage:
#   make install       Install core deps
#   make install-all   Install core + streaming + dev deps
#   make data          Generate sample data
#   make train         Train all 8 AI models
#   make finetune      Fine-tune with deep learning backbone
#   make stream        Launch streaming pipeline (simulate)
#   make test          Run test suite
#   make lint          Lint & format-check
#   make format        Auto-format code
#   make clean         Remove build artefacts
#   make docker-build  Build Docker image
#   make docker-up     Spin up local services via docker-compose

.PHONY: all install install-all data train finetune stream test lint format clean \
        docker-build docker-up docker-down help

PYTHON ?= python
PIP    ?= pip

# ─────────────────────────────────────────────────────────────
# Installation
# ─────────────────────────────────────────────────────────────
install:
	$(PIP) install --upgrade pip
	$(PIP) install .

install-streaming:
	$(PIP) install ".[streaming]"

install-dev:
	$(PIP) install ".[dev]"

install-all:
	$(PIP) install ".[all]"

# ─────────────────────────────────────────────────────────────
# Pipeline steps
# ─────────────────────────────────────────────────────────────
data:
	$(PYTHON) data/generate_data.py

train: data
	$(PYTHON) main.py train

finetune:
	$(PYTHON) main.py finetune

stream:
	$(PYTHON) main.py stream

demo:
	$(PYTHON) main.py demo

savings:
	$(PYTHON) main.py savings

info:
	$(PYTHON) main.py info

# ─────────────────────────────────────────────────────────────
# Testing
# ─────────────────────────────────────────────────────────────
test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ -v --tb=short \
	    --cov=. \
	    --cov-report=term-missing \
	    --cov-report=html:htmlcov

test-fast:
	pytest tests/ -v --tb=short -x \
	    --ignore=tests/test_data_generation.py

# ─────────────────────────────────────────────────────────────
# Linting & Formatting
# ─────────────────────────────────────────────────────────────
lint:
	ruff check .
	ruff format --check .

format:
	ruff format .
	ruff check . --fix

# ─────────────────────────────────────────────────────────────
# Docker
# ─────────────────────────────────────────────────────────────
docker-build:
	docker build -f streaming/cloud/Dockerfile -t energy-saver-ai:latest .

docker-up:
	docker compose -f streaming/cloud/docker-compose.yml up -d

docker-down:
	docker compose -f streaming/cloud/docker-compose.yml down

docker-logs:
	docker compose -f streaming/cloud/docker-compose.yml logs -f

# ─────────────────────────────────────────────────────────────
# Housekeeping
# ─────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	rm -rf .pytest_cache .coverage coverage.xml htmlcov .mypy_cache .ruff_cache
	rm -rf dist build *.egg-info

clean-models:
	rm -f ml_models/*.keras ml_models/*.h5 ml_models/*.pkl
	rm -rf ml_models/finetuned ml_models/pretrained

clean-outputs:
	rm -rf outputs/

# ─────────────────────────────────────────────────────────────
# Help
# ─────────────────────────────────────────────────────────────
help:
	@echo "Energy Saver AI - Available Targets"
	@echo "====================================="
	@echo "  install        Install core dependencies"
	@echo "  install-all    Install all dependencies (core + streaming + dev)"
	@echo "  data           Generate sample CSV data"
	@echo "  train          Train all 8 AI models"
	@echo "  finetune       Fine-tune with deep learning backbone"
	@echo "  stream         Start streaming pipeline (simulate mode)"
	@echo "  demo           End-to-end demo"
	@echo "  test           Run tests"
	@echo "  test-cov       Run tests with HTML coverage report"
	@echo "  lint           Lint code with ruff"
	@echo "  format         Auto-format code with ruff"
	@echo "  docker-build   Build Docker image"
	@echo "  docker-up      Start local services (Kafka, MQTT)"
	@echo "  docker-down    Stop local services"
	@echo "  clean          Remove build artefacts"

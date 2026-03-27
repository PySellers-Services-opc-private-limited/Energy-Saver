# Contributing to Energy Saver AI

Thank you for considering contributing! This guide explains how to set up your development environment, write code that fits the project's style, and submit your changes.

---

## Table of Contents
1. [Getting Started](#getting-started)
2. [Development Setup](#development-setup)
3. [Project Structure](#project-structure)
4. [Coding Standards](#coding-standards)
5. [Writing Tests](#writing-tests)
6. [Submitting a Pull Request](#submitting-a-pull-request)
7. [Reporting Issues](#reporting-issues)

---

## Getting Started

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/your-username/energy-saver-ai.git
   cd energy-saver-ai
   ```
3. Add the upstream remote:
   ```bash
   git remote add upstream https://github.com/your-org/energy-saver-ai.git
   ```

---

## Development Setup

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# Install all dependencies (core + streaming + dev tools)
make install-all
# or manually:
pip install -r requirements.txt -r requirements_streaming.txt -r requirements_dev.txt

# Install pre-commit hooks
pre-commit install

# Copy environment template
cp .env.example .env
# Edit .env with your local settings (at minimum: CLOUD_PROVIDER)
```

### Local services (Kafka + MQTT)

```bash
# Start local Kafka + Mosquitto MQTT via Docker Compose
make docker-up

# Stop them
make docker-down
```

---

## Project Structure

```
energy_saver_ai/
├── config/              # Centralised settings (settings.py)
├── data/                # Data generation scripts + sample CSVs
├── models/              # 8 standalone training scripts (model_1 … model_8)
├── deep_learning/       # TCN backbone, BERT pretraining, fine-tuning strategies
├── streaming/           # Live pipeline: MQTT, Kafka, WebSocket, REST, HA, alerts
├── utils/               # Shared helpers, metrics, feature encoding
├── tests/               # pytest test suite
├── .github/workflows/   # CI/CD (GitHub Actions)
├── main.py              # Unified CLI entry point
├── run_all.py           # Sequential pipeline runner
├── pyproject.toml       # Package metadata + tool config
├── Makefile             # Common dev commands
└── requirements*.txt    # Dependency files
```

---

## Coding Standards

We use **ruff** for linting and formatting.

```bash
# Check for issues
make lint

# Auto-fix formatting
make format
```

Key rules:
- Line length: **100 characters**
- Imports: **isort** order (stdlib → third-party → local)
- Type hints for all **public** functions and methods
- Docstrings for all public classes, methods, and modules
- No bare `except:` — always catch specific exceptions
- Log with `logging.getLogger(__name__)` — never `print()` in library code

---

## Writing Tests

Tests live in `tests/`. We use **pytest** with **pytest-asyncio** for async tests.

```bash
# Run the full test suite
make test

# Run with coverage report
make test-cov

# Run a specific file
pytest tests/test_helpers.py -v
```

**Guidelines:**
- Every new public function needs at least one test
- Use `pytest.approx` for floating-point comparisons
- Mock external services (MQTT broker, Kafka, cloud APIs) — do not hit real endpoints in tests
- Async tests must be decorated with `@pytest.mark.asyncio`

Example:

```python
import pytest
from utils.helpers import current_tariff

def test_peak_tariff():
    assert current_tariff(18) == pytest.approx(0.28)
```

---

## Submitting a Pull Request

1. **Create a branch** from `develop` (not `main`):
   ```bash
   git checkout develop
   git pull upstream develop
   git checkout -b feat/my-feature
   ```
2. Make your changes and **write tests** for new code.
3. Ensure all checks pass locally:
   ```bash
   make lint test
   ```
4. **Commit** with a clear message following [Conventional Commits](https://www.conventionalcommits.org/):
   ```
   feat(streaming): add Azure Event Grid alert dispatcher
   fix(models): correct LSTM input shape for variable windows
   docs: update HVAC optimization section in README
   ```
5. **Push** and open a Pull Request against `develop`.
6. Fill in the PR template and link any related issues.

---

## Reporting Issues

Please open a GitHub Issue with:
- A clear title
- Steps to reproduce
- Expected vs actual behaviour
- Environment info (`python --version`, OS, GPU/CPU)
- Relevant logs (use `LOG_LEVEL=DEBUG` to capture verbose output)

---

*By contributing, you agree your code will be released under the [MIT License](LICENSE).*

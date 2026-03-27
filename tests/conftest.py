"""
pytest configuration and shared fixtures for Energy Saver AI test suite.
"""
import os
import sys

import pytest

# Ensure the project root is on sys.path so test imports work without
# installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────────────────────────────
# Environment defaults for tests (no real cloud services needed)
# ─────────────────────────────────────────────────────────────

os.environ.setdefault("CLOUD_PROVIDER", "gcp")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("KAFKA_BROKERS", "localhost:9092")
os.environ.setdefault("MQTT_BROKER", "localhost")


# ─────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def project_root() -> str:
    """Absolute path to the repository root."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

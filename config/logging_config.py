"""
Structured Logging Configuration — Energy Saver AI
=====================================================
Provides JSON-structured logging suitable for cloud log aggregators
(CloudWatch, Azure Monitor, GCP Cloud Logging, ELK Stack).

Usage:
    from config.logging_config import configure_logging
    configure_logging()

    import logging
    log = logging.getLogger(__name__)
    log.info("Pipeline started", extra={"device_id": "device-001"})
"""

from __future__ import annotations

import json
import logging
import logging.config
import os
import sys
from datetime import datetime, timezone
from typing import Any


# ─────────────────────────────────────────────────────────────
# JSON Formatter
# ─────────────────────────────────────────────────────────────

class _JSONFormatter(logging.Formatter):
    """
    Emit log records as single-line JSON for structured log ingestion.
    Standard fields: timestamp, level, logger, message.
    Any keys passed via extra={} are merged in.
    """

    # Keys that should not be forwarded from LogRecord.extra
    _RESERVED = frozenset(
        logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
        | {"message", "asctime", "exc_text"}
    )

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level":   record.levelname,
            "logger":  record.name,
            "message": record.message,
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Forward any user-supplied extra fields
        for key, val in record.__dict__.items():
            if key not in self._RESERVED:
                payload[key] = val

        return json.dumps(payload, default=str)


# ─────────────────────────────────────────────────────────────
# Human-friendly Formatter (for development)
# ─────────────────────────────────────────────────────────────

_DEV_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)-30s | %(message)s"
_DEV_DATE   = "%H:%M:%S"


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def configure_logging(
    level: str = "INFO",
    json_logs: bool | None = None,
    log_file: str | None = None,
) -> None:
    """
    Configure application-wide logging.

    Args:
        level:     Root log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_logs: Emit JSON lines. Defaults to True when LOG_FORMAT=json
                   or when stdout is not a TTY (i.e. running in a container).
        log_file:  Optional path to write logs to in addition to stdout.
    """
    if json_logs is None:
        json_logs = (
            os.environ.get("LOG_FORMAT", "").lower() == "json"
            or not sys.stdout.isatty()
        )

    root_level = getattr(logging, level.upper(), logging.INFO)

    # ── Handlers ─────────────────────────────────────────────
    handlers: list[dict[str, Any]] = {
        "console": {
            "class":     "logging.StreamHandler",
            "stream":    "ext://sys.stdout",
            "formatter": "json" if json_logs else "dev",
        }
    }
    handler_names = ["console"]

    if log_file:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        handlers["file"] = {
            "class":       "logging.handlers.TimedRotatingFileHandler",
            "filename":    log_file,
            "when":        "midnight",
            "backupCount": 7,
            "encoding":    "utf-8",
            "formatter":   "json",  # always JSON in files
        }
        handler_names.append("file")

    config: dict[str, Any] = {
        "version":                  1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {"()": _JSONFormatter},
            "dev":  {
                "format":  _DEV_FORMAT,
                "datefmt": _DEV_DATE,
            },
        },
        "handlers": handlers,
        "root": {
            "level":    root_level,
            "handlers": handler_names,
        },
        # Quiet noisy third-party libraries
        "loggers": {
            "urllib3":         {"level": "WARNING", "propagate": True},
            "asyncio":         {"level": "WARNING", "propagate": True},
            "websockets":      {"level": "WARNING", "propagate": True},
            "aiokafka":        {"level": "WARNING", "propagate": True},
            "tensorflow":      {"level": "ERROR",   "propagate": True},
            "absl":            {"level": "ERROR",   "propagate": True},
            "google":          {"level": "WARNING", "propagate": True},
            "azure":           {"level": "WARNING", "propagate": True},
            "botocore":        {"level": "WARNING", "propagate": True},
            "boto3":           {"level": "WARNING", "propagate": True},
        },
    }

    logging.config.dictConfig(config)

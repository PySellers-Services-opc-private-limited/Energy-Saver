"""
Shared Utilities — Energy Saver AI
====================================
Common helpers used across models, streaming, and fine-tuning.
"""

import logging
import os
import sys
import time
import json
import numpy as np
from datetime import datetime
from typing import Optional, List, Tuple


# ─────────────────────────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────────────────────────

def setup_logging(level: str = "INFO", log_file: Optional[str] = None):
    """
    Configure structured logging for the entire project.
    Writes to stdout (and optionally a file).
    """
    fmt = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        datefmt="%H:%M:%S",
        handlers=handlers,
    )
    # Quiet noisy third-party loggers
    for lib in ("urllib3", "asyncio", "websockets.server", "aiokafka"):
        logging.getLogger(lib).setLevel(logging.WARNING)


# ─────────────────────────────────────────────────────────────────
# FEATURE ENCODING
# ─────────────────────────────────────────────────────────────────

FEATURE_NAMES = [
    "consumption_kwh",
    "temperature",
    "humidity",
    "occupancy",
    "solar_kwh",
    "tariff",
]
N_FEATURES = len(FEATURE_NAMES)

FEATURE_DEFAULTS = {
    "consumption_kwh": 2.0,
    "temperature":     20.0,
    "humidity":        50.0,
    "occupancy":        0.0,
    "solar_kwh":        0.0,
    "tariff":           0.13,
}


def reading_to_vector(reading: dict) -> List[float]:
    """
    Convert a raw sensor reading dict to a fixed-length feature vector.
    Missing fields are filled with safe defaults.
    """
    return [float(reading.get(f, FEATURE_DEFAULTS[f])) for f in FEATURE_NAMES]


def normalize_window(window: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Min-max normalise a (T, F) sensor window per feature.
    Returns: (normalised, mins, maxs) — save mins/maxs to denormalise later.
    """
    mins = window.min(axis=0, keepdims=True)
    maxs = window.max(axis=0, keepdims=True)
    rng  = np.where(maxs - mins > 1e-8, maxs - mins, 1.0)
    return (window - mins) / rng, mins.squeeze(), maxs.squeeze()


def add_time_features(window: np.ndarray, start_hour: int = 0) -> np.ndarray:
    """
    Append sin/cos hour-of-day features to each time step.
    Helps models learn time-of-day patterns without explicit encoding.

    Returns: (T, F+2) array with hour_sin and hour_cos appended.
    """
    T = window.shape[0]
    hours    = np.arange(start_hour, start_hour + T) % 24
    hour_sin = np.sin(2 * np.pi * hours / 24).reshape(-1, 1)
    hour_cos = np.cos(2 * np.pi * hours / 24).reshape(-1, 1)
    return np.hstack([window, hour_sin, hour_cos])


# ─────────────────────────────────────────────────────────────────
# TARIFF SCHEDULE
# ─────────────────────────────────────────────────────────────────

TARIFF_SCHEDULE = {h: (
    0.28 if 17 <= h <= 20 else        # Peak
    0.08 if h < 7 or h >= 22 else    # Off-peak
    0.13                               # Standard
) for h in range(24)}


def current_tariff(hour: Optional[int] = None) -> float:
    """Return the time-of-use tariff for a given hour (default: now)."""
    if hour is None:
        hour = datetime.now().hour
    return TARIFF_SCHEDULE.get(hour, 0.13)


def is_peak_hour(hour: Optional[int] = None) -> bool:
    return current_tariff(hour) >= 0.20


def cheapest_hours(n: int = 8) -> List[int]:
    """Return the n cheapest hours of the day, sorted ascending."""
    return sorted(TARIFF_SCHEDULE, key=lambda h: TARIFF_SCHEDULE[h])[:n]


# ─────────────────────────────────────────────────────────────────
# MODEL HELPERS
# ─────────────────────────────────────────────────────────────────

def load_model_safe(path: str, fallback_fn=None):
    """
    Load a Keras model from disk. Returns None (or fallback result)
    if the file doesn't exist or TF is not installed.
    """
    if not os.path.exists(path):
        logging.getLogger("utils").warning(f"Model not found: {path}")
        return fallback_fn() if fallback_fn else None
    try:
        import tensorflow as tf
        model = tf.keras.models.load_model(path)
        logging.getLogger("utils").info(f"✅ Loaded model: {path}")
        return model
    except Exception as e:
        logging.getLogger("utils").error(f"Failed to load {path}: {e}")
        return fallback_fn() if fallback_fn else None


def count_parameters(model) -> int:
    """Count total trainable parameters in a Keras model."""
    try:
        return int(sum(np.prod(v.shape) for v in model.trainable_variables))
    except Exception:
        return 0


# ─────────────────────────────────────────────────────────────────
# METRICS TRACKING
# ─────────────────────────────────────────────────────────────────

class PipelineMetrics:
    """
    Lightweight in-memory metrics tracker.
    Exported via the WebSocket stats broadcast every 60s.
    """

    def __init__(self):
        self._start      = time.time()
        self._counters   = {}
        self._gauges     = {}
        self._histograms = {}

    def inc(self, name: str, amount: int = 1):
        self._counters[name] = self._counters.get(name, 0) + amount

    def set(self, name: str, value: float):
        self._gauges[name] = value

    def observe(self, name: str, value: float):
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(value)
        if len(self._histograms[name]) > 1000:
            self._histograms[name] = self._histograms[name][-500:]

    def summary(self) -> dict:
        uptime = int(time.time() - self._start)
        hist_summary = {}
        for k, vals in self._histograms.items():
            if vals:
                arr = np.array(vals)
                hist_summary[k] = {
                    "count": len(arr),
                    "mean":  round(float(arr.mean()), 4),
                    "p50":   round(float(np.percentile(arr, 50)), 4),
                    "p95":   round(float(np.percentile(arr, 95)), 4),
                    "p99":   round(float(np.percentile(arr, 99)), 4),
                }
        return {
            "uptime_s":   uptime,
            "counters":   dict(self._counters),
            "gauges":     dict(self._gauges),
            "histograms": hist_summary,
        }

    def reset(self):
        self._counters   = {}
        self._gauges     = {}
        self._histograms = {}


# ─────────────────────────────────────────────────────────────────
# ENERGY SAVINGS CALCULATOR
# ─────────────────────────────────────────────────────────────────

def estimate_annual_savings(
    baseline_kwh_per_day: float = 30.0,
    hvac_saving_pct:      float = 0.30,
    ev_saving_pct:        float = 0.15,
    anomaly_saving_pct:   float = 0.05,
    tariff_per_kwh:       float = 0.15,
) -> dict:
    """
    Estimate annual energy and cost savings from deploying Energy Saver AI.

    Args:
        baseline_kwh_per_day: Average daily consumption before AI
        hvac_saving_pct:      HVAC optimisation saving fraction
        ev_saving_pct:        EV smart charging saving fraction
        anomaly_saving_pct:   Waste from fixed anomalies fraction
        tariff_per_kwh:       Average electricity cost

    Returns dict with savings breakdown.
    """
    hvac_daily   = baseline_kwh_per_day * hvac_saving_pct
    ev_daily     = baseline_kwh_per_day * ev_saving_pct
    anomaly_daily = baseline_kwh_per_day * anomaly_saving_pct
    total_daily  = hvac_daily + ev_daily + anomaly_daily

    kwh_per_year = total_daily * 365
    cost_per_year = kwh_per_year * tariff_per_kwh
    co2_kg_per_year = kwh_per_year * 0.233   # avg grid 233gCO₂/kWh

    return {
        "kwh_saved_per_day":    round(total_daily, 2),
        "kwh_saved_per_year":   round(kwh_per_year, 1),
        "cost_saved_per_year":  round(cost_per_year, 2),
        "co2_saved_kg_per_year": round(co2_kg_per_year, 1),
        "breakdown": {
            "hvac_kwh":    round(hvac_daily * 365, 1),
            "ev_kwh":      round(ev_daily * 365, 1),
            "anomaly_kwh": round(anomaly_daily * 365, 1),
        }
    }


# ─────────────────────────────────────────────────────────────────
# JSON SERIALISER (handles numpy types)
# ─────────────────────────────────────────────────────────────────

class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy scalars and arrays."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def to_json(obj: dict) -> str:
    return json.dumps(obj, cls=NumpyEncoder)

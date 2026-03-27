"""
ModelService – loads and manages all 8 trained AI models for inference.
"""

from __future__ import annotations

import logging
import os
import pickle
from pathlib import Path
from typing import Any

import numpy as np

from app.schemas import ModelInfo

logger = logging.getLogger("energy_saver_ai.model_service")

_BACKEND_DIR  = Path(__file__).parent.parent.parent.resolve()
_PROJECT_ROOT = _BACKEND_DIR.parent
_MODELS_DIR   = _PROJECT_ROOT / "models"

_MODEL_REGISTRY = [
    {"name": "Energy Forecasting (LSTM)",       "file": "forecasting_model.keras",    "version": "1.0", "key": "forecasting"},
    {"name": "Anomaly Detection (Autoencoder)", "file": "anomaly_model.keras",         "version": "1.0", "key": "anomaly"},
    {"name": "Occupancy Classification",        "file": "occupancy_model.keras",       "version": "1.0", "key": "occupancy"},
    {"name": "HVAC Optimisation",               "file": None,                          "version": "1.0", "key": "hvac"},
    {"name": "Appliance Fingerprinting",        "file": "fingerprinting_model.keras",  "version": "1.0", "key": "fingerprinting"},
    {"name": "Solar Forecast (CNN-LSTM)",       "file": "solar_model.keras",           "version": "1.0", "key": "solar"},
    {"name": "EV Charging Optimiser",           "file": "ev_q_table.npy",             "version": "1.0", "key": "ev"},
    {"name": "Bill Predictor (Neural Net)",     "file": "bill_predictor_model.keras",  "version": "1.0", "key": "bill"},
]

# Scaler files associated with models
_SCALER_FILES = {
    "occupancy":     "occupancy_scaler.pkl",
    "solar":         "solar_scaler.pkl",
    "bill_X":        "bill_scaler_X.pkl",
    "bill_y":        "bill_scaler_y.pkl",
    "fingerprinting":"fingerprinting_encoder.pkl",
}


class ModelService:
    _models: dict[str, Any] = {}
    _scalers: dict[str, Any] = {}
    _anomaly_threshold: float = 0.5
    _status: list[ModelInfo] = []

    @classmethod
    def preload(cls) -> None:
        """Load all model files from disk into memory."""
        try:
            import tensorflow as tf  # type: ignore
            tf.get_logger().setLevel("ERROR")
        except ImportError:
            logger.warning("TensorFlow not installed – model inference unavailable")
            tf = None  # type: ignore

        cls._models = {}
        cls._scalers = {}
        cls._status = []

        # Load Keras models
        if tf is not None:
            for entry in _MODEL_REGISTRY:
                key = entry["key"]
                fname = entry["file"]
                if fname is None or not fname.endswith(".keras"):
                    continue
                path = _MODELS_DIR / fname
                if path.exists():
                    try:
                        cls._models[key] = tf.keras.models.load_model(str(path))
                        logger.info(f"Loaded model: {entry['name']}")
                    except Exception as exc:
                        logger.error(f"Failed to load {entry['name']}: {exc}")
                else:
                    logger.warning(f"Model file not found: {path}")

        # Load EV Q-table
        ev_path = _MODELS_DIR / "ev_q_table.npy"
        if ev_path.exists():
            cls._models["ev"] = np.load(str(ev_path))
            logger.info("Loaded EV Q-table")

        # Load anomaly threshold
        threshold_path = _MODELS_DIR / "anomaly_threshold.npy"
        if threshold_path.exists():
            cls._anomaly_threshold = float(np.load(str(threshold_path)))
            logger.info(f"Anomaly threshold: {cls._anomaly_threshold:.4f}")

        # Load scalers
        for skey, sfname in _SCALER_FILES.items():
            spath = _MODELS_DIR / sfname
            if spath.exists():
                try:
                    with open(spath, "rb") as f:
                        cls._scalers[skey] = pickle.load(f)
                    logger.info(f"Loaded scaler: {sfname}")
                except Exception as exc:
                    logger.error(f"Failed to load scaler {sfname}: {exc}")

        # Build status list
        for entry in _MODEL_REGISTRY:
            key = entry["key"]
            fname = entry["file"]
            is_loaded = key in cls._models
            fpath = str(_MODELS_DIR / fname) if fname else "N/A"
            cls._status.append(
                ModelInfo(
                    name=entry["name"],
                    version=entry["version"],
                    loaded=is_loaded,
                    path=fpath,
                )
            )

    @classmethod
    def get(cls, key: str) -> Any | None:
        """Return a loaded model by key, or None if not available."""
        return cls._models.get(key)

    @classmethod
    def get_scaler(cls, key: str) -> Any | None:
        """Return a loaded scaler by key, or None if not available."""
        return cls._scalers.get(key)

    @classmethod
    def anomaly_threshold(cls) -> float:
        return cls._anomaly_threshold

    @classmethod
    def list_models(cls) -> list[ModelInfo]:
        if not cls._status:
            cls.preload()
        return cls._status

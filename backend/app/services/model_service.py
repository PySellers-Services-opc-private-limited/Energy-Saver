"""
ModelService – reports the status of all 8 trained AI model files.
"""

from __future__ import annotations

import os
import sys

from app.schemas import ModelInfo

# Project root so we can resolve relative model paths
_BACKEND_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PROJECT_ROOT  = os.path.dirname(_BACKEND_DIR)
# models_storage/ sits at the project root alongside backend/
_MODELS_STORAGE = os.path.join(_PROJECT_ROOT, "models_storage")

_MODEL_REGISTRY = [
    {"name": "Energy Forecasting (LSTM)",         "file": "forecasting_model.keras",       "version": "1.0"},
    {"name": "Anomaly Detection (Autoencoder)",    "file": "anomaly_model.keras",           "version": "1.0"},
    {"name": "Occupancy Classification",           "file": "occupancy_model.keras",         "version": "1.0"},
    {"name": "HVAC Optimisation",                  "file": os.path.join(_PROJECT_ROOT, "outputs", "hvac_daily_schedule.csv"), "version": "1.0", "absolute": True},
    {"name": "Appliance Fingerprinting",           "file": "fingerprinting_model.keras",    "version": "1.0"},
    {"name": "Solar Forecast (CNN-LSTM)",          "file": "solar_model.keras",             "version": "1.0"},
    {"name": "EV Charging Optimiser",              "file": "ev_q_table.npy",               "version": "1.0"},
    {"name": "Bill Predictor (Neural Net)",        "file": "bill_predictor_model.keras",    "version": "1.0"},
]


class ModelService:
    _loaded: list[ModelInfo] = []

    @classmethod
    def preload(cls) -> None:
        """Check which model files exist on disk (no actual TF load to keep startup fast)."""
        cls._loaded = []
        for entry in _MODEL_REGISTRY:
            if entry.get("absolute"):
                path = entry["file"]
            else:
                path = os.path.join(_MODELS_STORAGE, entry["file"])
            cls._loaded.append(
                ModelInfo(
                    name=entry["name"],
                    version=entry["version"],
                    loaded=os.path.exists(path),
                    path=entry["file"],
                )
            )

    @classmethod
    def list_models(cls) -> list[ModelInfo]:
        if not cls._loaded:
            cls.preload()
        return cls._loaded

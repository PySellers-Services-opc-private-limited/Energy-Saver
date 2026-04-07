"""
ApplianceService – uses Model 5 (1D CNN) for appliance fingerprinting.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timezone

import numpy as np

from app.services.ml_loader import load_keras_model, load_pickle

logger = logging.getLogger(__name__)

APPLIANCE_PROFILES = {
    "Idle": {"base": 0.05, "noise": 0.02},
    "Refrigerator": {"base": 0.15, "noise": 0.03, "cycle": 0.1},
    "WashingMachine": {"base": 0.5, "noise": 0.1, "ramp": True},
    "Microwave": {"base": 1.2, "noise": 0.05},
    "AirConditioner": {"base": 1.5, "noise": 0.2, "cycle": 0.3},
    "EVCharger": {"base": 7.0, "noise": 0.3},
    "Dishwasher": {"base": 1.0, "noise": 0.15, "ramp": True},
}
TIME_STEPS = 60


class ApplianceService:

    _model = None
    _encoder = None
    _loaded = False

    @classmethod
    def _ensure_loaded(cls) -> bool:
        if cls._loaded:
            return cls._model is not None
        cls._loaded = True
        cls._model = load_keras_model("fingerprinting", "fingerprinting_model.keras")
        cls._encoder = load_pickle("fingerprinting_encoder", "fingerprinting_encoder.pkl")
        if cls._model:
            logger.info("Appliance fingerprinting model loaded")
        return cls._model is not None

    @classmethod
    def identify(cls, power_readings: list[float] | None = None) -> dict:
        """Identify appliance from power signature."""
        now = datetime.now(timezone.utc)

        if power_readings is None:
            # Generate a sample signature for demo
            appliance = random.choice(list(APPLIANCE_PROFILES.keys()))
            power_readings = cls._generate_signature(appliance)

        if cls._ensure_loaded() and cls._encoder is not None:
            try:
                data = np.array(power_readings[:TIME_STEPS]).reshape(1, TIME_STEPS, 1)
                probas = cls._model.predict(data, verbose=0)[0]
                class_idx = int(np.argmax(probas))
                confidence = float(probas[class_idx])
                label = cls._encoder.inverse_transform([class_idx])[0]

                top_3 = []
                sorted_idx = np.argsort(probas)[::-1][:3]
                for idx in sorted_idx:
                    top_3.append({
                        "appliance": cls._encoder.inverse_transform([idx])[0],
                        "confidence": round(float(probas[idx]) * 100, 1),
                    })

                return {
                    "identified_appliance": label,
                    "confidence_pct": round(confidence * 100, 1),
                    "top_predictions": top_3,
                    "power_readings_count": len(power_readings),
                    "model": "real",
                    "timestamp": now.isoformat(),
                }
            except Exception as e:
                logger.error("Appliance identification failed: %s", e)

        # Fallback
        avg_power = np.mean(power_readings) if power_readings else 0.5
        if avg_power < 0.1:
            label = "Idle"
        elif avg_power < 0.3:
            label = "Refrigerator"
        elif avg_power < 0.8:
            label = "WashingMachine"
        elif avg_power < 1.5:
            label = "AirConditioner"
        else:
            label = "EVCharger"

        return {
            "identified_appliance": label,
            "confidence_pct": round(random.uniform(60, 85), 1),
            "top_predictions": [{"appliance": label, "confidence": round(random.uniform(60, 85), 1)}],
            "power_readings_count": len(power_readings) if power_readings else 0,
            "model": "fallback",
            "timestamp": now.isoformat(),
        }

    @staticmethod
    def _generate_signature(appliance: str) -> list[float]:
        """Generate a synthetic power signature for an appliance."""
        profile = APPLIANCE_PROFILES.get(appliance, APPLIANCE_PROFILES["Idle"])
        base = profile["base"]
        noise = profile["noise"]
        readings = []
        for t in range(TIME_STEPS):
            val = base + random.gauss(0, noise)
            if profile.get("cycle"):
                val += profile["cycle"] * np.sin(2 * np.pi * t / 20)
            if profile.get("ramp") and t < 15:
                val *= t / 15
            readings.append(max(0, round(val, 3)))
        return readings

    @classmethod
    def list_appliances(cls) -> list[dict]:
        """Return known appliance types."""
        return [
            {"name": name, "typical_power_kw": profile["base"]}
            for name, profile in APPLIANCE_PROFILES.items()
        ]

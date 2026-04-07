"""
BillPredictorService – uses Model 8 (Dense NN + MC Dropout) for bill prediction.
"""

from __future__ import annotations

import logging
import math
import random
from datetime import datetime, timezone

import numpy as np

from app.services.ml_loader import load_keras_model, load_pickle

logger = logging.getLogger(__name__)


class BillPredictorService:

    _model = None
    _scaler_X = None
    _scaler_y = None
    _loaded = False

    @classmethod
    def _ensure_loaded(cls) -> bool:
        if cls._loaded:
            return cls._model is not None
        cls._loaded = True
        cls._model = load_keras_model("bill_predictor", "bill_predictor_model.keras")
        cls._scaler_X = load_pickle("bill_scaler_X", "bill_scaler_X.pkl")
        cls._scaler_y = load_pickle("bill_scaler_y", "bill_scaler_y.pkl")
        if cls._model:
            logger.info("Bill predictor model loaded")
        return cls._model is not None

    @classmethod
    def predict(cls, days_elapsed: int = 15, avg_daily_kwh: float = 30.0,
                tariff: float = 6.50, avg_temp: float = 28.0) -> dict:
        """Predict monthly bill with uncertainty estimation."""
        now = datetime.now(timezone.utc)
        month = now.month
        pct_elapsed = days_elapsed / 30.0
        kwh_so_far = avg_daily_kwh * days_elapsed
        projected_kwh = avg_daily_kwh * 30

        if cls._ensure_loaded() and cls._scaler_X is not None and cls._scaler_y is not None:
            try:
                features = np.array([[
                    days_elapsed, avg_daily_kwh, 0.35,  # peak_ratio
                    0.28,  # weekend_ratio
                    avg_daily_kwh * 0.02,  # rolling_7d_trend
                    avg_temp, pct_elapsed, kwh_so_far,
                    math.sin(2 * math.pi * month / 12),
                    math.cos(2 * math.pi * month / 12),
                    projected_kwh,
                ]])
                X_scaled = cls._scaler_X.transform(features)

                # MC Dropout — run 30 forward passes
                preds = []
                for _ in range(30):
                    p = cls._model(X_scaled, training=True).numpy()[0, 0]
                    preds.append(p)
                preds = np.array(preds)
                mean_scaled = float(np.mean(preds))
                std_scaled = float(np.std(preds))

                mean_bill = float(cls._scaler_y.inverse_transform([[mean_scaled]])[0, 0])
                # Confidence interval
                lower = float(cls._scaler_y.inverse_transform([[mean_scaled - 1.96 * std_scaled]])[0, 0])
                upper = float(cls._scaler_y.inverse_transform([[mean_scaled + 1.96 * std_scaled]])[0, 0])

                daily_budget = mean_bill / 30
                remaining_budget = max(0, mean_bill - (avg_daily_kwh * days_elapsed * tariff / 1000))

                return {
                    "predicted_bill": round(mean_bill, 2),
                    "lower_bound": round(max(0, lower), 2),
                    "upper_bound": round(upper, 2),
                    "confidence_pct": 95,
                    "daily_budget": round(daily_budget, 2),
                    "remaining_budget": round(remaining_budget, 2),
                    "days_elapsed": days_elapsed,
                    "kwh_so_far": round(kwh_so_far, 1),
                    "projected_kwh": round(projected_kwh, 1),
                    "model": "real",
                    "timestamp": now.isoformat(),
                }
            except Exception as e:
                logger.error("Bill prediction failed: %s", e)

        # Fallback
        estimated_bill = projected_kwh * tariff / 1000  # simple calculation
        return {
            "predicted_bill": round(estimated_bill, 2),
            "lower_bound": round(estimated_bill * 0.85, 2),
            "upper_bound": round(estimated_bill * 1.15, 2),
            "confidence_pct": 95,
            "daily_budget": round(estimated_bill / 30, 2),
            "remaining_budget": round(max(0, estimated_bill - kwh_so_far * tariff / 1000), 2),
            "days_elapsed": days_elapsed,
            "kwh_so_far": round(kwh_so_far, 1),
            "projected_kwh": round(projected_kwh, 1),
            "model": "fallback",
            "timestamp": now.isoformat(),
        }

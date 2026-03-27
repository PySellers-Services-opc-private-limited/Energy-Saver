"""
ForecastService – returns energy-consumption forecasts.
Uses the trained LSTM model when available; falls back to a sine-wave baseline
so the frontend always gets data even when TensorFlow is not installed.
"""

from __future__ import annotations

import logging
import math
import random
from datetime import datetime, timedelta, timezone

import numpy as np

from app.schemas import ForecastPoint, ForecastResponse

logger = logging.getLogger("energy_saver_ai.forecast_service")

# Number of past hours the LSTM was trained on
_WINDOW_SIZE = 48


class ForecastService:

    @staticmethod
    def forecast(device_id: str, horizon_hours: int) -> ForecastResponse:
        from app.services.model_service import ModelService

        model = ModelService.get("forecasting")
        now   = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

        if model is not None:
            return ForecastService._run_model(model, device_id, horizon_hours, now)
        else:
            logger.debug("Forecasting model not loaded – using synthetic baseline")
            return ForecastService._synthetic(device_id, horizon_hours, now)

    # ------------------------------------------------------------------ #
    # Real inference                                                       #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _run_model(model, device_id: str, horizon_hours: int, now: datetime) -> ForecastResponse:
        # Build a synthetic 48-hour window that mirrors how the model was trained.
        # In production this would come from the database / time-series store.
        seed_window = np.array([
            1.5 + 1.0 * math.sin(math.pi * ((now.hour - i) % 24 - 4) / 12)
            for i in range(_WINDOW_SIZE - 1, -1, -1)
        ], dtype=np.float32)

        points: list[ForecastPoint] = []
        window = seed_window.copy()

        for h in range(horizon_hours):
            X = window[-_WINDOW_SIZE:].reshape(1, _WINDOW_SIZE, 1)
            pred = float(model.predict(X, verbose=0)[0][0])
            pred = max(0.05, pred)
            margin = round(pred * 0.12, 3)
            ts = now + timedelta(hours=h + 1)
            points.append(ForecastPoint(
                timestamp=ts,
                predicted_kwh=round(pred, 3),
                lower_bound=round(pred - margin, 3),
                upper_bound=round(pred + margin, 3),
            ))
            window = np.append(window, pred)

        return ForecastResponse(device_id=device_id, horizon_hours=horizon_hours, forecasts=points)

    # ------------------------------------------------------------------ #
    # Synthetic fallback                                                   #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _synthetic(device_id: str, horizon_hours: int, now: datetime) -> ForecastResponse:
        points: list[ForecastPoint] = []
        for h in range(horizon_hours):
            ts    = now + timedelta(hours=h + 1)
            base  = 1.5 + 1.0 * math.sin(math.pi * (ts.hour - 4) / 12)
            pred  = round(max(0.1, base + random.gauss(0, 0.15)), 3)
            margin = round(pred * 0.12, 3)
            points.append(ForecastPoint(
                timestamp=ts,
                predicted_kwh=pred,
                lower_bound=round(pred - margin, 3),
                upper_bound=round(pred + margin, 3),
            ))
        return ForecastResponse(device_id=device_id, horizon_hours=horizon_hours, forecasts=points)

"""
ForecastService – uses the trained LSTM model for real energy forecasts.
Falls back to synthetic sine-wave when the model is unavailable.
"""

from __future__ import annotations

import logging
import math
import random
from datetime import datetime, timedelta, timezone

import numpy as np

from app.schemas import ForecastPoint, ForecastResponse
from app.services.ml_loader import load_keras_model, DATA_DIR

logger = logging.getLogger(__name__)

WINDOW_SIZE = 48
FORECAST_STEPS = 24


class ForecastService:

    _model = None
    _scaler = None
    _loaded = False

    @classmethod
    def _ensure_loaded(cls) -> bool:
        if cls._loaded:
            return cls._model is not None
        cls._loaded = True
        cls._model = load_keras_model("forecasting", "forecasting_model.keras")
        if cls._model is not None:
            logger.info("Forecasting LSTM model loaded successfully")
        return cls._model is not None

    @classmethod
    def _get_recent_data(cls) -> np.ndarray | None:
        """Prepare last WINDOW_SIZE rows from energy CSV as model input."""
        try:
            import os
            import pandas as pd
            from sklearn.preprocessing import MinMaxScaler

            csv_path = os.path.join(DATA_DIR, "energy_consumption.csv")
            if not os.path.exists(csv_path):
                return None
            df = pd.read_csv(csv_path, parse_dates=["timestamp"])
            df = df.sort_values("timestamp").reset_index(drop=True)

            df["sin_hour"] = np.sin(2 * np.pi * df["hour"] / 24)
            df["cos_hour"] = np.cos(2 * np.pi * df["hour"] / 24)
            df["sin_day"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
            df["cos_day"] = np.cos(2 * np.pi * df["day_of_week"] / 7)

            features = ["consumption_kwh", "sin_hour", "cos_hour", "sin_day", "cos_day", "is_weekend"]
            scaler = MinMaxScaler()
            scaled = scaler.fit_transform(df[features])

            consumption_scaler = MinMaxScaler()
            consumption_scaler.fit_transform(df[["consumption_kwh"]])
            cls._scaler = consumption_scaler

            if len(scaled) < WINDOW_SIZE:
                return None
            return scaled[-WINDOW_SIZE:]
        except Exception as e:
            logger.error("Failed to prepare forecast input: %s", e)
            return None

    @classmethod
    def forecast(cls, device_id: str, horizon_hours: int) -> ForecastResponse:
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

        if cls._ensure_loaded():
            input_data = cls._get_recent_data()
            if input_data is not None:
                try:
                    return cls._real_forecast(device_id, horizon_hours, now, input_data)
                except Exception as e:
                    logger.error("Real forecast failed, falling back: %s", e)

        return cls._synthetic_forecast(device_id, horizon_hours, now)

    @classmethod
    def _real_forecast(cls, device_id: str, horizon_hours: int, now: datetime, input_data: np.ndarray) -> ForecastResponse:
        """Run real LSTM prediction."""
        points: list[ForecastPoint] = []
        batch = input_data.reshape(1, WINDOW_SIZE, input_data.shape[1])
        raw_pred = cls._model.predict(batch, verbose=0)[0]

        if cls._scaler is not None:
            kwh_values = cls._scaler.inverse_transform(raw_pred.reshape(-1, 1)).flatten()
        else:
            kwh_values = raw_pred

        for h in range(min(horizon_hours, FORECAST_STEPS)):
            ts = now + timedelta(hours=h + 1)
            predicted = float(max(0.1, kwh_values[h]))
            margin = predicted * 0.10
            points.append(ForecastPoint(
                timestamp=ts,
                predicted_kwh=round(predicted, 3),
                lower_bound=round(max(0, predicted - margin), 3),
                upper_bound=round(predicted + margin, 3),
            ))

        if horizon_hours > FORECAST_STEPS:
            for h in range(FORECAST_STEPS, horizon_hours):
                ts = now + timedelta(hours=h + 1)
                idx = h % FORECAST_STEPS
                predicted = float(max(0.1, kwh_values[idx] * (1 + random.gauss(0, 0.05))))
                margin = predicted * 0.15
                points.append(ForecastPoint(
                    timestamp=ts,
                    predicted_kwh=round(predicted, 3),
                    lower_bound=round(max(0, predicted - margin), 3),
                    upper_bound=round(predicted + margin, 3),
                ))

        return ForecastResponse(device_id=device_id, horizon_hours=horizon_hours, forecasts=points)

    @staticmethod
    def _synthetic_forecast(device_id: str, horizon_hours: int, now: datetime) -> ForecastResponse:
        """Fallback: sine-wave baseline."""
        points: list[ForecastPoint] = []
        for h in range(horizon_hours):
            ts = now + timedelta(hours=h + 1)
            hour = ts.hour
            base = 1.5 + 1.0 * math.sin(math.pi * (hour - 4) / 12)
            predicted = round(max(0.1, base + random.gauss(0, 0.15)), 3)
            margin = round(predicted * 0.12, 3)
            points.append(ForecastPoint(
                timestamp=ts,
                predicted_kwh=predicted,
                lower_bound=round(predicted - margin, 3),
                upper_bound=round(predicted + margin, 3),
            ))
        return ForecastResponse(device_id=device_id, horizon_hours=horizon_hours, forecasts=points)

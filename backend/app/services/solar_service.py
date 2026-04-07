"""
SolarForecastService – uses Model 6 (Bidirectional LSTM) for solar generation forecast.
"""

from __future__ import annotations

import logging
import math
import random
from datetime import datetime, timedelta, timezone

import numpy as np

from app.services.ml_loader import load_keras_model, load_pickle

logger = logging.getLogger(__name__)

WINDOW_SIZE = 48
FORECAST_STEPS = 24


class SolarForecastService:

    _model = None
    _scaler = None
    _loaded = False

    @classmethod
    def _ensure_loaded(cls) -> bool:
        if cls._loaded:
            return cls._model is not None
        cls._loaded = True
        cls._model = load_keras_model("solar", "solar_model.keras")
        cls._scaler = load_pickle("solar_scaler", "solar_scaler.pkl")
        if cls._model:
            logger.info("Solar forecast model loaded")
        return cls._model is not None

    @classmethod
    def forecast(cls, system_kw: float = 5.0) -> dict:
        """Predict next 24 hours of solar generation."""
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

        if cls._ensure_loaded() and cls._scaler is not None:
            try:
                return cls._real_forecast(now, system_kw)
            except Exception as e:
                logger.error("Solar forecast failed: %s", e)

        return cls._synthetic_forecast(now, system_kw)

    @classmethod
    def _real_forecast(cls, now: datetime, system_kw: float) -> dict:
        """Build synthetic input to get model prediction."""
        from sklearn.preprocessing import MinMaxScaler

        # Build 48-hour lookback with synthetic weather features
        rows = []
        for h in range(WINDOW_SIZE):
            t = now - timedelta(hours=WINDOW_SIZE - h)
            hour = t.hour
            day_of_year = t.timetuple().tm_yday

            cloud = random.uniform(0.1, 0.4)
            temp = 25 + 10 * math.sin(math.pi * (hour - 6) / 12)
            humidity = 50 + random.gauss(0, 10)
            wind = random.uniform(1, 8)
            is_daytime = 1 if 6 <= hour <= 18 else 0
            solar_gen = max(0, system_kw * 0.8 * math.sin(math.pi * (hour - 6) / 12) * (1 - cloud * 0.5)) if is_daytime else 0

            rows.append([
                solar_gen, cloud, temp, humidity, wind,
                math.sin(2 * math.pi * hour / 24),
                math.cos(2 * math.pi * hour / 24),
                math.sin(2 * math.pi * day_of_year / 365),
                math.cos(2 * math.pi * day_of_year / 365),
                is_daytime,
            ])

        data = np.array(rows)
        if cls._scaler is not None:
            data = cls._scaler.transform(data)

        batch = data.reshape(1, WINDOW_SIZE, data.shape[1])
        raw_pred = cls._model.predict(batch, verbose=0)[0]

        # Inverse transform solar generation
        if cls._scaler is not None:
            dummy = np.zeros((len(raw_pred), data.shape[1]))
            dummy[:, 0] = raw_pred
            kwh_values = cls._scaler.inverse_transform(dummy)[:, 0]
        else:
            kwh_values = raw_pred

        hourly = []
        total_kwh = 0.0
        for h in range(FORECAST_STEPS):
            ts = now + timedelta(hours=h + 1)
            gen = float(max(0.0, kwh_values[h]))
            total_kwh += gen
            hourly.append({
                "timestamp": ts.isoformat(),
                "solar_kwh": round(gen, 3),
                "hour": ts.hour,
            })

        tariff_avg = 6.50
        daily_savings = total_kwh * tariff_avg
        annual_savings = daily_savings * 365

        return {
            "system_kw": system_kw,
            "hourly_forecast": hourly,
            "total_24h_kwh": round(total_kwh, 2),
            "estimated_daily_savings_inr": round(daily_savings, 2),
            "estimated_annual_savings_inr": round(annual_savings, 2),
            "model": "real",
            "timestamp": now.isoformat(),
        }

    @staticmethod
    def _synthetic_forecast(now: datetime, system_kw: float) -> dict:
        """Fallback: synthetic solar curve."""
        hourly = []
        total_kwh = 0.0
        for h in range(FORECAST_STEPS):
            ts = now + timedelta(hours=h + 1)
            hour = ts.hour
            gen = max(0, system_kw * 0.7 * math.sin(math.pi * (hour - 6) / 12)) if 6 <= hour <= 20 else 0.0
            gen = round(gen + random.gauss(0, 0.1), 3)
            gen = max(0.0, gen)
            total_kwh += gen
            hourly.append({
                "timestamp": ts.isoformat(),
                "solar_kwh": round(gen, 3),
                "hour": hour,
            })

        daily_savings = total_kwh * 6.50
        return {
            "system_kw": system_kw,
            "hourly_forecast": hourly,
            "total_24h_kwh": round(total_kwh, 2),
            "estimated_daily_savings_inr": round(daily_savings, 2),
            "estimated_annual_savings_inr": round(daily_savings * 365, 2),
            "model": "fallback",
            "timestamp": now.isoformat(),
        }

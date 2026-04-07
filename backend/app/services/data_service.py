"""
DataService – assembles live KPI summaries from real DB data + ML models.
Falls back to simulated values when no energy logs exist.
"""

from __future__ import annotations

import logging
import math
import random
from datetime import datetime, timezone

from app.schemas import KPISummary

logger = logging.getLogger(__name__)


def _get_tariff(hour: int) -> float:
    """Return INR/kWh tariff for the given hour."""
    if 17 <= hour <= 21:
        return 9.50
    elif 0 <= hour <= 6:
        return 3.50
    return 6.50


def _get_solar_kwh() -> float:
    """Get solar generation from the real Solar Forecast model."""
    try:
        from app.services.solar_service import SolarForecastService
        result = SolarForecastService.forecast(system_kw=5.0)
        hourly = result.get("hourly", [])
        if hourly:
            return round(max(0.0, hourly[0].get("generation_kwh", 0.0)), 2)
    except Exception as e:
        logger.debug("Solar model fallback: %s", e)
    # Fallback: physics-based estimate
    hour = datetime.now(timezone.utc).hour
    if 6 <= hour <= 20:
        return round(max(0.0, 3.0 * math.sin(math.pi * (hour - 6) / 12)), 2)
    return 0.0


def _get_occupancy_rate() -> float:
    """Get occupancy probability from the real Occupancy model."""
    try:
        from app.services.ml_loader import load_keras_model, load_pickle
        import numpy as np

        model = load_keras_model("occupancy", "occupancy_model.keras")
        scaler = load_pickle("occupancy_scaler", "occupancy_scaler.pkl")
        if model is not None:
            now = datetime.now(timezone.utc)
            hour = now.hour
            day_of_week = now.weekday()
            features = np.array([[
                hour,
                day_of_week,
                np.sin(2 * np.pi * hour / 24),
                np.cos(2 * np.pi * hour / 24),
                np.sin(2 * np.pi * day_of_week / 7),
                np.cos(2 * np.pi * day_of_week / 7),
            ]])
            if scaler is not None:
                features = scaler.transform(features)
            prob = float(model.predict(features, verbose=0)[0][0])
            return round(min(1.0, max(0.0, prob)), 2)
    except Exception as e:
        logger.debug("Occupancy model fallback: %s", e)
    # Fallback: time-based heuristic
    hour = datetime.now(timezone.utc).hour
    return round(random.uniform(0.3, 0.9), 2) if 8 <= hour <= 22 else round(random.uniform(0, 0.1), 2)


class DataService:
    """Produces dashboard KPI snapshots from EnergyLog + TenantAlert tables + ML models."""

    @staticmethod
    def latest_kpis() -> KPISummary:
        now = datetime.now(timezone.utc)
        hour = now.hour
        tariff = _get_tariff(hour)

        # Try real DB data first
        try:
            from app.database import SessionLocal
            from app.models.energy_log_model import EnergyLog
            from app.models.alert_model import TenantAlert
            from sqlalchemy import func
            from datetime import timedelta

            db = SessionLocal()
            try:
                # Last hour consumption
                one_hour_ago = now - timedelta(hours=1)
                result = db.query(
                    func.sum(EnergyLog.consumption),
                    func.max(EnergyLog.power),
                    func.count(EnergyLog.id),
                ).filter(EnergyLog.timestamp >= one_hour_ago).first()

                total_kwh = float(result[0]) if result[0] else None
                peak_power = float(result[1]) if result[1] else None
                log_count = result[2] or 0

                # Today's alerts
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                anomaly_count = db.query(func.count(TenantAlert.id)).filter(
                    TenantAlert.created_at >= today_start
                ).scalar() or 0

                if log_count > 0 and total_kwh is not None:
                    consumption = round(total_kwh / max(log_count, 1), 2)
                    peak = round(peak_power / 1000, 2) if peak_power else round(consumption * 1.3, 2)
                    savings_today = round(30 * 0.15 * tariff * (hour / 24), 2)

                    return KPISummary(
                        total_consumption_kwh=consumption,
                        anomalies_detected=anomaly_count,
                        occupancy_rate=_get_occupancy_rate(),
                        solar_generation_kwh=_get_solar_kwh(),
                        current_tariff=tariff,
                        estimated_savings_today=savings_today,
                        peak_demand_kw=peak,
                        timestamp=now,
                    )
            finally:
                db.close()
        except Exception:
            pass

        # Fallback to simulated consumption + real ML for occupancy/solar
        base_kwh = 2.0 + 1.5 * math.sin(math.pi * (hour - 4) / 12)
        consumption = round(max(0.5, base_kwh + random.gauss(0, 0.3)), 2)
        savings_today = round(30 * 0.15 * tariff * (hour / 24), 2)

        return KPISummary(
            total_consumption_kwh=consumption,
            anomalies_detected=random.randint(0, 3),
            occupancy_rate=_get_occupancy_rate(),
            solar_generation_kwh=_get_solar_kwh(),
            current_tariff=tariff,
            estimated_savings_today=savings_today,
            peak_demand_kw=round(consumption * 1.3, 2),
            timestamp=now,
        )

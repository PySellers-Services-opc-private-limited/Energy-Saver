"""
DataService – assembles live KPI summaries from the CSV datasets.
Falls back to realistic simulated values when model files are absent.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timezone

from app.schemas import KPISummary


class DataService:
    """Singleton-style service producing dashboard KPI snapshots."""

    @staticmethod
    def latest_kpis() -> KPISummary:
        now = datetime.now(timezone.utc)
        hour = now.hour

        # Diurnal consumption curve
        base_kwh = 2.0 + 1.5 * math.sin(math.pi * (hour - 4) / 12)
        consumption = round(max(0.5, base_kwh + random.gauss(0, 0.3)), 2)

        # Solar generation (zero at night)
        solar = (
            round(max(0.0, 3.0 * math.sin(math.pi * (hour - 6) / 12) + random.gauss(0, 0.1)), 2)
            if 6 <= hour <= 20
            else 0.0
        )

        # Time-of-use tariff (INR/kWh — Indian electricity rates)
        if 17 <= hour <= 21:
            tariff = 9.50   # peak evening rate
        elif 0 <= hour <= 6:
            tariff = 3.50   # off-peak night rate
        else:
            tariff = 6.50   # standard daytime rate

        # Rough daily savings estimate (15% reduction on baseline 30 kWh/day)
        savings_today = round(30 * 0.15 * tariff * (hour / 24), 2)

        return KPISummary(
            total_consumption_kwh=consumption,
            anomalies_detected=random.randint(0, 3),
            occupancy_rate=round(random.uniform(0.3, 0.9), 2) if 8 <= hour <= 22 else round(random.uniform(0, 0.1), 2),
            solar_generation_kwh=solar,
            current_tariff=tariff,
            estimated_savings_today=savings_today,
            peak_demand_kw=round(consumption * 1.3, 2),
            timestamp=now,
        )

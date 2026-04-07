"""
EVOptimizerService – uses Model 7 (Q-Learning) for EV charging optimization.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone

import numpy as np

from app.services.ml_loader import load_numpy

logger = logging.getLogger(__name__)

# Must match training constants from model_7_ev_optimizer.py
SOC_BINS = 10
HOURS = 24
TARIFF_LEVELS = 3
SOLAR_BINS = 3
DEPARTURE_BINS = 8
BATTERY_KWH = 60.0
EFFICIENCY = 0.9
SLOW_KW = 1.4
FAST_KW = 7.2
ACTIONS = ["no_charge", "slow_charge", "fast_charge"]


class EVOptimizerService:

    _q_table = None
    _loaded = False

    @classmethod
    def _ensure_loaded(cls) -> bool:
        if cls._loaded:
            return cls._q_table is not None
        cls._loaded = True
        cls._q_table = load_numpy("ev_q_table", "ev_q_table.npy")
        if cls._q_table is not None:
            logger.info("EV Q-table loaded: shape=%s", cls._q_table.shape)
        return cls._q_table is not None

    @classmethod
    def _get_tariff_level(cls, hour: int) -> int:
        if 17 <= hour <= 21:
            return 2  # peak
        elif 0 <= hour <= 6:
            return 0  # off-peak
        return 1  # standard

    @classmethod
    def _get_solar_bin(cls, hour: int) -> int:
        if 10 <= hour <= 14:
            return 2  # high
        elif 6 <= hour <= 18:
            return 1  # medium
        return 0  # none

    @classmethod
    def optimize(cls, current_soc: float = 20.0, departure_hour: int = 8,
                 target_soc: float = 80.0) -> dict:
        """Generate optimal EV charging schedule."""
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

        if not cls._ensure_loaded():
            return cls._fallback_schedule(now, current_soc, departure_hour, target_soc)

        try:
            schedule = []
            soc = current_soc
            total_cost = 0.0
            total_kwh = 0.0

            for step in range(48):  # 48 half-hour slots
                hour = (now.hour + step // 2) % 24
                half = step % 2

                soc_bin = min(int(soc / 100 * SOC_BINS), SOC_BINS - 1)
                tariff_level = cls._get_tariff_level(hour)
                solar_bin = cls._get_solar_bin(hour)
                hours_until = max(0, min(DEPARTURE_BINS - 1, departure_hour - hour if departure_hour > hour else departure_hour + 24 - hour))

                state_idx = (
                    soc_bin * HOURS * TARIFF_LEVELS * SOLAR_BINS * DEPARTURE_BINS +
                    hour * TARIFF_LEVELS * SOLAR_BINS * DEPARTURE_BINS +
                    tariff_level * SOLAR_BINS * DEPARTURE_BINS +
                    solar_bin * DEPARTURE_BINS +
                    hours_until
                )

                if state_idx < len(cls._q_table):
                    action = int(np.argmax(cls._q_table[state_idx]))
                else:
                    action = 0

                action_name = ACTIONS[action]
                tariff_rates = [3.50, 6.50, 9.50]
                tariff = tariff_rates[tariff_level]

                if action == 1:  # slow
                    kwh = SLOW_KW * 0.5 * EFFICIENCY
                elif action == 2:  # fast
                    kwh = FAST_KW * 0.5 * EFFICIENCY
                else:
                    kwh = 0.0

                soc_delta = (kwh / BATTERY_KWH) * 100
                soc = min(100.0, soc + soc_delta)
                cost = kwh * tariff
                total_cost += cost
                total_kwh += kwh

                ts = now + timedelta(minutes=step * 30)
                schedule.append({
                    "timestamp": ts.isoformat(),
                    "hour": hour,
                    "action": action_name,
                    "soc_pct": round(soc, 1),
                    "kwh_added": round(kwh, 2),
                    "tariff_inr": tariff,
                    "cost_inr": round(cost, 2),
                })

                if soc >= target_soc:
                    break

            naive_cost = (target_soc - current_soc) / 100 * BATTERY_KWH * 6.50
            savings = max(0, naive_cost - total_cost)

            return {
                "schedule": schedule,
                "final_soc_pct": round(soc, 1),
                "total_kwh_charged": round(total_kwh, 2),
                "total_cost_inr": round(total_cost, 2),
                "savings_vs_naive_inr": round(savings, 2),
                "departure_hour": departure_hour,
                "target_soc_pct": target_soc,
                "model": "real",
                "timestamp": now.isoformat(),
            }
        except Exception as e:
            logger.error("EV optimization failed: %s", e)
            return cls._fallback_schedule(now, current_soc, departure_hour, target_soc)

    @staticmethod
    def _fallback_schedule(now: datetime, soc: float, departure: int, target: float) -> dict:
        schedule = []
        total_cost = 0.0
        for h in range(24):
            ts = now + timedelta(hours=h)
            hour = ts.hour
            tariff = 3.50 if 0 <= hour <= 6 else (9.50 if 17 <= hour <= 21 else 6.50)
            if soc < target and 0 <= hour <= 6:
                kwh = FAST_KW * EFFICIENCY
                soc = min(100, soc + (kwh / BATTERY_KWH) * 100)
                cost = kwh * tariff
                total_cost += cost
                action = "fast_charge"
            else:
                kwh = 0
                cost = 0
                action = "no_charge"
            schedule.append({
                "timestamp": ts.isoformat(),
                "hour": hour,
                "action": action,
                "soc_pct": round(soc, 1),
                "kwh_added": round(kwh, 2),
                "tariff_inr": tariff,
                "cost_inr": round(cost, 2),
            })
        return {
            "schedule": schedule,
            "final_soc_pct": round(soc, 1),
            "total_kwh_charged": round(sum(s["kwh_added"] for s in schedule), 2),
            "total_cost_inr": round(total_cost, 2),
            "savings_vs_naive_inr": 0.0,
            "departure_hour": departure,
            "target_soc_pct": target,
            "model": "fallback",
            "timestamp": now.isoformat(),
        }

"""
Real-Time HVAC Stream Decision Engine
=======================================
Makes instant HVAC control decisions from live sensor data.
Publishes commands to IoT actuators via MQTT/Kafka.
"""

import numpy as np
from datetime import datetime

TARIFFS = {h: 0.08 if h < 7 or h >= 21 else (0.22 if 17 <= h <= 20 else 0.13)
           for h in range(24)}

MODES = {
    "ECO":             {"target_temp": 17, "fan": "low",    "savings": "40%"},
    "PRE_CONDITION":   {"target_temp": 22, "fan": "medium", "savings": "15%"},
    "COMFORT":         {"target_temp": 22, "fan": "auto",   "savings": "0%"},
    "DEMAND_RESPONSE": {"target_temp": 20, "fan": "low",    "savings": "25%"},
    "NIGHT_SETBACK":   {"target_temp": 18, "fan": "off",    "savings": "35%"},
}


def make_hvac_decision(occupied: bool, hour: int, forecast_kwh: float,
                       current_temp: float) -> dict:
    """
    Instant HVAC decision from live sensor values.
    Returns command dict ready to publish to IoT actuator.
    """
    tariff    = TARIFFS[hour]
    is_peak   = tariff >= 0.20
    pre_peak  = hour in (6, 7, 8, 15, 16)

    if not occupied and (hour < 6 or hour > 23):
        mode = "NIGHT_SETBACK"
    elif not occupied:
        mode = "ECO"
    elif is_peak and forecast_kwh > 4.5:
        mode = "DEMAND_RESPONSE"
    elif pre_peak:
        mode = "PRE_CONDITION"
    else:
        mode = "COMFORT"

    cfg = MODES[mode]
    return {
        "mode":        mode,
        "target_temp": cfg["target_temp"],
        "fan_speed":   cfg["fan"],
        "tariff":      tariff,
        "savings_est": cfg["savings"],
        "reason":      _reason(mode, occupied, tariff, forecast_kwh),
        "command_ts":  datetime.now().isoformat(),
    }


def _reason(mode, occupied, tariff, forecast_kwh):
    if mode == "ECO":             return f"Empty room → saving energy"
    if mode == "NIGHT_SETBACK":   return f"Night setback active"
    if mode == "DEMAND_RESPONSE": return f"Peak tariff ${tariff:.2f}/kWh + high demand {forecast_kwh:.1f}kWh"
    if mode == "PRE_CONDITION":   return f"Pre-conditioning before peak hours"
    return f"Occupied, normal hours (${tariff:.2f}/kWh)"

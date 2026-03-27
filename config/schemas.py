"""
Data Schemas — Energy Saver AI
================================
Validated dataclass schemas for all data flowing through the pipeline.
Validation is intentionally lightweight (no Pydantic dependency) so these
schemas can be used in edge / embedded contexts that only have stdlib.

For input validation at API boundaries:
    reading = SensorReadingSchema.validate(raw_dict)

For output serialisation:
    json.dumps(reading.to_dict())
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Any


# ─────────────────────────────────────────────────────────────
# Validation Error
# ─────────────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised when a data payload fails schema validation."""


# ─────────────────────────────────────────────────────────────
# Sensor Reading
# ─────────────────────────────────────────────────────────────

@dataclass
class SensorReadingSchema:
    """
    Validated sensor reading from any IoT source.

    All physical quantities have realistic bounds to catch
    obviously bad readings (sensor faults, protocol errors).
    """

    device_id:        str
    timestamp:        float          # UNIX epoch seconds (UTC)
    consumption_kwh:  float          # Instantaneous energy reading [0, 100]
    temperature:      float = 20.0   # Degrees Celsius [-40, 85]
    humidity:         float = 50.0   # Relative humidity [0, 100] %
    occupancy:        float = 0.0    # Occupancy probability [0, 1]
    solar_kwh:        float = 0.0    # Solar generation [0, 50]
    tariff:           float = 0.13   # $/kWh  [0, 10]
    co2_ppm:          float = 400.0  # CO₂ concentration [300, 5000]
    light_level:      float = 0.0    # Illuminance [0, 100_000] lux

    # ── Validation bounds ─────────────────────────────────────
    _BOUNDS: dict[str, tuple[float, float]] = field(
        default_factory=lambda: {
            "consumption_kwh": (0.0, 100.0),
            "temperature":     (-40.0, 85.0),
            "humidity":        (0.0, 100.0),
            "occupancy":       (0.0, 1.0),
            "solar_kwh":       (0.0, 50.0),
            "tariff":          (0.0, 10.0),
            "co2_ppm":         (300.0, 5000.0),
            "light_level":     (0.0, 100_000.0),
        },
        repr=False,
    )

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if not self.device_id or not isinstance(self.device_id, str):
            raise ValidationError("device_id must be a non-empty string")

        if not math.isfinite(self.timestamp) or self.timestamp <= 0:
            raise ValidationError(f"Invalid timestamp: {self.timestamp}")

        for field_name, (lo, hi) in self._BOUNDS.items():
            val = getattr(self, field_name)
            if not isinstance(val, (int, float)) or not math.isfinite(val):
                raise ValidationError(
                    f"{field_name} must be a finite number, got {val!r}"
                )
            if not (lo <= val <= hi):
                raise ValidationError(
                    f"{field_name}={val} out of range [{lo}, {hi}]"
                )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("_BOUNDS", None)
        return d

    @classmethod
    def validate(cls, raw: dict[str, Any]) -> "SensorReadingSchema":
        """
        Build and validate a SensorReadingSchema from a raw dict.
        Unknown extra keys are silently ignored (forward-compatible).
        """
        known_fields = {
            "device_id", "timestamp", "consumption_kwh", "temperature",
            "humidity", "occupancy", "solar_kwh", "tariff", "co2_ppm",
            "light_level",
        }
        filtered = {k: v for k, v in raw.items() if k in known_fields}
        return cls(**filtered)


# ─────────────────────────────────────────────────────────────
# HVAC Command
# ─────────────────────────────────────────────────────────────

HVAC_MODES = frozenset({"COMFORT", "ECO", "DEMAND_RESPONSE", "PRE_CONDITION", "OFF"})


@dataclass
class HVACCommandSchema:
    """Output command sent to the HVAC controller."""

    device_id:   str
    timestamp:   float
    mode:        str           # One of HVAC_MODES
    setpoint_c:  float         # Target temperature [10, 35] °C
    reason:      str = ""

    def __post_init__(self) -> None:
        if self.mode not in HVAC_MODES:
            raise ValidationError(
                f"Invalid HVAC mode '{self.mode}'. Valid: {sorted(HVAC_MODES)}"
            )
        if not (10.0 <= self.setpoint_c <= 35.0):
            raise ValidationError(
                f"setpoint_c={self.setpoint_c} out of range [10, 35]"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─────────────────────────────────────────────────────────────
# Alert
# ─────────────────────────────────────────────────────────────

ALERT_LEVELS = frozenset({"OK", "WARN", "CRITICAL"})


@dataclass
class AlertSchema:
    """Anomaly alert emitted by the inference engine."""

    device_id:     str
    timestamp:     float
    level:         str         # OK | WARN | CRITICAL
    anomaly_score: float       # [0.0, 1.0]
    message:       str
    model_version: str = "unknown"

    def __post_init__(self) -> None:
        if self.level not in ALERT_LEVELS:
            raise ValidationError(
                f"Invalid alert level '{self.level}'. Valid: {sorted(ALERT_LEVELS)}"
            )
        if not (0.0 <= self.anomaly_score <= 1.0):
            raise ValidationError(
                f"anomaly_score={self.anomaly_score} must be in [0, 1]"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

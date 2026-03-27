"""Pydantic v2 schemas shared by all routers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Sensor / Reading ─────────────────────────────────────────────────────────

class SensorReading(BaseModel):
    device_id: str
    timestamp: datetime
    consumption_kwh: float = Field(ge=0, le=100)
    temperature: float = Field(default=21.0, ge=-40, le=85)
    humidity: float = Field(default=50.0, ge=0, le=100)
    occupancy: int = Field(default=0, ge=0, le=1)
    solar_kwh: float = Field(default=0.0, ge=0, le=50)
    tariff: float = Field(default=6.50, ge=0, le=100)  # INR/kWh


# ── Dashboard KPIs ───────────────────────────────────────────────────────────

class KPISummary(BaseModel):
    total_consumption_kwh: float
    anomalies_detected: int
    occupancy_rate: float
    solar_generation_kwh: float
    current_tariff: float
    estimated_savings_today: float
    peak_demand_kw: float
    timestamp: datetime


# ── Forecast ────────────────────────────────────────────────────────────────

class ForecastPoint(BaseModel):
    timestamp: datetime
    predicted_kwh: float
    lower_bound: float
    upper_bound: float


class ForecastResponse(BaseModel):
    device_id: str
    horizon_hours: int
    forecasts: list[ForecastPoint]


# ── Anomaly ──────────────────────────────────────────────────────────────────

class AnomalyEvent(BaseModel):
    device_id: str
    timestamp: datetime
    anomaly_score: float = Field(ge=0, le=1)
    is_anomaly: bool
    consumption_kwh: float
    reconstruction_error: float


class AnomalyResponse(BaseModel):
    total: int
    anomalies: list[AnomalyEvent]


# ── HVAC ─────────────────────────────────────────────────────────────────────

class HVACCommandRequest(BaseModel):
    zone_id: str = "zone_1"
    mode: str = Field(default="ECO", pattern=r"^(COMFORT|ECO|DEMAND_RESPONSE|PRE_CONDITION|OFF)$")
    setpoint_c: float = Field(default=21.0, ge=10, le=35)


class HVACCommandResponse(BaseModel):
    zone_id: str
    mode: str
    setpoint_c: float
    estimated_saving_pct: float
    issued_at: datetime


# ── Savings ──────────────────────────────────────────────────────────────────

class SavingsRequest(BaseModel):
    baseline_kwh_per_day: float = Field(default=30.0, gt=0)
    tariff_per_kwh: float = Field(default=6.50, gt=0)  # INR/kWh


class SavingsBreakdown(BaseModel):
    hvac_kwh_per_year: float
    ev_kwh_per_year: float
    anomaly_kwh_per_year: float


class SavingsResponse(BaseModel):
    kwh_saved_per_day: float
    kwh_saved_per_year: float
    cost_saved_per_year: float
    co2_saved_kg_per_year: float
    breakdown: SavingsBreakdown


# ── Model Status ─────────────────────────────────────────────────────────────

class ModelInfo(BaseModel):
    name: str
    version: str
    loaded: bool
    path: str
    metrics: dict[str, Any] = {}


class ModelListResponse(BaseModel):
    models: list[ModelInfo]


# ── Pipeline ─────────────────────────────────────────────────────────────────

class PipelineStatus(BaseModel):
    running: bool
    mode: str
    uptime_s: float
    messages_processed: int
    anomalies_detected: int
    kafka_connected: bool
    mqtt_connected: bool
    ws_clients: int

"""Pydantic v2 schemas shared by all routers."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


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


# ═══════════════════════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════════════════════

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: str
    password: str = Field(min_length=6)
    role: str = Field(default="tenant", pattern=r"^(admin|tenant)$")
    unit_key: Optional[str] = Field(default=None, max_length=50)


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    unit_key: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Optional[UserResponse] = None


class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None
    role: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════
# TENANT
# ═══════════════════════════════════════════════════════════════════

class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str
    phone: str = Field(default="", max_length=20)
    unit_key: str = Field(min_length=1, max_length=50)
    image: str = Field(default="")
    tenant_type: str = Field(default="home", pattern=r"^(home|commercial|industrial)$")
    subscription_plan: str = Field(default="basic", pattern=r"^(basic|pro|enterprise)$")
    timezone: str = Field(default="UTC", max_length=100)
    currency: str = Field(default="INR", max_length=10)


class TenantUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    email: Optional[str] = None
    phone: Optional[str] = Field(default=None, max_length=20)
    unit_key: Optional[str] = Field(default=None, max_length=50)
    image: Optional[str] = None
    tenant_type: Optional[str] = None
    subscription_plan: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None
    is_active: Optional[bool] = None


class TenantResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str]
    unit_key: str
    image: Optional[str]
    tenant_type: Optional[str]
    subscription_plan: Optional[str]
    timezone: str
    currency: str
    is_active: bool
    plan_start_date: Optional[date] = None
    plan_end_date: Optional[date] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════
# BUILDING
# ═══════════════════════════════════════════════════════════════════

class BuildingCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: Optional[str] = None
    area_sqm: Optional[float] = None
    floor_count: Optional[int] = None


class BuildingUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    address: Optional[str] = None
    area_sqm: Optional[float] = None
    floor_count: Optional[int] = None
    is_active: Optional[bool] = None


class BuildingResponse(BaseModel):
    id: int
    tenant_id: int
    name: str
    address: Optional[str]
    area_sqm: Optional[float]
    floor_count: Optional[int]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════
# SUBSCRIPTION
# ═══════════════════════════════════════════════════════════════════

class SubscriptionCreate(BaseModel):
    plan: str = Field(pattern=r"^(basic|pro|enterprise)$")
    billing_cycle: str = Field(default="monthly", pattern=r"^(monthly|annual)$")


class SubscriptionResponse(BaseModel):
    id: int
    tenant_id: int
    plan: str
    max_devices: int
    max_users: int
    max_buildings: int
    price_per_month: float
    billing_cycle: str
    status: str
    starts_at: Optional[date] = None
    ends_at: Optional[date] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════
# DEVICE
# ═══════════════════════════════════════════════════════════════════

class DeviceCreate(BaseModel):
    unit_key: str
    device_id: str = ""
    bacnet_object_no: Optional[int] = None


class DeviceResponse(BaseModel):
    id: int
    device_id: Optional[str]
    unit_key: str
    bacnet_object_no: Optional[int]

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════
# ENERGY LOG
# ═══════════════════════════════════════════════════════════════════

class EnergyLogCreate(BaseModel):
    unit_key: str
    voltage: Optional[float] = None
    current: Optional[float] = None
    power: Optional[float] = None
    consumption: float = Field(ge=0)


class EnergyLogResponse(BaseModel):
    id: int
    unit_key: str
    timestamp: datetime
    voltage: Optional[float]
    current: Optional[float]
    power: Optional[float]
    consumption: float

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════
# TENANT ALERTS
# ═══════════════════════════════════════════════════════════════════

class TenantAlertResponse(BaseModel):
    id: int
    unit_key: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════
# FORECAST VS ACTUAL
# ═══════════════════════════════════════════════════════════════════

class ForecastMetricItem(BaseModel):
    """One metric inside the forecast-vs-actual scorecard."""
    forecast: float
    actual: float
    delta: float
    delta_pct: float
    rag: str  # green | amber | red
    label: str

    model_config = {"from_attributes": True}


class ForecastVsActualSummary(BaseModel):
    """Per-tenant scorecard for a given date."""
    tenant_id: int
    period: str  # day | week | month
    date: str
    overall_rag: str
    metrics: dict[str, Any]
    model_accuracy: dict[str, float]


class ForecastVsActualChartPoint(BaseModel):
    """One data point for the dual-line chart."""
    date: str
    forecast: float
    actual: float
    delta_pct: float
    rag: str


class ForecastVsActualHistory(BaseModel):
    """Historical accuracy trend response."""
    tenant_id: int
    metric: str
    from_date: str
    to_date: str
    points: list[ForecastVsActualChartPoint]
    avg_accuracy_pct: float


class DailyForecastVsActualResponse(BaseModel):
    id: int
    tenant_id: int
    unit_key: str
    date: date
    forecast_kwh: Optional[float]
    actual_kwh: Optional[float]
    delta_kwh: Optional[float]
    delta_pct: Optional[float]
    forecast_bill: Optional[float]
    actual_bill: Optional[float]
    forecast_solar_kwh: Optional[float]
    actual_solar_kwh: Optional[float]
    forecast_peak_kw: Optional[float]
    actual_peak_kw: Optional[float]
    anomaly_count: int
    forecast_accuracy_pct: Optional[float]
    mae: Optional[float]
    mape: Optional[float]
    rag_status: str
    computed_at: Optional[datetime]

    model_config = {"from_attributes": True}

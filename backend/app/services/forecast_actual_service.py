"""
Forecast vs Actual — background computation service.

Generates simulated forecast-vs-actual data for tenants.
In production this would query real sensor data and ML model predictions;
here we simulate realistic values for demonstration.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.forecast_actual_model import DailyForecastVsActual
from app.models.tenant_model import Tenant
from app.models.energy_log_model import EnergyLog
from app.models.alert_model import TenantAlert
from sqlalchemy import func


# ── RAG calculation ───────────────────────────────────────────────────────────

def compute_rag(delta_pct: float, metric: str = "consumption") -> str:
    """Return green / amber / red based on percentage deviation."""
    thresholds = {
        "consumption": (5.0, 15.0),
        "bill":        (5.0, 15.0),
        "solar":       (5.0, 10.0),
        "peak":        (5.0, 20.0),
    }
    low, high = thresholds.get(metric, (5.0, 15.0))
    if abs(delta_pct) <= low:
        return "green"
    if abs(delta_pct) <= high:
        return "amber"
    return "red"


def _overall_rag(*statuses: str) -> str:
    """Worst-case RAG from a list of statuses."""
    if "red" in statuses:
        return "red"
    if "amber" in statuses:
        return "amber"
    return "green"


# ── Seed / refresh daily data ────────────────────────────────────────────────

def seed_forecast_vs_actual_for_tenant(
    db: Session,
    tenant: Tenant,
    target_date: date,
) -> DailyForecastVsActual:
    """Create or update a DailyForecastVsActual row for a tenant + date.

    Uses real energy_logs if available, otherwise generates realistic
    simulated values so the dashboard always has data to display.
    """
    existing = (
        db.query(DailyForecastVsActual)
        .filter(
            DailyForecastVsActual.tenant_id == tenant.id,
            DailyForecastVsActual.date == target_date,
        )
        .first()
    )
    if existing:
        return existing

    # ── Try real sensor data first ────────────────────────────────────────
    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = day_start + timedelta(days=1)

    actual_total = (
        db.query(func.sum(EnergyLog.consumption))
        .filter(
            EnergyLog.unit_key == tenant.unit_key,
            EnergyLog.timestamp >= day_start,
            EnergyLog.timestamp < day_end,
        )
        .scalar()
    )

    anomaly_count = (
        db.query(func.count(TenantAlert.id))
        .filter(
            TenantAlert.unit_key == tenant.unit_key,
            TenantAlert.created_at >= day_start,
            TenantAlert.created_at < day_end,
        )
        .scalar()
    ) or 0

    # ── Simulated forecast + actual if no real data ──────────────────────
    base_kwh = {"home": 25.0, "commercial": 120.0, "industrial": 450.0}.get(
        tenant.tenant_type or "home", 30.0
    )
    tariff = 6.5  # INR/kWh average

    forecast_kwh = round(base_kwh * random.uniform(0.85, 1.15), 2)
    if actual_total and actual_total > 0:
        actual_kwh = round(float(actual_total), 2)
    else:
        # Simulate: actual deviates ±20% from forecast
        actual_kwh = round(forecast_kwh * random.uniform(0.80, 1.20), 2)

    delta_kwh = round(actual_kwh - forecast_kwh, 2)
    delta_pct = round((delta_kwh / forecast_kwh) * 100, 2) if forecast_kwh else 0.0

    forecast_bill = round(forecast_kwh * tariff, 2)
    actual_bill = round(actual_kwh * tariff, 2)

    solar_base = base_kwh * 0.3
    forecast_solar = round(solar_base * random.uniform(0.8, 1.2), 2)
    actual_solar = round(forecast_solar * random.uniform(0.75, 1.25), 2)

    forecast_peak = round(base_kwh * 0.15 * random.uniform(0.9, 1.1), 2)
    actual_peak = round(forecast_peak * random.uniform(0.85, 1.25), 2)

    mape = round(abs(delta_pct), 2)
    mae = round(abs(delta_kwh), 2)
    accuracy = round(max(0, 100 - mape), 2)

    rag_consumption = compute_rag(delta_pct, "consumption")
    rag_bill = compute_rag(
        ((actual_bill - forecast_bill) / forecast_bill * 100) if forecast_bill else 0,
        "bill",
    )
    rag_solar = compute_rag(
        ((actual_solar - forecast_solar) / forecast_solar * 100) if forecast_solar else 0,
        "solar",
    )
    rag_peak = compute_rag(
        ((actual_peak - forecast_peak) / forecast_peak * 100) if forecast_peak else 0,
        "peak",
    )
    overall = _overall_rag(rag_consumption, rag_bill, rag_solar, rag_peak)

    row = DailyForecastVsActual(
        tenant_id=tenant.id,
        unit_key=tenant.unit_key,
        date=target_date,
        forecast_kwh=forecast_kwh,
        actual_kwh=actual_kwh,
        delta_kwh=delta_kwh,
        delta_pct=delta_pct,
        forecast_bill=forecast_bill,
        actual_bill=actual_bill,
        forecast_solar_kwh=forecast_solar,
        actual_solar_kwh=actual_solar,
        forecast_peak_kw=forecast_peak,
        actual_peak_kw=actual_peak,
        anomaly_count=anomaly_count,
        forecast_accuracy_pct=accuracy,
        mae=mae,
        mape=mape,
        rag_status=overall,
        computed_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def seed_history_for_tenant(db: Session, tenant: Tenant, days: int = 30) -> int:
    """Seed up to `days` worth of historical forecast-vs-actual rows."""
    today = date.today()
    created = 0
    for i in range(days):
        d = today - timedelta(days=i)
        existing = (
            db.query(DailyForecastVsActual)
            .filter(
                DailyForecastVsActual.tenant_id == tenant.id,
                DailyForecastVsActual.date == d,
            )
            .first()
        )
        if not existing:
            seed_forecast_vs_actual_for_tenant(db, tenant, d)
            created += 1
    return created


def seed_all_tenants(days: int = 30) -> int:
    """Run seeding for every active tenant. Returns rows created."""
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
        total = 0
        for t in tenants:
            total += seed_history_for_tenant(db, t, days)
        return total
    finally:
        db.close()

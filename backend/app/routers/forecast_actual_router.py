"""Forecast vs Actual router — scorecard, chart, history, export."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.forecast_actual_model import DailyForecastVsActual
from app.models.tenant_model import Tenant
from app.services.forecast_actual_service import (
    compute_rag,
    seed_history_for_tenant,
    _overall_rag,
)

router = APIRouter(prefix="/forecast-vs-actual", tags=["Forecast vs Actual"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_tenant_or_404(tenant_id: int, db: Session) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


def _date_range(period: str, ref_date: date | None = None):
    """Return (start_date, end_date) for a period string."""
    today = ref_date or date.today()
    if period == "week":
        return today - timedelta(days=6), today
    if period == "month":
        return today.replace(day=1), today
    # default: day
    return today, today


# ══════════════════════════════════════════════════════════════════════════════
#  1. SUMMARY / SCORECARD
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{tenant_id}", summary="Forecast vs Actual summary")
def get_summary(
    tenant_id: int,
    period: str = Query(default="day", pattern=r"^(day|week|month)$"),
    db: Session = Depends(get_db),
):
    tenant = _get_tenant_or_404(tenant_id, db)

    # Ensure data exists
    seed_history_for_tenant(db, tenant, days=31)

    start, end = _date_range(period)
    rows = (
        db.query(DailyForecastVsActual)
        .filter(
            DailyForecastVsActual.tenant_id == tenant_id,
            DailyForecastVsActual.date >= start,
            DailyForecastVsActual.date <= end,
        )
        .order_by(DailyForecastVsActual.date.desc())
        .all()
    )

    if not rows:
        raise HTTPException(status_code=404, detail="No forecast data for this period")

    # Aggregate across rows
    sum_f_kwh = sum(r.forecast_kwh or 0 for r in rows)
    sum_a_kwh = sum(r.actual_kwh or 0 for r in rows)
    sum_f_bill = sum(r.forecast_bill or 0 for r in rows)
    sum_a_bill = sum(r.actual_bill or 0 for r in rows)
    sum_f_solar = sum(r.forecast_solar_kwh or 0 for r in rows)
    sum_a_solar = sum(r.actual_solar_kwh or 0 for r in rows)
    sum_f_peak = max((r.forecast_peak_kw or 0 for r in rows), default=0)
    sum_a_peak = max((r.actual_peak_kw or 0 for r in rows), default=0)
    total_anomalies = sum(r.anomaly_count or 0 for r in rows)

    def pct(f: float, a: float) -> float:
        return round(((a - f) / f) * 100, 1) if f else 0.0

    def label(delta_pct: float) -> str:
        direction = "above" if delta_pct > 0 else "below"
        return f"{abs(delta_pct)}% {direction} forecast"

    c_pct = pct(sum_f_kwh, sum_a_kwh)
    b_pct = pct(sum_f_bill, sum_a_bill)
    s_pct = pct(sum_f_solar, sum_a_solar)
    p_pct = pct(sum_f_peak, sum_a_peak)

    rag_c = compute_rag(c_pct, "consumption")
    rag_b = compute_rag(b_pct, "bill")
    rag_s = compute_rag(s_pct, "solar")
    rag_p = compute_rag(p_pct, "peak")
    rag_anomaly = "green" if total_anomalies == 0 else ("amber" if total_anomalies <= 2 else "red")

    avg_mape = round(sum(r.mape or 0 for r in rows) / len(rows), 2) if rows else 0
    avg_mae = round(sum(r.mae or 0 for r in rows) / len(rows), 2) if rows else 0
    avg_accuracy = round(100 - avg_mape, 2)

    overall = _overall_rag(rag_c, rag_b, rag_s, rag_p, rag_anomaly)

    return {
        "tenant_id": tenant_id,
        "period": period,
        "date": str(end),
        "overall_rag": overall,
        "metrics": {
            "consumption": {
                "forecast_kwh": round(sum_f_kwh, 2),
                "actual_kwh": round(sum_a_kwh, 2),
                "delta_kwh": round(sum_a_kwh - sum_f_kwh, 2),
                "delta_pct": c_pct,
                "rag": rag_c,
                "label": label(c_pct),
            },
            "bill": {
                "forecast_inr": round(sum_f_bill, 2),
                "actual_inr": round(sum_a_bill, 2),
                "delta_inr": round(sum_a_bill - sum_f_bill, 2),
                "delta_pct": b_pct,
                "rag": rag_b,
                "label": label(b_pct),
            },
            "solar": {
                "forecast_kwh": round(sum_f_solar, 2),
                "actual_kwh": round(sum_a_solar, 2),
                "delta_kwh": round(sum_a_solar - sum_f_solar, 2),
                "delta_pct": s_pct,
                "rag": rag_s,
                "label": label(s_pct),
            },
            "peak_demand": {
                "forecast_kw": round(sum_f_peak, 2),
                "actual_kw": round(sum_a_peak, 2),
                "delta_kw": round(sum_a_peak - sum_f_peak, 2),
                "delta_pct": p_pct,
                "rag": rag_p,
                "label": label(p_pct),
            },
            "anomalies": {
                "forecast": 0,
                "actual": total_anomalies,
                "rag": rag_anomaly,
                "label": f"{total_anomalies} anomalies detected",
            },
        },
        "model_accuracy": {
            "model_1_mape": avg_mape,
            "model_1_mae_kwh": avg_mae,
            "accuracy_pct": avg_accuracy,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  2. CHART DATA (dual-line)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{tenant_id}/chart", summary="Chart time-series data")
def get_chart_data(
    tenant_id: int,
    period: str = Query(default="week", pattern=r"^(day|week|month)$"),
    metric: str = Query(default="consumption", pattern=r"^(consumption|bill|solar|peak)$"),
    db: Session = Depends(get_db),
):
    tenant = _get_tenant_or_404(tenant_id, db)
    seed_history_for_tenant(db, tenant, days=31)

    start, end = _date_range(period)
    rows = (
        db.query(DailyForecastVsActual)
        .filter(
            DailyForecastVsActual.tenant_id == tenant_id,
            DailyForecastVsActual.date >= start,
            DailyForecastVsActual.date <= end,
        )
        .order_by(DailyForecastVsActual.date.asc())
        .all()
    )

    field_map = {
        "consumption": ("forecast_kwh", "actual_kwh"),
        "bill":        ("forecast_bill", "actual_bill"),
        "solar":       ("forecast_solar_kwh", "actual_solar_kwh"),
        "peak":        ("forecast_peak_kw", "actual_peak_kw"),
    }
    f_field, a_field = field_map[metric]

    points = []
    for r in rows:
        f_val = getattr(r, f_field) or 0
        a_val = getattr(r, a_field) or 0
        d_pct = round(((a_val - f_val) / f_val) * 100, 1) if f_val else 0
        points.append({
            "date": str(r.date),
            "forecast": round(f_val, 2),
            "actual": round(a_val, 2),
            "delta_pct": d_pct,
            "rag": compute_rag(d_pct, metric),
        })

    return {
        "tenant_id": tenant_id,
        "metric": metric,
        "period": period,
        "points": points,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  3. SCORECARD (single date, all metrics)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{tenant_id}/scorecard", summary="RAG scorecard for one day")
def get_scorecard(
    tenant_id: int,
    target_date: str = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
):
    tenant = _get_tenant_or_404(tenant_id, db)
    seed_history_for_tenant(db, tenant, days=31)

    d = date.fromisoformat(target_date) if target_date else date.today()

    row = (
        db.query(DailyForecastVsActual)
        .filter(
            DailyForecastVsActual.tenant_id == tenant_id,
            DailyForecastVsActual.date == d,
        )
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail=f"No data for {d}")

    def metric_card(name: str, f_val: float, a_val: float, unit: str, metric_type: str):
        delta = round(a_val - f_val, 2)
        d_pct = round((delta / f_val) * 100, 1) if f_val else 0
        rag = compute_rag(d_pct, metric_type)
        direction = "up" if delta > 0 else "down"
        return {
            "name": name,
            "forecast": f_val,
            "actual": a_val,
            "delta": delta,
            "delta_pct": d_pct,
            "rag": rag,
            "unit": unit,
            "direction": direction,
        }

    cards = [
        metric_card("Consumption", row.forecast_kwh or 0, row.actual_kwh or 0, "kWh", "consumption"),
        metric_card("Monthly Bill", row.forecast_bill or 0, row.actual_bill or 0, "INR", "bill"),
        metric_card("Solar Gen", row.forecast_solar_kwh or 0, row.actual_solar_kwh or 0, "kWh", "solar"),
        metric_card("Peak Demand", row.forecast_peak_kw or 0, row.actual_peak_kw or 0, "kW", "peak"),
    ]

    # Anomaly card
    anomaly_rag = "green" if row.anomaly_count == 0 else ("amber" if row.anomaly_count <= 2 else "red")
    cards.append({
        "name": "Anomalies",
        "forecast": 0,
        "actual": row.anomaly_count,
        "delta": row.anomaly_count,
        "delta_pct": 0,
        "rag": anomaly_rag,
        "unit": "count",
        "direction": "up" if row.anomaly_count > 0 else "neutral",
    })

    # Accuracy card
    cards.append({
        "name": "Accuracy Score",
        "forecast": 100,
        "actual": row.forecast_accuracy_pct or 0,
        "delta": round((row.forecast_accuracy_pct or 0) - 100, 1),
        "delta_pct": 0,
        "rag": "green" if (row.forecast_accuracy_pct or 0) >= 90 else ("amber" if (row.forecast_accuracy_pct or 0) >= 80 else "red"),
        "unit": "%",
        "direction": "neutral",
    })

    overall = _overall_rag(*(c["rag"] for c in cards))

    return {
        "tenant_id": tenant_id,
        "date": str(d),
        "overall_rag": overall,
        "cards": cards,
        "model_accuracy": {
            "mape": row.mape or 0,
            "mae": row.mae or 0,
            "accuracy_pct": row.forecast_accuracy_pct or 0,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  4. HISTORY (accuracy trend)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{tenant_id}/history", summary="Historical accuracy trend")
def get_history(
    tenant_id: int,
    metric: str = Query(default="consumption", pattern=r"^(consumption|bill|solar|peak)$"),
    from_date: str = Query(default=None),
    to_date: str = Query(default=None),
    db: Session = Depends(get_db),
):
    tenant = _get_tenant_or_404(tenant_id, db)
    seed_history_for_tenant(db, tenant, days=31)

    end = date.fromisoformat(to_date) if to_date else date.today()
    start = date.fromisoformat(from_date) if from_date else end - timedelta(days=29)

    rows = (
        db.query(DailyForecastVsActual)
        .filter(
            DailyForecastVsActual.tenant_id == tenant_id,
            DailyForecastVsActual.date >= start,
            DailyForecastVsActual.date <= end,
        )
        .order_by(DailyForecastVsActual.date.asc())
        .all()
    )

    field_map = {
        "consumption": ("forecast_kwh", "actual_kwh"),
        "bill":        ("forecast_bill", "actual_bill"),
        "solar":       ("forecast_solar_kwh", "actual_solar_kwh"),
        "peak":        ("forecast_peak_kw", "actual_peak_kw"),
    }
    f_field, a_field = field_map[metric]

    points = []
    for r in rows:
        f_val = getattr(r, f_field) or 0
        a_val = getattr(r, a_field) or 0
        d_pct = round(((a_val - f_val) / f_val) * 100, 1) if f_val else 0
        points.append({
            "date": str(r.date),
            "forecast": round(f_val, 2),
            "actual": round(a_val, 2),
            "delta_pct": d_pct,
            "rag": compute_rag(d_pct, metric),
        })

    accuracies = [100 - abs(p["delta_pct"]) for p in points]
    avg_acc = round(sum(accuracies) / len(accuracies), 2) if accuracies else 0

    return {
        "tenant_id": tenant_id,
        "metric": metric,
        "from_date": str(start),
        "to_date": str(end),
        "points": points,
        "avg_accuracy_pct": avg_acc,
    }

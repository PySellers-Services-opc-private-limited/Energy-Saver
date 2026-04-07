"""Alerts router — query tenant anomaly alerts."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.alert_model import TenantAlert
from app.schemas import TenantAlertResponse
from app.utils.jwt_utils import get_unit_key_or_none

router = APIRouter(prefix="/tenant-alerts", tags=["Tenant Alerts"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── GET all alerts (optionally filtered by unit_key) ──────────────────────────

@router.get(
    "/",
    response_model=list[TenantAlertResponse],
    summary="List alerts (all units or filtered)",
)
def get_alerts(
    unit_key: str | None = Query(default=None, description="Filter by unit_key"),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    caller_unit: str | None = Depends(get_unit_key_or_none),
) -> list[TenantAlert]:
    q = db.query(TenantAlert).order_by(TenantAlert.created_at.desc())
    # Tenant users always see only their own alerts
    effective_unit = caller_unit or unit_key
    if effective_unit:
        q = q.filter(TenantAlert.unit_key == effective_unit)
    return q.limit(limit).all()


# ── GET alerts for a specific unit ────────────────────────────────────────────

@router.get(
    "/{unit_key}",
    response_model=list[TenantAlertResponse],
    summary="List alerts for a specific unit",
)
def get_alerts_for_unit(
    unit_key: str,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[TenantAlert]:
    return (
        db.query(TenantAlert)
        .filter(TenantAlert.unit_key == unit_key)
        .order_by(TenantAlert.created_at.desc())
        .limit(limit)
        .all()
    )

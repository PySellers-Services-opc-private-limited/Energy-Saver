"""Energy endpoints — log readings and retrieve history per unit_key."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.energy_log_model import EnergyLog
from app.models.tenant_model import Tenant
from app.schemas import EnergyLogCreate, EnergyLogResponse
from app.services.tenant_anomaly_service import check_anomaly
from app.utils.jwt_utils import get_current_user_payload, get_unit_key_or_none

router = APIRouter(prefix="/energy", tags=["Energy"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── GET history for a unit ────────────────────────────────────────────────────

@router.get(
    "/{unit_key}",
    response_model=list[EnergyLogResponse],
    summary="Get energy readings for a unit",
)
def get_energy_logs(
    unit_key: str,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    caller_unit: str | None = Depends(get_unit_key_or_none),
) -> list[EnergyLog]:
    # Tenants can only access their own unit
    if caller_unit and caller_unit != unit_key:
        raise HTTPException(status_code=403, detail="Access denied: not your unit")
    if not db.query(Tenant).filter(Tenant.unit_key == unit_key).first():
        raise HTTPException(status_code=404, detail="Unit not found")
    return (
        db.query(EnergyLog)
        .filter(EnergyLog.unit_key == unit_key)
        .order_by(EnergyLog.timestamp.desc())
        .limit(limit)
        .all()
    )


# ── POST — ingest a new reading ───────────────────────────────────────────────

@router.post(
    "/",
    response_model=EnergyLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest an energy reading for a unit",
)
def add_energy_log(
    log_in: EnergyLogCreate,
    db: Session = Depends(get_db),
) -> EnergyLog:
    if not db.query(Tenant).filter(Tenant.unit_key == log_in.unit_key).first():
        raise HTTPException(status_code=404, detail="Unit not found")

    new_log = EnergyLog(**log_in.model_dump())
    db.add(new_log)
    db.commit()
    db.refresh(new_log)

    # Run AI anomaly check AFTER commit to include this reading in history
    check_anomaly(db=db, unit_key=log_in.unit_key, latest_consumption=log_in.consumption)

    return new_log


# ── GET summary stats for a unit ──────────────────────────────────────────────

@router.get(
    "/{unit_key}/summary",
    summary="Get energy summary (avg, max, total) for a unit",
)
def energy_summary(unit_key: str, db: Session = Depends(get_db)) -> dict:
    if not db.query(Tenant).filter(Tenant.unit_key == unit_key).first():
        raise HTTPException(status_code=404, detail="Unit not found")

    logs = (
        db.query(EnergyLog)
        .filter(EnergyLog.unit_key == unit_key)
        .all()
    )
    if not logs:
        return {"unit_key": unit_key, "count": 0, "avg_kwh": 0, "max_kwh": 0, "total_kwh": 0}

    consumptions = [l.consumption for l in logs]
    return {
        "unit_key": unit_key,
        "count": len(consumptions),
        "avg_kwh": round(sum(consumptions) / len(consumptions), 4),
        "max_kwh": round(max(consumptions), 4),
        "total_kwh": round(sum(consumptions), 4),
    }

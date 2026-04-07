"""Anomaly detection endpoints."""

from fastapi import APIRouter, Query
from app.schemas import AnomalyResponse
from app.services.anomaly_service import AnomalyService

router = APIRouter(tags=["anomalies"])


@router.get("/anomalies", response_model=AnomalyResponse)
async def get_anomalies(
    limit: int = Query(default=20, ge=1, le=200, description="Max number of events to return"),
    device_id: str | None = Query(default=None, description="Filter by device ID"),
):
    """Return recent anomaly detection events."""
    return AnomalyService.recent(limit=limit, device_id=device_id)

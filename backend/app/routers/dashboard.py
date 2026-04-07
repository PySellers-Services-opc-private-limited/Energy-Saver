"""Dashboard KPI endpoint."""

from datetime import datetime, timezone
import random

from fastapi import APIRouter

from app.schemas import KPISummary
from app.services.data_service import DataService

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=KPISummary)
async def get_dashboard():
    """Return latest KPI summary for the main dashboard."""
    return DataService.latest_kpis()

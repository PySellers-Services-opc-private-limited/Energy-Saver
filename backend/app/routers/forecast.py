"""Energy forecasting endpoints."""

from fastapi import APIRouter, Query
from app.schemas import ForecastResponse
from app.services.forecast_service import ForecastService

router = APIRouter(tags=["forecast"])


@router.get("/forecast", response_model=ForecastResponse)
async def get_forecast(
    device_id: str = Query(default="device_001", description="Target device ID"),
    horizon_hours: int = Query(default=24, ge=1, le=168, description="Forecast horizon in hours"),
):
    """Return energy consumption forecast for the given device."""
    return ForecastService.forecast(device_id=device_id, horizon_hours=horizon_hours)

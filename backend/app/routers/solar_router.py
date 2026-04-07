"""Solar forecast endpoint – uses Model 6."""

from fastapi import APIRouter, Query

from app.services.solar_service import SolarForecastService

router = APIRouter(tags=["solar"])


@router.get("/solar/forecast")
async def solar_forecast(
    system_kw: float = Query(default=5.0, gt=0, le=100, description="Solar system size in kW"),
):
    """Predict next 24 hours of solar energy generation."""
    return SolarForecastService.forecast(system_kw=system_kw)

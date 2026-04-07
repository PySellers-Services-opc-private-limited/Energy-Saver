"""EV charging optimizer endpoint – uses Model 7."""

from fastapi import APIRouter, Query

from app.services.ev_service import EVOptimizerService

router = APIRouter(tags=["ev"])


@router.get("/ev/optimize")
async def optimize_ev_charging(
    current_soc: float = Query(default=20.0, ge=0, le=100, description="Current battery SOC %"),
    departure_hour: int = Query(default=8, ge=0, le=23, description="Target departure hour"),
    target_soc: float = Query(default=80.0, ge=0, le=100, description="Target SOC %"),
):
    """Generate optimal EV charging schedule using Q-learning."""
    return EVOptimizerService.optimize(
        current_soc=current_soc,
        departure_hour=departure_hour,
        target_soc=target_soc,
    )

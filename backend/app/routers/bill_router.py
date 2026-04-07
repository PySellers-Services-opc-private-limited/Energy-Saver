"""Bill prediction endpoint – uses Model 8."""

from fastapi import APIRouter, Query

from app.services.bill_service import BillPredictorService

router = APIRouter(tags=["bill"])


@router.get("/bill/predict")
async def predict_bill(
    days_elapsed: int = Query(default=15, ge=1, le=31, description="Days elapsed in current month"),
    avg_daily_kwh: float = Query(default=30.0, gt=0, description="Average daily consumption kWh"),
    tariff: float = Query(default=6.50, gt=0, description="Tariff INR/kWh"),
    avg_temp: float = Query(default=28.0, description="Average temperature °C"),
):
    """Predict the end-of-month electricity bill with confidence interval."""
    return BillPredictorService.predict(
        days_elapsed=days_elapsed,
        avg_daily_kwh=avg_daily_kwh,
        tariff=tariff,
        avg_temp=avg_temp,
    )

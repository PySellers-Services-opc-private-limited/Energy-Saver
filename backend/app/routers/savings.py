"""Annual savings estimator endpoint."""

from fastapi import APIRouter
from app.schemas import SavingsRequest, SavingsResponse, SavingsBreakdown
from app.services.savings_service import SavingsService

router = APIRouter(tags=["savings"])


@router.post("/savings", response_model=SavingsResponse)
async def estimate_savings(body: SavingsRequest):
    """Calculate estimated annual energy savings."""
    return SavingsService.estimate(body)

"""Model status & info endpoints."""

from fastapi import APIRouter
from app.schemas import ModelListResponse
from app.services.model_service import ModelService

router = APIRouter(tags=["models"])


@router.get("/models", response_model=ModelListResponse)
async def list_models():
    """Return status of all 8 AI models."""
    return ModelListResponse(models=ModelService.list_models())

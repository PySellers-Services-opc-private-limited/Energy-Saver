"""Streaming pipeline status endpoint."""

from fastapi import APIRouter
from app.schemas import PipelineStatus
from app.services.pipeline_service import PipelineService

router = APIRouter(tags=["pipeline"])


@router.get("/pipeline/status", response_model=PipelineStatus)
async def pipeline_status():
    """Return current streaming pipeline status."""
    return PipelineService.status()

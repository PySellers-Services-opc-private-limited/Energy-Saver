"""HVAC optimisation endpoints."""

from fastapi import APIRouter
from app.schemas import HVACCommandRequest, HVACCommandResponse
from app.services.hvac_service import HVACService

router = APIRouter(tags=["hvac"])


@router.post("/hvac/command", response_model=HVACCommandResponse)
async def send_hvac_command(cmd: HVACCommandRequest):
    """Issue an HVAC optimisation command and return the result."""
    return HVACService.issue_command(cmd)


@router.get("/hvac/status")
async def get_hvac_status():
    """Return the current HVAC optimisation status."""
    return HVACService.status()

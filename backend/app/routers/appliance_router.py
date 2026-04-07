"""Appliance fingerprinting endpoint – uses Model 5."""

from typing import Optional

from fastapi import APIRouter, Body

from app.services.appliance_service import ApplianceService

router = APIRouter(tags=["appliance"])


@router.post("/appliance/identify")
async def identify_appliance(
    power_readings: Optional[list[float]] = Body(default=None, description="60 power readings (kW)"),
):
    """Identify which appliance is running from its power signature."""
    return ApplianceService.identify(power_readings=power_readings)


@router.get("/appliance/list")
async def list_appliances():
    """Return known appliance types and typical power draw."""
    return ApplianceService.list_appliances()


@router.get("/appliance/demo")
async def demo_identify():
    """Demo: generate a random appliance signature and identify it."""
    return ApplianceService.identify(power_readings=None)

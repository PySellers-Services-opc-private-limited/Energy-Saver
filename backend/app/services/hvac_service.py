"""
HVACService – issues HVAC optimisation commands and tracks current status.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas import HVACCommandRequest, HVACCommandResponse

_SAVING_PCT = {
    "COMFORT": 0.0,
    "ECO": 15.0,
    "DEMAND_RESPONSE": 30.0,
    "PRE_CONDITION": 5.0,
    "OFF": 100.0,
}

_state: dict = {
    "zone_id": "zone_1",
    "mode": "ECO",
    "setpoint_c": 21.0,
    "last_updated": datetime.now(timezone.utc).isoformat(),
}


class HVACService:

    @staticmethod
    def issue_command(cmd: HVACCommandRequest) -> HVACCommandResponse:
        _state.update(
            zone_id=cmd.zone_id,
            mode=cmd.mode,
            setpoint_c=cmd.setpoint_c,
            last_updated=datetime.now(timezone.utc).isoformat(),
        )
        return HVACCommandResponse(
            zone_id=cmd.zone_id,
            mode=cmd.mode,
            setpoint_c=cmd.setpoint_c,
            estimated_saving_pct=_SAVING_PCT.get(cmd.mode, 0.0),
            issued_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def status() -> dict:
        return {**_state, "estimated_saving_pct": _SAVING_PCT.get(_state["mode"], 0.0)}

"""
SavingsService – wraps the project-level estimate_annual_savings helper.
"""

from __future__ import annotations

import sys
import os

# Ensure project root importable
_BACKEND_DIR  = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from utils.helpers import estimate_annual_savings  # noqa: E402

from app.schemas import SavingsBreakdown, SavingsRequest, SavingsResponse


class SavingsService:

    @staticmethod
    def estimate(req: SavingsRequest) -> SavingsResponse:
        result = estimate_annual_savings(
            baseline_kwh_per_day=req.baseline_kwh_per_day,
            tariff_per_kwh=req.tariff_per_kwh,
        )
        bd = result["breakdown"]
        return SavingsResponse(
            kwh_saved_per_day=result["kwh_saved_per_day"],
            kwh_saved_per_year=result["kwh_saved_per_year"],
            cost_saved_per_year=result["cost_saved_per_year"],
            co2_saved_kg_per_year=result["co2_saved_kg_per_year"],
            breakdown=SavingsBreakdown(
                hvac_kwh_per_year=bd.get("hvac_kwh", 0.0),
                ev_kwh_per_year=bd.get("ev_kwh", 0.0),
                anomaly_kwh_per_year=bd.get("anomaly_kwh", 0.0),
            ),
        )

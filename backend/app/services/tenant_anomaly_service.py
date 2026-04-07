"""
Tenant Anomaly Service
======================
Detects energy spikes per apartment unit using a simple statistical rule:

    if latest_consumption > rolling_average * SPIKE_THRESHOLD → anomaly

When an anomaly is found an alert row is written to `tenant_alerts`.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.alert_model import TenantAlert
from app.models.energy_log_model import EnergyLog

log = logging.getLogger("TenantAnomalyService")

# A reading is flagged if it is this many times above the rolling average
SPIKE_THRESHOLD: float = 1.5
# Minimum historical readings needed before we make a judgement
MIN_HISTORY: int = 3
# Rolling window size
WINDOW: int = 10


def check_anomaly(db: Session, unit_key: str, latest_consumption: float) -> bool:
    """
    Compare *latest_consumption* against the rolling average for *unit_key*.

    Returns True if an anomaly was detected (and an alert was saved).
    """
    recent = (
        db.query(EnergyLog)
        .filter(EnergyLog.unit_key == unit_key)
        .order_by(EnergyLog.timestamp.desc())
        .limit(WINDOW)
        .all()
    )

    if len(recent) < MIN_HISTORY:
        return False

    avg = sum(r.consumption for r in recent) / len(recent)

    if avg <= 0:
        return False

    ratio = latest_consumption / avg

    if ratio >= SPIKE_THRESHOLD:
        msg = (
            f"⚠️ Energy spike detected for unit {unit_key}: "
            f"{latest_consumption:.3f} kWh is {ratio:.1f}× the rolling average "
            f"({avg:.3f} kWh over last {len(recent)} readings)."
        )
        alert = TenantAlert(unit_key=unit_key, message=msg)
        db.add(alert)
        db.commit()
        log.warning(msg)
        return True

    return False

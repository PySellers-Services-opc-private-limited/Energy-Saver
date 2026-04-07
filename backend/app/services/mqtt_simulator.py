"""
MQTT Apartment Simulator
========================
Simulates IoT energy meters for each apartment unit.

Each unit publishes on topic:  apartment/{unit_key}

Readings are also written directly to the database so the energy
history is populated even without a real MQTT broker.

Start / stop lifecycle is managed by FastAPI's lifespan handler in main.py.
"""

from __future__ import annotations

import asyncio
import logging
import math
import random
from datetime import datetime, timezone
from typing import List

log = logging.getLogger("MQTTSimulator")

# Unit keys are loaded dynamically from the tenants table at startup.
# No hardcoded values — the simulator adapts to whatever tenants exist.
DEFAULT_UNIT_KEYS: List[str] = []


def _load_unit_keys() -> List[str]:
    """Load active tenant unit_keys from the database."""
    try:
        from app.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        rows = db.execute(text("SELECT unit_key FROM tenants WHERE is_active = TRUE")).fetchall()
        db.close()
        return [r[0] for r in rows]
    except Exception:
        return []

PUBLISH_INTERVAL_S = 5   # seconds between simulated readings
_tasks: List[asyncio.Task] = []


# ── Reading simulation ────────────────────────────────────────────────────────

def _simulate_reading(unit_key: str) -> dict:
    now = datetime.now(timezone.utc)
    hour = now.hour
    # Diurnal consumption curve (kWh)
    base = 0.5 + 1.5 * math.sin(math.pi * (hour - 4) / 12)
    consumption = round(max(0.01, base + random.gauss(0, 0.15)), 4)
    voltage = round(220 + random.gauss(0, 3), 2)
    current = round(max(0.05, consumption * 1000 / voltage), 3)
    power = round(voltage * current / 1000, 3)

    return {
        "topic": f"apartment/{unit_key}",
        "unit_key": unit_key,
        "timestamp": now.isoformat(),
        "voltage": voltage,
        "current": current,
        "power": power,
        "consumption": consumption,
    }


# ── Per-unit coroutine ────────────────────────────────────────────────────────

async def _simulate_unit(unit_key: str) -> None:
    """Simulate meter readings for one apartment unit and (optionally) persist them."""
    log.info("MQTT simulator: starting for unit %s", unit_key)
    while True:
        try:
            reading = _simulate_reading(unit_key)
            log.debug("MQTT [%s] → %s", reading["topic"], reading)

            # Persist to DB (best-effort — skip if tenant row doesn't exist yet)
            _try_persist(reading)

            await asyncio.sleep(PUBLISH_INTERVAL_S)
        except asyncio.CancelledError:
            log.info("MQTT simulator: stopped for unit %s", unit_key)
            raise


def _try_persist(reading: dict) -> None:
    """Write the reading to energy_logs if the tenant exists."""
    try:
        # Import here to avoid circular imports at module load time
        from app.database import SessionLocal
        from app.models.energy_log_model import EnergyLog
        from app.models.tenant_model import Tenant
        from app.services.tenant_anomaly_service import check_anomaly

        db = SessionLocal()
        try:
            tenant = db.query(Tenant).filter(
                Tenant.unit_key == reading["unit_key"]
            ).first()
            if not tenant:
                return   # No tenant for this unit yet — skip silently

            new_log = EnergyLog(
                unit_key=reading["unit_key"],
                voltage=reading["voltage"],
                current=reading["current"],
                power=reading["power"],
                consumption=reading["consumption"],
            )
            db.add(new_log)
            db.commit()
            db.refresh(new_log)

            check_anomaly(
                db=db,
                unit_key=reading["unit_key"],
                latest_consumption=reading["consumption"],
            )
        finally:
            db.close()
    except Exception as exc:  # pragma: no cover
        log.debug("MQTT persist skipped: %s", exc)


# ── Public API ────────────────────────────────────────────────────────────────

def start(unit_keys: List[str] | None = None) -> None:
    """Schedule a simulation task for each unit key."""
    keys = unit_keys or _load_unit_keys()
    if not keys:
        log.info("MQTT simulator: no tenants in DB — skipping")
        return
    loop = asyncio.get_event_loop()
    for uk in keys:
        task = loop.create_task(_simulate_unit(uk), name=f"mqtt-sim-{uk}")
        _tasks.append(task)
    log.info("MQTT simulator: started %d unit tasks", len(_tasks))


def stop() -> None:
    """Cancel all running simulation tasks."""
    for task in _tasks:
        task.cancel()
    _tasks.clear()
    log.info("MQTT simulator: all tasks stopped")

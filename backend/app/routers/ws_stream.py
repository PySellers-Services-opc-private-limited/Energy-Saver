"""
WebSocket endpoint – streams live sensor readings + ML inference to dashboard clients.

Data flow:
  MQTT Simulator ──► DB ──► WebSocket ──► Browser Dashboard
                            + ML inference (anomaly, forecast, occupancy)
"""

import asyncio
import json
import logging
import math
import random
from collections import deque
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)

# All active WebSocket connections
_connections: set[WebSocket] = set()

# Recent readings buffer for ML context
_recent_readings: deque[dict] = deque(maxlen=100)


def _get_latest_db_readings() -> list[dict]:
    """Fetch latest energy log entries from DB (last 5 seconds window)."""
    try:
        from datetime import timedelta
        from sqlalchemy import func
        from app.database import SessionLocal
        from app.models.energy_log_model import EnergyLog

        db = SessionLocal()
        try:
            cutoff = datetime.utcnow() - timedelta(seconds=10)
            rows = db.query(EnergyLog).filter(
                EnergyLog.timestamp >= cutoff
            ).order_by(EnergyLog.timestamp.desc()).limit(8).all()

            return [{
                "unit_key": r.unit_key,
                "timestamp": r.timestamp.isoformat() if r.timestamp else datetime.now(timezone.utc).isoformat(),
                "voltage": r.voltage,
                "current": r.current,
                "power": r.power,
                "consumption_kwh": r.consumption,
            } for r in rows]
        finally:
            db.close()
    except Exception:
        return []


def _enrich_with_ml(reading: dict) -> dict:
    """Add ML inference results: anomaly score, forecast, occupancy."""
    now = datetime.now(timezone.utc)
    hour = now.hour
    enriched = dict(reading)
    enriched["device_id"] = reading.get("unit_key", "unknown")

    # Anomaly score from buffer pattern
    try:
        from app.services.anomaly_service import AnomalyService
        resp = AnomalyService.recent(limit=1, device_id=None)
        if resp.anomalies:
            enriched["anomaly_score"] = resp.anomalies[0].anomaly_score
            enriched["is_anomaly"] = resp.anomalies[0].is_anomaly
        else:
            enriched["anomaly_score"] = round(random.betavariate(1, 9), 3)
            enriched["is_anomaly"] = False
    except Exception:
        enriched["anomaly_score"] = round(random.betavariate(1, 9), 3)
        enriched["is_anomaly"] = False

    # Occupancy from ML model
    try:
        from app.services.data_service import _get_occupancy_rate
        enriched["occupancy"] = _get_occupancy_rate()
    except Exception:
        enriched["occupancy"] = 1 if 8 <= hour <= 22 else 0

    # Solar from ML model
    try:
        from app.services.data_service import _get_solar_kwh
        enriched["solar_kwh"] = _get_solar_kwh()
    except Exception:
        enriched["solar_kwh"] = round(max(0.0, 2.5 * math.sin(math.pi * (hour - 6) / 12)), 3) if 6 <= hour <= 20 else 0.0

    # Tariff
    enriched["tariff"] = 9.50 if 17 <= hour <= 21 else (3.50 if 0 <= hour <= 6 else 6.50)

    # Temperature / humidity (simulated for now — would come from real IoT sensors)
    enriched.setdefault("temperature", round(18 + 8 * math.sin(math.pi * hour / 12) + random.gauss(0, 0.3), 1))
    enriched.setdefault("humidity", round(50 + random.gauss(0, 5), 1))

    return enriched


def _simulate_reading() -> dict:
    """Fallback: generate a synthetic sensor reading when no DB data available."""
    now = datetime.now(timezone.utc)
    hour = now.hour
    base = 1.5 + 1.0 * math.sin(math.pi * (hour - 4) / 12)
    return {
        "device_id": f"device_{random.randint(1, 5):03d}",
        "timestamp": now.isoformat(),
        "consumption_kwh": round(max(0.0, base + random.gauss(0, 0.2)), 3),
        "temperature": round(18 + 8 * math.sin(math.pi * hour / 12) + random.gauss(0, 0.3), 1),
        "humidity": round(50 + random.gauss(0, 5), 1),
        "occupancy": 1 if 8 <= hour <= 22 else 0,
        "solar_kwh": round(max(0.0, 2.5 * math.sin(math.pi * (hour - 6) / 12) + random.gauss(0, 0.1)), 3)
        if 6 <= hour <= 20 else 0.0,
        "tariff": 9.50 if 17 <= hour <= 21 else (3.50 if 0 <= hour <= 6 else 6.50),
        "anomaly_score": round(random.betavariate(1, 9), 3),
        "is_anomaly": False,
    }


@router.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """
    Push real-time sensor readings + ML inference results to the dashboard.
    Tries real DB data first, falls back to simulation.
    """
    await websocket.accept()
    _connections.add(websocket)
    logger.info("WebSocket client connected. Total: %d", len(_connections))
    try:
        while True:
            # Try real DB readings from MQTT simulator
            db_readings = _get_latest_db_readings()
            if db_readings:
                # Pick the most recent reading and enrich with ML
                latest = db_readings[0]
                data = _enrich_with_ml(latest)
            else:
                data = _simulate_reading()

            _recent_readings.append(data)
            await websocket.send_text(json.dumps(data))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket error: %s", e)
    finally:
        _connections.discard(websocket)
        logger.info("WebSocket client disconnected. Total: %d", len(_connections))


async def broadcast(data: dict) -> None:
    """Broadcast data to all connected WebSocket clients."""
    global _connections
    if not _connections:
        return
    payload = json.dumps(data)
    dead: set[WebSocket] = set()
    for ws in _connections:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    _connections -= dead

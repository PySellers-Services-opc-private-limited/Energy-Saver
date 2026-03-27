"""WebSocket endpoint – streams simulated sensor readings to connected clients."""

import asyncio
import json
import math
import random
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])

# Keep track of all active WebSocket connections
_connections: set[WebSocket] = set()


def _simulate_reading() -> dict:
    """Generate a realistic sensor reading with sinusoidal base + noise."""
    now = datetime.now(timezone.utc)
    hour = now.hour
    # Realistic diurnal curve: peak ~18:00, trough ~04:00
    base = 1.5 + 1.0 * math.sin(math.pi * (hour - 4) / 12)
    reading = {
        "device_id": f"device_{random.randint(1, 5):03d}",
        "timestamp": now.isoformat(),
        "consumption_kwh": round(max(0.0, base + random.gauss(0, 0.2)), 3),
        "temperature": round(18 + 8 * math.sin(math.pi * hour / 12) + random.gauss(0, 0.3), 1),
        "humidity": round(50 + random.gauss(0, 5), 1),
        "occupancy": 1 if 8 <= hour <= 22 else 0,
        "solar_kwh": round(max(0.0, 2.5 * math.sin(math.pi * (hour - 6) / 12) + random.gauss(0, 0.1)), 3)
        if 6 <= hour <= 20 else 0.0,
        "tariff": 9.50 if 17 <= hour <= 21 else (3.50 if 0 <= hour <= 6 else 6.50),  # INR/kWh
        "anomaly_score": round(random.betavariate(1, 9), 3),
    }
    return reading


@router.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """Push a simulated sensor reading every second to the client."""
    await websocket.accept()
    _connections.add(websocket)
    try:
        while True:
            data = _simulate_reading()
            await websocket.send_text(json.dumps(data))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    finally:
        _connections.discard(websocket)

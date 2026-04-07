"""
Real MQTT Subscriber — connects to a Mosquitto broker and ingests
live sensor data from ESP32 / smart meters / Tasmota devices.

Topics:
  energy/{device_id}/reading   ← sensor readings (kWh, voltage, current, etc.)
  apartment/{unit_key}         ← apartment-level energy meter data

When a real broker is available (MQTT_BROKER env var), this service
connects and writes incoming readings to the database + pushes to WebSocket.
When no broker is reachable, it silently falls back — the existing
MQTT simulator keeps running as usual.

Start/stop managed by FastAPI lifespan in main.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv

# Load both .env files (backend/.env + root .env for MQTT config)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(os.path.dirname(_THIS_DIR))
_ROOT_DIR = os.path.dirname(_BACKEND_DIR)
load_dotenv(os.path.join(_BACKEND_DIR, ".env"))
load_dotenv(os.path.join(_ROOT_DIR, ".env"))

logger = logging.getLogger("RealMQTT")

# Config from env
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "energy_saver_backend") + f"_{uuid.uuid4().hex[:6]}"

# Topics to subscribe
SUBSCRIBE_TOPICS = [
    ("energy/+/reading", 1),      # IoT meters: energy/{device_id}/reading
    ("apartment/+", 1),           # Apartment meters: apartment/{unit_key}
    ("home/+/energy", 1),         # Home Assistant style
    ("tasmota/+/SENSOR", 1),      # Tasmota smart plugs
]

_client = None
_thread: Optional[threading.Thread] = None
_running = False


def _on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info("Connected to MQTT broker %s:%d", MQTT_BROKER, MQTT_PORT)
        for topic, qos in SUBSCRIBE_TOPICS:
            client.subscribe(topic, qos=qos)
            logger.info("  Subscribed: %s (QoS %d)", topic, qos)
    else:
        logger.error("MQTT connection failed: rc=%d", rc)


def _on_disconnect(client, userdata, flags_or_rc=None, rc=None, properties=None):
    # paho-mqtt v2 passes (client, userdata, flags, rc, properties)
    # paho-mqtt v1 passes (client, userdata, rc)
    actual_rc = rc if rc is not None else (flags_or_rc if isinstance(flags_or_rc, int) else 0)
    if actual_rc != 0:
        logger.warning("MQTT disconnected unexpectedly (rc=%s) — will auto-reconnect", actual_rc)


def _on_message(client, userdata, msg):
    """Handle incoming MQTT message from any subscribed topic."""
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode("utf-8"))

        # Parse based on topic pattern
        reading = _parse_message(topic, payload)
        if reading:
            _persist_reading(reading)
            logger.debug("MQTT [%s] → %s kWh", topic, reading.get("consumption", "?"))
    except json.JSONDecodeError:
        logger.debug("MQTT non-JSON message on %s: %s", msg.topic, msg.payload[:100])
    except Exception as e:
        logger.error("MQTT message error: %s", e)


def _parse_message(topic: str, payload: dict) -> Optional[dict]:
    """Parse MQTT payload from different device types into a unified reading."""
    parts = topic.split("/")
    now = datetime.now(timezone.utc)

    # Pattern: energy/{device_id}/reading
    if topic.startswith("energy/") and topic.endswith("/reading"):
        device_id = parts[1]
        return {
            "unit_key": payload.get("unit_key", device_id),
            "timestamp": now,
            "voltage": float(payload.get("voltage", payload.get("V", 220))),
            "current": float(payload.get("current", payload.get("I", 0))),
            "power": float(payload.get("power", payload.get("W", 0))),
            "consumption": float(payload.get("kwh", payload.get("consumption_kwh", payload.get("kWh", 0)))),
        }

    # Pattern: apartment/{unit_key}
    if topic.startswith("apartment/"):
        unit_key = parts[1]
        return {
            "unit_key": unit_key,
            "timestamp": now,
            "voltage": float(payload.get("voltage", 220)),
            "current": float(payload.get("current", 0)),
            "power": float(payload.get("power", 0)),
            "consumption": float(payload.get("consumption", payload.get("consumption_kwh", 0))),
        }

    # Pattern: home/{device}/energy (Home Assistant style)
    if topic.startswith("home/") and topic.endswith("/energy"):
        device_id = parts[1]
        return {
            "unit_key": device_id,
            "timestamp": now,
            "voltage": float(payload.get("voltage", 220)),
            "current": float(payload.get("current", 0)),
            "power": float(payload.get("power", 0)),
            "consumption": float(payload.get("total_kwh", payload.get("energy", 0))),
        }

    # Pattern: tasmota/{device}/SENSOR (Tasmota smart plug)
    if topic.startswith("tasmota/") and topic.endswith("/SENSOR"):
        device_id = parts[1]
        # Tasmota nests under ENERGY key
        energy = payload.get("ENERGY", payload)
        return {
            "unit_key": device_id,
            "timestamp": now,
            "voltage": float(energy.get("Voltage", 220)),
            "current": float(energy.get("Current", 0)),
            "power": float(energy.get("Power", 0)),
            "consumption": float(energy.get("Total", energy.get("Today", 0))),
        }

    return None


def _persist_reading(reading: dict) -> None:
    """Write the reading to energy_logs if the tenant exists."""
    try:
        from app.database import SessionLocal
        from app.models.energy_log_model import EnergyLog
        from app.models.tenant_model import Tenant

        db = SessionLocal()
        try:
            # Check if unit_key matches any tenant
            tenant = db.query(Tenant).filter(
                Tenant.unit_key == reading["unit_key"]
            ).first()
            if not tenant:
                # Try matching without prefix (e.g., "A101" → "UNIT-A101")
                tenant = db.query(Tenant).filter(
                    Tenant.unit_key.contains(reading["unit_key"])
                ).first()
            if not tenant:
                logger.debug("No tenant for unit_key=%s — skipping", reading["unit_key"])
                return

            new_log = EnergyLog(
                unit_key=tenant.unit_key,
                voltage=reading.get("voltage"),
                current=reading.get("current"),
                power=reading.get("power"),
                consumption=reading.get("consumption"),
            )
            db.add(new_log)
            db.commit()

            # Check anomaly
            try:
                from app.services.tenant_anomaly_service import check_anomaly
                check_anomaly(
                    db=db,
                    unit_key=tenant.unit_key,
                    latest_consumption=reading.get("consumption", 0),
                )
            except Exception:
                pass

        finally:
            db.close()
    except Exception as e:
        logger.debug("MQTT persist error: %s", e)


# ── Public API ────────────────────────────────────────────────────────────────

def start() -> None:
    """Start the real MQTT subscriber in a background thread."""
    global _client, _thread, _running

    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        logger.info("paho-mqtt not installed — real MQTT disabled (pip install paho-mqtt)")
        return

    # Don't start if broker is localhost and no explicit config
    if MQTT_BROKER == "localhost" and not os.getenv("MQTT_BROKER"):
        logger.info("Real MQTT: no MQTT_BROKER configured — using simulator only")
        return

    _running = True
    _client = mqtt.Client(
        client_id=MQTT_CLIENT_ID,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2 if hasattr(mqtt, 'CallbackAPIVersion') else None,
    )

    if MQTT_USER:
        _client.username_pw_set(MQTT_USER, MQTT_PASS)

    _client.on_connect = _on_connect
    _client.on_disconnect = _on_disconnect
    _client.on_message = _on_message
    _client.reconnect_delay_set(min_delay=1, max_delay=30)

    def _mqtt_loop():
        try:
            _client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            _client.loop_forever()
        except Exception as e:
            logger.error("MQTT connection failed: %s", e)

    _thread = threading.Thread(target=_mqtt_loop, name="real-mqtt-subscriber", daemon=True)
    _thread.start()
    logger.info("Real MQTT subscriber started → %s:%d", MQTT_BROKER, MQTT_PORT)


def stop() -> None:
    """Stop the MQTT subscriber."""
    global _client, _running
    _running = False
    if _client:
        try:
            _client.disconnect()
            _client.loop_stop()
        except Exception:
            pass
        _client = None
    logger.info("Real MQTT subscriber stopped")


def is_connected() -> bool:
    """Check if connected to the MQTT broker."""
    return _client is not None and _client.is_connected() if _client else False

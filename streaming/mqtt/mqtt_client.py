"""
MQTT Client — IoT Sensor Bridge
=================================
Connects to MQTT broker and ingests real-time sensor data
from smart plugs, energy meters, thermostats, etc.

AWS IoT Core setup:
  Broker: <account>.iot.<region>.amazonaws.com
  Port:   8883 (TLS)
  Auth:   X.509 certificates

Topics consumed:
  energy/+/reading        ← Raw sensor readings
  energy/+/status         ← Device online/offline
  energy/command/+        ← HVAC/device commands (published)

Usage:
  client = MQTTClient(config)
  await client.connect()
  await client.run(engine)   # feeds StreamEngine
"""

import asyncio
import json
import logging
import time
import numpy as np
from datetime import datetime
from typing import Optional

log = logging.getLogger("MQTT")

# Try real paho-mqtt, fall back to simulator
try:
    import paho.mqtt.client as mqtt_lib
    HAS_PAHO = True
except ImportError:
    HAS_PAHO = False
    log.warning("paho-mqtt not installed — using built-in simulator")

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from streaming.stream_engine import SensorReading, StreamEngine


# ─────────────────────────────────────────────────────────────────
# TOPIC SCHEMA
# ─────────────────────────────────────────────────────────────────

TOPIC_READING  = "energy/{device_id}/reading"
TOPIC_STATUS   = "energy/{device_id}/status"
TOPIC_CMD      = "energy/command/{device_id}"
TOPIC_ALERT    = "energy/alert/{device_id}"
TOPIC_HVAC     = "hvac/command/{zone}"

# Expected MQTT payload schema:
# {
#   "device_id": "meter_01",
#   "ts": 1710000000.0,
#   "kwh": 2.34,
#   "temp": 21.5,
#   "humidity": 48.0,
#   "co2": 520,
#   "light": 350,
#   "voltage": 230,
#   "current": 10.17,
#   "zone": "living_room"
# }


# ─────────────────────────────────────────────────────────────────
# MQTT CLIENT
# ─────────────────────────────────────────────────────────────────

class MQTTClient:
    """
    Async MQTT client that bridges IoT sensors → StreamEngine.
    Supports AWS IoT Core with TLS certificates.
    """

    def __init__(self, config: dict):
        self.config    = config
        self.broker    = config.get("broker",   "localhost")
        self.port      = config.get("port",     1883)
        self.client_id = config.get("client_id","energy_saver_ai")
        self.topics    = config.get("topics",   ["energy/#"])
        self.engine: Optional[StreamEngine] = None
        self._client   = None
        self._loop     = None
        self._queue    = asyncio.Queue(maxsize=10000)
        self._stats    = {"received": 0, "parsed": 0, "errors": 0}

        # AWS IoT Core TLS config
        self.tls_config = config.get("tls", {})

    # ── Connection ──────────────────────────────────────────────

    async def connect(self):
        if not HAS_PAHO:
            log.info("MQTT simulator mode (paho-mqtt not installed)")
            return

        self._client = mqtt_lib.Client(client_id=self.client_id, protocol=mqtt_lib.MQTTv5)

        # AWS IoT Core TLS
        if self.tls_config:
            self._client.tls_set(
                ca_certs   = self.tls_config.get("ca_cert"),
                certfile   = self.tls_config.get("certfile"),
                keyfile    = self.tls_config.get("keyfile"),
            )
            log.info("TLS configured for AWS IoT Core")

        self._client.on_connect    = self._on_connect
        self._client.on_message    = self._on_message
        self._client.on_disconnect = self._on_disconnect

        self._client.connect(self.broker, self.port, keepalive=60)
        self._client.loop_start()
        log.info(f"MQTT connecting to {self.broker}:{self.port}")

    def _on_connect(self, client, userdata, flags, rc, props=None):
        if rc == 0:
            log.info(f"✅ MQTT connected to {self.broker}")
            for topic in self.topics:
                client.subscribe(topic, qos=1)
                log.info(f"   Subscribed: {topic}")
        else:
            log.error(f"❌ MQTT connection failed: rc={rc}")

    def _on_disconnect(self, client, userdata, rc, props=None):
        log.warning(f"MQTT disconnected (rc={rc}) — auto-reconnecting...")

    def _on_message(self, client, userdata, msg):
        """Called by paho thread — put on asyncio queue."""
        self._stats["received"] += 1
        try:
            payload = json.loads(msg.payload.decode())
            payload["_topic"] = msg.topic
            # Thread-safe put to asyncio queue
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._queue.put(payload), self._loop
                )
        except Exception as e:
            self._stats["errors"] += 1
            log.error(f"MQTT parse error: {e}")

    # ── Message Processing ───────────────────────────────────────

    def _parse_payload(self, payload: dict) -> Optional[SensorReading]:
        """Convert raw MQTT payload to SensorReading."""
        try:
            return SensorReading(
                device_id       = payload.get("device_id", "unknown"),
                timestamp       = payload.get("ts", time.time()),
                consumption_kwh = float(payload.get("kwh",      0.0)),
                temperature     = float(payload.get("temp",     20.0)),
                humidity        = float(payload.get("humidity", 50.0)),
                co2             = float(payload.get("co2",      400.0)),
                light           = float(payload.get("light",    100.0)),
                voltage         = float(payload.get("voltage",  230.0)),
                current         = float(payload.get("current",  0.0)),
                source          = "mqtt",
                building_zone   = payload.get("zone", "main"),
            )
        except Exception as e:
            log.error(f"Failed to parse MQTT payload: {e}")
            return None

    async def publish_hvac_command(self, zone: str, action: str, target_temp: float):
        """Publish HVAC command back to smart thermostat via MQTT."""
        if not self._client:
            return
        topic   = TOPIC_HVAC.format(zone=zone)
        payload = json.dumps({
            "action":      action,
            "target_temp": target_temp,
            "ts":          time.time(),
            "source":      "energy_saver_ai"
        })
        self._client.publish(topic, payload, qos=1)
        log.info(f"📤 HVAC command → {topic}: {action} @ {target_temp}°C")

    async def publish_alert(self, device_id: str, alert_level: str,
                             anomaly_score: float, kwh: float):
        """Publish anomaly alert to MQTT alert topic."""
        if not self._client:
            return
        topic   = TOPIC_ALERT.format(device_id=device_id)
        payload = json.dumps({
            "level":   alert_level,
            "score":   round(anomaly_score, 3),
            "kwh":     round(kwh, 3),
            "ts":      time.time(),
        })
        self._client.publish(topic, payload, qos=1)

    # ── Main Run Loop ────────────────────────────────────────────

    async def run(self, engine: StreamEngine):
        """Main async loop: drain queue → parse → ingest into engine."""
        self.engine = engine
        self._loop  = asyncio.get_event_loop()
        log.info("MQTT consumer loop started")

        while True:
            try:
                payload = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                reading = self._parse_payload(payload)
                if reading:
                    self._stats["parsed"] += 1
                    await engine.ingest(reading)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self._stats["errors"] += 1
                log.error(f"MQTT consumer error: {e}")

    # ── Simulator (for testing without real hardware) ─────────────

    async def run_simulator(self, engine: StreamEngine, hz: float = 1.0):
        """
        Simulate IoT sensor data for testing.
        Generates realistic readings for 5 devices at `hz` readings/sec.
        """
        self.engine = engine
        self._loop  = asyncio.get_event_loop()
        log.info(f"🎮 MQTT simulator running at {hz} Hz for 5 virtual devices")

        devices = [
            {"id": "meter_living",   "base_kwh": 1.5, "zone": "living_room"},
            {"id": "meter_kitchen",  "base_kwh": 2.2, "zone": "kitchen"},
            {"id": "meter_hvac",     "base_kwh": 3.5, "zone": "hvac"},
            {"id": "meter_bedroom",  "base_kwh": 0.8, "zone": "bedroom"},
            {"id": "meter_office",   "base_kwh": 1.2, "zone": "office"},
        ]
        anomaly_countdown = 50   # Inject anomaly every 50 readings

        while True:
            for dev in devices:
                hour = datetime.now().hour
                # Time-of-day pattern
                tod_factor = 1.5 if (17 <= hour <= 21) else (0.6 if hour < 6 else 1.0)
                # Random anomaly injection
                anomaly_spike = 4.0 if anomaly_countdown <= 0 else 0.0

                reading = SensorReading(
                    device_id       = dev["id"],
                    timestamp       = time.time(),
                    consumption_kwh = dev["base_kwh"] * tod_factor
                                      + np.random.normal(0, 0.15)
                                      + anomaly_spike,
                    temperature     = 21 + np.random.normal(0, 0.5),
                    humidity        = 50 + np.random.normal(0, 3),
                    co2             = 500 + np.random.normal(0, 40),
                    light           = 200 + np.random.normal(0, 30),
                    source          = "mqtt_sim",
                    building_zone   = dev["zone"],
                )
                await engine.ingest(reading)

            anomaly_countdown -= 1
            if anomaly_countdown <= 0:
                anomaly_countdown = 50

            await asyncio.sleep(1.0 / max(hz, 0.1))

    def get_stats(self) -> dict:
        return self._stats


# ─────────────────────────────────────────────────────────────────
# AWS IOT CORE HELPERS
# ─────────────────────────────────────────────────────────────────

AWS_IOT_CONFIG_TEMPLATE = {
    "broker":    "<account-id>.iot.<region>.amazonaws.com",
    "port":      8883,
    "client_id": "energy_saver_ai_cloud",
    "topics":    ["energy/#", "hvac/#"],
    "tls": {
        "ca_cert":  "certs/AmazonRootCA1.pem",
        "certfile": "certs/device-certificate.pem.crt",
        "keyfile":  "certs/device-private.pem.key",
    }
}

AZURE_IOT_CONFIG_TEMPLATE = {
    "broker":    "<hub-name>.azure-devices.net",
    "port":      8883,
    "client_id": "<device-id>",
    "topics":    ["devices/<device-id>/messages/devicebound/#"],
    "username":  "<hub-name>.azure-devices.net/<device-id>/?api-version=2021-04-12",
    "tls": {
        "ca_cert": "certs/DigiCertGlobalRootG2.crt.pem",
    }
}


if __name__ == "__main__":
    async def demo():
        from streaming.stream_engine import StreamEngine

        engine = StreamEngine({"window_size": 10})
        await engine.start()

        alert_count = 0
        async def on_alert(evt):
            nonlocal alert_count
            alert_count += 1
            print(f"  🚨 [{evt.alert_level}] {evt.reading.device_id} "
                  f"score={evt.anomaly_score:.2f} kwh={evt.reading.consumption_kwh:.2f}")

        engine.register_handler("on_alert", on_alert)

        client = MQTTClient({"window_size": 10})
        print("Running MQTT simulator for 3 seconds...")
        try:
            await asyncio.wait_for(client.run_simulator(engine, hz=10), timeout=3.0)
        except asyncio.TimeoutError:
            pass

        stats = engine.get_stats()
        print(f"\n📊 Total readings : {stats['total_readings']}")
        print(f"📊 Total alerts   : {alert_count}")
        print(f"📊 Avg latency    : {stats['avg_latency_ms']:.2f} ms")
        print("✅ MQTT demo complete")

    asyncio.run(demo())

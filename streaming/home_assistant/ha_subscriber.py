"""
Home Assistant WebSocket Subscriber
=====================================
Connects to Home Assistant via its native WebSocket API.
Subscribes to state_changed events for all energy/sensor entities.

Entities tracked automatically:
  sensor.power_*          → current power draw (W)
  sensor.energy_*         → cumulative energy (kWh)
  sensor.temperature_*    → temperature sensors
  climate.*               → HVAC state and setpoints
  binary_sensor.occupancy_* → motion / occupancy
  sensor.solar_power      → solar inverter output

Setup:
  1. In HA: Profile → Long-Lived Access Tokens → Create Token
  2. Set HA_URL=http://homeassistant.local:8123
  3. Set HA_TOKEN=your_token_here
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Callable, Optional

log = logging.getLogger("HomeAssistant")

# Entity patterns to track
ENERGY_PATTERNS  = ("sensor.power", "sensor.energy", "sensor.electricity")
SENSOR_PATTERNS  = ("sensor.temperature", "sensor.humidity", "sensor.co2")
CLIMATE_PATTERNS = ("climate.",)
SOLAR_PATTERNS   = ("sensor.solar", "sensor.pv")
OCCUPANCY_PATTERNS = ("binary_sensor.occupancy", "binary_sensor.motion")


def _matches(entity_id: str, patterns: tuple) -> bool:
    return any(entity_id.startswith(p) for p in patterns)


class HomeAssistantSubscriber:
    """
    WebSocket subscriber for Home Assistant.
    Translates HA state changes → sensor buffer readings.
    """

    def __init__(self, cfg, on_reading: Callable):
        self.cfg        = cfg
        self.on_reading = on_reading   # async callback(device_id, reading)
        self.running    = False
        self._ws        = None
        self._msg_id    = 1
        self._entity_cache: dict = {}   # entity_id → last state

    async def start(self):
        self.running = True
        log.info(f"🏠 Home Assistant subscriber starting: {self.cfg.home_assistant.url}")

        while self.running:
            try:
                await self._connect_and_listen()
            except Exception as e:
                log.error(f"HA connection error: {e} — reconnecting in 10s")
                await asyncio.sleep(10)

    async def _connect_and_listen(self):
        """Open WebSocket, auth, subscribe, process events."""
        try:
            import websockets
        except ImportError:
            log.warning("websockets not installed — HA subscriber disabled")
            log.info("  Install: pip install websockets")
            # Fall back to polling
            await self._poll_fallback()
            return

        ha_ws_url = self.cfg.home_assistant.url.replace("http", "ws") + "/api/websocket"
        token     = self.cfg.home_assistant.token

        async with websockets.connect(ha_ws_url) as ws:
            self._ws = ws
            log.info(f"🏠 Connected to {ha_ws_url}")

            # Auth
            auth_req  = await ws.recv()
            auth_data = json.loads(auth_req)
            if auth_data.get("type") == "auth_required":
                await ws.send(json.dumps({"type": "auth", "access_token": token}))
                auth_resp = json.loads(await ws.recv())
                if auth_resp.get("type") != "auth_ok":
                    raise RuntimeError(f"HA auth failed: {auth_resp}")
                log.info("🏠 HA authenticated ✓")

            # Subscribe to state_changed events
            await ws.send(json.dumps({
                "id":         self._next_id(),
                "type":       "subscribe_events",
                "event_type": "state_changed"
            }))
            log.info("🏠 Subscribed to state_changed events")

            # Process event stream
            while self.running:
                try:
                    raw  = await asyncio.wait_for(ws.recv(), timeout=30)
                    msg  = json.loads(raw)
                    if msg.get("type") == "event":
                        await self._handle_event(msg["event"])
                except asyncio.TimeoutError:
                    # Send ping to keep alive
                    await ws.send(json.dumps({"id": self._next_id(), "type": "ping"}))

    async def _handle_event(self, event: dict):
        """Process a state_changed event from Home Assistant."""
        data       = event.get("data", {})
        entity_id  = data.get("entity_id", "")
        new_state  = data.get("new_state", {})

        if new_state is None:
            return

        state_val = new_state.get("state", "")
        attrs     = new_state.get("attributes", {})

        reading = {
            "source":    "home_assistant",
            "entity_id": entity_id,
            "hour":      datetime.now().hour,
        }

        # Power / energy sensors
        if _matches(entity_id, ENERGY_PATTERNS):
            try:
                val = float(state_val)
                unit = attrs.get("unit_of_measurement", "")
                if "W" in unit and "k" not in unit:
                    val /= 1000.0   # Convert W → kWh estimate
                reading["consumption_kwh"] = round(val, 4)
                device_id = entity_id.replace("sensor.", "").replace(".", "_")
                await self.on_reading(device_id, reading)
            except ValueError:
                pass

        # Temperature sensors
        elif _matches(entity_id, SENSOR_PATTERNS):
            try:
                reading["temperature"] = float(state_val)
                if "humidity" in entity_id:
                    reading["humidity"] = float(state_val)
                device_id = "environment"
                await self.on_reading(device_id, reading)
            except ValueError:
                pass

        # Solar power
        elif _matches(entity_id, SOLAR_PATTERNS):
            try:
                val = float(state_val)
                unit = attrs.get("unit_of_measurement", "W")
                if "W" in unit and "k" not in unit:
                    val /= 1000.0
                reading["solar_kwh"] = round(val, 4)
                await self.on_reading("solar", reading)
            except ValueError:
                pass

        # Occupancy / motion
        elif _matches(entity_id, OCCUPANCY_PATTERNS):
            reading["occupancy"] = 1 if state_val == "on" else 0
            device_id = entity_id.replace("binary_sensor.", "").replace(".", "_")
            await self.on_reading(device_id, reading)

        # HVAC climate entities
        elif _matches(entity_id, CLIMATE_PATTERNS):
            reading["hvac_mode"]       = state_val
            reading["target_temp"]     = float(attrs.get("temperature", 22))
            reading["current_temp"]    = float(attrs.get("current_temperature", 20))
            await self.on_reading("hvac", reading)

    async def _poll_fallback(self):
        """
        REST API polling fallback when WebSocket unavailable.
        Uses /api/states endpoint every poll_interval_s seconds.
        """
        log.info("🏠 HA: using REST polling fallback")
        token    = self.cfg.home_assistant.token
        base_url = self.cfg.home_assistant.url
        interval = self.cfg.home_assistant.poll_interval_s

        while self.running:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as sess:
                    async with sess.get(
                        f"{base_url}/api/states",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 200:
                            states = await resp.json()
                            for state in states:
                                await self._handle_event(
                                    {"data": {"entity_id": state["entity_id"],
                                              "new_state": state}}
                                )
            except ImportError:
                log.debug("HA poll: aiohttp not available")
            except Exception as e:
                log.error(f"HA poll error: {e}")
            await asyncio.sleep(interval)

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    def stop(self):
        self.running = False

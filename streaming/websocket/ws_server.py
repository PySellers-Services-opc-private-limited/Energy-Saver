"""
WebSocket Server — Live Energy Dashboard
==========================================
Real-time bidirectional WebSocket server that pushes
ML inference results to the browser dashboard.

Clients receive:
  • Live sensor readings (every second)
  • Anomaly alerts (instant push)
  • HVAC decisions
  • Energy forecasts
  • System stats

Server → Client messages:
  { "type": "reading",  "data": {...} }
  { "type": "event",    "data": {...} }
  { "type": "alert",    "data": {...} }
  { "type": "hvac",     "data": {...} }
  { "type": "stats",    "data": {...} }

Client → Server messages:
  { "cmd": "subscribe",   "device": "meter_01" }
  { "cmd": "unsubscribe", "device": "meter_01" }
  { "cmd": "get_history", "device": "meter_01", "minutes": 60 }

Deploy on AWS:
  EC2 / ECS + Application Load Balancer (sticky sessions)
  OR API Gateway WebSocket API
"""

import asyncio
import json
import logging
import time
import numpy as np
from typing import Set, Dict, Optional
from dataclasses import asdict

log = logging.getLogger("WebSocket")

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    HAS_WS = True
except ImportError:
    HAS_WS = False
    log.warning("websockets not installed — using simulator")

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from streaming.stream_engine import SensorReading, StreamEvent, StreamEngine


# ─────────────────────────────────────────────────────────────────
# CLIENT MANAGER
# ─────────────────────────────────────────────────────────────────

class ClientManager:
    """Tracks connected WebSocket clients and their subscriptions."""

    def __init__(self):
        self._clients:      Set = set()
        self._subscriptions: Dict[str, Set] = {}   # device_id → set of ws
        self._client_meta:  Dict = {}               # ws → {ip, connected_at, subs}

    def add(self, ws, ip: str):
        self._clients.add(ws)
        self._client_meta[ws] = {
            "ip": ip, "connected_at": time.time(),
            "messages_sent": 0, "subscriptions": set()
        }
        log.info(f"Client connected: {ip} (total: {len(self._clients)})")

    def remove(self, ws):
        self._clients.discard(ws)
        meta = self._client_meta.pop(ws, {})
        for dev in meta.get("subscriptions", set()):
            self._subscriptions.get(dev, set()).discard(ws)
        log.info(f"Client disconnected: {meta.get('ip')} "
                 f"(total: {len(self._clients)})")

    def subscribe(self, ws, device_id: str):
        if device_id not in self._subscriptions:
            self._subscriptions[device_id] = set()
        self._subscriptions[device_id].add(ws)
        if ws in self._client_meta:
            self._client_meta[ws]["subscriptions"].add(device_id)

    def get_subscribers(self, device_id: str) -> Set:
        return self._subscriptions.get(device_id, set()).copy()

    @property
    def all_clients(self) -> Set:
        return self._clients.copy()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def increment_sent(self, ws):
        if ws in self._client_meta:
            self._client_meta[ws]["messages_sent"] += 1

    def get_stats(self):
        return {
            "connected_clients":   self.client_count,
            "subscribed_devices":  len(self._subscriptions),
            "client_details": [
                {"ip": m["ip"],
                 "connected_sec": round(time.time() - m["connected_at"]),
                 "messages_sent": m["messages_sent"],
                 "subscriptions": list(m["subscriptions"])}
                for m in self._client_meta.values()
            ]
        }


# ─────────────────────────────────────────────────────────────────
# WEBSOCKET SERVER
# ─────────────────────────────────────────────────────────────────

class EnergyWebSocketServer:
    """
    WebSocket server that broadcasts ML results to dashboard clients.
    Integrates with StreamEngine via handler registration.
    """

    def __init__(self, config: dict, engine: StreamEngine):
        self.host     = config.get("host",     "0.0.0.0")
        self.port     = config.get("port",     8765)
        self.engine   = engine
        self.clients  = ClientManager()
        self._history: Dict[str, list] = {}   # device → last 1h readings
        self._max_history = 3600              # 1 hour at 1Hz
        self._stats   = {"broadcasts": 0, "errors": 0}

        # Register engine handlers
        engine.register_handler("on_event", self._broadcast_event)
        engine.register_handler("on_alert", self._broadcast_alert)
        engine.register_handler("on_hvac",  self._broadcast_hvac)

    # ── Broadcast Methods ────────────────────────────────────────

    async def _broadcast(self, message: dict, target_set: Optional[Set] = None):
        """Send JSON message to a set of clients (or all)."""
        clients = target_set or self.clients.all_clients
        if not clients:
            return

        payload = json.dumps(message)
        dead    = set()

        await asyncio.gather(*[
            self._send_one(ws, payload, dead)
            for ws in clients
        ], return_exceptions=True)

        for ws in dead:
            self.clients.remove(ws)

    async def _send_one(self, ws, payload: str, dead: set):
        try:
            await ws.send(payload)
            self.clients.increment_sent(ws)
            self._stats["broadcasts"] += 1
        except Exception:
            dead.add(ws)

    async def _broadcast_event(self, event: StreamEvent):
        """Push full ML inference result to all subscribers."""
        dev_id = event.reading.device_id

        # Store in history
        if dev_id not in self._history:
            self._history[dev_id] = []
        self._history[dev_id].append({
            "ts":     event.reading.timestamp,
            "kwh":    event.reading.consumption_kwh,
            "score":  event.anomaly_score,
            "occ":    event.occupancy_prob,
            "hvac":   event.hvac_action,
            "alert":  event.alert_level,
        })
        if len(self._history[dev_id]) > self._max_history:
            self._history[dev_id].pop(0)

        msg = {
            "type": "event",
            "data": {
                "device_id":      dev_id,
                "timestamp":      event.reading.timestamp,
                "kwh":            round(event.reading.consumption_kwh, 3),
                "temperature":    event.reading.temperature,
                "humidity":       event.reading.humidity,
                "co2":            event.reading.co2,
                "anomaly_score":  round(event.anomaly_score, 3),
                "anomaly_alert":  event.anomaly_alert,
                "predicted_kwh":  round(event.predicted_kwh_1h, 3),
                "occupancy_prob": round(event.occupancy_prob, 3),
                "hvac_action":    event.hvac_action,
                "hvac_temp":      event.hvac_target_temp,
                "alert_level":    event.alert_level,
                "latency_ms":     round(event.processing_ms, 2),
                "zone":           event.reading.building_zone,
            }
        }

        # Broadcast to device subscribers + all-device subscribers
        targets = (self.clients.get_subscribers(dev_id) |
                   self.clients.get_subscribers("*"))
        await self._broadcast(msg, targets or self.clients.all_clients)

    async def _broadcast_alert(self, event: StreamEvent):
        """Push high-priority anomaly alert to ALL clients."""
        msg = {
            "type": "alert",
            "priority": "high",
            "data": {
                "device_id":    event.reading.device_id,
                "timestamp":    event.reading.timestamp,
                "alert_level":  event.alert_level,
                "anomaly_score": round(event.anomaly_score, 3),
                "kwh":          round(event.reading.consumption_kwh, 3),
                "zone":         event.reading.building_zone,
                "message":      f"⚠️ Anomaly detected on {event.reading.device_id} "
                                f"(score={event.anomaly_score:.2f})",
            }
        }
        await self._broadcast(msg)   # All clients get alerts

    async def _broadcast_hvac(self, event: StreamEvent):
        """Push HVAC decision to subscribed clients."""
        msg = {
            "type": "hvac",
            "data": {
                "device_id":   event.reading.device_id,
                "zone":        event.reading.building_zone,
                "action":      event.hvac_action,
                "target_temp": event.hvac_target_temp,
                "reason":      f"Occupancy={event.occupancy_prob:.0%}, "
                               f"Alert={event.alert_level}",
                "timestamp":   event.reading.timestamp,
            }
        }
        await self._broadcast(msg)

    # ── Client Connection Handler ────────────────────────────────

    async def _handle_client(self, ws, path="/"):
        ip = ws.remote_address[0] if ws.remote_address else "unknown"
        self.clients.add(ws, ip)

        # Send welcome + current stats
        await ws.send(json.dumps({
            "type": "welcome",
            "data": {
                "server": "Energy Saver AI Live Stream",
                "version": "3.0",
                "commands": ["subscribe", "unsubscribe", "get_history", "get_stats"],
            }
        }))

        try:
            async for raw_msg in ws:
                await self._handle_client_message(ws, raw_msg)
        except Exception as e:
            log.debug(f"Client {ip} disconnected: {e}")
        finally:
            self.clients.remove(ws)

    async def _handle_client_message(self, ws, raw: str):
        """Process incoming message from dashboard client."""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            await ws.send(json.dumps({"type": "error", "msg": "Invalid JSON"}))
            return

        cmd = msg.get("cmd")

        if cmd == "subscribe":
            device = msg.get("device", "*")
            self.clients.subscribe(ws, device)
            await ws.send(json.dumps({
                "type": "subscribed", "device": device
            }))

        elif cmd == "unsubscribe":
            device = msg.get("device", "*")
            self.clients.get_subscribers(device).discard(ws)
            await ws.send(json.dumps({"type": "unsubscribed", "device": device}))

        elif cmd == "get_history":
            device  = msg.get("device", "")
            minutes = int(msg.get("minutes", 60))
            cutoff  = time.time() - minutes * 60
            history = [r for r in self._history.get(device, [])
                       if r["ts"] >= cutoff]
            await ws.send(json.dumps({
                "type":   "history",
                "device": device,
                "data":   history[-500:],   # Cap at 500 points
            }))

        elif cmd == "get_stats":
            await ws.send(json.dumps({
                "type": "stats",
                "data": {
                    "engine":    self.engine.get_stats(),
                    "websocket": self.clients.get_stats(),
                    "server":    self._stats,
                }
            }))

    # ── Start Server ─────────────────────────────────────────────

    async def start(self):
        if not HAS_WS:
            log.info(f"WebSocket simulator: ws://{self.host}:{self.port}")
            return

        server = await websockets.serve(
            self._handle_client,
            self.host, self.port,
            ping_interval = 30,
            ping_timeout  = 10,
            max_size      = 1_048_576,
        )
        log.info(f"✅ WebSocket server listening on ws://{self.host}:{self.port}")
        return server

    # ── Periodic Stats Broadcast ─────────────────────────────────

    async def broadcast_stats_loop(self, interval_sec: float = 10.0):
        """Push engine + WS stats to all clients every N seconds."""
        while True:
            await asyncio.sleep(interval_sec)
            if self.clients.client_count > 0:
                await self._broadcast({
                    "type": "stats",
                    "data": {
                        "engine":    self.engine.get_stats(),
                        "websocket": self.clients.get_stats(),
                        "ts":        time.time(),
                    }
                })


# ─────────────────────────────────────────────────────────────────
# JAVASCRIPT CLIENT EXAMPLE
# ─────────────────────────────────────────────────────────────────

JS_CLIENT_EXAMPLE = '''
// Browser WebSocket client example for the live dashboard
const ws = new WebSocket("wss://your-server.com:8765");

ws.onopen = () => {
  console.log("Connected to Energy Saver AI Live Stream");

  // Subscribe to all devices
  ws.send(JSON.stringify({ cmd: "subscribe", device: "*" }));

  // Or subscribe to specific device
  ws.send(JSON.stringify({ cmd: "subscribe", device: "meter_living" }));

  // Get last 60 minutes of history
  ws.send(JSON.stringify({ cmd: "get_history", device: "meter_living", minutes: 60 }));
};

ws.onmessage = (msg) => {
  const payload = JSON.parse(msg.data);

  if (payload.type === "event") {
    updateDashboard(payload.data);            // Update charts
  }
  else if (payload.type === "alert") {
    showAlert(payload.data);                  // Anomaly popup
  }
  else if (payload.type === "hvac") {
    updateHVACStatus(payload.data);           // HVAC panel
  }
  else if (payload.type === "stats") {
    updateSystemStats(payload.data);          // System health
  }
  else if (payload.type === "history") {
    initializeChart(payload.device, payload.data); // Historical chart
  }
};

ws.onerror = (err) => console.error("WS Error:", err);
ws.onclose = () => setTimeout(() => location.reload(), 3000); // Auto-reconnect
'''


if __name__ == "__main__":
    async def demo():
        from streaming.stream_engine import StreamEngine
        from streaming.mqtt.mqtt_client import MQTTClient

        engine = StreamEngine({"window_size": 10})
        await engine.start()

        ws_server = EnergyWebSocketServer({"port": 8765}, engine)
        await ws_server.start()

        # Simulate incoming data
        mqtt = MQTTClient({})
        print("🚀 WebSocket server running. Connect at ws://localhost:8765")
        print("   Run for 5 seconds with simulated data...")
        try:
            await asyncio.wait_for(mqtt.run_simulator(engine, hz=2.0), timeout=5.0)
        except asyncio.TimeoutError:
            pass

        stats = ws_server.clients.get_stats()
        print(f"\n📊 WebSocket stats: {stats}")
        print(f"📊 Broadcasts: {ws_server._stats['broadcasts']}")

    asyncio.run(demo())

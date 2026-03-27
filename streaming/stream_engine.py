"""
Live Streaming Core Engine — Energy Saver AI
==============================================
Central hub that connects ALL streaming protocols:
  • MQTT        ← IoT sensors (smart plugs, meters, thermostats)
  • WebSocket   ← Real-time browser dashboard
  • Kafka       ← High-volume cloud event bus
  • REST API    ← Polling fallback + external integrations
  • Home Assistant ← Smart home platform bridge

Data flow:
  [IoT Sensors]
       │  MQTT
       ▼
  [Stream Engine] ──► Kafka topic ──► [ML Inference]
       │                                    │
       │  WebSocket                         ▼
       ▼                            [Anomaly Alerts]
  [Live Dashboard]                  [HVAC Decisions]
                                    [Fine-tuning Buffer]
"""

import asyncio
import json
import logging
import time
import numpy as np
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Optional, Callable, Dict, List
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("StreamEngine")


# ─────────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────────

@dataclass
class SensorReading:
    """Unified sensor reading from any source."""
    device_id:       str
    timestamp:       float
    consumption_kwh: float
    temperature:     float  = 20.0
    humidity:        float  = 50.0
    co2:             float  = 400.0
    light:           float  = 100.0
    voltage:         float  = 230.0
    current:         float  = 0.0
    source:          str    = "unknown"   # mqtt / websocket / kafka / rest / ha
    building_zone:   str    = "main"

    def to_dict(self):
        return asdict(self)

    def to_feature_vector(self):
        """Convert to numpy array for ML model input."""
        hour = datetime.fromtimestamp(self.timestamp).hour
        return np.array([
            self.consumption_kwh,
            self.temperature,
            self.humidity,
            self.co2,
            self.light,
            np.sin(2 * np.pi * hour / 24),
            np.cos(2 * np.pi * hour / 24),
        ], dtype=np.float32)


@dataclass
class StreamEvent:
    """Enriched event after ML inference."""
    reading:          SensorReading
    anomaly_score:    float  = 0.0
    anomaly_alert:    bool   = False
    predicted_kwh_1h: float  = 0.0
    occupancy_prob:   float  = 0.0
    hvac_action:      str    = "COMFORT"
    hvac_target_temp: float  = 22.0
    processing_ms:    float  = 0.0
    alert_level:      str    = "OK"      # OK / WARN / CRITICAL


# ─────────────────────────────────────────────────────────────────
# SLIDING WINDOW BUFFER
# ─────────────────────────────────────────────────────────────────

class StreamBuffer:
    """
    Thread-safe sliding window buffer for storing recent readings.
    Used to feed ML models that need historical context (LSTM lookback).
    """
    def __init__(self, device_id: str, window_size: int = 48):
        self.device_id   = device_id
        self.window_size = window_size
        self._buffer     = deque(maxlen=window_size)
        self._lock       = asyncio.Lock()
        self.total_seen  = 0

    async def push(self, reading: SensorReading):
        async with self._lock:
            self._buffer.append(reading)
            self.total_seen += 1

    async def get_window(self) -> Optional[np.ndarray]:
        """Returns (window_size, n_features) array if buffer is full."""
        async with self._lock:
            if len(self._buffer) < self.window_size:
                return None
            features = np.stack([r.to_feature_vector() for r in self._buffer])
            return features.astype(np.float32)

    @property
    def fill_pct(self):
        return len(self._buffer) / self.window_size * 100


# ─────────────────────────────────────────────────────────────────
# STREAM ENGINE
# ─────────────────────────────────────────────────────────────────

class StreamEngine:
    """
    Central coordinator for all live streaming protocols.
    Manages buffers, routing, and ML inference dispatch.
    """

    def __init__(self, config: dict):
        self.config    = config
        self.buffers:  Dict[str, StreamBuffer] = {}
        self.handlers: Dict[str, List[Callable]] = {
            "on_reading":  [],
            "on_event":    [],
            "on_alert":    [],
            "on_hvac":     [],
        }
        self._running  = False
        self._stats    = {
            "total_readings": 0, "total_alerts": 0,
            "total_hvac_actions": 0, "avg_latency_ms": 0.0,
            "sources": {}
        }
        log.info("StreamEngine initialized")

    def register_handler(self, event_type: str, fn: Callable):
        """Register a callback for a stream event type."""
        if event_type in self.handlers:
            self.handlers[event_type].append(fn)
            log.info(f"Registered handler '{fn.__name__}' for '{event_type}'")

    def get_or_create_buffer(self, device_id: str) -> StreamBuffer:
        if device_id not in self.buffers:
            self.buffers[device_id] = StreamBuffer(
                device_id,
                window_size=self.config.get("window_size", 48)
            )
        return self.buffers[device_id]

    async def ingest(self, reading: SensorReading):
        """Main ingestion point for all protocols."""
        t0 = time.monotonic()

        # Track per-source stats
        src = reading.source
        self.config.setdefault("sources", {})
        self._stats["sources"][src] = self._stats["sources"].get(src, 0) + 1
        self._stats["total_readings"] += 1

        # Push to buffer
        buf = self.get_or_create_buffer(reading.device_id)
        await buf.push(reading)

        # Fire on_reading handlers
        for fn in self.handlers["on_reading"]:
            try:
                await fn(reading)
            except Exception as e:
                log.warning(f"on_reading handler error: {e}")

        # Run ML inference once buffer is warm
        window = await buf.get_window()
        if window is not None:
            event = await self._run_inference(reading, window)
            event.processing_ms = (time.monotonic() - t0) * 1000

            # Update rolling avg latency
            n = self._stats["total_readings"]
            self._stats["avg_latency_ms"] = (
                self._stats["avg_latency_ms"] * (n-1) + event.processing_ms
            ) / n

            # Fire event handlers
            for fn in self.handlers["on_event"]:
                await fn(event)

            if event.anomaly_alert:
                self._stats["total_alerts"] += 1
                for fn in self.handlers["on_alert"]:
                    await fn(event)

            if event.hvac_action != "NONE":
                self._stats["total_hvac_actions"] += 1
                for fn in self.handlers["on_hvac"]:
                    await fn(event)

    async def _run_inference(self, reading: SensorReading,
                              window: np.ndarray) -> StreamEvent:
        """Stub: replaced by inference/stream_inference.py in production."""
        # Anomaly: simple threshold on consumption spike
        recent_mean = np.mean(window[-12:, 0])
        recent_std  = np.std(window[-12:, 0]) + 0.01
        z_score     = abs(reading.consumption_kwh - recent_mean) / recent_std
        anomaly     = bool(z_score > 3.0)

        # Occupancy: simple CO2 heuristic
        occ_prob = min(1.0, max(0.0, (reading.co2 - 400) / 400))

        # HVAC decision
        hour = datetime.fromtimestamp(reading.timestamp).hour
        if occ_prob < 0.2:
            hvac_action, target = "ECO", 18.0
        elif 17 <= hour <= 20:
            hvac_action, target = "DEMAND_RESPONSE", 21.0
        else:
            hvac_action, target = "COMFORT", 22.0

        alert_level = "CRITICAL" if z_score > 5 else ("WARN" if anomaly else "OK")

        return StreamEvent(
            reading=reading,
            anomaly_score=float(z_score),
            anomaly_alert=anomaly,
            predicted_kwh_1h=float(recent_mean),
            occupancy_prob=float(occ_prob),
            hvac_action=hvac_action,
            hvac_target_temp=target,
            alert_level=alert_level,
        )

    def get_stats(self) -> dict:
        return {
            **self._stats,
            "active_devices": len(self.buffers),
            "buffer_fill": {
                dev: f"{buf.fill_pct:.0f}%"
                for dev, buf in self.buffers.items()
            }
        }

    async def start(self):
        self._running = True
        log.info("StreamEngine started ✅")

    async def stop(self):
        self._running = False
        log.info("StreamEngine stopped")


if __name__ == "__main__":
    async def demo():
        engine = StreamEngine({"window_size": 12})

        async def on_alert(event):
            print(f"🚨 ALERT [{event.alert_level}] "
                  f"device={event.reading.device_id} "
                  f"score={event.anomaly_score:.2f} "
                  f"kwh={event.reading.consumption_kwh:.2f}")

        async def on_hvac(event):
            print(f"❄️  HVAC → {event.hvac_action} "
                  f"target={event.hvac_target_temp}°C")

        engine.register_handler("on_alert", on_alert)
        engine.register_handler("on_hvac",  on_hvac)
        await engine.start()

        print("\n📡 Simulating 20 live sensor readings...\n")
        for i in range(20):
            reading = SensorReading(
                device_id="sensor_01",
                timestamp=time.time(),
                consumption_kwh=2.0 + np.random.normal(0, 0.2) + (5.0 if i == 17 else 0),
                temperature=21 + np.random.normal(0, 0.5),
                humidity=50 + np.random.normal(0, 2),
                co2=500 + np.random.normal(0, 30),
                source="mqtt"
            )
            await engine.ingest(reading)
            await asyncio.sleep(0.05)

        print("\n📊 Engine Stats:")
        import pprint; pprint.pprint(engine.get_stats())

    asyncio.run(demo())

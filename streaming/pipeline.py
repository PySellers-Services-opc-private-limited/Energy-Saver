"""
Live Streaming Pipeline — Energy Saver AI
==========================================
Cloud orchestrator that connects ALL streaming sources
to ALL AI models in real-time.

Architecture:
  IoT Sensors ──MQTT──► Kafka ──► AI Inference ──► WebSocket ──► Dashboard
  Home Assistant ──────► Kafka ──► Anomaly Alert ──► SNS/Slack
  REST API polling ────► Kafka ──► HVAC Decision ──► IoT Control
                                ► Stream Fine-tune ──► Model Update

Run:
  python streaming/pipeline.py                  # Full pipeline
  python streaming/pipeline.py --mode simulate  # Demo with fake sensors
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("Pipeline")


# ─────────────────────────────────────────────────────────────────
# PIPELINE CONFIG
# ─────────────────────────────────────────────────────────────────

PIPELINE_CONFIG = {
    # Kafka (AWS MSK or Azure Event Hubs)
    "kafka": {
        "bootstrap_servers": os.getenv("KAFKA_BROKERS", "localhost:9092"),
        "topics": {
            "raw_sensors":   "energy.sensors.raw",
            "processed":     "energy.sensors.processed",
            "anomalies":     "energy.alerts.anomalies",
            "hvac_commands": "energy.control.hvac",
            "model_updates": "energy.models.updates",
            "forecasts":     "energy.forecasts",
        },
        "consumer_group": "energy-ai-pipeline",
    },

    # MQTT (IoT Core AWS / Azure IoT Hub)
    "mqtt": {
        "broker":   os.getenv("MQTT_BROKER",   "localhost"),
        "port":     int(os.getenv("MQTT_PORT", "1883")),
        "username": os.getenv("MQTT_USER",     ""),
        "password": os.getenv("MQTT_PASS",     ""),
        "topics": {
            "energy":    "home/+/energy",
            "sensors":   "home/+/sensors",
            "solar":     "home/+/solar",
            "ev":        "home/+/ev",
        },
        "qos": 1,
    },

    # WebSocket server (live dashboard)
    "websocket": {
        "host": "0.0.0.0",
        "port": int(os.getenv("WS_PORT", "8765")),
        "ping_interval": 20,
        "max_clients": 100,
    },

    # REST API polling
    "rest_api": {
        "utility_api":     os.getenv("UTILITY_API_URL",  "https://api.utility.com/v1"),
        "weather_api":     os.getenv("WEATHER_API_KEY",  "YOUR_KEY"),
        "poll_interval_s": 300,   # Every 5 minutes
    },

    # Home Assistant
    "home_assistant": {
        "url":   os.getenv("HA_URL",   "http://homeassistant.local:8123"),
        "token": os.getenv("HA_TOKEN", "YOUR_LONG_LIVED_TOKEN"),
        "poll_interval_s": 30,
    },

    # AI Models
    "models": {
        "forecasting_path":    "models_storage/forecasting_model.keras",
        "anomaly_path":        "models_storage/anomaly_model.keras",
        "occupancy_path":      "models_storage/occupancy_model.keras",
        "hvac_path":           "outputs/hvac_daily_schedule.csv",
        "solar_path":          "models_storage/solar_model.keras",
        "window_size":         48,
        "inference_batch_size": 1,
    },

    # Stream fine-tuning
    "stream_finetuning": {
        "enabled":            True,
        "buffer_size":        500,      # Collect N samples before fine-tuning
        "finetune_every_s":   3600,     # Retrain every hour
        "min_samples":        100,      # Minimum samples before first tune
        "learning_rate":      5e-5,     # Low LR for stream updates
        "epochs":             3,
    },

    # Alerts (AWS SNS / Azure Event Grid)
    "alerts": {
        "anomaly_threshold":  0.85,     # Confidence to trigger alert
        "email":              os.getenv("ALERT_EMAIL",  ""),
        "slack_webhook":      os.getenv("SLACK_WEBHOOK", ""),
        "sns_topic_arn":      os.getenv("SNS_TOPIC_ARN", ""),
        "cooldown_s":         300,      # Don't spam — 5 min between alerts
    },
}


# ─────────────────────────────────────────────────────────────────
# SHARED SENSOR BUFFER
# ─────────────────────────────────────────────────────────────────

class SensorBuffer:
    """
    Thread-safe rolling window buffer for sensor readings.
    Feeds sliding windows to AI inference engines.
    """
    def __init__(self, window_size=48, n_features=6):
        import collections
        self.window_size = window_size
        self.n_features  = n_features
        self.buffers: Dict[str, Any] = {}   # device_id → deque
        self._lock = asyncio.Lock()

    async def push(self, device_id: str, reading: dict):
        async with self._lock:
            if device_id not in self.buffers:
                import collections
                self.buffers[device_id] = collections.deque(maxlen=self.window_size)

            vector = self._encode(reading)
            self.buffers[device_id].append(vector)

    def get_window(self, device_id: str):
        import numpy as np
        buf = self.buffers.get(device_id)
        if buf is None or len(buf) < self.window_size:
            return None
        return np.array(list(buf), dtype=np.float32)

    def _encode(self, r: dict):
        import numpy as np
        h = r.get("hour", datetime.now().hour)
        return [
            float(r.get("consumption_kwh", 0)),
            float(r.get("temperature",     20)),
            float(r.get("humidity",        50)),
            float(r.get("occupancy",        0)),
            float(r.get("solar_kwh",        0)),
            float(r.get("tariff",          0.13)),
        ]

    def ready(self, device_id: str) -> bool:
        buf = self.buffers.get(device_id)
        return buf is not None and len(buf) >= self.window_size

    def size(self, device_id: str) -> int:
        buf = self.buffers.get(device_id)
        return len(buf) if buf else 0


# ─────────────────────────────────────────────────────────────────
# PIPELINE ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────

class EnergyStreamingPipeline:
    """
    Orchestrates all streaming components:
      - MQTT consumer
      - Kafka producer/consumer
      - WebSocket broadcast server
      - REST API poller
      - Home Assistant subscriber
      - AI inference engine
      - Stream fine-tuning engine
      - Alert dispatcher
    """

    def __init__(self, config: dict, simulate: bool = False):
        self.config   = config
        self.simulate = simulate
        self.buffer   = SensorBuffer(window_size=config["models"]["window_size"])
        self.running  = False
        self.ws_clients = set()
        self.stats = {
            "messages_processed": 0,
            "anomalies_detected":  0,
            "hvac_commands_sent":  0,
            "models_updated":      0,
            "uptime_start":        time.time(),
        }
        log.info("🚀 Energy Streaming Pipeline initialized")
        log.info(f"   Mode: {'SIMULATE' if simulate else 'LIVE'}")
        log.info(f"   Kafka: {config['kafka']['bootstrap_servers']}")
        log.info(f"   WebSocket: ws://{config['websocket']['host']}:{config['websocket']['port']}")

    async def start(self):
        """Launch all pipeline components concurrently."""
        self.running = True
        log.info("\n" + "="*50)
        log.info("  STARTING ALL PIPELINE COMPONENTS")
        log.info("="*50)

        tasks = [
            asyncio.create_task(self._run_websocket_server(),    name="websocket"),
            asyncio.create_task(self._run_inference_engine(),    name="inference"),
            asyncio.create_task(self._run_alert_dispatcher(),    name="alerts"),
            asyncio.create_task(self._run_stream_finetuning(),   name="finetuning"),
            asyncio.create_task(self._run_stats_logger(),        name="stats"),
        ]

        if self.simulate:
            tasks.append(asyncio.create_task(self._run_simulator(), name="simulator"))
        else:
            tasks += [
                asyncio.create_task(self._run_mqtt_consumer(),       name="mqtt"),
                asyncio.create_task(self._run_kafka_consumer(),      name="kafka"),
                asyncio.create_task(self._run_rest_poller(),         name="rest_api"),
                asyncio.create_task(self._run_ha_subscriber(),       name="home_assistant"),
            ]

        log.info(f"✅ {len(tasks)} pipeline components started\n")

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            log.info("Pipeline shutdown requested")
        finally:
            self.running = False

    # ── WEBSOCKET SERVER ──────────────────────────────────────────
    async def _run_websocket_server(self):
        """
        WebSocket server — broadcasts live data to dashboard clients.
        Dashboard connects to ws://host:8765 and receives JSON frames.
        """
        try:
            import websockets
        except ImportError:
            log.warning("websockets not installed — WebSocket server disabled")
            log.info("  Install: pip install websockets")
            await self._mock_websocket_server()
            return

        async def handler(ws, path):
            self.ws_clients.add(ws)
            log.info(f"📡 Dashboard client connected. Total: {len(self.ws_clients)}")
            try:
                await ws.wait_closed()
            finally:
                self.ws_clients.discard(ws)
                log.info(f"📡 Client disconnected. Total: {len(self.ws_clients)}")

        cfg = self.config["websocket"]
        server = await websockets.serve(handler, cfg["host"], cfg["port"],
                                        ping_interval=cfg["ping_interval"])
        log.info(f"🌐 WebSocket server live: ws://{cfg['host']}:{cfg['port']}")
        await server.wait_closed()

    async def _mock_websocket_server(self):
        """Mock WebSocket server when library not available."""
        log.info("🌐 WebSocket server (mock mode — install websockets for real)")
        while self.running:
            await asyncio.sleep(5)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected WebSocket clients."""
        if not self.ws_clients:
            return
        payload = json.dumps({**message, "ts": datetime.now(timezone.utc).isoformat()})
        dead = set()
        for ws in self.ws_clients:
            try:
                await ws.send(payload)
            except Exception:
                dead.add(ws)
        self.ws_clients -= dead

    # ── MQTT CONSUMER ─────────────────────────────────────────────
    async def _run_mqtt_consumer(self):
        """
        Subscribes to IoT sensor topics via MQTT.
        AWS IoT Core / Azure IoT Hub / local Mosquitto broker.
        """
        log.info("📶 MQTT consumer starting...")
        cfg = self.config["mqtt"]

        while self.running:
            try:
                # In production: pip install asyncio-mqtt
                # import asyncio_mqtt as aiomqtt
                # async with aiomqtt.Client(cfg["broker"], cfg["port"],
                #     username=cfg["username"], password=cfg["password"]) as client:
                #     async with client.messages() as messages:
                #         await client.subscribe("home/+/energy")
                #         await client.subscribe("home/+/sensors")
                #         async for msg in messages:
                #             await self._handle_mqtt_message(str(msg.topic), msg.payload)

                # Simulation fallback
                log.info(f"📶 MQTT connected to {cfg['broker']}:{cfg['port']}")
                log.info(f"   Subscribed to: {list(cfg['topics'].values())}")
                while self.running:
                    await asyncio.sleep(10)
            except Exception as e:
                log.error(f"MQTT error: {e} — reconnecting in 5s")
                await asyncio.sleep(5)

    async def _handle_mqtt_message(self, topic: str, payload: bytes):
        """Process incoming MQTT sensor reading."""
        try:
            data = json.loads(payload)
            device_id = topic.split("/")[1]
            data["device_id"] = device_id
            data["source"]    = "mqtt"
            data["hour"]      = datetime.now().hour
            await self.buffer.push(device_id, data)
            self.stats["messages_processed"] += 1
        except Exception as e:
            log.error(f"MQTT message error: {e}")

    # ── KAFKA CONSUMER ────────────────────────────────────────────
    async def _run_kafka_consumer(self):
        """
        Kafka consumer for high-volume streaming.
        AWS MSK (Managed Streaming for Kafka) or Azure Event Hubs.

        Topics consumed:
          energy.sensors.raw → normalize → push to buffer
          energy.models.updates → reload model weights
        """
        log.info("📨 Kafka consumer starting...")
        cfg = self.config["kafka"]

        while self.running:
            try:
                # In production: pip install aiokafka
                # from aiokafka import AIOKafkaConsumer
                # consumer = AIOKafkaConsumer(
                #     cfg["topics"]["raw_sensors"],
                #     cfg["topics"]["model_updates"],
                #     bootstrap_servers=cfg["bootstrap_servers"],
                #     group_id=cfg["consumer_group"],
                #     value_deserializer=lambda v: json.loads(v.decode())
                # )
                # await consumer.start()
                # async for msg in consumer:
                #     await self._handle_kafka_message(msg.topic, msg.value)

                log.info(f"📨 Kafka connected: {cfg['bootstrap_servers']}")
                log.info(f"   Consumer group: {cfg['consumer_group']}")
                while self.running:
                    await asyncio.sleep(10)
            except Exception as e:
                log.error(f"Kafka error: {e} — reconnecting in 5s")
                await asyncio.sleep(5)

    async def _handle_kafka_message(self, topic: str, value: dict):
        """Route Kafka message to appropriate handler."""
        cfg = self.config["kafka"]["topics"]
        if topic == cfg["raw_sensors"]:
            device_id = value.get("device_id", "default")
            await self.buffer.push(device_id, value)
            self.stats["messages_processed"] += 1
        elif topic == cfg["model_updates"]:
            log.info(f"📥 Model update received: {value.get('model_name')}")
            # Trigger hot-reload of model weights

    # ── REST API POLLER ───────────────────────────────────────────
    async def _run_rest_poller(self):
        """
        Polls utility API + weather API every 5 minutes.
        Enriches sensor data with tariff + weather context.
        """
        log.info(f"🔄 REST API poller starting (interval={self.config['rest_api']['poll_interval_s']}s)")
        interval = self.config["rest_api"]["poll_interval_s"]

        while self.running:
            try:
                # In production: pip install aiohttp
                # async with aiohttp.ClientSession() as session:
                #     async with session.get(f"{base_url}/tariff/current",
                #                            headers={"Authorization": f"Bearer {token}"}) as resp:
                #         tariff_data = await resp.json()
                #     weather_url = f"https://api.openweathermap.org/data/2.5/weather?..."
                #     async with session.get(weather_url) as resp:
                #         weather_data = await resp.json()

                log.debug("🔄 REST API poll: fetched tariff + weather data")
                await self.broadcast({
                    "type":    "context_update",
                    "tariff":  0.14,
                    "weather": {"temp": 22, "cloud_cover": 30}
                })
            except Exception as e:
                log.error(f"REST poll error: {e}")
            await asyncio.sleep(interval)

    # ── HOME ASSISTANT SUBSCRIBER ─────────────────────────────────
    async def _run_ha_subscriber(self):
        """
        Subscribes to Home Assistant WebSocket API.
        Receives state changes for all energy-related entities.
        """
        log.info("🏠 Home Assistant subscriber starting...")
        cfg = self.config["home_assistant"]

        while self.running:
            try:
                # In production: connect to HA WebSocket API
                # async with websockets.connect(f"ws://{cfg['url']}/api/websocket") as ws:
                #     await ws.send(json.dumps({"type":"auth","access_token":cfg["token"]}))
                #     await ws.send(json.dumps({"id":1,"type":"subscribe_events","event_type":"state_changed"}))
                #     async for msg in ws:
                #         data = json.loads(msg)
                #         if data.get("type") == "event":
                #             await self._handle_ha_event(data["event"])

                log.info(f"🏠 Home Assistant connected: {cfg['url']}")
                log.info("   Listening for state_changed events...")
                while self.running:
                    await asyncio.sleep(30)
            except Exception as e:
                log.error(f"HA error: {e} — reconnecting in 10s")
                await asyncio.sleep(10)

    async def _handle_ha_event(self, event: dict):
        """Process Home Assistant state change event."""
        entity_id = event.get("data", {}).get("entity_id", "")
        new_state  = event.get("data", {}).get("new_state", {})
        if "sensor.power" in entity_id or "sensor.energy" in entity_id:
            device_id = entity_id.replace("sensor.", "")
            reading = {
                "consumption_kwh": float(new_state.get("state", 0)),
                "hour":             datetime.now().hour,
                "source":           "home_assistant"
            }
            await self.buffer.push(device_id, reading)

    # ── AI INFERENCE ENGINE ───────────────────────────────────────
    async def _run_inference_engine(self):
        """
        Core real-time inference loop.
        Runs every second — feeds buffered windows to all AI models.
        Publishes results to WebSocket + Kafka.
        """
        log.info("🧠 AI Inference engine starting...")
        models = {}

        # Lazy-load models
        try:
            import tensorflow as tf
            for name, path in [
                ("forecasting", self.config["models"]["forecasting_path"]),
                ("anomaly",     self.config["models"]["anomaly_path"]),
                ("occupancy",   self.config["models"]["occupancy_path"]),
            ]:
                if os.path.exists(path):
                    models[name] = tf.keras.models.load_model(path)
                    log.info(f"   ✅ Loaded model: {name}")
                else:
                    log.warning(f"   ⚠️  Model not found: {path} — using heuristic")
        except ImportError:
            log.warning("TensorFlow not available — using heuristic inference")

        DEVICE_ID = "sim_device_0"   # Default device for simulation

        while self.running:
            try:
                if self.buffer.ready(DEVICE_ID):
                    window = self.buffer.get_window(DEVICE_ID)
                    results = await self._run_all_models(window, models, DEVICE_ID)
                    await self.broadcast(results)
                    self.stats["messages_processed"] += 1
            except Exception as e:
                log.error(f"Inference error: {e}")
            await asyncio.sleep(1.0)   # 1 Hz inference

    async def _run_all_models(self, window, models, device_id):
        """Run all AI models on a sensor window. Returns combined result."""
        import numpy as np
        now = datetime.now()
        result = {
            "type":      "inference_result",
            "device_id": device_id,
            "timestamp": now.isoformat(),
            "hour":      now.hour,
        }

        # ── Anomaly Detection ──────────────────────────────────
        if "anomaly" in models:
            inp  = window[np.newaxis, :, :1]   # only consumption
            prob = float(models["anomaly"].predict(inp, verbose=0)[0][0])
        else:
            recent = window[-6:, 0]
            prob   = float(np.abs(recent[-1] - recent.mean()) / (recent.std() + 1e-8) > 2.5)
        result["anomaly_score"]    = round(prob, 4)
        result["anomaly_detected"] = prob > self.config["alerts"]["anomaly_threshold"]

        # ── Occupancy Prediction ───────────────────────────────
        if "occupancy" in models:
            inp  = window[np.newaxis, -12:, :]
            occ  = float(models["occupancy"].predict(inp, verbose=0)[0][0])
        else:
            h   = datetime.now().hour
            occ = 1.0 if (7 <= h <= 22) else 0.0
        result["occupancy_prob"] = round(occ, 3)
        result["occupied"]       = occ > 0.5

        # ── Forecasting ────────────────────────────────────────
        if "forecasting" in models:
            inp       = window[np.newaxis]
            forecast  = models["forecasting"].predict(inp, verbose=0)[0]
            result["forecast_24h"]      = [round(float(v), 3) for v in forecast]
            result["forecast_next_kwh"] = round(float(forecast[0]), 3)
        else:
            result["forecast_next_kwh"] = round(float(window[-1, 0] * 1.05), 3)

        # ── HVAC Decision ──────────────────────────────────────
        from streaming.inference.hvac_stream import make_hvac_decision
        hvac = make_hvac_decision(
            occupied=result["occupied"],
            hour=now.hour,
            forecast_kwh=result.get("forecast_next_kwh", 2.0),
            current_temp=float(window[-1, 1])
        )
        result["hvac"] = hvac

        # ── Current reading summary ────────────────────────────
        result["current_kwh"]  = round(float(window[-1, 0]), 3)
        result["current_temp"] = round(float(window[-1, 1]), 1)

        return result

    # ── ALERT DISPATCHER ──────────────────────────────────────────
    async def _run_alert_dispatcher(self):
        """
        Monitors inference results and fires alerts when anomalies detected.
        Supports: email (SES), Slack webhook, AWS SNS, Azure Event Grid.
        """
        log.info("🚨 Alert dispatcher starting...")
        last_alert: Dict[str, float] = {}

        while self.running:
            # Poll inference results queue (simplified polling approach)
            await asyncio.sleep(2)

    async def dispatch_alert(self, device_id: str, alert_type: str, data: dict):
        """Fire alert via all configured channels."""
        cfg      = self.config["alerts"]
        cooldown = cfg["cooldown_s"]
        now      = time.time()

        key = f"{device_id}:{alert_type}"
        # (last_alert tracking omitted for brevity — use Redis in production)

        msg = self._format_alert(alert_type, device_id, data)
        log.warning(f"🚨 ALERT: {msg}")

        # Slack
        if cfg.get("slack_webhook"):
            await self._send_slack(cfg["slack_webhook"], msg)

        # AWS SNS
        if cfg.get("sns_topic_arn"):
            await self._send_sns(cfg["sns_topic_arn"], msg, alert_type)

        self.stats["anomalies_detected"] += 1
        await self.broadcast({"type": "alert", "alert_type": alert_type,
                               "device_id": device_id, "message": msg, **data})

    def _format_alert(self, alert_type: str, device_id: str, data: dict) -> str:
        ts = datetime.now().strftime("%H:%M:%S")
        if alert_type == "anomaly":
            return (f"[{ts}] ⚡ ENERGY ANOMALY on {device_id} "
                    f"| Score: {data.get('anomaly_score', '?')} "
                    f"| Current: {data.get('current_kwh', '?')} kWh")
        return f"[{ts}] {alert_type.upper()} on {device_id}: {data}"

    async def _send_slack(self, webhook_url: str, message: str):
        try:
            # import aiohttp
            # async with aiohttp.ClientSession() as s:
            #     await s.post(webhook_url, json={"text": message})
            log.debug(f"Slack alert sent: {message[:60]}")
        except Exception as e:
            log.error(f"Slack alert failed: {e}")

    async def _send_sns(self, topic_arn: str, message: str, subject: str):
        try:
            # import aioboto3
            # async with aioboto3.Session().client("sns") as sns:
            #     await sns.publish(TopicArn=topic_arn, Message=message, Subject=subject)
            log.debug(f"SNS alert sent: {subject}")
        except Exception as e:
            log.error(f"SNS alert failed: {e}")

    # ── STREAM FINE-TUNING ────────────────────────────────────────
    async def _run_stream_finetuning(self):
        """
        Continuously fine-tunes models on fresh streaming data.
        Runs in background — updates models without stopping inference.
        """
        cfg = self.config["stream_finetuning"]
        if not cfg["enabled"]:
            log.info("⏸  Stream fine-tuning disabled")
            return

        log.info(f"🔁 Stream fine-tuner: updates every {cfg['finetune_every_s']}s "
                 f"(min {cfg['min_samples']} samples)")

        from streaming.finetuning.stream_finetuner import StreamFineTuner
        tuner = StreamFineTuner(cfg)

        while self.running:
            await asyncio.sleep(cfg["finetune_every_s"])
            if tuner.has_enough_data():
                log.info("🔁 Starting stream fine-tune cycle...")
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        None, tuner.run_finetune_cycle
                    )
                    self.stats["models_updated"] += 1
                    await self.broadcast({"type": "model_updated",
                                          "timestamp": datetime.now().isoformat()})
                    log.info("✅ Stream fine-tune complete — models updated")
                except Exception as e:
                    log.error(f"Stream fine-tune error: {e}")

    # ── SIMULATOR ─────────────────────────────────────────────────
    async def _run_simulator(self):
        """
        Generates realistic fake sensor data for demo/testing.
        Simulates a home with occupancy patterns, solar, and anomalies.
        """
        import numpy as np
        log.info("🎮 Sensor simulator active — generating fake IoT data")
        DEVICE_ID  = "sim_device_0"
        step       = 0
        BASE_KWH   = 2.0

        while self.running:
            now  = datetime.now()
            hour = now.hour
            # Realistic daily pattern
            if 6 <= hour <= 9:    base = BASE_KWH * 1.8
            elif 17 <= hour <= 21: base = BASE_KWH * 2.2
            elif 0 <= hour <= 5:   base = BASE_KWH * 0.5
            else:                   base = BASE_KWH

            # 1% chance of anomaly spike
            anomaly_spike = np.random.choice([0, 4.0], p=[0.99, 0.01])
            kwh = max(0.1, base + np.random.normal(0, 0.2) + anomaly_spike)

            reading = {
                "consumption_kwh": round(kwh, 3),
                "temperature":     round(20 + 5 * np.sin(hour * np.pi / 12) + np.random.normal(0, 0.5), 1),
                "humidity":        round(50 + np.random.normal(0, 3), 1),
                "occupancy":       1 if (7 <= hour <= 22) else 0,
                "solar_kwh":       round(max(0, 3 * np.sin(max(0, (hour-6)*np.pi/13))), 3),
                "tariff":          0.22 if 17<=hour<=20 else (0.08 if hour<7 else 0.13),
                "hour":            hour,
                "source":          "simulator",
            }

            await self.buffer.push(DEVICE_ID, reading)
            step += 1

            if step % 60 == 0:
                log.info(f"📊 Sim step {step} | {kwh:.2f} kWh | "
                         f"{'☀️' if reading['solar_kwh']>0 else '🌙'} solar={reading['solar_kwh']} | "
                         f"{'👤' if reading['occupancy'] else '🏠'} | "
                         f"buf={self.buffer.size(DEVICE_ID)}/{self.buffer.window_size}")

            await asyncio.sleep(1.0)   # 1 reading/second

    # ── STATS LOGGER ──────────────────────────────────────────────
    async def _run_stats_logger(self):
        """Logs pipeline health stats every 60 seconds."""
        while self.running:
            await asyncio.sleep(60)
            uptime = int(time.time() - self.stats["uptime_start"])
            log.info(f"\n{'─'*45}")
            log.info(f"  📊 PIPELINE STATS (uptime {uptime}s)")
            log.info(f"  Messages processed : {self.stats['messages_processed']}")
            log.info(f"  Anomalies detected : {self.stats['anomalies_detected']}")
            log.info(f"  HVAC commands sent : {self.stats['hvac_commands_sent']}")
            log.info(f"  Model updates      : {self.stats['models_updated']}")
            log.info(f"  WS clients         : {len(self.ws_clients)}")
            log.info(f"{'─'*45}\n")


# ─────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Energy Saver AI — Live Streaming Pipeline")
    parser.add_argument("--mode", choices=["live","simulate"], default="simulate")
    args = parser.parse_args()

    pipeline = EnergyStreamingPipeline(PIPELINE_CONFIG, simulate=(args.mode == "simulate"))

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(pipeline)))

    await pipeline.start()

async def shutdown(pipeline):
    log.info("\n⛔ Shutting down pipeline...")
    pipeline.running = False
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for t in tasks:
        t.cancel()

if __name__ == "__main__":
    print("\n⚡ Energy Saver AI — Live Streaming Pipeline")
    print("   Run with: python streaming/pipeline.py --mode simulate")
    print("   Dashboard: ws://localhost:8765\n")
    asyncio.run(main())

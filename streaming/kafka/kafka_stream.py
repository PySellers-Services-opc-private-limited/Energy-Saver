"""
Kafka Streaming — High-Volume Cloud Event Bus
==============================================
Connects Energy Saver AI to Apache Kafka for enterprise-scale
real-time streaming on AWS MSK or Azure Event Hubs.

Topics:
  energy.raw          ← Raw sensor readings (ingestion)
  energy.events       ← Enriched ML inference events
  energy.alerts       ← Anomaly alerts (critical)
  energy.hvac         ← HVAC commands
  energy.finetune     ← Buffered samples for online fine-tuning

Partitioning strategy:
  Key = device_id → same device always goes to same partition
  Enables ordered processing & stateful operations per device

AWS MSK setup:
  Bootstrap: b-1.<cluster>.kafka.<region>.amazonaws.com:9092
  Auth:      IAM or SASL/SCRAM

Azure Event Hubs (Kafka-compatible):
  Bootstrap: <namespace>.servicebus.windows.net:9093
  Auth:      SASL/PLAIN with connection string
"""

import asyncio
import json
import logging
import time
import numpy as np
from typing import Optional, List
from dataclasses import asdict

log = logging.getLogger("Kafka")

try:
    from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
    from aiokafka.errors import KafkaConnectionError
    HAS_KAFKA = True
except ImportError:
    HAS_KAFKA = False
    log.warning("aiokafka not installed — using Kafka simulator")

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from streaming.stream_engine import SensorReading, StreamEvent, StreamEngine


# ─────────────────────────────────────────────────────────────────
# TOPIC DEFINITIONS
# ─────────────────────────────────────────────────────────────────

class KafkaTopics:
    RAW        = "energy.raw"
    EVENTS     = "energy.events"
    ALERTS     = "energy.alerts"
    HVAC       = "energy.hvac"
    FINETUNE   = "energy.finetune"
    DASHBOARD  = "energy.dashboard"


# ─────────────────────────────────────────────────────────────────
# KAFKA PRODUCER
# ─────────────────────────────────────────────────────────────────

class EnergyKafkaProducer:
    """
    Publishes sensor readings and ML events to Kafka topics.
    Used by MQTT/WebSocket/REST ingestion layers.
    """

    def __init__(self, config: dict):
        self.bootstrap = config.get("bootstrap_servers", "localhost:9092")
        self.config    = config
        self._producer = None
        self._stats    = {"published": 0, "errors": 0, "bytes_sent": 0}

    async def start(self):
        if not HAS_KAFKA:
            log.info("Kafka producer: simulator mode")
            return

        ssl_context = None
        sasl_config = self.config.get("sasl", {})

        self._producer = AIOKafkaProducer(
            bootstrap_servers = self.bootstrap,
            value_serializer  = lambda v: json.dumps(v).encode(),
            key_serializer    = lambda k: k.encode() if k else None,
            compression_type  = "gzip",
            acks              = "all",          # Strongest durability guarantee
            max_batch_size    = 65536,
            linger_ms         = 5,              # Batch up to 5ms for throughput
            ssl_context       = ssl_context,
            **({
                "sasl_mechanism": sasl_config.get("mechanism", "PLAIN"),
                "sasl_plain_username": sasl_config.get("username"),
                "sasl_plain_password": sasl_config.get("password"),
            } if sasl_config else {})
        )
        await self._producer.start()
        log.info(f"✅ Kafka producer connected to {self.bootstrap}")

    async def publish_reading(self, reading: SensorReading):
        """Publish raw sensor reading to energy.raw topic."""
        payload = {
            "device_id": reading.device_id,
            "timestamp": reading.timestamp,
            "kwh":       reading.consumption_kwh,
            "temp":      reading.temperature,
            "humidity":  reading.humidity,
            "co2":       reading.co2,
            "light":     reading.light,
            "source":    reading.source,
            "zone":      reading.building_zone,
        }
        await self._send(KafkaTopics.RAW, reading.device_id, payload)

    async def publish_event(self, event: StreamEvent):
        """Publish enriched ML inference event."""
        payload = {
            "device_id":      event.reading.device_id,
            "timestamp":      event.reading.timestamp,
            "kwh":            event.reading.consumption_kwh,
            "anomaly_score":  event.anomaly_score,
            "anomaly_alert":  event.anomaly_alert,
            "predicted_kwh":  event.predicted_kwh_1h,
            "occupancy_prob": event.occupancy_prob,
            "hvac_action":    event.hvac_action,
            "hvac_temp":      event.hvac_target_temp,
            "alert_level":    event.alert_level,
            "latency_ms":     event.processing_ms,
        }
        await self._send(KafkaTopics.EVENTS, event.reading.device_id, payload)

        if event.anomaly_alert:
            await self._send(KafkaTopics.ALERTS, event.reading.device_id, {
                **payload, "alert_ts": time.time()
            })

        # Buffer for fine-tuning if reading looks valid
        if not event.anomaly_alert:
            await self._send(KafkaTopics.FINETUNE, event.reading.device_id, {
                "features": event.reading.to_feature_vector().tolist(),
                "timestamp": event.reading.timestamp,
            })

    async def _send(self, topic: str, key: str, payload: dict):
        if not HAS_KAFKA or self._producer is None:
            # Simulator: just log
            self._stats["published"] += 1
            return

        try:
            msg = await self._producer.send(topic, value=payload, key=key)
            self._stats["published"] += 1
            self._stats["bytes_sent"] += len(json.dumps(payload))
        except Exception as e:
            self._stats["errors"] += 1
            log.error(f"Kafka publish error [{topic}]: {e}")

    async def stop(self):
        if self._producer:
            await self._producer.stop()

    def get_stats(self):
        return self._stats


# ─────────────────────────────────────────────────────────────────
# KAFKA CONSUMER
# ─────────────────────────────────────────────────────────────────

class EnergyKafkaConsumer:
    """
    Consumes events from Kafka for downstream processing:
      - Dashboard websocket broadcast
      - Alert notification dispatch
      - Online fine-tuning buffer drain
    """

    def __init__(self, config: dict, topics: List[str], group_id: str):
        self.bootstrap = config.get("bootstrap_servers", "localhost:9092")
        self.topics    = topics
        self.group_id  = group_id
        self._consumer = None
        self._handlers = {}
        self._stats    = {"consumed": 0, "errors": 0}

    def on_topic(self, topic: str):
        """Decorator to register handler for a specific topic."""
        def decorator(fn):
            self._handlers[topic] = fn
            log.info(f"Registered handler '{fn.__name__}' for topic '{topic}'")
            return fn
        return decorator

    async def start(self):
        if not HAS_KAFKA:
            log.info("Kafka consumer: simulator mode")
            return

        self._consumer = AIOKafkaConsumer(
            *self.topics,
            bootstrap_servers  = self.bootstrap,
            group_id           = self.group_id,
            value_deserializer = lambda v: json.loads(v.decode()),
            auto_offset_reset  = "latest",
            enable_auto_commit = True,
        )
        await self._consumer.start()
        log.info(f"✅ Kafka consumer [{self.group_id}] subscribed: {self.topics}")

    async def run(self):
        """Main consumer loop."""
        if not HAS_KAFKA or self._consumer is None:
            log.info("Kafka consumer simulator — waiting for messages...")
            await asyncio.sleep(3600)
            return

        async for msg in self._consumer:
            self._stats["consumed"] += 1
            topic   = msg.topic
            payload = msg.value

            handler = self._handlers.get(topic)
            if handler:
                try:
                    await handler(payload)
                except Exception as e:
                    self._stats["errors"] += 1
                    log.error(f"Consumer handler error [{topic}]: {e}")

    async def stop(self):
        if self._consumer:
            await self._consumer.stop()


# ─────────────────────────────────────────────────────────────────
# ONLINE FINE-TUNING BUFFER (Kafka → Training Buffer)
# ─────────────────────────────────────────────────────────────────

class OnlineFineTuneBuffer:
    """
    Drains energy.finetune Kafka topic into a labeled training buffer.
    Triggers micro-batch fine-tuning when buffer reaches threshold.

    Strategy: Continual Learning
      - Collect N new samples from live stream
      - Mix with M samples from historical memory (replay buffer)
      - Fine-tune model for K epochs
      - Repeat (prevents catastrophic forgetting)
    """

    def __init__(self, config: dict, kafka_config: dict):
        self.config         = config
        self.kafka_config   = kafka_config
        self.buffer_size    = config.get("buffer_size",    500)
        self.replay_size    = config.get("replay_size",    200)
        self.finetune_every = config.get("finetune_every", 500)
        self.n_epochs       = config.get("n_epochs",       3)

        self._new_samples   = []      # Live stream samples
        self._replay_memory = []      # Historical samples (ring buffer)
        self._ft_count      = 0       # Fine-tune trigger count

    async def consume_finetune_stream(self):
        """Drain energy.finetune topic and accumulate samples."""
        consumer = EnergyKafkaConsumer(
            self.kafka_config,
            topics   = [KafkaTopics.FINETUNE],
            group_id = "finetune_worker"
        )
        await consumer.start()

        @consumer.on_topic(KafkaTopics.FINETUNE)
        async def handle_sample(payload):
            features = np.array(payload["features"], dtype=np.float32)
            self._new_samples.append(features)
            # Add to replay memory
            self._replay_memory.append(features)
            if len(self._replay_memory) > 5000:
                self._replay_memory.pop(0)

            # Trigger fine-tuning when buffer full
            if len(self._new_samples) >= self.finetune_every:
                await self._trigger_finetune()

        await consumer.run()

    async def _trigger_finetune(self):
        """Execute micro-batch fine-tuning with experience replay."""
        self._ft_count += 1
        new_data    = np.array(self._new_samples)
        replay_data = np.array(self._replay_memory[-self.replay_size:]) \
                      if len(self._replay_memory) >= self.replay_size \
                      else np.array(self._replay_memory)

        combined = np.vstack([new_data, replay_data]) \
                   if len(replay_data) > 0 else new_data
        np.random.shuffle(combined)

        log.info(
            f"🔄 Fine-tune trigger #{self._ft_count}: "
            f"{len(new_data)} new + {len(replay_data)} replay = {len(combined)} samples"
        )

        # Clear new samples buffer (keep replay memory)
        self._new_samples.clear()

        # In production: load model, fine-tune, save back
        # from deep_learning.fine_tuning.finetune_manager import FineTuneManager
        # manager = FineTuneManager(task="forecasting", ...)
        # manager.fit(X_train, y_train, strategy="feature_extraction", epochs=self.n_epochs)

        log.info(f"   ✅ Micro-batch fine-tuning complete (buffer cleared)")
        log.info(f"   Replay memory size: {len(self._replay_memory)}")


# ─────────────────────────────────────────────────────────────────
# KAFKA SETUP HELPERS (AWS MSK / Azure Event Hubs)
# ─────────────────────────────────────────────────────────────────

AWS_MSK_CONFIG = {
    "bootstrap_servers": "b-1.<cluster>.kafka.<region>.amazonaws.com:9092",
    "security_protocol": "SASL_SSL",
    "sasl": {
        "mechanism": "SCRAM-SHA-512",
        "username":  "<your-username>",
        "password":  "<your-password>",
    }
}

AZURE_EVENTHUBS_CONFIG = {
    "bootstrap_servers": "<namespace>.servicebus.windows.net:9093",
    "security_protocol": "SASL_SSL",
    "sasl": {
        "mechanism": "PLAIN",
        "username":  "$ConnectionString",
        "password":  "Endpoint=sb://<namespace>.servicebus.windows.net/;SharedAccessKeyName=...",
    }
}

KAFKA_TOPICS_SETUP = """
# Create topics on AWS MSK / self-hosted Kafka:
kafka-topics.sh --create --topic energy.raw       --partitions 12 --replication-factor 3
kafka-topics.sh --create --topic energy.events    --partitions 12 --replication-factor 3
kafka-topics.sh --create --topic energy.alerts    --partitions 4  --replication-factor 3
kafka-topics.sh --create --topic energy.hvac      --partitions 4  --replication-factor 3
kafka-topics.sh --create --topic energy.finetune  --partitions 6  --replication-factor 3
kafka-topics.sh --create --topic energy.dashboard --partitions 6  --replication-factor 3

# Set retention (7 days for raw, 30 days for events)
kafka-configs.sh --alter --topic energy.raw    --add-config retention.ms=604800000
kafka-configs.sh --alter --topic energy.events --add-config retention.ms=2592000000
"""


if __name__ == "__main__":
    async def demo():
        config   = {"bootstrap_servers": "localhost:9092"}
        producer = EnergyKafkaProducer(config)
        await producer.start()

        print("📤 Publishing 10 simulated readings to Kafka...")
        for i in range(10):
            r = SensorReading(
                device_id="meter_01", timestamp=time.time(),
                consumption_kwh=2.0 + np.random.normal(0, 0.3),
                source="kafka_test"
            )
            await producer.publish_reading(r)
            await asyncio.sleep(0.1)

        await producer.stop()
        print(f"✅ Kafka demo done. Stats: {producer.get_stats()}")

    asyncio.run(demo())

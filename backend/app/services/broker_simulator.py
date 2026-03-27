"""
BrokerSimulator — In-process Kafka & MQTT simulation
=======================================================
Runs entirely inside the FastAPI process (no Docker, no external brokers).
Simulates the connection handshake and ongoing message flow for both
Kafka and MQTT so the Pipeline page can show "Connected" without
requiring real broker deployments.

Lifecycle
---------
  1. start_all()  — called once from FastAPI lifespan on startup
  2. Each broker task: waits a realistic handshake delay, then marks itself
     connected in PipelineService, then enters a steady-state loop that
     increments shared message/anomaly counters.
  3. stop_all()   — called from FastAPI lifespan on shutdown; cancels tasks.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import List

from app.services.pipeline_service import PipelineService

log = logging.getLogger("BrokerSimulator")

_tasks: List[asyncio.Task] = []


# ─────────────────────────────────────────────────────────────────────────────
# Kafka simulator
# ─────────────────────────────────────────────────────────────────────────────

async def _kafka_task() -> None:
    """Simulate Kafka bootstrap handshake then stream messages."""
    log.info("Kafka simulator: connecting to in-process broker …")
    await asyncio.sleep(2.5)   # realistic TCP + metadata handshake delay
    PipelineService.set_kafka_connected(True)
    log.info("Kafka simulator: connected (in-process simulation mode)")

    # Steady-state: publish batches of events from 3 simulated partitions
    while True:
        try:
            # Each partition produces 1-4 messages every ~0.5 s
            batch = random.randint(3, 12)
            PipelineService.increment_messages(batch)

            # 2 % chance of an anomaly event per tick (≈ every ~25 s on avg)
            if random.random() < 0.02:
                PipelineService.increment_anomalies(1)
                log.debug("Kafka: anomaly event published to energy.alerts")

            await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            PipelineService.set_kafka_connected(False)
            log.info("Kafka simulator: disconnected (shutdown)")
            raise


# ─────────────────────────────────────────────────────────────────────────────
# MQTT simulator
# ─────────────────────────────────────────────────────────────────────────────

async def _mqtt_task() -> None:
    """Simulate MQTT CONNECT/CONNACK then subscribe and receive readings."""
    log.info("MQTT simulator: sending CONNECT packet …")
    await asyncio.sleep(1.2)   # MQTT CONNECT / CONNACK round-trip
    PipelineService.set_mqtt_connected(True)
    log.info("MQTT simulator: connected (in-process simulation mode)")

    topics = [
        "energy/meter_01/reading",
        "energy/meter_02/reading",
        "energy/solar_01/reading",
        "energy/ev_charger_01/reading",
    ]

    # Steady-state: receive QoS-1 publishes from simulated IoT devices
    while True:
        try:
            # Each subscribed topic fires 1 message per second (IoT sensors)
            msgs = len(topics) * random.randint(1, 2)
            PipelineService.increment_messages(msgs)

            # 1 % anomaly chance per tick (separate source from Kafka)
            if random.random() < 0.01:
                PipelineService.increment_anomalies(1)
                log.debug("MQTT: anomaly reading on %s", random.choice(topics))

            await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            PipelineService.set_mqtt_connected(False)
            log.info("MQTT simulator: disconnected (shutdown)")
            raise


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def start_all() -> None:
    """Schedule both broker simulator tasks on the running event loop."""
    loop = asyncio.get_event_loop()
    _tasks.append(loop.create_task(_kafka_task(), name="kafka-simulator"))
    _tasks.append(loop.create_task(_mqtt_task(), name="mqtt-simulator"))
    log.info("BrokerSimulator: Kafka + MQTT simulation tasks started")


def stop_all() -> None:
    """Cancel simulator tasks on shutdown."""
    for task in _tasks:
        task.cancel()
    _tasks.clear()
    log.info("BrokerSimulator: all simulation tasks stopped")

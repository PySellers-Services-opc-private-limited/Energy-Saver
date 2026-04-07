"""
PipelineService – exposes the streaming pipeline's runtime status.

State is updated by BrokerSimulator background tasks so that
Kafka and MQTT reflect their (simulated) connection lifecycle.
"""

from __future__ import annotations

import time

_START_TIME = time.monotonic()

# Shared mutable state — written by BrokerSimulator, read by status().
_state: dict = {
    "running": True,
    "mode": "simulate",
    "anomalies_detected": 0,
    "kafka_connected": False,
    "mqtt_connected": False,
    "ws_clients": 0,
    "messages_processed": 0,
}


class PipelineService:

    @staticmethod
    def status() -> dict:
        uptime = round(time.monotonic() - _START_TIME, 1)
        return {**_state, "uptime_s": uptime}

    # ── Mutators called by BrokerSimulator ───────────────────────────────────

    @staticmethod
    def set_kafka_connected(value: bool) -> None:
        _state["kafka_connected"] = value

    @staticmethod
    def set_mqtt_connected(value: bool) -> None:
        _state["mqtt_connected"] = value

    @staticmethod
    def increment_messages(count: int = 1) -> None:
        _state["messages_processed"] += count

    @staticmethod
    def increment_anomalies(count: int = 1) -> None:
        _state["anomalies_detected"] += count

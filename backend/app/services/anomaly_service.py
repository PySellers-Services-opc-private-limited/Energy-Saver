"""
AnomalyService – real-time anomaly detection via trained Autoencoder.
Falls back to a synthetic ring-buffer when the model is not loaded.
"""

from __future__ import annotations

import logging
import random
from collections import deque
from datetime import datetime, timedelta, timezone

import numpy as np

from app.schemas import AnomalyEvent, AnomalyResponse

logger = logging.getLogger("energy_saver_ai.anomaly_service")

_BUFFER: deque[AnomalyEvent] = deque(maxlen=200)
_FEATURE_COUNT = 6   # must match model_2_anomaly.py training


def _seed_buffer() -> None:
    now     = datetime.now(timezone.utc)
    devices = [f"device_{i:03d}" for i in range(1, 6)]
    for i in range(50):
        score = random.betavariate(1, 9)
        _BUFFER.append(AnomalyEvent(
            device_id=random.choice(devices),
            timestamp=now - timedelta(minutes=i * 5),
            anomaly_score=round(score, 4),
            is_anomaly=score > 0.6,
            consumption_kwh=round(random.uniform(0.5, 4.5), 3),
            reconstruction_error=round(score * 0.8, 4),
        ))


_seed_buffer()


class AnomalyService:

    @staticmethod
    def detect(reading_features: list[float], device_id: str) -> AnomalyEvent:
        """Run the autoencoder on a single sensor reading and record the result."""
        from app.services.model_service import ModelService

        model     = ModelService.get("anomaly")
        threshold = ModelService.anomaly_threshold()
        ts        = datetime.now(timezone.utc)

        if model is not None:
            x = np.array(reading_features[:_FEATURE_COUNT], dtype=np.float32).reshape(1, _FEATURE_COUNT)
            try:
                x_hat = model.predict(x, verbose=0)
                recon_err = float(np.mean(np.square(x - x_hat)))
                score     = min(1.0, recon_err / (threshold * 2 + 1e-9))
                is_anomaly = recon_err > threshold
            except Exception as exc:
                logger.error(f"Anomaly model inference failed: {exc}")
                recon_err, score, is_anomaly = 0.0, 0.0, False
        else:
            score      = random.betavariate(1, 9)
            recon_err  = score * 0.8
            is_anomaly = score > 0.6

        event = AnomalyEvent(
            device_id=device_id,
            timestamp=ts,
            anomaly_score=round(score, 4),
            is_anomaly=is_anomaly,
            consumption_kwh=round(reading_features[0] if reading_features else 0.0, 3),
            reconstruction_error=round(recon_err, 4),
        )
        _BUFFER.append(event)
        return event

    @staticmethod
    def recent(limit: int, device_id: str | None) -> AnomalyResponse:
        events = list(_BUFFER)
        if device_id:
            events = [e for e in events if e.device_id == device_id]
        events = sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]
        return AnomalyResponse(total=len(events), anomalies=events)

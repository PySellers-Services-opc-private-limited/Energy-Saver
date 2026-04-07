"""
AnomalyService – uses the trained LSTM Autoencoder for real anomaly detection.
Falls back to synthetic events when model is unavailable.
"""

from __future__ import annotations

import logging
import random
from collections import deque
from datetime import datetime, timedelta, timezone

import numpy as np

from app.schemas import AnomalyEvent, AnomalyResponse
from app.services.ml_loader import load_keras_model, load_numpy, DATA_DIR

logger = logging.getLogger(__name__)

_BUFFER: deque[AnomalyEvent] = deque(maxlen=200)
_REAL_DATA_LOADED = False
WINDOW_SIZE = 24  # Must match training in model_2_anomaly.py


def _load_real_anomalies() -> bool:
    """Detect anomalies using the real autoencoder on energy data."""
    global _REAL_DATA_LOADED
    if _REAL_DATA_LOADED:
        return len(_BUFFER) > 0
    _REAL_DATA_LOADED = True

    model = load_keras_model("anomaly", "anomaly_model.keras")
    threshold_arr = load_numpy("anomaly_threshold", "anomaly_threshold.npy")
    if model is None or threshold_arr is None:
        return False

    threshold = float(threshold_arr)

    try:
        import os
        import pandas as pd
        from sklearn.preprocessing import MinMaxScaler

        csv_path = os.path.join(DATA_DIR, "energy_consumption.csv")
        if not os.path.exists(csv_path):
            return False
        df = pd.read_csv(csv_path, parse_dates=["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)

        scaler = MinMaxScaler()
        consumption = scaler.fit_transform(df[["consumption_kwh"]])

        # Create windows
        windows = []
        for i in range(len(consumption) - WINDOW_SIZE):
            windows.append(consumption[i:i + WINDOW_SIZE])
        windows = np.array(windows)

        # Get last 200 windows for recent display
        recent = windows[-200:] if len(windows) > 200 else windows
        predictions = model.predict(recent, verbose=0)
        mse = np.mean(np.power(recent - predictions, 2), axis=(1, 2))

        base_idx = max(0, len(df) - len(recent) - WINDOW_SIZE)
        now = datetime.now(timezone.utc)

        _BUFFER.clear()
        for i, (error, score) in enumerate(zip(mse, mse / (threshold + 1e-9))):
            row_idx = base_idx + WINDOW_SIZE + i
            if row_idx < len(df):
                ts = df.iloc[row_idx]["timestamp"]
                if isinstance(ts, str):
                    ts = pd.Timestamp(ts)
                ts = ts.to_pydatetime().replace(tzinfo=timezone.utc)
                kwh = float(df.iloc[row_idx]["consumption_kwh"])
            else:
                ts = now - timedelta(minutes=(len(recent) - i) * 60)
                kwh = round(random.uniform(0.5, 4.5), 3)

            anomaly_score = float(min(1.0, score))
            _BUFFER.append(AnomalyEvent(
                device_id=f"device_{(i % 5) + 1:03d}",
                timestamp=ts,
                anomaly_score=round(anomaly_score, 4),
                is_anomaly=float(error) > threshold,
                consumption_kwh=round(kwh, 3),
                reconstruction_error=round(float(error), 6),
            ))

        logger.info("Loaded %d real anomaly events (threshold=%.6f)", len(_BUFFER), threshold)
        return True
    except Exception as e:
        logger.error("Failed to run anomaly detection: %s", e)
        return False


def _seed_buffer() -> None:
    """Fallback: seed with synthetic events."""
    now = datetime.now(timezone.utc)
    devices = [f"device_{i:03d}" for i in range(1, 6)]
    for i in range(50):
        score = random.betavariate(1, 9)
        _BUFFER.append(
            AnomalyEvent(
                device_id=random.choice(devices),
                timestamp=now - timedelta(minutes=i * 5),
                anomaly_score=round(score, 4),
                is_anomaly=score > 0.6,
                consumption_kwh=round(random.uniform(0.5, 4.5), 3),
                reconstruction_error=round(score * 0.8, 4),
            )
        )


class AnomalyService:

    @staticmethod
    def recent(limit: int, device_id: str | None) -> AnomalyResponse:
        if len(_BUFFER) == 0:
            if not _load_real_anomalies():
                _seed_buffer()

        events = list(_BUFFER)
        if device_id:
            events = [e for e in events if e.device_id == device_id]
        events = sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]
        return AnomalyResponse(total=len(events), anomalies=events)

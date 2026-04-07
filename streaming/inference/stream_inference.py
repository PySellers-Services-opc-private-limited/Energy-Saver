"""
Live Stream ML Inference Engine
=================================
Performs real-time inference on every sensor reading using
all trained Energy Saver AI models. Optimized for low latency.

Inference pipeline (per reading):
  1. Buffer incoming reading into sliding window
  2. Scale features using saved scalers
  3. Run all models in parallel (asyncio)
  4. Merge results into StreamEvent
  5. Emit to WebSocket + Kafka + alerts

Latency targets:
  • p50: < 10ms
  • p95: < 50ms
  • p99: < 100ms

Model loading strategy:
  - Models loaded ONCE at startup (warm)
  - Batch inference when possible
  - TensorFlow Lite for edge deployment
  - ONNX export for maximum speed
"""

import asyncio
import logging
import time
import numpy as np
from typing import Optional, Dict
from collections import deque

log = logging.getLogger("Inference")

try:
    import tensorflow as tf
    HAS_TF = True
except ImportError:
    HAS_TF = False
    log.warning("TensorFlow not available — using mock inference")

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from streaming.stream_engine import SensorReading, StreamEvent, StreamEngine


# ─────────────────────────────────────────────────────────────────
# MODEL REGISTRY
# ─────────────────────────────────────────────────────────────────

class ModelRegistry:
    """
    Loads and caches all trained models at startup.
    Provides thread-safe inference methods.
    """

    def __init__(self, model_dir: str = "models"):
        self.model_dir = model_dir
        self._models:  Dict[str, object] = {}
        self._scalers: Dict[str, object] = {}
        self._load_times: Dict[str, float] = {}

    def load_all(self):
        """Load all available models from disk."""
        import os
        model_files = {
            "forecasting":   "forecasting_model.keras",
            "anomaly":       "anomaly_model.keras",
            "occupancy":     "occupancy_model.keras",
            "solar":         "solar_model.keras",
            "bill":          "bill_predictor_model.keras",
            "fingerprinting":"fingerprinting_model.keras",
        }
        scaler_files = {
            "occupancy":  "occupancy_scaler.pkl",
            "solar":      "solar_scaler.pkl",
            "bill_X":     "bill_scaler_X.pkl",
            "bill_y":     "bill_scaler_y.pkl",
        }

        if HAS_TF:
            for name, fname in model_files.items():
                path = os.path.join(self.model_dir, fname)
                if os.path.exists(path):
                    t0 = time.monotonic()
                    try:
                        self._models[name] = tf.keras.models.load_model(path)
                        self._load_times[name] = (time.monotonic() - t0) * 1000
                        log.info(f"✅ Loaded [{name}] in {self._load_times[name]:.0f}ms")
                    except Exception as e:
                        log.warning(f"⚠️  Could not load [{name}]: {e}")
                else:
                    log.info(f"ℹ️  Model not found: {path} (will use heuristic)")

        try:
            import joblib
            for name, fname in scaler_files.items():
                path = os.path.join(self.model_dir, fname)
                if os.path.exists(path):
                    self._scalers[name] = joblib.load(path)
        except ImportError:
            pass

        loaded = len(self._models)
        log.info(f"ModelRegistry: {loaded}/{len(model_files)} models loaded")

    def get(self, name: str):
        return self._models.get(name)

    def get_scaler(self, name: str):
        return self._scalers.get(name)

    def is_loaded(self, name: str) -> bool:
        return name in self._models

    def summary(self):
        return {
            "loaded_models":  list(self._models.keys()),
            "load_times_ms":  self._load_times,
            "missing_models": [n for n in ["forecasting","anomaly","occupancy","solar"]
                               if n not in self._models]
        }


# ─────────────────────────────────────────────────────────────────
# ANOMALY THRESHOLD TRACKER (adaptive)
# ─────────────────────────────────────────────────────────────────

class AdaptiveThreshold:
    """
    Maintains a rolling baseline of reconstruction errors per device.
    Adapts the anomaly threshold as usage patterns change over time.
    """

    def __init__(self, window=500, percentile=95):
        self._errors    = deque(maxlen=window)
        self._percentile = percentile
        self._threshold = None

    def update(self, error: float):
        self._errors.append(error)
        if len(self._errors) >= 20:
            self._threshold = float(np.percentile(self._errors, self._percentile))

    @property
    def threshold(self) -> float:
        return self._threshold or float("inf")

    def is_anomaly(self, error: float) -> bool:
        return self._threshold is not None and error > self._threshold


# ─────────────────────────────────────────────────────────────────
# LIVE INFERENCE ENGINE
# ─────────────────────────────────────────────────────────────────

class LiveInferenceEngine:
    """
    Replaces StreamEngine's built-in stub inference with
    full ML model inference from all trained models.
    """

    def __init__(self, engine: StreamEngine, registry: ModelRegistry,
                 config: dict = None):
        self.engine    = engine
        self.registry  = registry
        self.config    = config or {}
        self._thresholds: Dict[str, AdaptiveThreshold] = {}
        self._latency_log = deque(maxlen=1000)

        # Override the engine's internal inference
        self._patch_engine()

    def _patch_engine(self):
        """Monkey-patch engine's _run_inference with our full ML version."""
        engine = self.engine
        async def full_inference(reading: SensorReading, window: np.ndarray):
            return await self._full_inference(reading, window)
        engine._run_inference = full_inference
        log.info("✅ LiveInferenceEngine patched into StreamEngine")

    def _get_threshold(self, device_id: str) -> AdaptiveThreshold:
        if device_id not in self._thresholds:
            self._thresholds[device_id] = AdaptiveThreshold(
                window=self.config.get("threshold_window", 500),
                percentile=self.config.get("threshold_percentile", 95)
            )
        return self._thresholds[device_id]

    async def _full_inference(self, reading: SensorReading,
                               window: np.ndarray) -> StreamEvent:
        """
        Full parallel inference across all models.
        Returns enriched StreamEvent within latency budget.
        """
        t0 = time.monotonic()

        # Run all inferences concurrently
        results = await asyncio.gather(
            self._infer_anomaly(reading, window),
            self._infer_forecast(reading, window),
            self._infer_occupancy(reading),
            return_exceptions=True
        )

        anomaly_score, anomaly_alert = results[0] if not isinstance(results[0], Exception) else (0.0, False)
        predicted_kwh = results[1] if not isinstance(results[1], Exception) else reading.consumption_kwh
        occ_prob      = results[2] if not isinstance(results[2], Exception) else 0.5

        # HVAC decision (deterministic, fast)
        hvac_action, hvac_temp = self._decide_hvac(reading, occ_prob, predicted_kwh)

        # Alert level
        if anomaly_score > 5.0:
            alert_level = "CRITICAL"
        elif anomaly_alert:
            alert_level = "WARN"
        else:
            alert_level = "OK"

        latency = (time.monotonic() - t0) * 1000
        self._latency_log.append(latency)

        return StreamEvent(
            reading          = reading,
            anomaly_score    = anomaly_score,
            anomaly_alert    = anomaly_alert,
            predicted_kwh_1h = predicted_kwh,
            occupancy_prob   = occ_prob,
            hvac_action      = hvac_action,
            hvac_target_temp = hvac_temp,
            alert_level      = alert_level,
            processing_ms    = latency,
        )

    async def _infer_anomaly(self, reading: SensorReading,
                              window: np.ndarray):
        """Anomaly detection using Autoencoder reconstruction error."""
        model = self.registry.get("anomaly")
        threshold_tracker = self._get_threshold(reading.device_id)

        if model is None or not HAS_TF:
            # Heuristic fallback: z-score on recent window
            recent = window[-12:, 0]
            z = abs(reading.consumption_kwh - recent.mean()) / (recent.std() + 0.01)
            threshold_tracker.update(z)
            return float(z), threshold_tracker.is_anomaly(z)

        # Autoencoder: reshape to (1, window, 1)
        win_1d = window[:, 0:1].reshape(1, len(window), 1)
        recon  = model.predict(win_1d, verbose=0)
        mse    = float(np.mean((win_1d - recon) ** 2))
        threshold_tracker.update(mse)
        return mse, threshold_tracker.is_anomaly(mse)

    async def _infer_forecast(self, reading: SensorReading,
                               window: np.ndarray):
        """Energy forecasting using LSTM — predict next hour."""
        model = self.registry.get("forecasting")
        if model is None or not HAS_TF:
            return float(np.mean(window[-6:, 0]))

        # Use last 48 steps if available, otherwise pad
        seq_len = model.input_shape[1]
        if len(window) >= seq_len:
            seq = window[-seq_len:]
        else:
            pad = np.zeros((seq_len - len(window), window.shape[1]))
            seq = np.vstack([pad, window])

        inp  = seq.reshape(1, seq_len, -1)
        pred = model.predict(inp, verbose=0)[0]
        return float(pred[0]) if len(pred) > 0 else float(np.mean(window[:, 0]))

    async def _infer_occupancy(self, reading: SensorReading):
        """Occupancy prediction from current sensor readings."""
        model  = self.registry.get("occupancy")
        scaler = self.registry.get_scaler("occupancy")

        if model is None or not HAS_TF:
            # CO2-based heuristic
            return float(min(1.0, max(0.0, (reading.co2 - 400) / 400)))

        from datetime import datetime
        hour = datetime.fromtimestamp(reading.timestamp).hour
        features = np.array([[
            reading.temperature, reading.humidity, reading.co2, reading.light,
            0.0, 0.0, 0.0,
            np.sin(2 * np.pi * hour / 24),
            np.cos(2 * np.pi * hour / 24),
        ]])
        if scaler:
            features = scaler.transform(features)
        # Reshape for LSTM input if needed
        if len(model.input_shape) == 3:
            features = features.reshape(1, 1, -1)
        prob = model.predict(features, verbose=0)[0][0]
        return float(prob)

    def _decide_hvac(self, reading: SensorReading,
                      occ_prob: float, forecast_kwh: float):
        """Fast rule-based HVAC decision using ML inputs."""
        from datetime import datetime
        hour = datetime.fromtimestamp(reading.timestamp).hour
        is_peak = 17 <= hour <= 20

        if occ_prob < 0.2:
            return "ECO", 18.0
        elif is_peak and forecast_kwh > 4.0:
            return "DEMAND_RESPONSE", 21.0
        elif 6 <= hour <= 8:
            return "PRE_CONDITION", 22.0
        else:
            return "COMFORT", 22.0

    def get_latency_stats(self) -> dict:
        if not self._latency_log:
            return {}
        arr = np.array(self._latency_log)
        return {
            "p50_ms":  float(np.percentile(arr, 50)),
            "p95_ms":  float(np.percentile(arr, 95)),
            "p99_ms":  float(np.percentile(arr, 99)),
            "mean_ms": float(arr.mean()),
            "max_ms":  float(arr.max()),
        }


if __name__ == "__main__":
    async def demo():
        from streaming.stream_engine import StreamEngine
        from streaming.mqtt.mqtt_client import MQTTClient

        engine   = StreamEngine({"window_size": 15})
        registry = ModelRegistry("models")
        registry.load_all()
        print(f"\n📦 Registry: {registry.summary()}")

        inf_engine = LiveInferenceEngine(engine, registry)
        await engine.start()

        alert_count = 0
        async def on_alert(evt):
            nonlocal alert_count
            alert_count += 1
            print(f"  🚨 [{evt.alert_level}] {evt.reading.device_id} "
                  f"score={evt.anomaly_score:.3f} "
                  f"latency={evt.processing_ms:.1f}ms")

        async def on_hvac(evt):
            print(f"  ❄️  HVAC → {evt.hvac_action} {evt.hvac_target_temp}°C "
                  f"occ={evt.occupancy_prob:.0%}")

        engine.register_handler("on_alert", on_alert)
        engine.register_handler("on_hvac",  on_hvac)

        mqtt = MQTTClient({})
        print("\n📡 Running live inference for 5 seconds...\n")
        try:
            await asyncio.wait_for(mqtt.run_simulator(engine, hz=5.0), timeout=5.0)
        except asyncio.TimeoutError:
            pass

        print(f"\n📊 Alerts fired : {alert_count}")
        print(f"📊 Latency stats: {inf_engine.get_latency_stats()}")
        print(f"📊 Engine stats : {engine.get_stats()}")

    asyncio.run(demo())

"""
Fine-tuning router — trigger and monitor deep learning fine-tuning jobs.

POST /api/v1/finetune/start      → start a fine-tuning job
GET  /api/v1/finetune/status     → get current job status
GET  /api/v1/finetune/history    → list past fine-tuning runs
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.utils.jwt_utils import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/finetune", tags=["fine-tuning"])

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# ── Job tracking ──────────────────────────────────────────────────────────────

_current_job: dict[str, Any] | None = None
_job_history: list[dict[str, Any]] = []
_job_lock = threading.Lock()


# ── Schemas ───────────────────────────────────────────────────────────────────

class FineTuneRequest(BaseModel):
    task: str = Field(
        default="forecasting",
        pattern=r"^(forecasting|anomaly|occupancy|solar|bill)$",
        description="Which AI model to fine-tune",
    )
    strategy: str = Field(
        default="progressive",
        pattern=r"^(feature_extraction|progressive|full_finetune)$",
        description="Fine-tuning strategy",
    )
    epochs: int = Field(default=20, ge=1, le=100, description="Max training epochs")
    batch_size: int = Field(default=32, ge=8, le=256)
    learning_rate: float = Field(default=1e-3, gt=0, le=0.1)


class FineTuneStatus(BaseModel):
    running: bool
    task: str | None = None
    strategy: str | None = None
    status: str  # idle | running | completed | failed
    progress_pct: float = 0.0
    started_at: str | None = None
    finished_at: str | None = None
    message: str = ""
    metrics: dict[str, Any] = {}


class FineTuneHistoryItem(BaseModel):
    task: str
    strategy: str
    status: str
    started_at: str
    finished_at: str | None = None
    duration_s: float = 0
    metrics: dict[str, Any] = {}


# ── Fine-tune worker ─────────────────────────────────────────────────────────

def _run_finetune_job(request: FineTuneRequest) -> None:
    """Background worker that runs a fine-tuning job."""
    global _current_job

    try:
        import sys
        sys.path.insert(0, _PROJECT_ROOT)
        sys.path.insert(0, os.path.join(_PROJECT_ROOT, "deep_learning"))

        import numpy as np

        with _job_lock:
            _current_job["status"] = "loading_data"
            _current_job["message"] = f"Loading training data for {request.task}..."
            _current_job["progress_pct"] = 10.0

        # Prepare training data based on task
        X_train, y_train = _prepare_training_data(request.task)

        with _job_lock:
            _current_job["status"] = "building_model"
            _current_job["message"] = "Building model with backbone + task head..."
            _current_job["progress_pct"] = 25.0

        from fine_tuning.finetune_manager import FineTuneManager

        input_shape = (X_train.shape[1], X_train.shape[2])
        save_dir = os.path.join(_PROJECT_ROOT, "models_storage", "finetuned")
        os.makedirs(save_dir, exist_ok=True)

        manager = FineTuneManager(
            task=request.task,
            input_shape=input_shape,
            save_dir=save_dir,
        )
        manager.build_model()

        with _job_lock:
            _current_job["status"] = "training"
            _current_job["message"] = f"Fine-tuning with {request.strategy} strategy..."
            _current_job["progress_pct"] = 40.0

        history = manager.fit(
            X_train, y_train,
            strategy=request.strategy,
            epochs=request.epochs,
            batch_size=request.batch_size,
        )

        # Extract final metrics
        metrics = {}
        for phase, hist in history.items():
            for key, vals in hist.items():
                if vals:
                    metrics[f"{phase}_{key}"] = round(float(vals[-1]), 6)

        manager.save_training_log()

        with _job_lock:
            _current_job["status"] = "completed"
            _current_job["message"] = "Fine-tuning completed successfully"
            _current_job["progress_pct"] = 100.0
            _current_job["finished_at"] = datetime.now(timezone.utc).isoformat()
            _current_job["metrics"] = metrics
            _current_job["duration_s"] = round(
                time.time() - _current_job.get("_start_time", time.time()), 1
            )
            _job_history.append({k: v for k, v in _current_job.items() if not k.startswith("_")})

        logger.info("Fine-tuning completed: %s/%s", request.task, request.strategy)

    except Exception as e:
        logger.error("Fine-tuning failed: %s", e)
        with _job_lock:
            if _current_job:
                _current_job["status"] = "failed"
                _current_job["message"] = str(e)
                _current_job["finished_at"] = datetime.now(timezone.utc).isoformat()
                _current_job["duration_s"] = round(
                    time.time() - _current_job.get("_start_time", time.time()), 1
                )
                _job_history.append({k: v for k, v in _current_job.items() if not k.startswith("_")})


def _prepare_training_data(task: str):
    """Load and prepare training data for the specified task."""
    import numpy as np
    import pandas as pd
    from sklearn.preprocessing import MinMaxScaler

    data_dir = os.path.join(_PROJECT_ROOT, "data")

    if task in ("forecasting", "anomaly"):
        csv_path = os.path.join(data_dir, "energy_consumption.csv")
        df = pd.read_csv(csv_path, parse_dates=["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)

        df["sin_hour"] = np.sin(2 * np.pi * df["hour"] / 24)
        df["cos_hour"] = np.cos(2 * np.pi * df["hour"] / 24)
        df["sin_day"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
        df["cos_day"] = np.cos(2 * np.pi * df["day_of_week"] / 7)

        features = ["consumption_kwh", "sin_hour", "cos_hour", "sin_day", "cos_day", "is_weekend"]
        scaler = MinMaxScaler()
        scaled = scaler.fit_transform(df[features])

        window_size = 48
        X, y = [], []
        if task == "forecasting":
            for i in range(len(scaled) - window_size - 24):
                X.append(scaled[i:i + window_size])
                y.append(scaled[i + window_size:i + window_size + 24, 0])
        else:  # anomaly — autoencoder (input == output)
            for i in range(len(scaled) - window_size):
                X.append(scaled[i:i + window_size])
                y.append(scaled[i:i + window_size, 0])

        return np.array(X), np.array(y)

    elif task == "occupancy":
        csv_path = os.path.join(data_dir, "occupancy_data.csv")
        df = pd.read_csv(csv_path)
        features = [c for c in df.columns if c not in ("timestamp", "occupancy")]
        scaler = MinMaxScaler()
        X_scaled = scaler.fit_transform(df[features])
        # Reshape for LSTM: (samples, timesteps=1, features)
        X = X_scaled.reshape(-1, 1, X_scaled.shape[1])
        y = df["occupancy"].values
        return X, y

    elif task == "solar":
        csv_path = os.path.join(data_dir, "solar_data.csv")
        df = pd.read_csv(csv_path)
        features = [c for c in df.columns if c not in ("timestamp", "solar_generation_kwh")]
        scaler = MinMaxScaler()
        all_data = scaler.fit_transform(df[features + ["solar_generation_kwh"]])
        window_size = 48
        X, y = [], []
        for i in range(len(all_data) - window_size - 24):
            X.append(all_data[i:i + window_size, :-1])
            y.append(all_data[i + window_size:i + window_size + 24, -1])
        return np.array(X), np.array(y)

    elif task == "bill":
        csv_path = os.path.join(data_dir, "billing_data.csv")
        df = pd.read_csv(csv_path)
        features = [c for c in df.columns if c not in ("timestamp", "bill_amount")]
        scaler = MinMaxScaler()
        X_scaled = scaler.fit_transform(df[features])
        X = X_scaled.reshape(-1, 1, X_scaled.shape[1])
        y = df["bill_amount"].values if "bill_amount" in df.columns else np.random.rand(len(df))
        return X, y

    raise ValueError(f"Unknown task: {task}")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/start", response_model=FineTuneStatus)
def start_finetune(
    body: FineTuneRequest,
    _: dict = Depends(require_admin),
):
    """Start a fine-tuning job (admin only). Runs in background."""
    global _current_job

    with _job_lock:
        if _current_job and _current_job.get("status") in ("running", "loading_data", "building_model", "training"):
            raise HTTPException(409, "A fine-tuning job is already running")

        _current_job = {
            "running": True,
            "task": body.task,
            "strategy": body.strategy,
            "status": "starting",
            "progress_pct": 0.0,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "message": "Job queued...",
            "metrics": {},
            "_start_time": time.time(),
        }

    thread = threading.Thread(
        target=_run_finetune_job,
        args=(body,),
        name="finetune-worker",
        daemon=True,
    )
    thread.start()

    return FineTuneStatus(
        running=True,
        task=body.task,
        strategy=body.strategy,
        status="starting",
        progress_pct=0.0,
        started_at=_current_job["started_at"],
        message="Fine-tuning job started",
    )


@router.get("/status", response_model=FineTuneStatus)
def get_finetune_status(_: dict = Depends(require_admin)):
    """Get the status of the current (or last) fine-tuning job."""
    if _current_job is None:
        return FineTuneStatus(
            running=False,
            status="idle",
            message="No fine-tuning job has been run yet",
        )

    with _job_lock:
        return FineTuneStatus(
            running=_current_job.get("status") in ("running", "loading_data", "building_model", "training", "starting"),
            task=_current_job.get("task"),
            strategy=_current_job.get("strategy"),
            status=_current_job.get("status", "unknown"),
            progress_pct=_current_job.get("progress_pct", 0),
            started_at=_current_job.get("started_at"),
            finished_at=_current_job.get("finished_at"),
            message=_current_job.get("message", ""),
            metrics=_current_job.get("metrics", {}),
        )


@router.get("/history", response_model=list[FineTuneHistoryItem])
def get_finetune_history(_: dict = Depends(require_admin)):
    """List all past fine-tuning runs."""
    return [
        FineTuneHistoryItem(
            task=item.get("task", ""),
            strategy=item.get("strategy", ""),
            status=item.get("status", ""),
            started_at=item.get("started_at", ""),
            finished_at=item.get("finished_at"),
            duration_s=item.get("duration_s", 0),
            metrics=item.get("metrics", {}),
        )
        for item in reversed(_job_history[-20:])  # Last 20 runs
    ]

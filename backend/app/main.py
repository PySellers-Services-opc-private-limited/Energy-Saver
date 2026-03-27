"""
Energy Saver AI – FastAPI Backend
====================================
REST API + WebSocket server for the Energy Saver AI dashboard.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Make the project root importable so services can reach utils/, config/, etc.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.database import init_db, Session
from app.routers import dashboard, forecast, anomalies, hvac, savings, models, pipeline, ws_stream
from app.routers import auth as auth_router
from app.services.model_service import ModelService
from app.services import broker_simulator
from app.services.auth_service import ensure_default_admin


# ── Logging Setup ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("energy_saver_ai")


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown logic."""
    logger.info("Starting Energy Saver AI backend")

    # 1. Database – create tables
    await init_db()
    logger.info("Database initialised")

    # 2. Create default admin user if absent
    async with Session() as session:
        await ensure_default_admin(session)

    # 3. Load AI models
    ModelService.preload()
    loaded = sum(1 for m in ModelService.list_models() if m.loaded)
    logger.info(f"Models loaded: {loaded}/{len(ModelService.list_models())}")

    # 4. Start in-process broker simulators
    broker_simulator.start_all()
    logger.info("Broker simulators started")

    yield

    broker_simulator.stop_all()
    logger.info("Energy Saver AI backend shutdown complete")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Energy Saver AI",
    description="AI-powered energy management REST API",
    version="1.0.0",
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request Logging Middleware ────────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        f"{request.method} {request.url.path} "
        f"→ {response.status_code} ({duration_ms:.1f}ms)"
    )
    return response


# ── Global Exception Handlers ─────────────────────────────────────────────────

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    logger.warning(f"Validation error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc)},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth_router.router, prefix="/api/v1")
app.include_router(dashboard.router,   prefix="/api/v1")
app.include_router(forecast.router,    prefix="/api/v1")
app.include_router(anomalies.router,   prefix="/api/v1")
app.include_router(hvac.router,        prefix="/api/v1")
app.include_router(savings.router,     prefix="/api/v1")
app.include_router(models.router,      prefix="/api/v1")
app.include_router(pipeline.router,    prefix="/api/v1")
app.include_router(ws_stream.router)


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/healthz", tags=["health"])
def health():
    return {"status": "ok", "service": "energy-saver-ai-backend"}


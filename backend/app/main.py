"""
Energy Saver AI – FastAPI Backend
====================================
REST API + WebSocket server for the Energy Saver AI dashboard.
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── DB ────────────────────────────────────────────────────────────────────────
from app.database import Base, engine

# ── Models (must be imported so SQLAlchemy registers them before create_all) ──
from app.models.tenant_model import Tenant          # noqa: F401
from app.models.user_model import User              # noqa: F401
from app.models.device_model import Device          # noqa: F401
from app.models.energy_log_model import EnergyLog   # noqa: F401
from app.models.alert_model import TenantAlert      # noqa: F401
from app.models.building_model import Building      # noqa: F401
from app.models.subscription_model import Subscription  # noqa: F401
from app.models.forecast_actual_model import DailyForecastVsActual  # noqa: F401

# Make the project root importable
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in (_PROJECT_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Existing routers ──────────────────────────────────────────────────────────
from app.routers import dashboard, forecast, anomalies, hvac, savings, models, pipeline, ws_stream

# ── Smart Apartment routers ───────────────────────────────────────────────────
from app.routers import tenant_router
from app.routers import auth_router
from app.routers import energy_router
from app.routers import alerts_router
from app.routers import forecast_actual_router

# ── New AI model routers ─────────────────────────────────────────────────────
from app.routers import bill_router
from app.routers import solar_router
from app.routers import ev_router
from app.routers import appliance_router
from app.routers import notification_router
from app.routers import settings_router
from app.routers import finetune_router

# ── Services ──────────────────────────────────────────────────────────────────
from app.services.model_service import ModelService
from app.services import broker_simulator
from app.services import mqtt_simulator
from app.services import email_scheduler
from app.services import real_mqtt_service


# ── INITIAL ADMIN — create first admin if no users exist ─────────────────────

def _ensure_admin(eng):
    """Create a default admin user ONLY if the users table is completely empty.
    Admin credentials come from environment variables — nothing hardcoded."""
    from datetime import datetime
    from sqlalchemy import text
    import bcrypt
    import os

    admin_email = os.getenv("ADMIN_EMAIL", "")
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    admin_username = os.getenv("ADMIN_USERNAME", "admin")

    with eng.connect() as c:
        user_count = c.execute(text("SELECT COUNT(*) FROM users")).scalar()
        if user_count == 0 and admin_email and admin_password:
            now = datetime.utcnow().isoformat()
            pw_hash = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()
            c.execute(text(
                "INSERT INTO users (username, email, hashed_password, role, is_active, created_at) "
                "VALUES (:u, :e, :p, 'admin', TRUE, :now)"
            ), {"u": admin_username, "e": admin_email, "p": pw_hash, "now": now})
            c.commit()
            print(f"[INIT] Created admin user ({admin_email})")
        elif user_count == 0:
            print("[WARN] No users exist. Set ADMIN_EMAIL and ADMIN_PASSWORD in .env to create the first admin.")


# ── MIGRATIONS — add new columns to existing tables ──────────────────────────

def _run_migrations(eng):
    """Idempotent ALTER TABLE statements for new tenant columns."""
    from sqlalchemy import text, inspect

    inspector = inspect(eng)

    # tenants table new columns
    if "tenants" in inspector.get_table_names():
        existing = {c["name"] for c in inspector.get_columns("tenants")}
        alter_stmts = []
        if "plan_start_date" not in existing:
            alter_stmts.append("ALTER TABLE tenants ADD COLUMN plan_start_date DATE")
        if "plan_end_date" not in existing:
            alter_stmts.append("ALTER TABLE tenants ADD COLUMN plan_end_date DATE")
        if "timezone" not in existing:
            alter_stmts.append("ALTER TABLE tenants ADD COLUMN timezone VARCHAR(100) DEFAULT 'UTC' NOT NULL")
        if "currency" not in existing:
            alter_stmts.append("ALTER TABLE tenants ADD COLUMN currency VARCHAR(10) DEFAULT 'INR' NOT NULL")
        if "is_active" not in existing:
            alter_stmts.append("ALTER TABLE tenants ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL")
        if "metadata_json" not in existing:
            alter_stmts.append("ALTER TABLE tenants ADD COLUMN metadata_json TEXT")
        if "updated_at" not in existing:
            alter_stmts.append("ALTER TABLE tenants ADD COLUMN updated_at TIMESTAMP")

        if alter_stmts:
            with eng.begin() as conn:
                for stmt in alter_stmts:
                    try:
                        conn.execute(text(stmt))
                    except Exception as e:
                        print(f"[MIGRATION] Skipped: {e}")
            print(f"[OK] Ran {len(alter_stmts)} tenant migration(s)")
        else:
            print("[OK] Tenant table up to date")

    # users table — add unit_key column
    if "users" in inspector.get_table_names():
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        if "unit_key" not in user_cols:
            with eng.begin() as conn:
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN unit_key VARCHAR(50)"))
                    print("[OK] Added unit_key column to users table")
                except Exception as e:
                    print(f"[MIGRATION] Skipped users.unit_key: {e}")


# ── LIFESPAN ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables (new tables are created, existing ones left alone)
    Base.metadata.create_all(bind=engine)
    print("[OK] Database tables created")

    # Add new columns to existing tables (safe: IF NOT EXISTS / try-except)
    _run_migrations(engine)

    # Create first admin from env vars (only if users table is empty)
    _ensure_admin(engine)

    # Preload ML models
    ModelService.preload()

    # Start IoT simulators
    broker_simulator.start_all()
    # mqtt_simulator disabled — use device_simulator.py + real MQTT instead
    # mqtt_simulator.start()

    # Start real MQTT subscriber (only activates when MQTT_BROKER is set)
    real_mqtt_service.start()

    # Start email notification schedulers
    email_scheduler.start()
    print("[OK] Email schedulers started")

    yield

    # Shutdown
    real_mqtt_service.stop()
    email_scheduler.stop()
    broker_simulator.stop_all()
    # mqtt_simulator.stop()
    print("[STOP] Server shutdown complete")


# ── APP ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Smart Apartment Energy Saver AI",
    description="AI-powered energy management REST API",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",

    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── ROUTERS ───────────────────────────────────────────────────────────────────

# Existing AI / dashboard routers
app.include_router(dashboard.router,  prefix="/api/v1")
app.include_router(forecast.router,   prefix="/api/v1")
app.include_router(anomalies.router,  prefix="/api/v1")
app.include_router(hvac.router,       prefix="/api/v1")
app.include_router(savings.router,    prefix="/api/v1")
app.include_router(models.router,     prefix="/api/v1")
app.include_router(pipeline.router,   prefix="/api/v1")
app.include_router(ws_stream.router)  # WebSocket endpoint for live dashboard

# Smart Apartment routers
app.include_router(auth_router.router,    prefix="/api/v1")
app.include_router(tenant_router.router,  prefix="/api/v1")
app.include_router(energy_router.router,  prefix="/api/v1")
app.include_router(alerts_router.router,  prefix="/api/v1")
app.include_router(forecast_actual_router.router, prefix="/api/v1")

# New AI model routers
app.include_router(bill_router.router,      prefix="/api/v1")
app.include_router(solar_router.router,     prefix="/api/v1")
app.include_router(ev_router.router,        prefix="/api/v1")
app.include_router(appliance_router.router, prefix="/api/v1")
app.include_router(notification_router.router, prefix="/api/v1")
app.include_router(settings_router.router, prefix="/api/v1")
app.include_router(finetune_router.router,    prefix="/api/v1")


# ── HEALTH CHECK ──────────────────────────────────────────────────────────────

@app.get("/healthz", tags=["health"])
def health():
    return {"status": "ok", "service": "smart-apartment-energy-saver-ai"}

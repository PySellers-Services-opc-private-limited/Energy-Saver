"""
Database setup – async SQLite via SQLAlchemy 2.0 + aiosqlite.
Tables: sensor_readings, anomaly_events, users
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, Text
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func

# ── DB file location ──────────────────────────────────────────────────────────
_DB_DIR  = Path(__file__).parent.parent.parent / "data"
_DB_DIR.mkdir(parents=True, exist_ok=True)
_DB_URL  = f"sqlite+aiosqlite:///{_DB_DIR / 'energy_saver.db'}"

engine  = create_async_engine(_DB_URL, echo=False)
Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# ── ORM Models ────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class SensorReadingORM(Base):
    __tablename__ = "sensor_readings"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    device_id        = Column(String(64), nullable=False, index=True)
    timestamp        = Column(DateTime(timezone=True), nullable=False, index=True)
    consumption_kwh  = Column(Float, nullable=False)
    temperature      = Column(Float, default=21.0)
    humidity         = Column(Float, default=50.0)
    occupancy        = Column(Integer, default=0)
    solar_kwh        = Column(Float, default=0.0)
    tariff           = Column(Float, default=6.50)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())


class AnomalyEventORM(Base):
    __tablename__ = "anomaly_events"

    id                   = Column(Integer, primary_key=True, autoincrement=True)
    device_id            = Column(String(64), nullable=False, index=True)
    timestamp            = Column(DateTime(timezone=True), nullable=False, index=True)
    anomaly_score        = Column(Float, nullable=False)
    is_anomaly           = Column(Boolean, nullable=False)
    consumption_kwh      = Column(Float, nullable=False)
    reconstruction_error = Column(Float, nullable=False)
    created_at           = Column(DateTime(timezone=True), server_default=func.now())


class UserORM(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    username        = Column(String(64), unique=True, nullable=False, index=True)
    email           = Column(String(128), unique=True, nullable=False)
    hashed_password = Column(Text, nullable=False)
    is_active       = Column(Boolean, default=True)
    is_admin        = Column(Boolean, default=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())


# ── Helpers ───────────────────────────────────────────────────────────────────

async def init_db() -> None:
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:  # type: ignore[return]
    """FastAPI dependency – yields an async DB session."""
    async with Session() as session:
        yield session

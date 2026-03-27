"""
DBService – async helpers for reading/writing sensor data and anomaly events.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AnomalyEventORM, SensorReadingORM
from app.schemas import AnomalyEvent, SensorReading

logger = logging.getLogger("energy_saver_ai.db_service")


class DBService:

    # ── Sensor Readings ───────────────────────────────────────────────────── #

    @staticmethod
    async def save_reading(session: AsyncSession, reading: SensorReading) -> None:
        row = SensorReadingORM(
            device_id=reading.device_id,
            timestamp=reading.timestamp,
            consumption_kwh=reading.consumption_kwh,
            temperature=reading.temperature,
            humidity=reading.humidity,
            occupancy=reading.occupancy,
            solar_kwh=reading.solar_kwh,
            tariff=reading.tariff,
        )
        session.add(row)
        await session.commit()

    @staticmethod
    async def recent_readings(
        session: AsyncSession,
        device_id: str | None = None,
        limit: int = 100,
    ) -> list[SensorReadingORM]:
        stmt = select(SensorReadingORM).order_by(SensorReadingORM.timestamp.desc()).limit(limit)
        if device_id:
            stmt = stmt.where(SensorReadingORM.device_id == device_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # ── Anomaly Events ────────────────────────────────────────────────────── #

    @staticmethod
    async def save_anomaly(session: AsyncSession, event: AnomalyEvent) -> None:
        row = AnomalyEventORM(
            device_id=event.device_id,
            timestamp=event.timestamp,
            anomaly_score=event.anomaly_score,
            is_anomaly=event.is_anomaly,
            consumption_kwh=event.consumption_kwh,
            reconstruction_error=event.reconstruction_error,
        )
        session.add(row)
        await session.commit()

    @staticmethod
    async def recent_anomalies(
        session: AsyncSession,
        device_id: str | None = None,
        limit: int = 50,
    ) -> list[AnomalyEventORM]:
        stmt = (
            select(AnomalyEventORM)
            .where(AnomalyEventORM.is_anomaly == True)  # noqa: E712
            .order_by(AnomalyEventORM.timestamp.desc())
            .limit(limit)
        )
        if device_id:
            stmt = stmt.where(AnomalyEventORM.device_id == device_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())

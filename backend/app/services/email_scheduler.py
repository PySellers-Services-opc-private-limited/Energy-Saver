"""
Email Scheduler — background tasks for automated email notifications.

1. Anomaly watcher      — checks every 5 min, emails tenants on new anomalies
2. Mid‑month report     — sends bill forecast on the 15th of each month at 9 AM
3. Month‑end summary    — sends full monthly report on the last day of each month
"""

from __future__ import annotations

import calendar
import logging
import os
import threading
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BILL_REPORT_DAY = int(os.getenv("BILL_REPORT_DAY", "15"))
ANOMALY_CHECK_INTERVAL = 300  # 5 minutes

_stop_event = threading.Event()
_threads: list[threading.Thread] = []

# Track what we already emailed so we don't spam
_emailed_anomalies: set[str] = set()   # "unit_key:device_id:timestamp"
_bill_sent_months: set[str] = set()    # "unit_key:2026-04"
_monthend_sent: set[str] = set()       # "unit_key:2026-04"


# ═══════════════════════════════════════════════════════════════════════════════
#  1.  ANOMALY WATCHER
# ═══════════════════════════════════════════════════════════════════════════════

def _anomaly_watcher() -> None:
    """Poll anomaly buffer; email tenants for new high‑score anomalies."""
    logger.info("[EMAIL‑SCHEDULER] Anomaly watcher started (every %ds)", ANOMALY_CHECK_INTERVAL)

    # Wait for the server to boot and models to load
    time.sleep(30)

    while not _stop_event.is_set():
        try:
            _check_anomalies()
        except Exception as exc:
            logger.error("[EMAIL‑SCHEDULER] Anomaly check error: %s", exc)
        _stop_event.wait(ANOMALY_CHECK_INTERVAL)


def _check_anomalies() -> None:
    from app.database import SessionLocal
    from app.models.tenant_model import Tenant
    from app.services.anomaly_service import AnomalyService
    from app.services.email_service import send_anomaly_alert

    resp = AnomalyService.recent(limit=50, device_id=None)
    critical = [e for e in resp.anomalies if e.is_anomaly and e.anomaly_score >= 0.7]

    if not critical:
        return

    db = SessionLocal()
    try:
        tenants = {t.unit_key: t for t in db.query(Tenant).filter(Tenant.is_active == True).all()}
    finally:
        db.close()

    if not tenants:
        return

    for event in critical:
        # Map device to a tenant via round‑robin (or all tenants for now)
        # In production, devices would be linked to unit_keys
        for unit_key, tenant in tenants.items():
            dedup_key = f"{unit_key}:{event.device_id}:{event.timestamp.isoformat()}"
            if dedup_key in _emailed_anomalies:
                continue
            _emailed_anomalies.add(dedup_key)

            send_anomaly_alert(
                to_email=tenant.email,
                tenant_name=tenant.name,
                unit_key=unit_key,
                device_id=event.device_id,
                anomaly_score=event.anomaly_score,
                consumption_kwh=event.consumption_kwh,
                reconstruction_error=event.reconstruction_error,
                timestamp=event.timestamp,
            )

    # Limit set size to prevent unbounded growth
    if len(_emailed_anomalies) > 5000:
        _emailed_anomalies.clear()


# ═══════════════════════════════════════════════════════════════════════════════
#  2.  MID‑MONTH BILL REPORT
# ═══════════════════════════════════════════════════════════════════════════════

def _bill_reporter() -> None:
    """Send bill reports on the configured day of each month."""
    logger.info("[EMAIL‑SCHEDULER] Bill reporter started (day %d)", BILL_REPORT_DAY)
    time.sleep(60)  # let server settle

    while not _stop_event.is_set():
        try:
            _check_bill_report()
        except Exception as exc:
            logger.error("[EMAIL‑SCHEDULER] Bill report error: %s", exc)
        # Check once per hour
        _stop_event.wait(3600)


def _check_bill_report() -> None:
    now = datetime.now(timezone.utc)
    if now.day != BILL_REPORT_DAY:
        return

    month_key_base = now.strftime("%Y-%m")

    from app.database import SessionLocal
    from app.models.tenant_model import Tenant
    from app.services.bill_service import BillPredictorService
    from app.services.email_service import send_bill_report

    db = SessionLocal()
    try:
        tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
    finally:
        db.close()

    for tenant in tenants:
        dedup_key = f"{tenant.unit_key}:{month_key_base}"
        if dedup_key in _bill_sent_months:
            continue

        bill_data = BillPredictorService.predict(
            days_elapsed=BILL_REPORT_DAY,
            avg_daily_kwh=30.0,
            tariff=6.50,
            avg_temp=28.0,
        )

        ok = send_bill_report(
            to_email=tenant.email,
            tenant_name=tenant.name,
            unit_key=tenant.unit_key,
            bill_data=bill_data,
        )
        if ok:
            _bill_sent_months.add(dedup_key)
            logger.info("[EMAIL‑SCHEDULER] Bill report sent to %s (%s)",
                        tenant.name, tenant.email)


# ═══════════════════════════════════════════════════════════════════════════════
#  3.  MONTH‑END SUMMARY REPORT
# ═══════════════════════════════════════════════════════════════════════════════

def _month_end_reporter() -> None:
    """Send month‑end summary emails on the last day of each month."""
    logger.info("[EMAIL‑SCHEDULER] Month‑end reporter started")
    time.sleep(60)  # let server settle

    while not _stop_event.is_set():
        try:
            _check_month_end_report()
        except Exception as exc:
            logger.error("[EMAIL‑SCHEDULER] Month‑end report error: %s", exc)
        # Check once per hour
        _stop_event.wait(3600)


def _get_monthly_stats(unit_key: str) -> dict:
    """Query EnergyLog for the current month's consumption stats."""
    from datetime import date
    from sqlalchemy import func

    from app.database import SessionLocal
    from app.models.energy_log_model import EnergyLog
    from app.models.alert_model import TenantAlert

    now = datetime.now(timezone.utc)
    month_start = date(now.year, now.month, 1)
    today = now.date()

    db = SessionLocal()
    try:
        # Monthly energy stats from energy_logs
        row = db.query(
            func.coalesce(func.sum(EnergyLog.consumption), 0).label("total_kwh"),
            func.coalesce(func.max(EnergyLog.consumption), 0).label("peak_kwh"),
            func.count(func.distinct(func.date(EnergyLog.timestamp))).label("days_with_data"),
        ).filter(
            EnergyLog.unit_key == unit_key,
            func.date(EnergyLog.timestamp) >= month_start,
            func.date(EnergyLog.timestamp) <= today,
        ).first()

        total_kwh = float(row.total_kwh) if row and row.total_kwh else 0
        peak_kwh = float(row.peak_kwh) if row and row.peak_kwh else 0
        days_with_data = int(row.days_with_data) if row and row.days_with_data else 1

        # Daily aggregation for peak day
        daily_sums = db.query(
            func.date(EnergyLog.timestamp).label("day"),
            func.sum(EnergyLog.consumption).label("day_kwh"),
        ).filter(
            EnergyLog.unit_key == unit_key,
            func.date(EnergyLog.timestamp) >= month_start,
            func.date(EnergyLog.timestamp) <= today,
        ).group_by(func.date(EnergyLog.timestamp)).all()

        if daily_sums:
            peak_day_kwh = max(float(d.day_kwh) for d in daily_sums)
        else:
            peak_day_kwh = peak_kwh

        avg_daily_kwh = total_kwh / max(days_with_data, 1)

        # Anomaly count for the month
        anomaly_count = db.query(func.count(TenantAlert.id)).filter(
            TenantAlert.unit_key == unit_key,
            TenantAlert.created_at >= datetime(now.year, now.month, 1),
        ).scalar() or 0

        return {
            "total_kwh": round(total_kwh, 1),
            "avg_daily_kwh": round(avg_daily_kwh, 1),
            "peak_kwh": round(peak_day_kwh, 1),
            "anomaly_count": anomaly_count,
            "days_with_data": days_with_data,
        }
    finally:
        db.close()


def _check_month_end_report() -> None:
    now = datetime.now(timezone.utc)
    last_day = calendar.monthrange(now.year, now.month)[1]

    # Only run on the last day of the month
    if now.day != last_day:
        return

    month_key_base = now.strftime("%Y-%m")

    from app.database import SessionLocal
    from app.models.tenant_model import Tenant
    from app.services.bill_service import BillPredictorService
    from app.services.email_service import send_month_end_report

    db = SessionLocal()
    try:
        tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
    finally:
        db.close()

    for tenant in tenants:
        dedup_key = f"{tenant.unit_key}:{month_key_base}"
        if dedup_key in _monthend_sent:
            continue

        # Get real monthly stats from DB
        monthly_stats = _get_monthly_stats(tenant.unit_key)
        avg_daily = monthly_stats.get("avg_daily_kwh", 30.0)

        # Predict final bill using full month data
        bill_data = BillPredictorService.predict(
            days_elapsed=last_day,
            avg_daily_kwh=avg_daily if avg_daily > 0 else 30.0,
            tariff=6.50,
            avg_temp=28.0,
        )

        ok = send_month_end_report(
            to_email=tenant.email,
            tenant_name=tenant.name,
            unit_key=tenant.unit_key,
            bill_data=bill_data,
            monthly_stats=monthly_stats,
        )
        if ok:
            _monthend_sent.add(dedup_key)
            logger.info("[EMAIL‑SCHEDULER] Month‑end report sent to %s (%s)",
                        tenant.name, tenant.email)


# ═══════════════════════════════════════════════════════════════════════════════
#  START / STOP
# ═══════════════════════════════════════════════════════════════════════════════

def start() -> None:
    """Start all email scheduler threads."""
    _stop_event.clear()
    for target, name in [
        (_anomaly_watcher, "email-anomaly-watcher"),
        (_bill_reporter, "email-bill-reporter"),
        (_month_end_reporter, "email-month-end-reporter"),
    ]:
        t = threading.Thread(target=target, name=name, daemon=True)
        t.start()
        _threads.append(t)
    logger.info("[EMAIL‑SCHEDULER] All email schedulers started")


def stop() -> None:
    """Signal all scheduler threads to stop."""
    _stop_event.set()
    for t in _threads:
        t.join(timeout=5)
    _threads.clear()
    logger.info("[EMAIL‑SCHEDULER] All email schedulers stopped")

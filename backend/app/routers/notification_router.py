"""
Notification router — email alerts for anomalies & bill reports.

POST /api/v1/notifications/anomaly-alert    → send anomaly email to tenant
POST /api/v1/notifications/bill-report      → send mid‑month bill report
POST /api/v1/notifications/test-email       → send a quick test email
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.tenant_model import Tenant
from app.models.user_model import User
from app.services.email_service import send_anomaly_alert, send_bill_report, send_month_end_report, _send, _wrap
from app.services.bill_service import BillPredictorService
from app.services.email_scheduler import _get_monthly_stats
from app.utils.jwt_utils import get_current_user_payload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Schemas ───────────────────────────────────────────────────────────────────

class AnomalyAlertRequest(BaseModel):
    device_id: str
    anomaly_score: float
    consumption_kwh: float
    reconstruction_error: float
    unit_key: str | None = None  # auto‑detect from JWT for tenants


class BillReportRequest(BaseModel):
    unit_key: str | None = None
    days_elapsed: int = 15
    avg_daily_kwh: float = 30.0
    tariff: float = 6.50
    avg_temp: float = 28.0


class EmailResult(BaseModel):
    sent: bool
    to: str
    message: str


# ── 1.  Anomaly alert → email ────────────────────────────────────────────────

@router.post("/anomaly-alert", response_model=EmailResult)
def send_anomaly_email(
    body: AnomalyAlertRequest,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload),
):
    """Send an anomaly‑detection alert email to the tenant's registered email."""
    role = payload.get("role", "")
    unit_key = body.unit_key or payload.get("unit_key")
    # Admin without unit_key → send to ALL active tenants
    if not unit_key and role == "admin":
        tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
        if not tenants:
            raise HTTPException(404, "No active tenants found")
        sent_to = []
        for t in tenants:
            ok = send_anomaly_alert(
                to_email=t.email, tenant_name=t.name, unit_key=t.unit_key,
                device_id=body.device_id, anomaly_score=body.anomaly_score,
                consumption_kwh=body.consumption_kwh, reconstruction_error=body.reconstruction_error,
            )
            if ok:
                sent_to.append(t.email)
        return EmailResult(sent=bool(sent_to), to=", ".join(sent_to) if sent_to else "none",
                           message=f"Anomaly alert sent to {len(sent_to)} tenant(s)" if sent_to else "Failed to send")
    if not unit_key:
        raise HTTPException(400, "unit_key is required (or login as tenant)")

    tenant = db.query(Tenant).filter(Tenant.unit_key == unit_key).first()
    if not tenant:
        raise HTTPException(404, f"No tenant found for unit_key={unit_key}")

    ok = send_anomaly_alert(
        to_email=tenant.email,
        tenant_name=tenant.name,
        unit_key=tenant.unit_key,
        device_id=body.device_id,
        anomaly_score=body.anomaly_score,
        consumption_kwh=body.consumption_kwh,
        reconstruction_error=body.reconstruction_error,
    )
    return EmailResult(
        sent=ok,
        to=tenant.email,
        message="Anomaly alert sent" if ok else "Failed to send email",
    )


# ── 2.  Mid‑month bill report → email ────────────────────────────────────────

@router.post("/bill-report", response_model=EmailResult)
def send_bill_report_email(
    body: BillReportRequest,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload),
):
    """Send mid‑month energy & bill forecast report to the tenant."""
    role = payload.get("role", "")
    unit_key = body.unit_key or payload.get("unit_key")

    bill_data = BillPredictorService.predict(
        days_elapsed=body.days_elapsed,
        avg_daily_kwh=body.avg_daily_kwh,
        tariff=body.tariff,
        avg_temp=body.avg_temp,
    )

    # Admin without unit_key → send to ALL active tenants
    if not unit_key and role == "admin":
        tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
        if not tenants:
            raise HTTPException(404, "No active tenants found")
        sent_to = []
        for t in tenants:
            ok = send_bill_report(to_email=t.email, tenant_name=t.name, unit_key=t.unit_key, bill_data=bill_data)
            if ok:
                sent_to.append(t.email)
        return EmailResult(sent=bool(sent_to), to=", ".join(sent_to) if sent_to else "none",
                           message=f"Bill report sent to {len(sent_to)} tenant(s)" if sent_to else "Failed to send")

    if not unit_key:
        raise HTTPException(400, "unit_key is required (or login as tenant)")

    tenant = db.query(Tenant).filter(Tenant.unit_key == unit_key).first()
    if not tenant:
        raise HTTPException(404, f"No tenant found for unit_key={unit_key}")

    ok = send_bill_report(
        to_email=tenant.email,
        tenant_name=tenant.name,
        unit_key=tenant.unit_key,
        bill_data=bill_data,
    )
    return EmailResult(
        sent=ok,
        to=tenant.email,
        message="Bill report sent" if ok else "Failed to send email",
    )


# ── 3.  Month‑end summary report → email ─────────────────────────────────────

class MonthEndReportRequest(BaseModel):
    unit_key: str | None = None
    tariff: float = 6.50
    avg_temp: float = 28.0


@router.post("/month-end-report", response_model=EmailResult)
def send_month_end_email(
    body: MonthEndReportRequest,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user_payload),
):
    """Send month‑end energy summary email to the tenant (or all tenants if admin)."""
    role = payload.get("role", "")
    unit_key = body.unit_key or payload.get("unit_key")

    # Admin without unit_key → send to ALL active tenants
    if not unit_key and role == "admin":
        tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
        if not tenants:
            raise HTTPException(404, "No active tenants found")
        sent_to = []
        for t in tenants:
            monthly_stats = _get_monthly_stats(t.unit_key)
            avg_daily = monthly_stats.get("avg_daily_kwh", 30.0)
            bill_data = BillPredictorService.predict(
                days_elapsed=30, avg_daily_kwh=avg_daily if avg_daily > 0 else 30.0,
                tariff=body.tariff, avg_temp=body.avg_temp,
            )
            ok = send_month_end_report(
                to_email=t.email, tenant_name=t.name, unit_key=t.unit_key,
                bill_data=bill_data, monthly_stats=monthly_stats,
            )
            if ok:
                sent_to.append(t.email)
        return EmailResult(
            sent=bool(sent_to),
            to=", ".join(sent_to) if sent_to else "none",
            message=f"Month‑end report sent to {len(sent_to)} tenant(s)" if sent_to else "Failed to send",
        )

    if not unit_key:
        raise HTTPException(400, "unit_key is required (or login as tenant)")

    tenant = db.query(Tenant).filter(Tenant.unit_key == unit_key).first()
    if not tenant:
        raise HTTPException(404, f"No tenant found for unit_key={unit_key}")

    monthly_stats = _get_monthly_stats(tenant.unit_key)
    avg_daily = monthly_stats.get("avg_daily_kwh", 30.0)
    bill_data = BillPredictorService.predict(
        days_elapsed=30, avg_daily_kwh=avg_daily if avg_daily > 0 else 30.0,
        tariff=body.tariff, avg_temp=body.avg_temp,
    )

    ok = send_month_end_report(
        to_email=tenant.email,
        tenant_name=tenant.name,
        unit_key=tenant.unit_key,
        bill_data=bill_data,
        monthly_stats=monthly_stats,
    )
    return EmailResult(
        sent=ok,
        to=tenant.email,
        message="Month‑end report sent" if ok else "Failed to send email",
    )


# ── 4.  Quick test email ─────────────────────────────────────────────────────

@router.post("/test-email", response_model=EmailResult)
def test_email(
    to: str = Query(default=None, description="Override recipient (email or unit_key)"),
    payload: dict = Depends(get_current_user_payload),
    db: Session = Depends(get_db),
):
    """Send a test email. Pass ?to=email or ?to=unit_key to target a specific tenant."""
    email_addr = None
    recipient_name = "User"

    if to:
        # Check if 'to' is a unit_key
        tenant = db.query(Tenant).filter(Tenant.unit_key == to).first()
        if tenant:
            email_addr = tenant.email
            recipient_name = tenant.name
        # Check if 'to' is an email
        elif "@" in to:
            email_addr = to
            tenant_by_email = db.query(Tenant).filter(Tenant.email == to).first()
            if tenant_by_email:
                recipient_name = tenant_by_email.name

    if not email_addr:
        user = db.query(User).filter(User.email == payload.get("email")).first()
        email_addr = user.email if user else payload.get("email")
        recipient_name = user.username if user else "Admin"

    if not email_addr:
        raise HTTPException(400, "No email address found")

    body = f"""
    <p style="color:#334155;font-size:14px">
      Hi <b>{recipient_name}</b>,
    </p>
    <p style="color:#334155;font-size:14px">
      ✅ Your email notification system is <b>working correctly</b>!
    </p>
    <p style="color:#64748b;font-size:13px">
      You will receive anomaly alerts and mid‑month bill reports
      at this address.
    </p>
    """
    html = _wrap("🔔 Test Notification", body)
    ok = _send(email_addr, "Energy Saver AI — Test Email", html)
    return EmailResult(
        sent=ok,
        to=email_addr,
        message="Test email sent!" if ok else "Failed — check SMTP configuration",
    )

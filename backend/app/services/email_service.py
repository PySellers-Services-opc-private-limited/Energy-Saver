"""
Email Service — sends anomaly alerts & mid‑month bill reports via Gmail SMTP.
"""

from __future__ import annotations

import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from dotenv import load_dotenv

# Resolve .env from project root (3 levels up: services → app → backend → project root)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR)))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

logger = logging.getLogger(__name__)

# ── SMTP Settings ─────────────────────────────────────────────────────────────

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Energy Saver AI")


def _is_configured() -> bool:
    return bool(SMTP_USER and SMTP_PASS)


# ── Low‑level sender ─────────────────────────────────────────────────────────

def _send(to_email: str, subject: str, html_body: str) -> bool:
    """Send an email over TLS.  Returns True on success."""
    if not _is_configured():
        logger.warning("SMTP not configured — skipping email to %s", to_email)
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        logger.info("Email sent → %s  [%s]", to_email, subject)
        return True
    except Exception as exc:
        logger.error("Email failed → %s : %s", to_email, exc)
        return False


# ── HTML helpers ──────────────────────────────────────────────────────────────

_HEADER = """
<div style="background:linear-gradient(135deg,#0ea5e9,#10b981);padding:24px 32px;
border-radius:12px 12px 0 0;text-align:center">
  <h1 style="color:#fff;margin:0;font-family:Segoe UI,sans-serif;font-size:22px">
    ⚡ Energy Saver AI
  </h1>
  <p style="color:#d1fae5;margin:4px 0 0;font-size:13px">{subtitle}</p>
</div>
"""

_FOOTER = """
<div style="text-align:center;padding:16px;font-size:11px;color:#94a3b8;
border-top:1px solid #e2e8f0">
  Energy Saver AI &middot; Smart Apartment Management<br>
  This is an automated notification. Do not reply.
</div>
"""

def _wrap(subtitle: str, inner_html: str) -> str:
    return f"""
    <div style="max-width:600px;margin:24px auto;font-family:Segoe UI,sans-serif;
    background:#fff;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.08);
    overflow:hidden">
      {_HEADER.format(subtitle=subtitle)}
      <div style="padding:24px 32px">{inner_html}</div>
      {_FOOTER}
    </div>
    """


# ═══════════════════════════════════════════════════════════════════════════════
#  1.  ANOMALY ALERT EMAIL
# ═══════════════════════════════════════════════════════════════════════════════

def send_anomaly_alert(
    to_email: str,
    tenant_name: str,
    unit_key: str,
    device_id: str,
    anomaly_score: float,
    consumption_kwh: float,
    reconstruction_error: float,
    timestamp: datetime | None = None,
) -> bool:
    """Send a real‑time anomaly‑detection email alert."""
    ts = timestamp or datetime.now(timezone.utc)
    ts_str = ts.strftime("%d %b %Y, %I:%M %p UTC")

    severity = "CRITICAL" if anomaly_score > 0.85 else "WARNING"
    sev_color = "#ef4444" if severity == "CRITICAL" else "#f59e0b"

    body = f"""
    <p style="color:#334155;font-size:14px">Hi <b>{tenant_name}</b>,</p>
    <p style="color:#334155;font-size:14px">
      Our AI detected an <span style="color:{sev_color};font-weight:700">
      unusual energy pattern</span> on your device.
    </p>

    <table style="width:100%;border-collapse:collapse;margin:16px 0">
      <tr>
        <td style="padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;
        font-size:13px;color:#64748b;width:40%">Severity</td>
        <td style="padding:10px 14px;border:1px solid #e2e8f0;font-weight:700;
        color:{sev_color};font-size:14px">{severity}</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;
        font-size:13px;color:#64748b">Unit</td>
        <td style="padding:10px 14px;border:1px solid #e2e8f0;font-size:14px;
        color:#0f172a">{unit_key}</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;
        font-size:13px;color:#64748b">Device</td>
        <td style="padding:10px 14px;border:1px solid #e2e8f0;font-size:14px;
        color:#0f172a">{device_id}</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;
        font-size:13px;color:#64748b">Anomaly Score</td>
        <td style="padding:10px 14px;border:1px solid #e2e8f0;font-size:14px;
        font-weight:700;color:{sev_color}">{anomaly_score:.4f}</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;
        font-size:13px;color:#64748b">Consumption</td>
        <td style="padding:10px 14px;border:1px solid #e2e8f0;font-size:14px;
        color:#0f172a">{consumption_kwh:.3f} kWh</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;
        font-size:13px;color:#64748b">Reconstruction Error</td>
        <td style="padding:10px 14px;border:1px solid #e2e8f0;font-size:14px;
        color:#0f172a">{reconstruction_error:.6f}</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;
        font-size:13px;color:#64748b">Detected At</td>
        <td style="padding:10px 14px;border:1px solid #e2e8f0;font-size:14px;
        color:#0f172a">{ts_str}</td>
      </tr>
    </table>

    <p style="color:#475569;font-size:13px">
      <b>Recommended actions:</b>
    </p>
    <ul style="color:#475569;font-size:13px;padding-left:20px">
      <li>Check if the device is running normally</li>
      <li>Verify no appliance is malfunctioning</li>
      <li>Review the Anomalies page in your dashboard for more details</li>
    </ul>
    """
    html = _wrap("🚨 Anomaly Alert", body)
    subject = f"[{severity}] Anomaly detected — {device_id} ({unit_key})"
    return _send(to_email, subject, html)


# ═══════════════════════════════════════════════════════════════════════════════
#  2.  MID‑MONTH BILL REPORT EMAIL
# ═══════════════════════════════════════════════════════════════════════════════

def send_bill_report(
    to_email: str,
    tenant_name: str,
    unit_key: str,
    bill_data: dict[str, Any],
) -> bool:
    """Send mid‑month consumption & bill‑prediction report."""
    now = datetime.now(timezone.utc)
    month_name = now.strftime("%B %Y")

    predicted = bill_data.get("predicted_bill", 0)
    lower = bill_data.get("lower_bound", 0)
    upper = bill_data.get("upper_bound", 0)
    kwh_so_far = bill_data.get("kwh_so_far", 0)
    projected_kwh = bill_data.get("projected_kwh", 0)
    days_elapsed = bill_data.get("days_elapsed", 15)
    daily_budget = bill_data.get("daily_budget", 0)
    remaining_budget = bill_data.get("remaining_budget", 0)
    model_type = bill_data.get("model", "fallback")

    pct_used = min(100, int(kwh_so_far / max(projected_kwh, 1) * 100))
    bar_color = "#10b981" if pct_used < 60 else ("#f59e0b" if pct_used < 85 else "#ef4444")

    body = f"""
    <p style="color:#334155;font-size:14px">Hi <b>{tenant_name}</b>,</p>
    <p style="color:#334155;font-size:14px">
      Here's your mid‑month energy consumption &amp; bill forecast for
      <b>{month_name}</b>.
    </p>

    <!-- Progress bar -->
    <div style="margin:20px 0">
      <div style="display:flex;justify-content:space-between;font-size:12px;color:#64748b;
      margin-bottom:4px">
        <span>Energy Used: {kwh_so_far:.0f} kWh</span>
        <span>Projected: {projected_kwh:.0f} kWh</span>
      </div>
      <div style="height:14px;background:#e2e8f0;border-radius:7px;overflow:hidden">
        <div style="height:100%;width:{pct_used}%;background:{bar_color};
        border-radius:7px;transition:width .3s"></div>
      </div>
      <p style="text-align:center;font-size:11px;color:#94a3b8;margin:4px 0">
        {pct_used}% of projected monthly usage ({days_elapsed}/30 days)
      </p>
    </div>

    <table style="width:100%;border-collapse:collapse;margin:16px 0">
      <tr>
        <td style="padding:10px 14px;background:#f0fdf4;border:1px solid #bbf7d0;
        font-size:13px;color:#166534;width:50%">📊 Predicted Bill</td>
        <td style="padding:10px 14px;background:#f0fdf4;border:1px solid #bbf7d0;
        font-size:20px;font-weight:700;color:#166534;text-align:right">
        ₹{predicted:,.2f}</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;
        font-size:13px;color:#64748b">Confidence Range (95%)</td>
        <td style="padding:10px 14px;border:1px solid #e2e8f0;font-size:14px;
        color:#334155;text-align:right">₹{lower:,.2f} — ₹{upper:,.2f}</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;
        font-size:13px;color:#64748b">Daily Budget</td>
        <td style="padding:10px 14px;border:1px solid #e2e8f0;font-size:14px;
        color:#334155;text-align:right">₹{daily_budget:,.2f}/day</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;
        font-size:13px;color:#64748b">Remaining Budget</td>
        <td style="padding:10px 14px;border:1px solid #e2e8f0;font-size:14px;
        color:#334155;text-align:right">₹{remaining_budget:,.2f}</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;
        font-size:13px;color:#64748b">kWh Consumed So Far</td>
        <td style="padding:10px 14px;border:1px solid #e2e8f0;font-size:14px;
        color:#334155;text-align:right">{kwh_so_far:,.1f} kWh</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;
        font-size:13px;color:#64748b">Days Elapsed</td>
        <td style="padding:10px 14px;border:1px solid #e2e8f0;font-size:14px;
        color:#334155;text-align:right">{days_elapsed} / 30</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;
        font-size:13px;color:#64748b">AI Model</td>
        <td style="padding:10px 14px;border:1px solid #e2e8f0;font-size:14px;
        color:#334155;text-align:right">{model_type.upper()}</td>
      </tr>
    </table>

    <p style="color:#475569;font-size:13px"><b>💡 Energy‑saving tips:</b></p>
    <ul style="color:#475569;font-size:13px;padding-left:20px">
      <li>Switch off idle appliances during peak hours (6–9 PM)</li>
      <li>Set AC thermostat to 24°C instead of 20°C to save ~15%</li>
      <li>Use the HVAC schedule in your dashboard for auto‑optimization</li>
    </ul>

    <p style="color:#94a3b8;font-size:11px;margin-top:24px">
      Unit: {unit_key} &middot; Report generated on {now.strftime("%d %b %Y, %I:%M %p UTC")}
    </p>
    """
    html = _wrap("📄 Mid‑Month Energy Report", body)
    subject = f"Your Energy Report — {month_name} ({unit_key})"
    return _send(to_email, subject, html)


# ═══════════════════════════════════════════════════════════════════════════════
#  3.  MONTH‑END SUMMARY EMAIL
# ═══════════════════════════════════════════════════════════════════════════════

def send_month_end_report(
    to_email: str,
    tenant_name: str,
    unit_key: str,
    bill_data: dict[str, Any],
    monthly_stats: dict[str, Any],
) -> bool:
    """Send month‑end energy summary & final bill report to a tenant."""
    now = datetime.now(timezone.utc)
    month_name = now.strftime("%B %Y")

    predicted = bill_data.get("predicted_bill", 0)
    lower = bill_data.get("lower_bound", 0)
    upper = bill_data.get("upper_bound", 0)
    model_type = bill_data.get("model", "fallback")

    total_kwh = monthly_stats.get("total_kwh", 0)
    avg_daily_kwh = monthly_stats.get("avg_daily_kwh", 0)
    peak_kwh = monthly_stats.get("peak_kwh", 0)
    anomaly_count = monthly_stats.get("anomaly_count", 0)
    days_with_data = monthly_stats.get("days_with_data", 30)

    # Colour‑code anomaly count
    anomaly_color = "#10b981" if anomaly_count == 0 else (
        "#f59e0b" if anomaly_count <= 3 else "#ef4444"
    )

    body = f"""
    <p style="color:#334155;font-size:14px">Hi <b>{tenant_name}</b>,</p>
    <p style="color:#334155;font-size:14px">
      Here's your <b>month‑end energy summary</b> for <b>{month_name}</b>.
    </p>

    <!-- Total Consumption Banner -->
    <div style="background:linear-gradient(135deg,#0ea5e9,#10b981);border-radius:10px;
    padding:20px 24px;text-align:center;margin:20px 0">
      <p style="color:#d1fae5;font-size:12px;margin:0 0 4px;text-transform:uppercase;
      letter-spacing:1px">Total Monthly Consumption</p>
      <p style="color:#fff;font-size:28px;font-weight:800;margin:0">
        {total_kwh:,.1f} kWh
      </p>
      <p style="color:#d1fae5;font-size:12px;margin:4px 0 0">
        Avg {avg_daily_kwh:,.1f} kWh/day &middot; Peak {peak_kwh:,.1f} kWh
      </p>
    </div>

    <table style="width:100%;border-collapse:collapse;margin:16px 0">
      <tr>
        <td style="padding:12px 14px;background:#f0fdf4;border:1px solid #bbf7d0;
        font-size:13px;color:#166534;width:50%">💰 Estimated Bill</td>
        <td style="padding:12px 14px;background:#f0fdf4;border:1px solid #bbf7d0;
        font-size:22px;font-weight:700;color:#166534;text-align:right">
        ₹{predicted:,.2f}</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;
        font-size:13px;color:#64748b">Confidence Range (95%)</td>
        <td style="padding:10px 14px;border:1px solid #e2e8f0;font-size:14px;
        color:#334155;text-align:right">₹{lower:,.2f} — ₹{upper:,.2f}</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;
        font-size:13px;color:#64748b">Total Consumption</td>
        <td style="padding:10px 14px;border:1px solid #e2e8f0;font-size:14px;
        color:#334155;text-align:right">{total_kwh:,.1f} kWh</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;
        font-size:13px;color:#64748b">Average Daily Usage</td>
        <td style="padding:10px 14px;border:1px solid #e2e8f0;font-size:14px;
        color:#334155;text-align:right">{avg_daily_kwh:,.1f} kWh/day</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;
        font-size:13px;color:#64748b">Peak Day Consumption</td>
        <td style="padding:10px 14px;border:1px solid #e2e8f0;font-size:14px;
        color:#334155;text-align:right">{peak_kwh:,.1f} kWh</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;
        font-size:13px;color:#64748b">Days with Data</td>
        <td style="padding:10px 14px;border:1px solid #e2e8f0;font-size:14px;
        color:#334155;text-align:right">{days_with_data} days</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;
        font-size:13px;color:#64748b">Anomalies Detected</td>
        <td style="padding:10px 14px;border:1px solid #e2e8f0;font-size:14px;
        font-weight:700;color:{anomaly_color};text-align:right">{anomaly_count}</td>
      </tr>
      <tr>
        <td style="padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;
        font-size:13px;color:#64748b">AI Model</td>
        <td style="padding:10px 14px;border:1px solid #e2e8f0;font-size:14px;
        color:#334155;text-align:right">{model_type.upper()}</td>
      </tr>
    </table>

    <p style="color:#475569;font-size:13px"><b>📋 Monthly Highlights:</b></p>
    <ul style="color:#475569;font-size:13px;padding-left:20px">
      <li>Your average daily usage was <b>{avg_daily_kwh:,.1f} kWh</b></li>
      <li>Peak consumption day reached <b>{peak_kwh:,.1f} kWh</b></li>
      {"<li style='color:#ef4444'>⚠️ " + str(anomaly_count) + " anomalies were detected — check your Anomalies dashboard</li>" if anomaly_count > 0 else "<li style='color:#10b981'>✅ No anomalies detected this month — great job!</li>"}
    </ul>

    <p style="color:#475569;font-size:13px"><b>💡 Tips for next month:</b></p>
    <ul style="color:#475569;font-size:13px;padding-left:20px">
      <li>Shift heavy appliance usage to off‑peak hours (10 PM – 6 AM)</li>
      <li>Review the HVAC schedule in your dashboard for auto‑optimization</li>
      <li>Consider setting monthly budget alerts to stay on track</li>
    </ul>

    <p style="color:#94a3b8;font-size:11px;margin-top:24px">
      Unit: {unit_key} &middot; Report generated on {now.strftime("%d %b %Y, %I:%M %p UTC")}
    </p>
    """
    html = _wrap("📊 Month‑End Energy Summary", body)
    subject = f"Monthly Energy Summary — {month_name} ({unit_key})"
    return _send(to_email, subject, html)

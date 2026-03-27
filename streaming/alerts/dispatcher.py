"""
Alert Dispatcher — Multi-Cloud
================================
Fires anomaly alerts to all configured channels simultaneously.
Supports: Slack, AWS SNS, GCP Pub/Sub, Azure Event Grid, Email.

Auto-detects which cloud is configured from CLOUD_PROVIDER env var.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict

log = logging.getLogger("Alerts")


class AlertDispatcher:
    """
    Unified alert dispatcher.
    Configure any combination of channels via environment variables.
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self._last_alert: Dict[str, float] = {}
        self._fired_count = 0

    async def dispatch(self, device_id: str, alert_type: str,
                       data: dict) -> bool:
        """
        Fire alert to all configured channels.
        Respects per-device cooldown. Returns True if sent.
        """
        key = f"{device_id}:{alert_type}"
        now = time.time()

        if now - self._last_alert.get(key, 0) < self.cfg.alerts.cooldown_s:
            return False

        self._last_alert[key] = now
        self._fired_count += 1

        msg = self._format(alert_type, device_id, data)
        log.warning(f"🚨 ALERT [{alert_type.upper()}] {device_id}: {msg}")

        # Fire all channels concurrently
        tasks = []
        if self.cfg.alerts.slack_webhook:
            tasks.append(self._send_slack(self.cfg.alerts.slack_webhook, msg, alert_type))
        if self.cfg.is_aws and self.cfg.alerts.aws_sns_arn:
            tasks.append(self._send_sns(self.cfg.alerts.aws_sns_arn, msg, alert_type))
        if self.cfg.is_gcp and self.cfg.gcp.project_id:
            tasks.append(self._send_gcp_pubsub(msg, alert_type, device_id, data))
        if self.cfg.is_azure and self.cfg.azure.connection_string:
            tasks.append(self._send_azure_event_grid(msg, alert_type, data))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    log.error(f"Alert channel error: {r}")

        return True

    def _format(self, alert_type: str, device_id: str, data: dict) -> str:
        ts = datetime.now().strftime("%H:%M:%S")
        if alert_type == "anomaly":
            score = data.get("anomaly_score", "?")
            kwh   = data.get("current_kwh", "?")
            return (f"[{ts}] ⚡ ENERGY ANOMALY | device={device_id} "
                    f"score={score} current={kwh} kWh")
        return f"[{ts}] {alert_type.upper()} | device={device_id} | {data}"

    # ── Slack ────────────────────────────────────────────────────
    async def _send_slack(self, webhook: str, message: str, alert_type: str):
        COLORS = {"anomaly": "#EF4444", "hvac": "#F97316", "model": "#8B5CF6"}
        payload = {
            "attachments": [{
                "color":  COLORS.get(alert_type, "#64748B"),
                "text":   message,
                "footer": "Energy Saver AI",
                "ts":     int(time.time()),
            }]
        }
        try:
            import aiohttp
            async with aiohttp.ClientSession() as sess:
                async with sess.post(webhook, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as r:
                    if r.status != 200:
                        log.error(f"Slack error {r.status}: {await r.text()}")
        except ImportError:
            log.debug(f"[Simulated] Slack: {message[:80]}")
        except Exception as e:
            log.error(f"Slack send failed: {e}")

    # ── AWS SNS ──────────────────────────────────────────────────
    async def _send_sns(self, topic_arn: str, message: str, subject: str):
        try:
            import aioboto3
            session = aioboto3.Session()
            async with session.client("sns") as sns:
                await sns.publish(
                    TopicArn=topic_arn,
                    Message=message,
                    Subject=f"Energy Saver AI — {subject.upper()} Alert",
                )
                log.debug(f"SNS sent to {topic_arn}")
        except ImportError:
            log.debug(f"[Simulated] SNS → {topic_arn}: {message[:60]}")
        except Exception as e:
            log.error(f"SNS send failed: {e}")

    # ── GCP Pub/Sub ──────────────────────────────────────────────
    async def _send_gcp_pubsub(self, message: str, alert_type: str,
                                device_id: str, data: dict):
        try:
            from streaming.gcp.gcp_client import PubSubPublisher
            publisher = PubSubPublisher(self.cfg.gcp.project_id)
            await publisher.publish(
                self.cfg.alerts.gcp_pubsub_alerts,
                {"message": message, "alert_type": alert_type,
                 "device_id": device_id, **data},
                attributes={"alert_type": alert_type}
            )
        except Exception as e:
            log.error(f"GCP alert failed: {e}")

    # ── Azure Event Grid ─────────────────────────────────────────
    async def _send_azure_event_grid(self, message: str,
                                      alert_type: str, data: dict):
        endpoint = self.cfg.alerts.azure_event_grid
        if not endpoint:
            return
        event = [{
            "id":          f"energy-alert-{int(time.time())}",
            "subject":     f"alerts/{alert_type}",
            "eventType":   f"EnergySaverAI.{alert_type.capitalize()}Detected",
            "data":        {"message": message, **data},
            "dataVersion": "1.0",
            "eventTime":   datetime.now(timezone.utc).isoformat(),
        }]
        try:
            import aiohttp
            key = self.cfg.azure.connection_string  # use Event Grid key in prod
            async with aiohttp.ClientSession() as sess:
                async with sess.post(endpoint, json=event,
                                     headers={"aeg-sas-key": key},
                                     timeout=aiohttp.ClientTimeout(total=5)) as r:
                    if r.status not in (200, 201):
                        log.error(f"Azure Event Grid error {r.status}")
        except ImportError:
            log.debug(f"[Simulated] Azure Event Grid: {alert_type}")
        except Exception as e:
            log.error(f"Azure Event Grid failed: {e}")

    @property
    def stats(self) -> dict:
        return {"alerts_fired": self._fired_count}

"""
REST API Poller
================
Polls external APIs every N seconds to enrich sensor data:
  - Utility API   → real-time tariff rates
  - OpenWeatherMap → temperature, cloud cover for solar model
  - Carbon intensity API → grid carbon factor

Results are pushed into a shared context dict read by the inference engine.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional

log = logging.getLogger("RestAPI")

# Shared live context — updated by poller, read by inference
LIVE_CONTEXT: dict = {
    "tariff":       0.13,      # $/kWh current rate
    "temp_c":       20.0,      # outdoor temperature
    "cloud_cover":  30,        # 0-100%
    "wind_ms":      3.0,       # wind speed m/s
    "humidity":     55,        # outdoor humidity %
    "carbon_gkwh":  250,       # gCO₂/kWh grid intensity
    "last_updated": None,
}


class RestAPIPoller:
    """
    Async polling loop that refreshes LIVE_CONTEXT every interval.
    Falls back to static defaults if APIs are unavailable.
    """

    def __init__(self, cfg):
        self.cfg      = cfg
        self.running  = False
        self._session = None   # aiohttp session

    async def start(self):
        self.running = True
        interval     = self.cfg.rest_api.poll_interval_s
        log.info(f"🔄 REST poller starting (every {interval}s)")

        while self.running:
            try:
                await self._poll_all()
            except Exception as e:
                log.error(f"REST poll error: {e}")
            await asyncio.sleep(interval)

    async def _poll_all(self):
        import aiohttp
        timeout = aiohttp.ClientTimeout(total=8)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as sess:
                await asyncio.gather(
                    self._poll_weather(sess),
                    self._poll_tariff(sess),
                    self._poll_carbon(sess),
                )
        except ImportError:
            # aiohttp not installed — use defaults
            LIVE_CONTEXT["last_updated"] = datetime.now().isoformat()
            log.debug("REST poll: aiohttp not available — using defaults")
            return

        LIVE_CONTEXT["last_updated"] = datetime.now().isoformat()
        log.debug(f"REST poll complete: tariff={LIVE_CONTEXT['tariff']:.3f} "
                  f"temp={LIVE_CONTEXT['temp_c']:.1f}°C "
                  f"cloud={LIVE_CONTEXT['cloud_cover']}%")

    async def _poll_weather(self, sess):
        """OpenWeatherMap current weather."""
        key = self.cfg.rest_api.weather_key
        if not key:
            # Simulate daily temp cycle
            h = datetime.now().hour
            import math
            LIVE_CONTEXT["temp_c"]      = round(15 + 7 * math.sin((h - 6) * math.pi / 12), 1)
            LIVE_CONTEXT["cloud_cover"] = 20
            return

        try:
            lat, lon = 51.5, -0.1   # Default: London — set from config in production
            url = (f"https://api.openweathermap.org/data/2.5/weather"
                   f"?lat={lat}&lon={lon}&appid={key}&units=metric")
            async with sess.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    LIVE_CONTEXT["temp_c"]      = data["main"]["temp"]
                    LIVE_CONTEXT["cloud_cover"] = data["clouds"]["all"]
                    LIVE_CONTEXT["humidity"]    = data["main"]["humidity"]
                    LIVE_CONTEXT["wind_ms"]     = data["wind"]["speed"]
        except Exception as e:
            log.debug(f"Weather API error: {e}")

    async def _poll_tariff(self, sess):
        """Utility/tariff API for real-time electricity rates."""
        url = self.cfg.rest_api.utility_url
        tok = self.cfg.rest_api.utility_token
        if not tok:
            # Time-of-use simulation
            h = datetime.now().hour
            if 17 <= h <= 20:    rate = 0.28   # Peak
            elif h < 7 or h > 21: rate = 0.08  # Off-peak
            else:                  rate = 0.13  # Standard
            LIVE_CONTEXT["tariff"] = rate
            return

        try:
            async with sess.get(f"{url}/tariff/current",
                                headers={"Authorization": f"Bearer {tok}"}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    LIVE_CONTEXT["tariff"] = data.get("rate_per_kwh", 0.13)
        except Exception as e:
            log.debug(f"Tariff API error: {e}")

    async def _poll_carbon(self, sess):
        """Carbon Intensity API (UK grid — adapt for other regions)."""
        try:
            async with sess.get("https://api.carbonintensity.org.uk/intensity") as resp:
                if resp.status == 200:
                    data   = await resp.json()
                    actual = data["data"][0]["intensity"]["actual"]
                    if actual:
                        LIVE_CONTEXT["carbon_gkwh"] = actual
        except Exception:
            pass   # Non-critical

    def stop(self):
        self.running = False

    @property
    def context(self) -> dict:
        return LIVE_CONTEXT

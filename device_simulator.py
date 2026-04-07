"""
Realistic IoT Device Simulator — mimics real smart meters publishing
to the Mosquitto MQTT broker every 5 seconds.

Simulates 8 apartment units with realistic patterns:
  - Base load varies by apartment type (home vs commercial vs industrial)
  - Time-of-day patterns (morning/evening peaks, night low)
  - Random fluctuations (appliance on/off)
  - Voltage varies around 230V ± 10V

Run:  python device_simulator.py
Stop: Ctrl+C

This is what a real ESP32 + CT clamp sensor would do.
"""

import json
import math
import random
import sys
import time
from datetime import datetime

import paho.mqtt.client as mqtt

# ── MQTT Broker Config ────────────────────────────────────────────
BROKER = "localhost"
PORT = 1883
USER = "energy_saver"
PASS = "Energy@mqtt2026"

# ── Base kWh profiles by tenant type ─────────────────────────────
BASE_KWH = {"home": 1.2, "commercial": 4.5, "industrial": 8.0}

PUBLISH_INTERVAL = 5  # seconds between readings


def load_apartments_from_db():
    """Load apartment list dynamically from the database."""
    try:
        sys.path.insert(0, "backend")
        from app.database import SessionLocal
        from sqlalchemy import text

        db = SessionLocal()
        rows = db.execute(text(
            "SELECT unit_key, name, tenant_type FROM tenants WHERE is_active = TRUE"
        )).fetchall()
        db.close()

        if not rows:
            print("[WARN] No tenants in database. Create tenants via the API first.")
            return []

        apartments = []
        for unit_key, name, tenant_type in rows:
            apartments.append({
                "unit_key": unit_key,
                "type": tenant_type or "home",
                "base_kwh": BASE_KWH.get(tenant_type, 1.2) + random.uniform(-0.3, 0.3),
                "name": name,
            })
        return apartments

    except Exception as e:
        print(f"[ERROR] Could not load tenants from DB: {e}")
        return []


def get_time_multiplier() -> float:
    """Realistic time-of-day energy pattern."""
    hour = datetime.now().hour
    # Night (11pm-5am): low usage
    if hour >= 23 or hour < 5:
        return 0.3
    # Morning peak (6am-9am): cooking, water heater
    if 6 <= hour <= 9:
        return 1.4
    # Daytime (10am-4pm): moderate
    if 10 <= hour <= 16:
        return 0.8
    # Evening peak (5pm-10pm): AC, cooking, TV, lights
    if 17 <= hour <= 22:
        return 1.6
    return 1.0


def generate_reading(apt: dict) -> dict:
    """Generate a realistic energy reading for one apartment."""
    time_mult = get_time_multiplier()

    # Commercial/industrial have different patterns
    if apt["type"] == "commercial":
        # High during business hours, low at night
        hour = datetime.now().hour
        time_mult = 1.5 if 8 <= hour <= 18 else 0.2
    elif apt["type"] == "industrial":
        # 24/7 operation with slight variations
        time_mult = 0.9 + random.uniform(0, 0.3)

    # Base consumption with time pattern + random appliance spikes
    consumption = apt["base_kwh"] * time_mult
    consumption += random.uniform(-0.3, 0.5)  # random fluctuation
    consumption = max(0.1, consumption)        # never negative

    # Voltage around 230V (Indian standard)
    voltage = 230 + random.uniform(-8, 8)

    # Current derived from power and voltage
    power = consumption  # kW
    current = (power * 1000) / voltage  # Amps

    return {
        "consumption": round(consumption, 2),
        "voltage": round(voltage, 1),
        "current": round(current, 2),
        "power": round(power, 2),
        "timestamp": datetime.now().isoformat(),
    }


def main():
    # Load apartments dynamically from DB
    apartments = load_apartments_from_db()
    if not apartments:
        print("No tenants found. Add tenants via the API, then run this simulator again.")
        return

    # Connect to MQTT broker
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="iot_device_simulator",
    )
    client.username_pw_set(USER, PASS)

    def on_connect(c, ud, flags, rc, props=None):
        if rc == 0:
            print(f"[OK] Connected to MQTT broker {BROKER}:{PORT}")
        else:
            print(f"[ERROR] Connection failed: rc={rc}")

    client.on_connect = on_connect
    client.connect(BROKER, PORT, 60)
    client.loop_start()

    time.sleep(1)  # wait for connection

    print(f"\nSimulating {len(apartments)} apartments (loaded from DB), publishing every {PUBLISH_INTERVAL}s")
    print("Press Ctrl+C to stop\n")
    print("-" * 80)

    reading_count = 0

    try:
        while True:
            for apt in apartments:
                reading = generate_reading(apt)
                topic = f"apartment/{apt['unit_key']}"

                payload = json.dumps(reading)
                client.publish(topic, payload, qos=1)
                reading_count += 1

                print(
                    f"  [{datetime.now().strftime('%H:%M:%S')}] "
                    f"{apt['unit_key']} ({apt['name']:20s}) → "
                    f"{reading['consumption']:5.2f} kWh | "
                    f"{reading['voltage']:5.1f}V | "
                    f"{reading['current']:5.2f}A"
                )

            print(f"  --- Batch #{reading_count // len(apartments)} sent ({reading_count} total readings) ---\n")
            time.sleep(PUBLISH_INTERVAL)

    except KeyboardInterrupt:
        print(f"\n\nStopped. Total readings published: {reading_count}")

    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()

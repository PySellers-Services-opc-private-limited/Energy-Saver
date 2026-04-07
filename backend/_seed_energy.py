"""Seed sample energy readings into PostgreSQL for the last 7 days.
Reads tenant unit_keys dynamically from the database — no hardcoded values."""
import random
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models.energy_log_model import EnergyLog
from sqlalchemy import text

db = SessionLocal()

# Load unit keys dynamically from tenants table
rows = db.execute(text("SELECT unit_key FROM tenants WHERE is_active = TRUE")).fetchall()
units = [r[0] for r in rows]

if not units:
    print("No tenants found in database. Create tenants via the API first.")
    db.close()
    exit()
now = datetime.utcnow()
count = 0

for unit in units:
    for day_offset in range(7):
        for hour in range(24):
            ts = now - timedelta(days=day_offset, hours=hour)
            db.add(EnergyLog(
                unit_key=unit,
                consumption=round(random.uniform(0.5, 8.0), 2),
                voltage=round(random.uniform(220, 240), 1),
                current=round(random.uniform(2, 35), 1),
                power=round(random.uniform(0.5, 5.0), 2),
                timestamp=ts,
            ))
            count += 1

db.commit()
db.close()
print(f"Inserted {count} energy log readings into PostgreSQL")

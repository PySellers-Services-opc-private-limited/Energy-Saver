"""
Step 1: Generate Sample Energy Data
====================================
This script generates realistic sample data for:
- Energy consumption (kWh)
- Occupancy (0/1)
- Temperature, Humidity, CO2, Light sensors
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def generate_energy_data(days=60):
    """Generate hourly energy consumption data"""
    print("📊 Generating energy consumption data...")
    
    np.random.seed(42)
    hours = days * 24
    timestamps = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(hours)]
    
    consumption = []
    for ts in timestamps:
        hour = ts.hour
        day_of_week = ts.weekday()  # 0=Monday, 6=Sunday
        is_weekend = day_of_week >= 5

        # Base consumption pattern (higher in morning/evening)
        if 6 <= hour <= 9:
            base = 3.5   # Morning peak
        elif 17 <= hour <= 21:
            base = 4.5   # Evening peak
        elif 22 <= hour or hour <= 5:
            base = 1.2   # Night low
        else:
            base = 2.5   # Daytime normal

        # Weekend adjustment
        if is_weekend:
            base *= 1.2

        # Add realistic noise
        noise = np.random.normal(0, 0.3)
        
        # Occasional anomalies (1% chance)
        anomaly = np.random.choice([0, 3.0], p=[0.99, 0.01])
        
        consumption.append(max(0.1, base + noise + anomaly))
    
    df = pd.DataFrame({
        "timestamp": timestamps,
        "consumption_kwh": consumption,
        "hour": [ts.hour for ts in timestamps],
        "day_of_week": [ts.weekday() for ts in timestamps],
        "is_weekend": [int(ts.weekday() >= 5) for ts in timestamps]
    })
    
    df.to_csv("data/energy_consumption.csv", index=False)
    print(f"   ✅ Saved {len(df)} hourly records → data/energy_consumption.csv")
    return df


def generate_occupancy_data(days=60):
    """Generate room occupancy sensor data"""
    print("🚶 Generating occupancy sensor data...")
    
    np.random.seed(42)
    records = []
    timestamps = [datetime(2024, 1, 1) + timedelta(minutes=i*5) for i in range(days * 24 * 12)]
    
    for ts in timestamps:
        hour = ts.hour
        is_weekend = ts.weekday() >= 5

        # Occupancy probability by time
        if is_weekend:
            if 9 <= hour <= 22:
                occ_prob = 0.75
            elif 7 <= hour <= 9:
                occ_prob = 0.4
            else:
                occ_prob = 0.05
        else:
            if 8 <= hour <= 17:
                occ_prob = 0.2   # Work hours - mostly out
            elif 17 <= hour <= 22:
                occ_prob = 0.85  # Evening at home
            elif 6 <= hour <= 8:
                occ_prob = 0.6   # Morning routine
            else:
                occ_prob = 0.05  # Sleeping

        occupied = int(np.random.random() < occ_prob)
        
        # Sensor readings depend on occupancy
        base_temp = 20 + np.random.normal(0, 0.5)
        base_humidity = 40 + np.random.normal(0, 3)
        base_co2 = 400 + np.random.normal(0, 20)
        base_light = 50 + np.random.normal(0, 10)

        if occupied:
            temp = base_temp + np.random.uniform(0.5, 2.0)
            humidity = base_humidity + np.random.uniform(2, 8)
            co2 = base_co2 + np.random.uniform(100, 400)
            light = base_light + np.random.uniform(100, 400) if 7 <= hour <= 22 else base_light
        else:
            temp = base_temp
            humidity = base_humidity
            co2 = base_co2
            light = base_light if 8 <= hour <= 18 else max(0, base_light - 40)

        records.append({
            "timestamp": ts,
            "temperature": round(temp, 2),
            "humidity": round(humidity, 2),
            "co2": round(co2, 2),
            "light": round(max(0, light), 2),
            "hour": hour,
            "occupied": occupied
        })
    
    df = pd.DataFrame(records)
    df.to_csv("data/occupancy_data.csv", index=False)
    print(f"   ✅ Saved {len(df)} sensor records → data/occupancy_data.csv")
    return df


if __name__ == "__main__":
    print("\n" + "="*50)
    print("  STEP 1: DATA GENERATION")
    print("="*50)
    
    energy_df = generate_energy_data(days=60)
    occupancy_df = generate_occupancy_data(days=60)
    
    print("\n📈 Energy Data Sample:")
    print(energy_df.head(5).to_string())
    
    print("\n🏠 Occupancy Data Sample:")
    print(occupancy_df.head(5).to_string())
    
    print("\n✅ Step 1 Complete! Run model_1_forecasting.py next.\n")

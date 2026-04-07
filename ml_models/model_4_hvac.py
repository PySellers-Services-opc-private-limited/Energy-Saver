"""
Step 5: HVAC Optimization System
===================================
Combines all 3 models to make smart HVAC decisions:
  - Model 1 (Forecasting) → Predicts energy demand
  - Model 3 (Occupancy)   → Detects if room is occupied
  - Rule-based AI         → Makes thermostat decisions

Optimizes for: Comfort + Energy Savings + Cost
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
os.makedirs("outputs", exist_ok=True)

import tensorflow as tf
import joblib

print("\n" + "="*50)
print("  STEP 5: HVAC OPTIMIZATION SYSTEM")
print("="*50)

# ─────────────────────────────────────────
# 1. LOAD ALL TRAINED MODELS
# ─────────────────────────────────────────
print("\n📂 Loading trained models...")
try:
    occupancy_model = tf.keras.models.load_model("models/occupancy_model.keras")
    occupancy_scaler = joblib.load("models/occupancy_scaler.pkl")
    print("   ✅ Occupancy model loaded")
except Exception as e:
    print(f"   ⚠️  Could not load occupancy model: {e}")
    occupancy_model = None

# ─────────────────────────────────────────
# 2. HVAC DECISION ENGINE
# ─────────────────────────────────────────

# Electricity tariff schedule ($/kWh) - time-of-use pricing
TARIFF_SCHEDULE = {
    range(0, 7):   0.08,   # Off-peak: midnight–7am
    range(7, 17):  0.12,   # Mid-peak: 7am–5pm
    range(17, 21): 0.22,   # Peak: 5pm–9pm
    range(21, 24): 0.08,   # Off-peak: 9pm–midnight
}

def get_tariff(hour):
    for hour_range, price in TARIFF_SCHEDULE.items():
        if hour in hour_range:
            return price
    return 0.12  # Default

def predict_occupancy(sensor_data, model, scaler):
    """Use ML model to predict if room is occupied"""
    if model is None:
        # Fallback: time-based heuristic
        hour = sensor_data.get("hour", 12)
        return 1 if (7 <= hour <= 22) else 0
    
    features = np.array([[
        sensor_data["temperature"],
        sensor_data["humidity"],
        sensor_data["co2"],
        sensor_data["light"],
        sensor_data.get("temp_diff", 0),
        sensor_data.get("co2_diff", 0),
        sensor_data.get("light_diff", 0),
        np.sin(2 * np.pi * sensor_data["hour"] / 24),
        np.cos(2 * np.pi * sensor_data["hour"] / 24)
    ]])
    scaled = scaler.transform(features)
    prob = model.predict(scaled, verbose=0)[0][0]
    return int(prob > 0.5), float(prob)


def hvac_decision(sensor_data, forecast_kwh=None):
    """
    Main HVAC optimization decision engine.
    
    Inputs:
        sensor_data: dict with temperature, humidity, co2, light, hour
        forecast_kwh: predicted energy demand for next hour
    
    Returns:
        decision dict with target_temp, mode, reason, estimated_savings
    """
    hour = sensor_data["hour"]
    current_temp = sensor_data["temperature"]
    tariff = get_tariff(hour)
    is_peak = tariff >= 0.18

    # --- Predict occupancy ---
    if occupancy_model:
        occupied, occ_prob = predict_occupancy(sensor_data, occupancy_model, occupancy_scaler)
    else:
        occupied = 1 if (7 <= hour <= 22) else 0
        occ_prob = float(occupied)

    # --- Make decision ---
    if not occupied:
        # NOBODY HOME → Energy saving mode
        target_temp = 16 if current_temp > 20 else 26  # Cool down or heat less
        mode = "ECO"
        reason = f"Room empty (confidence: {(1-occ_prob)*100:.0f}%) → Energy saving mode"
        savings_pct = 40

    elif is_peak and forecast_kwh and forecast_kwh > 5.0:
        # PEAK HOURS + HIGH DEMAND → Pre-cool/heat strategy
        target_temp = 20 if current_temp > 20 else 23
        mode = "DEMAND_RESPONSE"
        reason = f"Peak pricing (${tariff}/kWh) + high demand ({forecast_kwh:.1f} kWh) → Reduce load"
        savings_pct = 25

    elif hour >= 6 and hour <= 8:
        # MORNING WARM-UP → Pre-condition before peak
        target_temp = 22
        mode = "PRE_CONDITION"
        reason = "Morning pre-conditioning at off-peak rate"
        savings_pct = 15

    else:
        # NORMAL OCCUPIED → Comfort mode
        target_temp = 22
        mode = "COMFORT"
        reason = f"Normal occupied hours (tariff: ${tariff}/kWh)"
        savings_pct = 0

    return {
        "hour": hour,
        "occupied": bool(occupied),
        "occupancy_confidence": f"{occ_prob*100:.0f}%",
        "current_temp": current_temp,
        "target_temp": target_temp,
        "mode": mode,
        "tariff": f"${tariff}/kWh",
        "reason": reason,
        "estimated_savings": f"{savings_pct}%"
    }


# ─────────────────────────────────────────
# 3. SIMULATE A FULL DAY
# ─────────────────────────────────────────
print("\n🏠 Simulating 24-hour HVAC optimization...")

# Simulate realistic sensor readings + forecast throughout the day
np.random.seed(42)
daily_scenarios = []

sensor_readings_by_hour = {
    0:  {"temperature": 19, "humidity": 45, "co2": 420, "light": 5,   "hour": 0},
    6:  {"temperature": 19, "humidity": 47, "co2": 430, "light": 30,  "hour": 6},
    8:  {"temperature": 21, "humidity": 50, "co2": 650, "light": 200, "hour": 8},
    12: {"temperature": 23, "humidity": 52, "co2": 700, "light": 500, "hour": 12},
    17: {"temperature": 24, "humidity": 55, "co2": 800, "light": 300, "hour": 17},
    19: {"temperature": 23, "humidity": 54, "co2": 850, "light": 400, "hour": 19},
    22: {"temperature": 22, "humidity": 50, "co2": 500, "light": 100, "hour": 22},
}

# Fill in missing hours with interpolated/default values
for hour in range(24):
    closest = min(sensor_readings_by_hour.keys(), key=lambda h: abs(h - hour))
    sensor = dict(sensor_readings_by_hour[closest])
    sensor["hour"] = hour
    sensor["temp_diff"] = np.random.normal(0, 0.1)
    sensor["co2_diff"]  = np.random.normal(0, 5)
    sensor["light_diff"] = np.random.normal(0, 2)
    
    forecast = 2.0 + 2.5 * np.sin((hour - 6) * np.pi / 12) + np.random.normal(0, 0.3)
    forecast = max(0.5, forecast)
    
    decision = hvac_decision(sensor, forecast_kwh=forecast)
    decision["forecast_kwh"] = round(forecast, 2)
    daily_scenarios.append(decision)

# ─────────────────────────────────────────
# 4. DISPLAY RESULTS TABLE
# ─────────────────────────────────────────
results_df = pd.DataFrame(daily_scenarios)
print("\n📊 24-Hour HVAC Decision Summary:")
print("─" * 80)
display_cols = ["hour", "occupied", "current_temp", "target_temp",
                "mode", "tariff", "estimated_savings"]
print(results_df[display_cols].to_string(index=False))

# ─────────────────────────────────────────
# 5. PLOT HVAC DECISIONS
# ─────────────────────────────────────────
fig, axes = plt.subplots(3, 1, figsize=(14, 12))
fig.suptitle("HVAC Optimization - 24 Hour Decision Summary", fontsize=14, fontweight="bold")

hours = results_df["hour"].values
mode_colors = {
    "ECO": "green", "DEMAND_RESPONSE": "red",
    "PRE_CONDITION": "orange", "COMFORT": "blue"
}
colors = [mode_colors.get(m, "gray") for m in results_df["mode"]]

# Plot 1: Temperature decisions
axes[0].plot(hours, results_df["current_temp"], "b-o", label="Current Temp", linewidth=2)
axes[0].plot(hours, results_df["target_temp"],  "r--s", label="Target Temp", linewidth=2)
axes[0].fill_between(hours, 20, 24, alpha=0.1, color="green", label="Comfort Zone")
axes[0].set_title("Temperature Control"); axes[0].set_ylabel("°C")
axes[0].legend(); axes[0].grid(True, alpha=0.3)
axes[0].set_xlim(0, 23)

# Plot 2: Operating mode by hour
mode_map = {"ECO": 1, "PRE_CONDITION": 2, "COMFORT": 3, "DEMAND_RESPONSE": 4}
mode_nums = [mode_map.get(m, 0) for m in results_df["mode"]]
axes[1].bar(hours, mode_nums, color=colors, alpha=0.8)
axes[1].set_yticks([1, 2, 3, 4])
axes[1].set_yticklabels(["ECO", "PRE_COND", "COMFORT", "DEMAND_RESP"])
axes[1].set_title("HVAC Operating Mode"); axes[1].set_ylabel("Mode")
axes[1].grid(True, alpha=0.3, axis="y"); axes[1].set_xlim(-0.5, 23.5)

# Plot 3: Energy forecast + tariff overlay
ax3 = axes[2]
ax3b = ax3.twinx()
ax3.bar(hours, results_df["forecast_kwh"], alpha=0.6, color="steelblue", label="Forecast kWh")
tariff_vals = [float(get_tariff(h)) for h in hours]
ax3b.plot(hours, tariff_vals, "r-o", linewidth=2, markersize=4, label="Tariff ($/kWh)")
ax3.set_title("Energy Forecast & Tariff")
ax3.set_xlabel("Hour of Day"); ax3.set_ylabel("kWh", color="steelblue")
ax3b.set_ylabel("$/kWh", color="red")
ax3.set_xlim(-0.5, 23.5)
lines1, labels1 = ax3.get_legend_handles_labels()
lines2, labels2 = ax3b.get_legend_handles_labels()
ax3.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
ax3.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("outputs/model4_hvac_results.png", dpi=150)
print("\n   📊 Plot saved → outputs/model4_hvac_results.png")

# Save results
results_df.to_csv("outputs/hvac_daily_schedule.csv", index=False)
print("   💾 Schedule saved → outputs/hvac_daily_schedule.csv")

print("\n✅ Step 5 Complete! HVAC optimization system ready.")
print("   ▶ Run run_all.py to execute the full pipeline!\n")

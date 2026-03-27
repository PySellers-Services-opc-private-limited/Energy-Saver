"""
Step 7: Solar Generation Forecast (LSTM + Weather)
====================================================
Predicts how much solar energy your panels will
produce in the next 24 hours using weather features.

Input features:
  - Cloud cover (%)
  - Temperature (°C)
  - Hour of day (sin/cos encoded)
  - Day of year (seasonal position)
  - Humidity (%)
  - Wind speed (m/s)

Output: Predicted solar generation (kWh) per hour
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
os.makedirs("outputs", exist_ok=True)
os.makedirs("models",  exist_ok=True)
os.makedirs("data",    exist_ok=True)

from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, Bidirectional
from tensorflow.keras.callbacks import EarlyStopping

print("\n" + "="*55)
print("  STEP 7: SOLAR GENERATION FORECAST")
print("="*55)

# ─────────────────────────────────────────
# 1. GENERATE SOLAR + WEATHER DATA
# ─────────────────────────────────────────
print("\n☀️  Generating solar + weather dataset...")
np.random.seed(42)

from datetime import datetime, timedelta

DAYS = 90
timestamps = [datetime(2024, 1, 1) + timedelta(hours=h) for h in range(DAYS * 24)]
records = []

for ts in timestamps:
    hour       = ts.hour
    day_of_year = ts.timetuple().tm_yday

    # Seasonal sunlight intensity (stronger in summer)
    seasonal = 0.5 + 0.5 * np.sin((day_of_year - 80) * 2 * np.pi / 365)

    # Solar irradiance curve (bell shape, 0 at night)
    if 6 <= hour <= 19:
        solar_angle = np.sin((hour - 6) * np.pi / 13)
    else:
        solar_angle = 0.0

    # Weather simulation
    cloud_cover = np.clip(np.random.beta(2, 3) * 100, 0, 100)
    temp        = 15 + 10 * seasonal + np.random.normal(0, 3)
    humidity    = np.clip(50 + 20 * cloud_cover / 100 + np.random.normal(0, 5), 10, 100)
    wind_speed  = np.abs(np.random.normal(3, 2))

    # Solar generation: 5 kW peak system
    max_output  = 5.0
    cloud_factor = 1 - (cloud_cover / 100) * 0.85
    generation  = max_output * solar_angle * seasonal * cloud_factor
    generation  = max(0, generation + np.random.normal(0, 0.05))

    records.append({
        "timestamp":    ts,
        "hour":         hour,
        "day_of_year":  day_of_year,
        "cloud_cover":  round(cloud_cover, 1),
        "temperature":  round(temp, 1),
        "humidity":     round(humidity, 1),
        "wind_speed":   round(wind_speed, 2),
        "solar_kwh":    round(generation, 3)
    })

df = pd.DataFrame(records)
df.to_csv("data/solar_data.csv", index=False)
print(f"   ✅ Generated {len(df)} hourly records → data/solar_data.csv")
print(f"   Peak generation: {df['solar_kwh'].max():.2f} kWh")
print(f"   Daily avg (sunny): {df[df['cloud_cover']<20]['solar_kwh'].mean():.2f} kWh/hr")

# ─────────────────────────────────────────
# 2. FEATURE ENGINEERING
# ─────────────────────────────────────────
print("\n🔧 Engineering features...")
df["sin_hour"]   = np.sin(2 * np.pi * df["hour"] / 24)
df["cos_hour"]   = np.cos(2 * np.pi * df["hour"] / 24)
df["sin_doy"]    = np.sin(2 * np.pi * df["day_of_year"] / 365)
df["cos_doy"]    = np.cos(2 * np.pi * df["day_of_year"] / 365)
df["is_daytime"] = ((df["hour"] >= 6) & (df["hour"] <= 19)).astype(int)

feature_cols = [
    "solar_kwh", "cloud_cover", "temperature", "humidity",
    "wind_speed", "sin_hour", "cos_hour", "sin_doy", "cos_doy", "is_daytime"
]

# ─────────────────────────────────────────
# 3. SCALE + CREATE SEQUENCES
# ─────────────────────────────────────────
scaler = MinMaxScaler()
scaled = scaler.fit_transform(df[feature_cols])

WINDOW   = 48   # 2 days lookback
FORECAST = 24   # Predict next 24 hours

def make_sequences(data, window, forecast):
    X, y = [], []
    for i in range(len(data) - window - forecast):
        X.append(data[i : i + window])
        y.append(data[i + window : i + window + forecast, 0])
    return np.array(X), np.array(y)

X, y = make_sequences(scaled, WINDOW, FORECAST)
split = int(len(X) * 0.8)
X_train, X_test = X[:split], X[split:]
y_train, y_test = y[:split], y[split:]
print(f"   Train: {len(X_train)} | Test: {len(X_test)} sequences")

# ─────────────────────────────────────────
# 4. BUILD BIDIRECTIONAL LSTM
# ─────────────────────────────────────────
print("\n🧠 Building Bidirectional LSTM...")

model = Sequential([
    Bidirectional(LSTM(64, return_sequences=True), input_shape=(WINDOW, len(feature_cols))),
    Dropout(0.2),
    Bidirectional(LSTM(32, return_sequences=False)),
    Dropout(0.2),
    Dense(32, activation="relu"),
    Dense(FORECAST)
])

model.compile(optimizer="adam", loss="mse", metrics=["mae"])
model.summary()

# ─────────────────────────────────────────
# 5. TRAIN
# ─────────────────────────────────────────
print("\n🚀 Training Solar Forecast model...")
history = model.fit(
    X_train, y_train,
    epochs=40, batch_size=32,
    validation_split=0.1,
    callbacks=[EarlyStopping(patience=6, restore_best_weights=True, verbose=1)],
    verbose=1
)

# ─────────────────────────────────────────
# 6. EVALUATE + INVERSE TRANSFORM
# ─────────────────────────────────────────
print("\n📏 Evaluating...")
y_pred_scaled = model.predict(X_test, verbose=0)

def inv_transform(arr):
    n_feat = len(feature_cols)
    out = []
    for row in arr:
        dummy = np.zeros((len(row), n_feat))
        dummy[:, 0] = row
        out.append(scaler.inverse_transform(dummy)[:, 0])
    return np.array(out)

y_pred_kw = inv_transform(y_pred_scaled)
y_true_kw = inv_transform(y_test)
y_pred_kw = np.clip(y_pred_kw, 0, None)

mae  = mean_absolute_error(y_true_kw.flatten(), y_pred_kw.flatten())
rmse = np.sqrt(mean_squared_error(y_true_kw.flatten(), y_pred_kw.flatten()))
print(f"   MAE:  {mae:.4f} kWh")
print(f"   RMSE: {rmse:.4f} kWh")

# ─────────────────────────────────────────
# 7. SOLAR SAVINGS CALCULATOR
# ─────────────────────────────────────────
TARIFF = 0.15  # $/kWh
total_predicted_kwh  = y_pred_kw.sum() / len(X_test) * 365
estimated_annual_savings = total_predicted_kwh * TARIFF
print(f"\n💰 Estimated annual solar generation: {total_predicted_kwh:.0f} kWh")
print(f"   Estimated annual savings: ${estimated_annual_savings:.0f}")

# ─────────────────────────────────────────
# 8. PLOT
# ─────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle("Solar Generation Forecast - Results", fontsize=14, fontweight="bold")

axes[0,0].plot(history.history["loss"],     label="Train Loss", color="gold")
axes[0,0].plot(history.history["val_loss"], label="Val Loss",   color="orange")
axes[0,0].set_title("Training History"); axes[0,0].legend(); axes[0,0].grid(True, alpha=0.3)

# 24h forecast vs actual
for i in range(3):
    hours = range(24)
    axes[0,1].plot(hours, y_true_kw[i], "--", alpha=0.7, label=f"Actual #{i+1}")
    axes[0,1].plot(hours, y_pred_kw[i],       alpha=0.9, label=f"Forecast #{i+1}")
axes[0,1].set_title(f"24h Solar Forecast vs Actual (MAE={mae:.3f} kWh)")
axes[0,1].set_xlabel("Hour"); axes[0,1].set_ylabel("kWh")
axes[0,1].legend(fontsize=7); axes[0,1].grid(True, alpha=0.3)

# Scatter: predicted vs actual
axes[1,0].scatter(y_true_kw.flatten(), y_pred_kw.flatten(), alpha=0.3, s=5, color="steelblue")
lim = max(y_true_kw.max(), y_pred_kw.max())
axes[1,0].plot([0, lim], [0, lim], "r--", label="Perfect prediction")
axes[1,0].set_title("Predicted vs Actual"); axes[1,0].set_xlabel("Actual kWh")
axes[1,0].set_ylabel("Predicted kWh"); axes[1,0].legend(); axes[1,0].grid(True, alpha=0.3)

# Average daily generation profile
avg_by_hour = df.groupby("hour")["solar_kwh"].mean()
axes[1,1].fill_between(avg_by_hour.index, avg_by_hour.values, alpha=0.5, color="gold")
axes[1,1].plot(avg_by_hour.index, avg_by_hour.values, "o-", color="darkorange")
axes[1,1].set_title("Average Hourly Solar Generation Profile")
axes[1,1].set_xlabel("Hour of Day"); axes[1,1].set_ylabel("Avg kWh")
axes[1,1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("outputs/model6_solar_results.png", dpi=150)
print("   📊 Plot saved → outputs/model6_solar_results.png")

model.save("models/solar_model.keras")
import joblib; joblib.dump(scaler, "models/solar_scaler.pkl")
print("✅ Step 7 Complete! Solar forecast model saved.\n")

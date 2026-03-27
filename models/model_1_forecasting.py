"""
Step 2: Energy Forecasting Model (LSTM)
========================================
Predicts next 24 hours of energy consumption
based on historical patterns.

Input:  Past 48 hours of energy data
Output: Next 24 hours forecast
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
os.makedirs("outputs", exist_ok=True)

from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint

print("\n" + "="*50)
print("  STEP 2: ENERGY FORECASTING MODEL (LSTM)")
print("="*50)

# ─────────────────────────────────────────
# 1. LOAD DATA
# ─────────────────────────────────────────
print("\n📂 Loading energy data...")
df = pd.read_csv("data/energy_consumption.csv", parse_dates=["timestamp"])
df = df.sort_values("timestamp").reset_index(drop=True)
print(f"   Loaded {len(df)} records from {df['timestamp'].min()} to {df['timestamp'].max()}")

# ─────────────────────────────────────────
# 2. FEATURE ENGINEERING
# ─────────────────────────────────────────
print("\n🔧 Engineering features...")
df["sin_hour"] = np.sin(2 * np.pi * df["hour"] / 24)
df["cos_hour"] = np.cos(2 * np.pi * df["hour"] / 24)
df["sin_day"]  = np.sin(2 * np.pi * df["day_of_week"] / 7)
df["cos_day"]  = np.cos(2 * np.pi * df["day_of_week"] / 7)

features = ["consumption_kwh", "sin_hour", "cos_hour", "sin_day", "cos_day", "is_weekend"]
print(f"   Features used: {features}")

# ─────────────────────────────────────────
# 3. SCALE DATA
# ─────────────────────────────────────────
scaler = MinMaxScaler()
scaled = scaler.fit_transform(df[features])
consumption_scaler = MinMaxScaler()
consumption_scaler.fit_transform(df[["consumption_kwh"]])

# ─────────────────────────────────────────
# 4. CREATE SEQUENCES
# ─────────────────────────────────────────
WINDOW_SIZE = 48   # Look back 48 hours
FORECAST_STEPS = 24  # Predict next 24 hours

def create_sequences(data, window, forecast):
    X, y = [], []
    for i in range(len(data) - window - forecast):
        X.append(data[i : i + window])
        y.append(data[i + window : i + window + forecast, 0])  # Only consumption
    return np.array(X), np.array(y)

X, y = create_sequences(scaled, WINDOW_SIZE, FORECAST_STEPS)

# Train/Test split (80/20)
split = int(len(X) * 0.8)
X_train, X_test = X[:split], X[split:]
y_train, y_test = y[:split], y[split:]
print(f"\n📊 Dataset: {len(X_train)} train samples, {len(X_test)} test samples")

# ─────────────────────────────────────────
# 5. BUILD LSTM MODEL
# ─────────────────────────────────────────
print("\n🧠 Building LSTM model...")
model = Sequential([
    LSTM(128, return_sequences=True, input_shape=(WINDOW_SIZE, len(features))),
    Dropout(0.2),
    LSTM(64, return_sequences=False),
    Dropout(0.2),
    Dense(32, activation="relu"),
    Dense(FORECAST_STEPS)
])

model.compile(optimizer="adam", loss="mse", metrics=["mae"])
model.summary()

# ─────────────────────────────────────────
# 6. TRAIN MODEL
# ─────────────────────────────────────────
print("\n🚀 Training model...")
callbacks = [
    EarlyStopping(patience=5, restore_best_weights=True, verbose=1),
    ModelCheckpoint("models/forecasting_model.keras", save_best_only=True, verbose=0)
]

history = model.fit(
    X_train, y_train,
    epochs=30,
    batch_size=32,
    validation_split=0.1,
    callbacks=callbacks,
    verbose=1
)

# ─────────────────────────────────────────
# 7. EVALUATE
# ─────────────────────────────────────────
print("\n📏 Evaluating model...")
y_pred_scaled = model.predict(X_test)

# Inverse transform predictions
def inverse_transform(arr, scaler, n_features):
    dummy = np.zeros((arr.shape[0] * arr.shape[1], n_features))
    dummy[:, 0] = arr.flatten()
    return scaler.inverse_transform(dummy)[:, 0].reshape(arr.shape)

y_pred = inverse_transform(y_pred_scaled, scaler, len(features))
y_true = inverse_transform(y_test, scaler, len(features))

mae  = mean_absolute_error(y_true.flatten(), y_pred.flatten())
rmse = np.sqrt(mean_squared_error(y_true.flatten(), y_pred.flatten()))
print(f"   MAE  : {mae:.3f} kWh")
print(f"   RMSE : {rmse:.3f} kWh")

# ─────────────────────────────────────────
# 8. PLOT RESULTS
# ─────────────────────────────────────────
fig, axes = plt.subplots(2, 1, figsize=(14, 10))
fig.suptitle("Energy Forecasting Model - Results", fontsize=14, fontweight="bold")

# Plot 1: Training loss
axes[0].plot(history.history["loss"], label="Train Loss", color="blue")
axes[0].plot(history.history["val_loss"], label="Val Loss", color="orange")
axes[0].set_title("Training History")
axes[0].set_xlabel("Epoch")
axes[0].set_ylabel("Loss (MSE)")
axes[0].legend()
axes[0].grid(True, alpha=0.3)

# Plot 2: Forecast vs Actual (first 3 test samples)
sample_hours = list(range(24))
for i in range(3):
    axes[1].plot(sample_hours, y_true[i], label=f"Actual #{i+1}", linestyle="--", alpha=0.7)
    axes[1].plot(sample_hours, y_pred[i], label=f"Forecast #{i+1}")
axes[1].set_title(f"24-Hour Forecast vs Actual  (MAE={mae:.2f} kWh)")
axes[1].set_xlabel("Hour")
axes[1].set_ylabel("Energy (kWh)")
axes[1].legend(ncol=2, fontsize=8)
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("outputs/model1_forecasting_results.png", dpi=150)
print("   📊 Plot saved → outputs/model1_forecasting_results.png")

# Save model
model.save("models/forecasting_model.keras")
print("\n✅ Step 2 Complete! Forecasting model saved. Run model_2_anomaly.py next.\n")

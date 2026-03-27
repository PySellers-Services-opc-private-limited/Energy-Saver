"""
Step 3: Anomaly Detection Model (Autoencoder)
===============================================
Detects unusual energy consumption patterns
(energy waste, equipment faults, unusual spikes).

How it works:
  - Trains on NORMAL data only
  - High reconstruction error = ANOMALY detected!
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
os.makedirs("outputs", exist_ok=True)
os.makedirs("models", exist_ok=True)

from sklearn.preprocessing import MinMaxScaler

import tensorflow as tf
from tensorflow.keras.models import Model
from tensorflow.keras.layers import (Input, LSTM, Dense, RepeatVector,
                                      TimeDistributed, Dropout)
from tensorflow.keras.callbacks import EarlyStopping

print("\n" + "="*50)
print("  STEP 3: ANOMALY DETECTION (AUTOENCODER)")
print("="*50)

# ─────────────────────────────────────────
# 1. LOAD DATA
# ─────────────────────────────────────────
print("\n📂 Loading energy data...")
df = pd.read_csv("data/energy_consumption.csv", parse_dates=["timestamp"])
df = df.sort_values("timestamp").reset_index(drop=True)

# ─────────────────────────────────────────
# 2. SCALE & CREATE WINDOWS
# ─────────────────────────────────────────
print("\n🔧 Preparing sequences...")
scaler = MinMaxScaler()
scaled = scaler.fit_transform(df[["consumption_kwh"]])

WINDOW = 24  # 24-hour windows

def create_windows(data, window):
    return np.array([data[i:i+window] for i in range(len(data) - window)])

windows = create_windows(scaled, WINDOW)
print(f"   Created {len(windows)} windows of {WINDOW} hours each")

# Use first 80% (normal data) for training
# The autoencoder only learns what NORMAL looks like
split = int(len(windows) * 0.8)
train_data = windows[:split]
test_data  = windows[split:]
print(f"   Train: {len(train_data)} windows | Test: {len(test_data)} windows")

# ─────────────────────────────────────────
# 3. BUILD AUTOENCODER
# ─────────────────────────────────────────
print("\n🧠 Building LSTM Autoencoder...")

inputs = Input(shape=(WINDOW, 1))

# --- ENCODER (compress to small representation) ---
encoded = LSTM(32, return_sequences=False, activation="tanh")(inputs)
encoded = Dropout(0.2)(encoded)

# --- DECODER (reconstruct original sequence) ---
decoded = RepeatVector(WINDOW)(encoded)
decoded = LSTM(32, return_sequences=True, activation="tanh")(decoded)
decoded = Dropout(0.2)(decoded)
decoded = TimeDistributed(Dense(1))(decoded)

autoencoder = Model(inputs, decoded)
autoencoder.compile(optimizer="adam", loss="mse")
autoencoder.summary()

# ─────────────────────────────────────────
# 4. TRAIN
# ─────────────────────────────────────────
print("\n🚀 Training Autoencoder on normal data...")
callbacks = [EarlyStopping(patience=5, restore_best_weights=True, verbose=1)]

history = autoencoder.fit(
    train_data, train_data,   # Input = Output (reconstruction task)
    epochs=30,
    batch_size=32,
    validation_split=0.1,
    callbacks=callbacks,
    verbose=1
)

# ─────────────────────────────────────────
# 5. COMPUTE RECONSTRUCTION ERROR
# ─────────────────────────────────────────
print("\n🔍 Computing reconstruction errors...")
train_pred = autoencoder.predict(train_data, verbose=0)
test_pred  = autoencoder.predict(test_data,  verbose=0)

# Mean Squared Error per window
train_mse = np.mean(np.power(train_data - train_pred, 2), axis=(1, 2))
test_mse  = np.mean(np.power(test_data  - test_pred,  2), axis=(1, 2))

# Set threshold at 95th percentile of TRAINING errors
threshold = np.percentile(train_mse, 95)
print(f"   Anomaly threshold (95th percentile): {threshold:.6f}")

anomalies = test_mse > threshold
n_anomalies = anomalies.sum()
print(f"   Anomalies detected in test set: {n_anomalies} / {len(test_data)} windows ({100*n_anomalies/len(test_data):.1f}%)")

# ─────────────────────────────────────────
# 6. PLOT RESULTS
# ─────────────────────────────────────────
fig, axes = plt.subplots(3, 1, figsize=(14, 12))
fig.suptitle("Anomaly Detection Model - Results", fontsize=14, fontweight="bold")

# Plot 1: Training loss
axes[0].plot(history.history["loss"], label="Train Loss", color="blue")
axes[0].plot(history.history["val_loss"], label="Val Loss", color="orange")
axes[0].set_title("Autoencoder Training History")
axes[0].set_xlabel("Epoch"); axes[0].set_ylabel("Loss (MSE)")
axes[0].legend(); axes[0].grid(True, alpha=0.3)

# Plot 2: Reconstruction error distribution
axes[1].hist(train_mse, bins=50, alpha=0.6, label="Train (Normal)", color="green")
axes[1].hist(test_mse,  bins=50, alpha=0.6, label="Test",           color="blue")
axes[1].axvline(threshold, color="red", linestyle="--", linewidth=2,
                label=f"Threshold = {threshold:.5f}")
axes[1].set_title("Reconstruction Error Distribution")
axes[1].set_xlabel("MSE"); axes[1].set_ylabel("Count")
axes[1].legend(); axes[1].grid(True, alpha=0.3)

# Plot 3: Anomaly timeline
axes[2].plot(test_mse, label="Reconstruction Error", color="blue", alpha=0.7)
axes[2].axhline(threshold, color="red", linestyle="--", linewidth=2, label="Threshold")
anomaly_idx = np.where(anomalies)[0]
axes[2].scatter(anomaly_idx, test_mse[anomaly_idx],
                color="red", zorder=5, s=60, label=f"Anomalies ({n_anomalies})")
axes[2].set_title("Anomaly Detection Timeline")
axes[2].set_xlabel("Window Index"); axes[2].set_ylabel("Reconstruction Error")
axes[2].legend(); axes[2].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("outputs/model2_anomaly_results.png", dpi=150)
print("   📊 Plot saved → outputs/model2_anomaly_results.png")

# Save model & threshold
autoencoder.save("models/anomaly_model.keras")
np.save("models/anomaly_threshold.npy", threshold)
print("\n✅ Step 3 Complete! Anomaly model saved. Run model_3_occupancy.py next.\n")

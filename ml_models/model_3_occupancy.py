"""
Step 4: Occupancy Prediction Model (Dense Neural Network)
===========================================================
Predicts if a room is occupied (1) or empty (0)
using sensor data: temperature, humidity, CO2, light.

This model feeds into the HVAC optimization model.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
os.makedirs("outputs", exist_ok=True)
os.makedirs("models", exist_ok=True)

from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (classification_report, confusion_matrix,
                              roc_curve, auc)
from sklearn.utils.class_weight import compute_class_weight

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, BatchNormalization
from tensorflow.keras.callbacks import EarlyStopping

print("\n" + "="*50)
print("  STEP 4: OCCUPANCY PREDICTION MODEL")
print("="*50)

# ─────────────────────────────────────────
# 1. LOAD DATA
# ─────────────────────────────────────────
print("\n📂 Loading occupancy sensor data...")
df = pd.read_csv("data/occupancy_data.csv", parse_dates=["timestamp"])
df = df.sort_values("timestamp").reset_index(drop=True)

print(f"   Records: {len(df)}")
print(f"   Occupied: {df['occupied'].sum()} ({100*df['occupied'].mean():.1f}%)")
print(f"   Empty:    {(1-df['occupied']).sum()} ({100*(1-df['occupied'].mean()):.1f}%)")

# ─────────────────────────────────────────
# 2. FEATURE ENGINEERING
# ─────────────────────────────────────────
print("\n🔧 Engineering features...")

# Add rate-of-change features (sensor trends matter!)
df["temp_diff"] = df["temperature"].diff().fillna(0)
df["co2_diff"]  = df["co2"].diff().fillna(0)
df["light_diff"] = df["light"].diff().fillna(0)

# Time-based features
df["sin_hour"] = np.sin(2 * np.pi * df["hour"] / 24)
df["cos_hour"] = np.cos(2 * np.pi * df["hour"] / 24)

feature_cols = [
    "temperature", "humidity", "co2", "light",
    "temp_diff", "co2_diff", "light_diff",
    "sin_hour", "cos_hour"
]
print(f"   Features: {feature_cols}")

X = df[feature_cols].values
y = df["occupied"].values

# ─────────────────────────────────────────
# 3. SCALE FEATURES
# ─────────────────────────────────────────
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Train/test split (temporal — no data leakage!)
split = int(len(X_scaled) * 0.8)
X_train, X_test = X_scaled[:split], X_scaled[split:]
y_train, y_test = y[:split], y[split:]

# Handle class imbalance
class_weights = compute_class_weight("balanced", classes=np.unique(y_train), y=y_train)
class_weight_dict = {i: w for i, w in enumerate(class_weights)}
print(f"\n   Class weights: {class_weight_dict}")

# ─────────────────────────────────────────
# 4. BUILD MODEL
# ─────────────────────────────────────────
print("\n🧠 Building Dense Neural Network...")

model = Sequential([
    Dense(128, activation="relu", input_shape=(len(feature_cols),)),
    BatchNormalization(),
    Dropout(0.3),

    Dense(64, activation="relu"),
    BatchNormalization(),
    Dropout(0.3),

    Dense(32, activation="relu"),
    BatchNormalization(),
    Dropout(0.2),

    Dense(1, activation="sigmoid")   # 0=empty, 1=occupied
])

model.compile(
    optimizer="adam",
    loss="binary_crossentropy",
    metrics=["accuracy", tf.keras.metrics.AUC(name="auc"),
             tf.keras.metrics.Precision(name="precision"),
             tf.keras.metrics.Recall(name="recall")]
)
model.summary()

# ─────────────────────────────────────────
# 5. TRAIN
# ─────────────────────────────────────────
print("\n🚀 Training Occupancy model...")
callbacks = [EarlyStopping(patience=5, restore_best_weights=True, verbose=1)]

history = model.fit(
    X_train, y_train,
    epochs=30,
    batch_size=64,
    validation_split=0.1,
    class_weight=class_weight_dict,
    callbacks=callbacks,
    verbose=1
)

# ─────────────────────────────────────────
# 6. EVALUATE
# ─────────────────────────────────────────
print("\n📏 Evaluating model...")
y_pred_prob = model.predict(X_test, verbose=0).flatten()
y_pred = (y_pred_prob > 0.5).astype(int)

print("\nClassification Report:")
print(classification_report(y_test, y_pred, target_names=["Empty", "Occupied"]))

# ─────────────────────────────────────────
# 7. PLOT RESULTS
# ─────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle("Occupancy Prediction Model - Results", fontsize=14, fontweight="bold")

# Plot 1: Training accuracy
axes[0,0].plot(history.history["accuracy"],     label="Train Acc", color="blue")
axes[0,0].plot(history.history["val_accuracy"], label="Val Acc",   color="orange")
axes[0,0].set_title("Training Accuracy"); axes[0,0].set_xlabel("Epoch")
axes[0,0].legend(); axes[0,0].grid(True, alpha=0.3)

# Plot 2: Training loss
axes[0,1].plot(history.history["loss"],     label="Train Loss", color="blue")
axes[0,1].plot(history.history["val_loss"], label="Val Loss",   color="orange")
axes[0,1].set_title("Training Loss"); axes[0,1].set_xlabel("Epoch")
axes[0,1].legend(); axes[0,1].grid(True, alpha=0.3)

# Plot 3: Confusion matrix
cm = confusion_matrix(y_test, y_pred)
im = axes[1,0].imshow(cm, cmap="Blues")
axes[1,0].set_title("Confusion Matrix")
axes[1,0].set_xticks([0,1]); axes[1,0].set_yticks([0,1])
axes[1,0].set_xticklabels(["Empty","Occupied"]); axes[1,0].set_yticklabels(["Empty","Occupied"])
for i in range(2):
    for j in range(2):
        axes[1,0].text(j, i, str(cm[i,j]), ha="center", va="center",
                       color="white" if cm[i,j] > cm.max()/2 else "black", fontsize=14)

# Plot 4: ROC Curve
fpr, tpr, _ = roc_curve(y_test, y_pred_prob)
roc_auc = auc(fpr, tpr)
axes[1,1].plot(fpr, tpr, color="blue", label=f"AUC = {roc_auc:.3f}")
axes[1,1].plot([0,1], [0,1], "k--", alpha=0.5)
axes[1,1].set_title("ROC Curve"); axes[1,1].set_xlabel("False Positive Rate")
axes[1,1].set_ylabel("True Positive Rate"); axes[1,1].legend()
axes[1,1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("outputs/model3_occupancy_results.png", dpi=150)
print("   📊 Plot saved → outputs/model3_occupancy_results.png")

# Save model & scaler
model.save("models/occupancy_model.keras")
import joblib
joblib.dump(scaler, "models/occupancy_scaler.pkl")
print("\n✅ Step 4 Complete! Occupancy model saved. Run model_4_hvac.py next.\n")

"""
Step 6: Appliance Fingerprinting (CNN)
========================================
Identifies WHICH appliance is running using only the
total power draw signal — no individual sensors needed!

How it works:
  - Each appliance has a unique power "signature"
  - A CNN learns to recognize these patterns
  - Input: 60-second power reading window
  - Output: Appliance name + confidence

Appliances detected:
  0 = Idle / Background
  1 = Refrigerator
  2 = Washing Machine
  3 = Microwave
  4 = Air Conditioner
  5 = EV Charger
  6 = Dishwasher
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
os.makedirs("outputs", exist_ok=True)
os.makedirs("models",  exist_ok=True)

from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import (Conv1D, MaxPooling1D, Dense,
                                      Dropout, Flatten, BatchNormalization)
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.utils import to_categorical

print("\n" + "="*55)
print("  STEP 6: APPLIANCE FINGERPRINTING (CNN)")
print("="*55)

# ─────────────────────────────────────────
# 1. GENERATE APPLIANCE POWER SIGNATURES
# ─────────────────────────────────────────
print("\n⚡ Generating appliance power signatures...")

np.random.seed(42)
WINDOW = 60       # 60 time steps per sample
SAMPLES = 300     # samples per appliance

APPLIANCES = {
    "Idle":            {"base": 0.15, "noise": 0.05, "pattern": "flat"},
    "Refrigerator":    {"base": 0.15, "noise": 0.04, "pattern": "cycle"},
    "WashingMachine":  {"base": 0.50, "noise": 0.15, "pattern": "oscillate"},
    "Microwave":       {"base": 1.20, "noise": 0.08, "pattern": "flat_high"},
    "AirConditioner":  {"base": 1.50, "noise": 0.20, "pattern": "ramp"},
    "EVCharger":       {"base": 3.30, "noise": 0.10, "pattern": "flat_high"},
    "Dishwasher":      {"base": 0.80, "noise": 0.25, "pattern": "stepped"},
}

def generate_signature(appliance, props, n_samples, window):
    signals = []
    for _ in range(n_samples):
        t = np.linspace(0, 1, window)
        base  = props["base"]
        noise = props["noise"]
        pat   = props["pattern"]

        if pat == "flat":
            sig = base + np.random.normal(0, noise, window)
        elif pat == "flat_high":
            sig = base + np.random.normal(0, noise, window)
        elif pat == "cycle":
            # Compressor on/off cycle
            cycle = (np.sin(2 * np.pi * 3 * t) > 0).astype(float)
            sig = base * 0.3 + cycle * base + np.random.normal(0, noise, window)
        elif pat == "oscillate":
            sig = base + 0.3 * np.sin(2 * np.pi * 1.5 * t) + np.random.normal(0, noise, window)
        elif pat == "ramp":
            ramp = np.linspace(0, base, window // 3)
            steady = np.full(window - window // 3, base)
            sig = np.concatenate([ramp, steady]) + np.random.normal(0, noise, window)
        elif pat == "stepped":
            steps = np.zeros(window)
            for step_val, start, end in [(0.2,0,20),(0.8,20,40),(0.5,40,60)]:
                steps[start:end] = step_val
            sig = steps + np.random.normal(0, noise, window)
        else:
            sig = base + np.random.normal(0, noise, window)

        signals.append(np.clip(sig, 0, None))
    return np.array(signals)

X_list, y_list = [], []
for name, props in APPLIANCES.items():
    sigs = generate_signature(name, props, SAMPLES, WINDOW)
    X_list.append(sigs)
    y_list.extend([name] * SAMPLES)

X = np.vstack(X_list)
y = np.array(y_list)

# Encode labels
le = LabelEncoder()
y_enc = le.fit_transform(y)
y_cat = to_categorical(y_enc)
n_classes = len(le.classes_)

# Reshape for CNN: (samples, timesteps, channels)
X = X.reshape(X.shape[0], WINDOW, 1)

# Normalize per sample
X = (X - X.min(axis=1, keepdims=True)) / (X.max(axis=1, keepdims=True) - X.min(axis=1, keepdims=True) + 1e-8)

# Shuffle and split
idx = np.random.permutation(len(X))
X, y_cat, y_enc = X[idx], y_cat[idx], y_enc[idx]
split = int(len(X) * 0.8)
X_train, X_test = X[:split], X[split:]
y_train, y_test = y_cat[:split], y_cat[split:]
y_test_labels   = y_enc[split:]

print(f"   Dataset: {len(X_train)} train | {len(X_test)} test")
print(f"   Classes: {list(le.classes_)}")

# ─────────────────────────────────────────
# 2. BUILD CNN MODEL
# ─────────────────────────────────────────
print("\n🧠 Building 1D CNN model...")

model = Sequential([
    # Block 1
    Conv1D(32, kernel_size=5, activation="relu", padding="same", input_shape=(WINDOW, 1)),
    BatchNormalization(),
    MaxPooling1D(pool_size=2),
    Dropout(0.2),

    # Block 2
    Conv1D(64, kernel_size=3, activation="relu", padding="same"),
    BatchNormalization(),
    MaxPooling1D(pool_size=2),
    Dropout(0.2),

    # Block 3
    Conv1D(128, kernel_size=3, activation="relu", padding="same"),
    BatchNormalization(),
    Dropout(0.3),

    # Classifier head
    Flatten(),
    Dense(64, activation="relu"),
    Dropout(0.3),
    Dense(n_classes, activation="softmax")
])

model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
model.summary()

# ─────────────────────────────────────────
# 3. TRAIN
# ─────────────────────────────────────────
print("\n🚀 Training CNN...")
history = model.fit(
    X_train, y_train,
    epochs=40, batch_size=32,
    validation_split=0.1,
    callbacks=[EarlyStopping(patience=6, restore_best_weights=True, verbose=1)],
    verbose=1
)

# ─────────────────────────────────────────
# 4. EVALUATE
# ─────────────────────────────────────────
print("\n📏 Evaluating...")
y_pred_prob = model.predict(X_test, verbose=0)
y_pred      = np.argmax(y_pred_prob, axis=1)

print("\nClassification Report:")
print(classification_report(y_test_labels, y_pred, target_names=le.classes_))

# ─────────────────────────────────────────
# 5. DEMO: REAL-TIME IDENTIFICATION
# ─────────────────────────────────────────
print("\n🔍 Live Appliance Detection Demo:")
print("─" * 45)
for appliance_name in list(APPLIANCES.keys())[:4]:
    props = APPLIANCES[appliance_name]
    sample = generate_signature(appliance_name, props, 1, WINDOW)
    sample = sample.reshape(1, WINDOW, 1)
    sample = (sample - sample.min()) / (sample.max() - sample.min() + 1e-8)
    probs = model.predict(sample, verbose=0)[0]
    pred_idx  = np.argmax(probs)
    pred_name = le.classes_[pred_idx]
    confidence = probs[pred_idx] * 100
    status = "✅" if pred_name == appliance_name else "❌"
    print(f"  {status} Actual: {appliance_name:<18} → Predicted: {pred_name:<18} ({confidence:.1f}%)")

# ─────────────────────────────────────────
# 6. PLOT
# ─────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle("Appliance Fingerprinting (CNN) - Results", fontsize=14, fontweight="bold")

# Plot 1: Training curves
axes[0,0].plot(history.history["accuracy"],     label="Train Acc", color="blue")
axes[0,0].plot(history.history["val_accuracy"], label="Val Acc",   color="orange")
axes[0,0].set_title("Training Accuracy"); axes[0,0].legend(); axes[0,0].grid(True, alpha=0.3)

# Plot 2: Confusion matrix
cm = confusion_matrix(y_test_labels, y_pred)
im = axes[0,1].imshow(cm, cmap="Blues")
axes[0,1].set_xticks(range(n_classes)); axes[0,1].set_yticks(range(n_classes))
axes[0,1].set_xticklabels(le.classes_, rotation=45, ha="right", fontsize=8)
axes[0,1].set_yticklabels(le.classes_, fontsize=8)
axes[0,1].set_title("Confusion Matrix")
for i in range(n_classes):
    for j in range(n_classes):
        axes[0,1].text(j, i, str(cm[i,j]), ha="center", va="center",
                       color="white" if cm[i,j] > cm.max()/2 else "black", fontsize=9)

# Plot 3: Power signatures per appliance
colors = plt.cm.tab10(np.linspace(0, 1, len(APPLIANCES)))
for idx_a, (name, props) in enumerate(APPLIANCES.items()):
    sig = generate_signature(name, props, 1, WINDOW)[0]
    axes[1,0].plot(sig, label=name, color=colors[idx_a], alpha=0.85)
axes[1,0].set_title("Appliance Power Signatures")
axes[1,0].set_xlabel("Time (seconds)"); axes[1,0].set_ylabel("Power (kW)")
axes[1,0].legend(fontsize=7); axes[1,0].grid(True, alpha=0.3)

# Plot 4: Confidence bar for one sample
sample_name = "AirConditioner"
sample = generate_signature(sample_name, APPLIANCES[sample_name], 1, WINDOW)
sample = sample.reshape(1, WINDOW, 1)
sample = (sample - sample.min()) / (sample.max() - sample.min() + 1e-8)
probs = model.predict(sample, verbose=0)[0]
bar_colors = ["green" if c == np.argmax(probs) else "steelblue" for c in range(n_classes)]
axes[1,1].barh(le.classes_, probs * 100, color=bar_colors, alpha=0.8)
axes[1,1].set_title(f'Prediction Confidence (Input: {sample_name})')
axes[1,1].set_xlabel("Confidence (%)"); axes[1,1].grid(True, alpha=0.3, axis="x")

plt.tight_layout()
plt.savefig("outputs/model5_fingerprinting_results.png", dpi=150)
print("\n   📊 Plot saved → outputs/model5_fingerprinting_results.png")

model.save("models/fingerprinting_model.keras")
import joblib; joblib.dump(le, "models/fingerprinting_encoder.pkl")
print("✅ Step 6 Complete! Appliance fingerprinting model saved.\n")

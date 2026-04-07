"""
Step 9: Monthly Bill Predictor (Neural Network + Regression)
==============================================================
Predicts your electricity bill for the CURRENT month
using mid-month data — giving you time to adjust behavior!

Features used:
  - Days elapsed this month
  - Average daily consumption so far (kWh)
  - Peak hour usage ratio
  - Weekend vs weekday usage pattern
  - Month of year (seasonal factor)
  - Rolling 7-day trend (going up/down?)
  - Temperature (affects heating/cooling load)

Output:
  - Predicted monthly bill ($)
  - Confidence interval (low / high estimate)
  - Daily budget recommendation to stay on target
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
os.makedirs("outputs", exist_ok=True)
os.makedirs("models",  exist_ok=True)
os.makedirs("data",    exist_ok=True)

from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

import tensorflow as tf
from tensorflow.keras.models import Sequential, Model
from tensorflow.keras.layers import Dense, Dropout, BatchNormalization, Input
from tensorflow.keras.callbacks import EarlyStopping

print("\n" + "="*55)
print("  STEP 9: MONTHLY BILL PREDICTOR")
print("="*55)

# ─────────────────────────────────────────
# 1. GENERATE MONTHLY BILLING DATASET
# ─────────────────────────────────────────
print("\n💰 Generating monthly billing dataset...")
np.random.seed(42)

RATE_PER_KWH   = 0.14    # Average blended rate
FIXED_CHARGE   = 12.00   # Monthly fixed/service charge
N_MONTHS       = 500     # Synthetic training months

records = []

for _ in range(N_MONTHS):
    month          = np.random.randint(1, 13)
    days_elapsed   = np.random.randint(5, 28)

    # Seasonal base consumption
    seasonal = 1.0 + 0.35 * np.cos((month - 1) * 2 * np.pi / 12)
    base_daily_kwh = 18 + 8 * seasonal + np.random.normal(0, 2)

    avg_daily_kwh    = base_daily_kwh * np.random.uniform(0.85, 1.15)
    peak_ratio       = np.random.uniform(0.25, 0.55)      # % of usage in peak hours
    weekend_ratio    = np.random.uniform(0.30, 0.55)      # % used on weekends
    rolling_7d_trend = np.random.normal(0, 1.5)           # kWh/day change over 7 days
    avg_temp         = 10 + 12 * np.cos((month - 7) * 2 * np.pi / 12) + np.random.normal(0, 3)
    days_in_month    = 30 if month in [4,6,9,11] else (28 if month == 2 else 31)

    # Predict full month based on trend
    remaining_days = days_in_month - days_elapsed
    projected_remaining = (avg_daily_kwh + rolling_7d_trend * 0.5) * remaining_days
    actual_full_month_kwh = avg_daily_kwh * days_elapsed + projected_remaining + np.random.normal(0, 5)
    actual_bill = FIXED_CHARGE + actual_full_month_kwh * RATE_PER_KWH

    records.append({
        "month":             month,
        "days_elapsed":      days_elapsed,
        "avg_daily_kwh":     round(avg_daily_kwh, 2),
        "peak_ratio":        round(peak_ratio, 3),
        "weekend_ratio":     round(weekend_ratio, 3),
        "rolling_7d_trend":  round(rolling_7d_trend, 2),
        "avg_temp":          round(avg_temp, 1),
        "days_in_month":     days_in_month,
        "pct_month_elapsed": round(days_elapsed / days_in_month, 3),
        "kwh_so_far":        round(avg_daily_kwh * days_elapsed, 1),
        "actual_bill":       round(actual_bill, 2)
    })

df = pd.DataFrame(records)
df.to_csv("data/billing_data.csv", index=False)
print(f"   ✅ Generated {len(df)} monthly billing records")
print(f"   Avg bill: ${df['actual_bill'].mean():.2f} | Range: ${df['actual_bill'].min():.2f}–${df['actual_bill'].max():.2f}")

# ─────────────────────────────────────────
# 2. FEATURE ENGINEERING
# ─────────────────────────────────────────
print("\n🔧 Engineering features...")
df["sin_month"]    = np.sin(2 * np.pi * df["month"] / 12)
df["cos_month"]    = np.cos(2 * np.pi * df["month"] / 12)
df["kwh_per_day"]  = df["kwh_so_far"] / df["days_elapsed"]
df["projected_kwh"] = df["avg_daily_kwh"] * df["days_in_month"]

feature_cols = [
    "days_elapsed", "avg_daily_kwh", "peak_ratio", "weekend_ratio",
    "rolling_7d_trend", "avg_temp", "pct_month_elapsed",
    "kwh_so_far", "sin_month", "cos_month", "projected_kwh"
]

X = df[feature_cols].values
y = df["actual_bill"].values

# ─────────────────────────────────────────
# 3. SCALE + SPLIT
# ─────────────────────────────────────────
scaler_X = StandardScaler()
scaler_y = StandardScaler()

X_scaled = scaler_X.fit_transform(X)
y_scaled = scaler_y.fit_transform(y.reshape(-1, 1)).flatten()

X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y_scaled, test_size=0.2, random_state=42)
y_test_actual = scaler_y.inverse_transform(y_test.reshape(-1,1)).flatten()

# ─────────────────────────────────────────
# 4. BUILD NEURAL NETWORK WITH UNCERTAINTY
# ─────────────────────────────────────────
print("\n🧠 Building Bill Predictor NN (with uncertainty)...")

# Main prediction model
model = Sequential([
    Dense(128, activation="relu", input_shape=(len(feature_cols),)),
    BatchNormalization(), Dropout(0.2),
    Dense(64,  activation="relu"),
    BatchNormalization(), Dropout(0.2),
    Dense(32,  activation="relu"),
    Dense(1)
])
model.compile(optimizer="adam", loss="mse", metrics=["mae"])
model.summary()

# ─────────────────────────────────────────
# 5. TRAIN
# ─────────────────────────────────────────
print("\n🚀 Training Bill Predictor...")
history = model.fit(
    X_train, y_train,
    epochs=100, batch_size=32,
    validation_split=0.1,
    callbacks=[EarlyStopping(patience=10, restore_best_weights=True, verbose=1)],
    verbose=1
)

# ─────────────────────────────────────────
# 6. EVALUATE
# ─────────────────────────────────────────
print("\n📏 Evaluating...")
y_pred_scaled = model.predict(X_test, verbose=0).flatten()
y_pred_actual = scaler_y.inverse_transform(y_pred_scaled.reshape(-1,1)).flatten()

mae = mean_absolute_error(y_test_actual, y_pred_actual)
r2  = r2_score(y_test_actual, y_pred_actual)
print(f"   MAE: ${mae:.2f}  |  R²: {r2:.4f}")

# ─────────────────────────────────────────
# 7. UNCERTAINTY ESTIMATION (MC Dropout)
# ─────────────────────────────────────────
def predict_with_uncertainty(X_input, n_iterations=50):
    """Monte Carlo Dropout for confidence intervals"""
    preds = []
    for _ in range(n_iterations):
        p = model(X_input, training=True).numpy().flatten()
        preds.append(scaler_y.inverse_transform(p.reshape(-1,1)).flatten())
    preds = np.array(preds)
    return preds.mean(axis=0), preds.std(axis=0)

# ─────────────────────────────────────────
# 8. LIVE DEMO: MID-MONTH PREDICTION
# ─────────────────────────────────────────
print("\n🔮 Mid-Month Bill Prediction Demo:")
print("─" * 55)

demo_scenarios = [
    {"label": "Normal Month (Day 15)",  "month":3, "days_elapsed":15, "avg_daily_kwh":18, "peak_ratio":0.38, "weekend_ratio":0.40, "rolling_7d_trend":0.2,  "avg_temp":12, "days_in_month":31},
    {"label": "High Usage (Day 10)",    "month":7, "days_elapsed":10, "avg_daily_kwh":28, "peak_ratio":0.50, "weekend_ratio":0.45, "rolling_7d_trend":2.5,  "avg_temp":32, "days_in_month":31},
    {"label": "Low Usage (Day 20)",     "month":5, "days_elapsed":20, "avg_daily_kwh":12, "peak_ratio":0.28, "weekend_ratio":0.35, "rolling_7d_trend":-0.5, "avg_temp":18, "days_in_month":31},
]

BUDGET_TARGET = 80.0  # User's monthly budget goal

for scenario in demo_scenarios:
    label = scenario.pop("label")
    d = scenario
    d["pct_month_elapsed"] = d["days_elapsed"] / d["days_in_month"]
    d["kwh_so_far"]        = d["avg_daily_kwh"] * d["days_elapsed"]
    d["projected_kwh"]     = d["avg_daily_kwh"] * d["days_in_month"]
    d["sin_month"]         = np.sin(2 * np.pi * d["month"] / 12)
    d["cos_month"]         = np.cos(2 * np.pi * d["month"] / 12)

    row = np.array([[d[f] for f in feature_cols]])
    row_scaled = scaler_X.transform(row)

    mean_pred, std_pred = predict_with_uncertainty(row_scaled)
    low_est  = mean_pred[0] - 1.96 * std_pred[0]
    high_est = mean_pred[0] + 1.96 * std_pred[0]

    remaining_days = d["days_in_month"] - d["days_elapsed"]
    budget_remaining = BUDGET_TARGET - FIXED_CHARGE - (d["kwh_so_far"] * RATE_PER_KWH)
    daily_budget = budget_remaining / max(remaining_days, 1)
    max_daily_kwh = daily_budget / RATE_PER_KWH

    print(f"\n  📅 {label}")
    print(f"     Predicted bill:  ${mean_pred[0]:.2f}  (95% CI: ${low_est:.2f}–${high_est:.2f})")
    print(f"     Status:          {'⚠️  OVER BUDGET' if mean_pred[0] > BUDGET_TARGET else '✅ ON TRACK'}")
    print(f"     Budget target:   ${BUDGET_TARGET:.2f}/month")
    print(f"     Daily allowance: ${daily_budget:.2f}/day → max {max_daily_kwh:.1f} kWh/day")

# ─────────────────────────────────────────
# 9. PLOT
# ─────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle("Monthly Bill Predictor - Results", fontsize=14, fontweight="bold")

axes[0,0].plot(history.history["loss"],     label="Train Loss", color="purple")
axes[0,0].plot(history.history["val_loss"], label="Val Loss",   color="violet")
axes[0,0].set_title("Training History"); axes[0,0].legend(); axes[0,0].grid(True, alpha=0.3)

axes[0,1].scatter(y_test_actual, y_pred_actual, alpha=0.5, color="purple", s=20)
lim = max(y_test_actual.max(), y_pred_actual.max())
axes[0,1].plot([0,lim],[0,lim], "r--", label="Perfect")
axes[0,1].set_title(f"Predicted vs Actual Bill (R²={r2:.3f})")
axes[0,1].set_xlabel("Actual ($)"); axes[0,1].set_ylabel("Predicted ($)")
axes[0,1].legend(); axes[0,1].grid(True, alpha=0.3)

errors = y_pred_actual - y_test_actual
axes[1,0].hist(errors, bins=30, color="purple", alpha=0.7, edgecolor="white")
axes[1,0].axvline(0, color="red", linestyle="--")
axes[1,0].axvline(mae,  color="orange", linestyle="--", label=f"MAE = ${mae:.2f}")
axes[1,0].axvline(-mae, color="orange", linestyle="--")
axes[1,0].set_title("Prediction Error Distribution")
axes[1,0].set_xlabel("Error ($)"); axes[1,0].set_ylabel("Count")
axes[1,0].legend(); axes[1,0].grid(True, alpha=0.3)

monthly_avg = df.groupby("month")["actual_bill"].mean()
axes[1,1].bar(monthly_avg.index, monthly_avg.values, color="purple", alpha=0.7)
axes[1,1].set_xticks(range(1,13))
axes[1,1].set_xticklabels(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], rotation=45, fontsize=8)
axes[1,1].set_title("Average Bill by Month (Seasonal Pattern)")
axes[1,1].set_ylabel("Average Bill ($)"); axes[1,1].grid(True, alpha=0.3, axis="y")

plt.tight_layout()
plt.savefig("outputs/model8_bill_predictor_results.png", dpi=150)
print("\n   📊 Plot saved → outputs/model8_bill_predictor_results.png")

model.save("models/bill_predictor_model.keras")
import joblib
joblib.dump(scaler_X, "models/bill_scaler_X.pkl")
joblib.dump(scaler_y, "models/bill_scaler_y.pkl")
print("✅ Step 9 Complete! Bill predictor model saved.\n")

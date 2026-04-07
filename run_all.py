"""
🚀 Energy Saver AI - Complete Pipeline Runner
===============================================
Run this file to execute ALL steps in sequence:

  Step 1: Generate sample data
  Step 2: Train Energy Forecasting model (LSTM)
  Step 3: Train Anomaly Detection model (Autoencoder)
  Step 4: Train Occupancy Prediction model (Dense NN)
  Step 5: Run HVAC Optimization system

Usage:
  python run_all.py
"""

import os
import sys
import time
import subprocess

os.makedirs("data",       exist_ok=True)
os.makedirs("ml_models",  exist_ok=True)
os.makedirs("outputs",    exist_ok=True)

STEPS = [
    ("Step 1: Generate Data",               "data/generate_data.py"),
    ("Step 2: Energy Forecasting (LSTM)",   "ml_models/model_1_forecasting.py"),
    ("Step 3: Anomaly Detection",           "ml_models/model_2_anomaly.py"),
    ("Step 4: Occupancy Prediction",        "ml_models/model_3_occupancy.py"),
    ("Step 5: HVAC Optimization",           "ml_models/model_4_hvac.py"),
    ("Step 6: Appliance Fingerprinting",    "ml_models/model_5_appliance_fingerprinting.py"),
    ("Step 7: Solar Generation Forecast",   "ml_models/model_6_solar_forecast.py"),
    ("Step 8: EV Charging Optimizer",       "ml_models/model_7_ev_optimizer.py"),
    ("Step 9: Monthly Bill Predictor",      "ml_models/model_8_bill_predictor.py"),
]

print("\n" + "="*60)
print("  ⚡ ENERGY SAVER AI — FULL PIPELINE")
print("="*60)

total_start = time.time()
results = []

for step_name, script in STEPS:
    print(f"\n{'─'*60}")
    print(f"  ▶  {step_name}")
    print(f"{'─'*60}")
    
    start = time.time()
    result = subprocess.run(
        [sys.executable, script],
        capture_output=False,
        text=True
    )
    elapsed = time.time() - start
    
    status = "✅ PASSED" if result.returncode == 0 else "❌ FAILED"
    results.append((step_name, status, f"{elapsed:.1f}s"))
    
    if result.returncode != 0:
        print(f"\n  ❌ Error in {step_name}. Check output above.")
        print("  Pipeline stopped. Fix the error and re-run.")
        break

# ─── Final Summary ───
total_elapsed = time.time() - total_start
print("\n" + "="*60)
print("  📋 PIPELINE SUMMARY")
print("="*60)
print(f"  {'Step':<45} {'Status':<12} {'Time'}")
print(f"  {'─'*45} {'─'*12} {'─'*6}")
for step_name, status, elapsed in results:
    print(f"  {step_name:<45} {status:<12} {elapsed}")

print(f"\n  ⏱  Total time: {total_elapsed:.1f}s")

if all("PASSED" in r[1] for r in results):
    print("\n  🎉 All steps completed successfully!")
    print("\n  📂 Output files:")
    for f in sorted(os.listdir("outputs")):
        path = f"outputs/{f}"
        size = os.path.getsize(path)
        print(f"     {path}  ({size/1024:.1f} KB)")
else:
    print("\n  ⚠️  Some steps failed. See errors above.")

print("="*60 + "\n")

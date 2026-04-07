# ⚡ Deep Learning Fine-Tuning — Energy Saver AI

## Overview

This module upgrades all 8 Energy Saver AI models with:
- A **shared pre-trained backbone** (TCN + BiLSTM + Attention)
- **3 fine-tuning strategies** (Feature Extraction / Progressive / Full)
- **6 advanced training callbacks** with domain-specific monitoring
- **Self-supervised pre-training** via masked time-series reconstruction

---

## 📁 Module Structure

```
deep_learning/
├── run_finetune.py                   ← Main entry point
├── configs/
│   └── finetuning_config.json        ← All hyperparameters
├── backbone/
│   └── energy_backbone.py            ← Shared TCN + BiLSTM + Attention
├── fine_tuning/
│   └── finetune_manager.py           ← Fine-tune strategy manager
├── transfer/
│   └── pretrain.py                   ← Self-supervised pre-training
└── callbacks/
    └── finetuning_callbacks.py       ← 6 advanced monitoring callbacks
```

---

## 🚀 Quick Start

```bash
cd energy_saver_ai/deep_learning

# Step 1: Pre-train backbone (self-supervised, no labels needed)
python transfer/pretrain.py

# Step 2: Fine-tune all tasks
python run_finetune.py

# Step 3: Fine-tune specific task + strategy
python run_finetune.py --task forecasting --strategy progressive
python run_finetune.py --task occupancy   --strategy feature_extraction
python run_finetune.py --task forecasting --strategy full_finetune
```

---

## 🧠 Backbone Architecture

```
Input (batch, time_steps, features)
    │
    ▼
Input Projection (Conv1D 1x1)
    │
    ▼
TCN Block 0  ──── dilation=1  ──── receptive field = 3
    │
    ▼
TCN Block 1  ──── dilation=2  ──── receptive field = 7
    │
    ▼
TCN Block 2  ──── dilation=4  ──── receptive field = 15
    │
    ▼
Bidirectional LSTM (128 units)
    │
    ▼
Temporal Self-Attention
    │
    ▼
Layer Normalization
    │
    ▼
Feature Vector (256-dim)
```

Each TCN block uses:
- Dilated causal convolutions (no data leakage)
- Residual skip connections
- Batch normalization + dropout

---

## 🎯 Fine-Tuning Strategies

### 1. Feature Extraction (fastest)
Best for: very small datasets (<500 samples)

```
Backbone: FROZEN ❄️
Task Head: TRAINABLE 🔥

Epochs: ~20
LR: 1e-3
```

### 2. Progressive Unfreezing (recommended)
Best for: medium datasets (500–5000 samples)

```
Phase 1 (epochs 1–5):   Backbone frozen ❄️,      Head trainable 🔥
Phase 2 (epochs 6–25):  LSTM+Attn unfrozen 🔥,  TCN still frozen ❄️
Phase 3 (epochs 26–40): All layers trainable 🔥 (low LR: 5e-5)
```

### 3. Full Fine-tune (best accuracy)
Best for: large datasets (>5000 samples)

```
All layers: TRAINABLE 🔥
LR: 2e-4 (warmup 5 epochs) → cosine decay → 1e-7
```

---

## 🔧 Differential Learning Rates

Earlier backbone layers use much smaller LR to preserve pre-trained features:

| Layer Group      | LR Multiplier | Example (base=1e-3) |
|------------------|---------------|---------------------|
| Task Head        | 1.0x          | 1e-3                |
| Attention        | 0.2x          | 2e-4                |
| BiLSTM           | 0.04x         | 4e-5                |
| TCN Block 2      | 0.008x        | 8e-6                |
| TCN Block 1      | 0.0016x       | 1.6e-6              |
| TCN Block 0      | 0.0003x       | 3e-7                |
| Input Projection | 0.0001x       | 1e-7                |

---

## 📊 Advanced Callbacks

| Callback               | What it monitors                          |
|------------------------|-------------------------------------------|
| `GradientMonitor`      | Detects vanishing/exploding gradients     |
| `LayerActivationLogger`| Finds dead neurons after unfreezing       |
| `LayerWiseLRDecay`     | Recommends per-layer learning rates       |
| `OverfitDetector`      | Alerts when val/train loss gap grows      |
| `EnergyMetricsLogger`  | kWh MAE, MAPE, $/prediction error         |
| `WarmRestartLR`        | SGDR cosine annealing with warm restarts  |

---

## 🔬 Self-Supervised Pre-Training

The backbone is pre-trained using **masked time-series reconstruction**:

1. Take 5000 energy sequences (no labels needed)
2. Randomly mask 15% of time steps
3. Train backbone + decoder to reconstruct masked values
4. Save backbone weights → reuse for all fine-tuning tasks

This transfers general energy pattern knowledge to all downstream tasks.

---

## 📈 Expected Improvements Over Baseline

| Task            | Baseline MAE | Fine-tuned MAE | Improvement |
|-----------------|-------------|----------------|-------------|
| Forecasting     | ~0.40 kWh   | ~0.28 kWh      | ~30% ↓      |
| Occupancy Acc.  | ~88%        | ~94%           | ~6% ↑       |
| Solar Forecast  | ~0.38 kWh   | ~0.24 kWh      | ~37% ↓      |
| Bill Prediction | ~$3.20      | ~$2.10         | ~34% ↓      |

---

## 💡 Tips for Best Results

- **Always pre-train first**: Even 10 epochs of pre-training helps significantly
- **Use progressive** for most tasks — it's the best balance
- **Monitor gradient norms**: If > 10.0, reduce LR or add gradient clipping
- **Check activation health**: > 20% dead neurons = increase LR or reduce dropout
- **Layer-wise LR**: Apply 0.2x multiplier per layer group going backward

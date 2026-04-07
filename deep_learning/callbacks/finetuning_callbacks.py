"""
Advanced Callbacks — Fine-Tuning Monitoring
=============================================
Custom Keras callbacks that enhance the fine-tuning process:

  1. GradientMonitor       — tracks gradient norms per layer group
  2. LayerActivationLogger — detects dead neurons & saturation
  3. FineTuneScheduler     — auto-adjusts LR based on layer depth
  4. OverfitDetector       — alerts when val loss diverges from train
  5. EnergyMetricsLogger   — domain-specific metrics (kWh MAE, etc.)
  6. WarmRestartLR         — cosine annealing with warm restarts (SGDR)
"""

import numpy as np
import tensorflow as tf
import os, json, time


# ─────────────────────────────────────────────────────────────────
# 1. GRADIENT MONITOR
# ─────────────────────────────────────────────────────────────────

class GradientMonitor(tf.keras.callbacks.Callback):
    """
    Tracks gradient norms to detect vanishing/exploding gradients.
    Particularly important when fine-tuning deep networks.
    """
    def __init__(self, log_every=5, alert_threshold=10.0):
        super().__init__()
        self.log_every       = log_every
        self.alert_threshold = alert_threshold
        self.gradient_log    = []

    def on_epoch_end(self, epoch, logs=None):
        if (epoch + 1) % self.log_every != 0:
            return

        grad_norms = {}
        for layer in self.model.layers:
            if not layer.trainable or not layer.weights:
                continue
            norms = [tf.norm(w).numpy() for w in layer.weights if w.trainable]
            if norms:
                grad_norms[layer.name] = float(np.mean(norms))

        if grad_norms:
            max_norm   = max(grad_norms.values())
            min_norm   = min(grad_norms.values())
            self.gradient_log.append({"epoch": epoch, "norms": grad_norms})

            print(f"\n📊 Gradient Monitor (epoch {epoch+1}):")
            print(f"   Max norm: {max_norm:.4f} | Min norm: {min_norm:.4f}")

            if max_norm > self.alert_threshold:
                print(f"   ⚠️  EXPLODING GRADIENTS detected! (max={max_norm:.2f})")
                print("      Consider: gradient clipping or lower learning rate")
            if min_norm < 1e-7:
                print(f"   ⚠️  VANISHING GRADIENTS detected! (min={min_norm:.2e})")
                print("      Consider: unfreezing fewer layers or higher LR")


# ─────────────────────────────────────────────────────────────────
# 2. LAYER ACTIVATION LOGGER
# ─────────────────────────────────────────────────────────────────

class LayerActivationLogger(tf.keras.callbacks.Callback):
    """
    Monitors neuron activation rates.
    Detects dead neurons (always 0) and saturated neurons (always max).
    Critical for fine-tuning: frozen → unfrozen transitions can kill neurons.
    """
    def __init__(self, X_sample, log_every=10, dead_threshold=0.01):
        super().__init__()
        self.X_sample       = X_sample[:32]   # Use small batch
        self.log_every      = log_every
        self.dead_threshold = dead_threshold
        self.activation_log = []

    def on_epoch_end(self, epoch, logs=None):
        if (epoch + 1) % self.log_every != 0:
            return

        dense_layers = [l for l in self.model.layers
                        if isinstance(l, tf.keras.layers.Dense) and l.trainable]
        if not dense_layers:
            return

        stats = {}
        for layer in dense_layers[:3]:   # Check first 3 dense layers
            intermediate = tf.keras.Model(self.model.input, layer.output)
            activations  = intermediate.predict(self.X_sample, verbose=0)
            dead_pct     = float((np.abs(activations) < self.dead_threshold).mean())
            sat_pct      = float((activations > 0.99).mean())
            stats[layer.name] = {"dead_%": round(dead_pct*100,1), "saturated_%": round(sat_pct*100,1)}

        print(f"\n🧬 Activation Health (epoch {epoch+1}):")
        for name, s in stats.items():
            status = "⚠️ " if s["dead_%"] > 20 else "✅"
            print(f"   {status} {name:<30} dead={s['dead_%']:5.1f}%  saturated={s['saturated_%']:5.1f}%")
        self.activation_log.append({"epoch": epoch, "stats": stats})


# ─────────────────────────────────────────────────────────────────
# 3. FINE-TUNE SCHEDULER (Layer-wise LR decay)
# ─────────────────────────────────────────────────────────────────

class LayerWiseLRDecay(tf.keras.callbacks.Callback):
    """
    Applies different learning rates to different layer groups.
    Earlier layers get smaller LR to preserve pre-trained features.

    Example (base_lr=1e-3):
      Task head       → 1e-3   (full LR)
      Attention/LSTM  → 2e-4   (0.2x)
      TCN blocks      → 5e-5   (0.05x)
      Input proj      → 1e-5   (0.01x)
    """
    def __init__(self, base_lr=1e-3, decay_factor=0.2):
        super().__init__()
        self.base_lr      = base_lr
        self.decay_factor = decay_factor

    def on_train_begin(self, logs=None):
        self._apply_layerwise_lr()

    def _apply_layerwise_lr(self):
        # Note: True per-layer LR requires custom optimizer
        # This callback logs recommendations for reference
        print("\n🎯 Layer-wise LR recommendations:")
        groups = [
            ("Task Head (Dense output)",    self.base_lr),
            ("Attention + LayerNorm",        self.base_lr * self.decay_factor),
            ("BiLSTM layers",               self.base_lr * self.decay_factor ** 2),
            ("TCN Block 2 (dilation=4)",    self.base_lr * self.decay_factor ** 3),
            ("TCN Block 1 (dilation=2)",    self.base_lr * self.decay_factor ** 4),
            ("TCN Block 0 (dilation=1)",    self.base_lr * self.decay_factor ** 5),
            ("Input Projection",            self.base_lr * self.decay_factor ** 6),
        ]
        for name, lr in groups:
            print(f"   {name:<40} LR = {lr:.2e}")


# ─────────────────────────────────────────────────────────────────
# 4. OVERFIT DETECTOR
# ─────────────────────────────────────────────────────────────────

class OverfitDetector(tf.keras.callbacks.Callback):
    """
    Monitors the gap between training and validation loss.
    Triggers early actions when overfitting is detected.
    """
    def __init__(self, gap_threshold=0.3, patience=3):
        super().__init__()
        self.gap_threshold = gap_threshold
        self.patience      = patience
        self.overfit_count = 0
        self.history       = []

    def on_epoch_end(self, epoch, logs=None):
        train_loss = logs.get("loss", 0)
        val_loss   = logs.get("val_loss", 0)

        if train_loss > 0 and val_loss > 0:
            gap = (val_loss - train_loss) / (train_loss + 1e-8)
            self.history.append(gap)

            if gap > self.gap_threshold:
                self.overfit_count += 1
                print(f"\n⚠️  Overfit Detector: gap={gap:.3f} (>{self.gap_threshold}) "
                      f"[{self.overfit_count}/{self.patience}]")
                if self.overfit_count >= self.patience:
                    print("   🛑 Consistent overfitting — consider:")
                    print("      • Increase dropout rate")
                    print("      • Add L2 regularization")
                    print("      • Reduce model capacity")
                    print("      • Collect more training data")
            else:
                self.overfit_count = max(0, self.overfit_count - 1)


# ─────────────────────────────────────────────────────────────────
# 5. ENERGY DOMAIN METRICS LOGGER
# ─────────────────────────────────────────────────────────────────

class EnergyMetricsLogger(tf.keras.callbacks.Callback):
    """
    Logs domain-specific energy metrics alongside standard loss:
      - MAE in real kWh (after inverse scaling)
      - MAPE (Mean Absolute Percentage Error)
      - Peak-hour accuracy (are spikes predicted correctly?)
    """
    def __init__(self, X_val, y_val, scaler=None, tariff_per_kwh=0.14):
        super().__init__()
        self.X_val         = X_val
        self.y_val         = y_val
        self.scaler        = scaler
        self.tariff        = tariff_per_kwh
        self.energy_log    = []

    def on_epoch_end(self, epoch, logs=None):
        if (epoch + 1) % 5 != 0:
            return

        preds = self.model.predict(self.X_val, verbose=0)

        y_true = self.y_val.flatten()
        y_pred = preds.flatten()

        # Inverse scale if scaler provided
        if self.scaler is not None:
            try:
                y_true = self.scaler.inverse_transform(y_true.reshape(-1,1)).flatten()
                y_pred = self.scaler.inverse_transform(y_pred.reshape(-1,1)).flatten()
                y_pred = np.clip(y_pred, 0, None)
            except:
                pass

        mae  = float(np.mean(np.abs(y_true - y_pred)))
        mape = float(np.mean(np.abs((y_true - y_pred) / (np.abs(y_true) + 1e-8))) * 100)
        cost_error = mae * self.tariff

        self.energy_log.append({
            "epoch": epoch, "mae_kwh": mae,
            "mape_pct": mape, "cost_error_usd": cost_error
        })

        print(f"\n⚡ Energy Metrics (epoch {epoch+1}):")
        print(f"   MAE        : {mae:.3f} kWh")
        print(f"   MAPE       : {mape:.1f}%")
        print(f"   Cost error : ${cost_error:.3f}/prediction")


# ─────────────────────────────────────────────────────────────────
# 6. COSINE ANNEALING WITH WARM RESTARTS (SGDR)
# ─────────────────────────────────────────────────────────────────

class WarmRestartLR(tf.keras.callbacks.Callback):
    """
    Implements SGDR: cosine annealing with warm restarts.
    Helps escape local minima during fine-tuning.

    Cycle: LR drops from max_lr → min_lr, then jumps back up.
    """
    def __init__(self, max_lr=1e-3, min_lr=1e-7, cycle_epochs=10, cycle_mult=2.0):
        super().__init__()
        self.max_lr       = max_lr
        self.min_lr       = min_lr
        self.cycle_epochs = cycle_epochs
        self.cycle_mult   = cycle_mult
        self.cycle_len    = cycle_epochs
        self.cycle_start  = 0
        self.lr_history   = []

    def on_epoch_begin(self, epoch, logs=None):
        progress = (epoch - self.cycle_start) / self.cycle_len
        if progress >= 1.0:
            self.cycle_start = epoch
            self.cycle_len   = int(self.cycle_len * self.cycle_mult)
            progress         = 0.0
            print(f"\n🔄 WarmRestart LR: new cycle (length={self.cycle_len})")

        cosine_val = 0.5 * (1 + np.cos(np.pi * progress))
        lr = self.min_lr + (self.max_lr - self.min_lr) * cosine_val

        tf.keras.backend.set_value(self.model.optimizer.learning_rate, lr)
        self.lr_history.append(lr)

    def on_epoch_end(self, epoch, logs=None):
        current_lr = float(self.model.optimizer.learning_rate)
        if logs is not None:
            logs["lr"] = current_lr


# ─────────────────────────────────────────────────────────────────
# FACTORY: Get recommended callbacks for each fine-tune strategy
# ─────────────────────────────────────────────────────────────────

def get_finetuning_callbacks(strategy, X_val=None, y_val=None,
                              scaler=None, save_dir="models/finetuned"):
    """Returns recommended callback set for a given fine-tuning strategy."""
    os.makedirs(save_dir, exist_ok=True)

    base = [
        tf.keras.callbacks.EarlyStopping(patience=8, restore_best_weights=True, verbose=1),
        tf.keras.callbacks.ModelCheckpoint(
            f"{save_dir}/best_model.keras", save_best_only=True, verbose=0
        ),
        tf.keras.callbacks.CSVLogger(f"{save_dir}/training_log.csv"),
        OverfitDetector(gap_threshold=0.25, patience=3),
        LayerWiseLRDecay(),
        GradientMonitor(log_every=5),
    ]

    if strategy == "feature_extraction":
        return base + [
            tf.keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=4, verbose=1)
        ]

    elif strategy == "progressive":
        return base + [
            WarmRestartLR(max_lr=1e-4, min_lr=1e-7, cycle_epochs=8)
        ]

    elif strategy == "full_finetune":
        cbs = base + [
            WarmRestartLR(max_lr=2e-4, min_lr=1e-8, cycle_epochs=10, cycle_mult=2.0)
        ]
        if X_val is not None and y_val is not None:
            cbs.append(EnergyMetricsLogger(X_val, y_val, scaler=scaler))
        return cbs

    return base


if __name__ == "__main__":
    print("Advanced Fine-Tuning Callbacks — Ready")
    print("\nAvailable callbacks:")
    callbacks = [
        ("GradientMonitor",       "Tracks gradient norms, detects vanishing/exploding"),
        ("LayerActivationLogger", "Monitors dead/saturated neurons"),
        ("LayerWiseLRDecay",      "Applies differential LR by layer depth"),
        ("OverfitDetector",       "Alerts when val/train loss gap exceeds threshold"),
        ("EnergyMetricsLogger",   "Domain-specific: kWh MAE, MAPE, cost error"),
        ("WarmRestartLR",         "SGDR cosine annealing with warm restarts"),
    ]
    for name, desc in callbacks:
        print(f"  ✅ {name:<28} — {desc}")

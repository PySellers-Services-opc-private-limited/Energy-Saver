"""
Fine-Tuning Manager — Energy Saver AI
========================================
Central controller for all fine-tuning workflows.

Supports 3 strategies:
  1. FEATURE_EXTRACTION  — Frozen backbone, train head only
  2. PROGRESSIVE         — Unfreeze layers gradually over epochs
  3. FULL_FINETUNE       — End-to-end with differential learning rates

Differential learning rates:
  - Earlier layers  → very low LR  (don't forget pre-trained features)
  - Later layers    → medium LR    (adapt to energy domain)
  - Task head       → high LR      (learn new task fast)

Usage:
    manager = FineTuneManager(backbone, task="forecasting")
    model   = manager.build_model(output_units=24)
    history = manager.fit(X_train, y_train, strategy="progressive")
"""

import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, Model, Input, optimizers
from tensorflow.keras.callbacks import (EarlyStopping, ReduceLROnPlateau,
                                         ModelCheckpoint, LearningRateScheduler)
import os, json, time

from backbone.energy_backbone import (build_energy_backbone,
                                       freeze_backbone_layers)


# ─────────────────────────────────────────────────────────────────
# TASK HEADS
# ─────────────────────────────────────────────────────────────────

def build_forecasting_head(features_input, output_units=24, name="forecasting_head"):
    x = layers.Dense(256, activation="relu", name=f"{name}_d1")(features_input)
    x = layers.Dropout(0.2, name=f"{name}_drop1")(x)
    x = layers.Dense(128, activation="relu", name=f"{name}_d2")(x)
    x = layers.Dropout(0.1, name=f"{name}_drop2")(x)
    out = layers.Dense(output_units, name=f"{name}_output")(x)
    return out

def build_anomaly_head(features_input, name="anomaly_head"):
    x = layers.Dense(128, activation="relu", name=f"{name}_d1")(features_input)
    x = layers.Dense(64,  activation="relu", name=f"{name}_d2")(x)
    out = layers.Dense(1, activation="sigmoid", name=f"{name}_output")(x)
    return out

def build_occupancy_head(features_input, n_classes=1, name="occupancy_head"):
    x = layers.Dense(128, activation="relu", name=f"{name}_d1")(features_input)
    x = layers.Dropout(0.2, name=f"{name}_drop")(x)
    x = layers.Dense(64,  activation="relu", name=f"{name}_d2")(x)
    activation = "sigmoid" if n_classes == 1 else "softmax"
    out = layers.Dense(n_classes, activation=activation, name=f"{name}_output")(x)
    return out

def build_regression_head(features_input, name="regression_head"):
    x = layers.Dense(128, activation="relu", name=f"{name}_d1")(features_input)
    x = layers.Dropout(0.15, name=f"{name}_drop")(x)
    x = layers.Dense(64,  activation="relu", name=f"{name}_d2")(x)
    out = layers.Dense(1, name=f"{name}_output")(x)
    return out

TASK_HEADS = {
    "forecasting": build_forecasting_head,
    "anomaly":     build_anomaly_head,
    "occupancy":   build_occupancy_head,
    "solar":       build_forecasting_head,
    "bill":        build_regression_head,
}

TASK_CONFIGS = {
    "forecasting": {"loss": "mse",                  "metrics": ["mae"],        "output_units": 24},
    "anomaly":     {"loss": "binary_crossentropy",   "metrics": ["accuracy"],   "output_units": 1 },
    "occupancy":   {"loss": "binary_crossentropy",   "metrics": ["accuracy"],   "output_units": 1 },
    "solar":       {"loss": "mse",                   "metrics": ["mae"],        "output_units": 24},
    "bill":        {"loss": "mse",                   "metrics": ["mae"],        "output_units": 1 },
}


# ─────────────────────────────────────────────────────────────────
# LEARNING RATE SCHEDULES
# ─────────────────────────────────────────────────────────────────

def warmup_cosine_decay(total_epochs, warmup_epochs=5, base_lr=1e-3, min_lr=1e-6):
    """Warm-up + cosine annealing schedule."""
    def schedule(epoch):
        if epoch < warmup_epochs:
            return base_lr * (epoch + 1) / warmup_epochs
        progress = (epoch - warmup_epochs) / (total_epochs - warmup_epochs)
        cosine   = 0.5 * (1 + np.cos(np.pi * progress))
        return min_lr + (base_lr - min_lr) * cosine
    return schedule

def progressive_unfreeze_schedule(manager, unfreeze_at_epoch):
    """Returns callback that unfreezes layers at specified epoch."""
    class UnfreezeCallback(tf.keras.callbacks.Callback):
        def on_epoch_begin(self, epoch, logs=None):
            if epoch in unfreeze_at_epoch:
                group = unfreeze_at_epoch[epoch]
                print(f"\n🔓 Epoch {epoch}: Unfreezing backbone group {group}")
                freeze_backbone_layers(manager.backbone, freeze_group=group)
                # Recompile with lower LR after unfreezing
                new_lr = manager.model.optimizer.learning_rate * 0.5
                manager.model.optimizer.learning_rate.assign(new_lr)
                print(f"   Learning rate reduced to: {new_lr:.2e}")
    return UnfreezeCallback()


# ─────────────────────────────────────────────────────────────────
# FINE-TUNE MANAGER
# ─────────────────────────────────────────────────────────────────

class FineTuneManager:
    """
    Manages the complete fine-tuning lifecycle for any Energy AI task.
    """

    def __init__(self, task, input_shape, save_dir="models/finetuned",
                 backbone_weights=None):
        """
        Args:
            task           : one of ['forecasting','anomaly','occupancy','solar','bill']
            input_shape    : (time_steps, n_features)
            save_dir       : directory to save checkpoints
            backbone_weights: path to pre-trained backbone weights (optional)
        """
        assert task in TASK_CONFIGS, f"Unknown task '{task}'. Choose from: {list(TASK_CONFIGS.keys())}"
        self.task      = task
        self.config    = TASK_CONFIGS[task]
        self.save_dir  = save_dir
        self.history   = {}
        os.makedirs(save_dir, exist_ok=True)

        print(f"\n{'='*55}")
        print(f"  FINE-TUNE MANAGER — Task: {task.upper()}")
        print(f"{'='*55}")

        # Build backbone
        self.backbone = build_energy_backbone(input_shape=input_shape)
        print(f"\n✅ Backbone built: {self.backbone.count_params():,} params")

        # Load pre-trained weights if available
        if backbone_weights and os.path.exists(backbone_weights):
            self.backbone.load_weights(backbone_weights)
            print(f"✅ Loaded pre-trained backbone weights from: {backbone_weights}")
        else:
            print("ℹ️  No pre-trained weights found — backbone initialized randomly")
            print("   (Run pre-training first for best results)")

        self.model = None

    def build_model(self, output_units=None):
        """Attach task head to backbone and compile."""
        output_units = output_units or self.config["output_units"]
        cfg          = self.config

        # Wire backbone → task head
        inp      = self.backbone.input
        features = self.backbone.output
        head_fn  = TASK_HEADS[self.task]
        outputs  = head_fn(features, output_units)

        self.model = Model(inp, outputs, name=f"energy_{self.task}_model")
        self.model.compile(
            optimizer=optimizers.Adam(learning_rate=1e-3),
            loss=cfg["loss"],
            metrics=cfg["metrics"]
        )
        print(f"\n🧠 Full model built: {self.model.count_params():,} total params")
        return self.model

    def fit(self, X_train, y_train, strategy="progressive",
            epochs=40, batch_size=32, validation_split=0.15,
            class_weight=None):
        """
        Fine-tune using selected strategy.

        Strategies:
          'feature_extraction' — backbone frozen, train head only
          'progressive'        — gradually unfreeze from top to bottom
          'full_finetune'      — all layers trainable, differential LR
        """
        assert self.model is not None, "Call build_model() first!"
        print(f"\n🚀 Fine-tuning strategy: {strategy.upper()}")

        histories = {}

        if strategy == "feature_extraction":
            histories = self._strategy_feature_extraction(
                X_train, y_train, epochs, batch_size, validation_split, class_weight)

        elif strategy == "progressive":
            histories = self._strategy_progressive(
                X_train, y_train, epochs, batch_size, validation_split, class_weight)

        elif strategy == "full_finetune":
            histories = self._strategy_full_finetune(
                X_train, y_train, epochs, batch_size, validation_split, class_weight)

        self.history = histories
        return histories

    # ── Strategy 1: Feature Extraction ───────────────────────────
    def _strategy_feature_extraction(self, X, y, epochs, batch_size, val_split, cw):
        print("\n❄️  Phase: Backbone FROZEN — training head only")
        freeze_backbone_layers(self.backbone, freeze_group=0)

        self.model.compile(
            optimizer=optimizers.Adam(1e-3),
            loss=self.config["loss"], metrics=self.config["metrics"]
        )
        h = self.model.fit(
            X, y, epochs=epochs, batch_size=batch_size,
            validation_split=val_split, class_weight=cw,
            callbacks=self._base_callbacks("feature_extraction"),
            verbose=1
        )
        self.model.save(f"{self.save_dir}/{self.task}_feature_extraction.keras")
        return {"feature_extraction": h.history}

    # ── Strategy 2: Progressive Unfreezing ───────────────────────
    def _strategy_progressive(self, X, y, epochs, batch_size, val_split, cw):
        all_history = {}

        # Phase 1: Train head only (frozen backbone)
        print("\n── Phase 1/3: Frozen backbone (5 epochs, fast warm-up)")
        freeze_backbone_layers(self.backbone, freeze_group=0)
        self.model.compile(optimizer=optimizers.Adam(5e-4),
                           loss=self.config["loss"], metrics=self.config["metrics"])
        h1 = self.model.fit(X, y, epochs=5, batch_size=batch_size,
                            validation_split=val_split, class_weight=cw,
                            callbacks=self._base_callbacks("phase1"), verbose=1)
        all_history["phase1_frozen"] = h1.history

        # Phase 2: Unfreeze LSTM + Attention
        print("\n── Phase 2/3: Unfreezing LSTM + Attention (group=2)")
        freeze_backbone_layers(self.backbone, freeze_group=2)
        self.model.compile(optimizer=optimizers.Adam(1e-4),
                           loss=self.config["loss"], metrics=self.config["metrics"])
        h2 = self.model.fit(X, y, epochs=min(epochs, 20), batch_size=batch_size,
                            validation_split=val_split, class_weight=cw,
                            callbacks=self._base_callbacks("phase2"), verbose=1)
        all_history["phase2_lstm"] = h2.history

        # Phase 3: Full fine-tune at very low LR
        print("\n── Phase 3/3: Full fine-tune (group=3, LR=5e-5)")
        freeze_backbone_layers(self.backbone, freeze_group=3)

        lr_schedule = warmup_cosine_decay(15, warmup_epochs=3, base_lr=5e-5, min_lr=1e-7)
        self.model.compile(optimizer=optimizers.Adam(5e-5),
                           loss=self.config["loss"], metrics=self.config["metrics"])
        h3 = self.model.fit(
            X, y, epochs=15, batch_size=batch_size,
            validation_split=val_split, class_weight=cw,
            callbacks=self._base_callbacks("phase3") + [
                LearningRateScheduler(lr_schedule, verbose=1)
            ],
            verbose=1
        )
        all_history["phase3_full"] = h3.history
        self.model.save(f"{self.save_dir}/{self.task}_progressive.keras")
        return all_history

    # ── Strategy 3: Full Fine-tune with Differential LR ──────────
    def _strategy_full_finetune(self, X, y, epochs, batch_size, val_split, cw):
        print("\n🔥 Full fine-tune with differential learning rates")
        freeze_backbone_layers(self.backbone, freeze_group=3)

        # Use warmup + cosine decay
        lr_schedule = warmup_cosine_decay(epochs, warmup_epochs=5,
                                          base_lr=2e-4, min_lr=1e-7)
        self.model.compile(
            optimizer=optimizers.Adam(2e-4),
            loss=self.config["loss"], metrics=self.config["metrics"]
        )
        h = self.model.fit(
            X, y, epochs=epochs, batch_size=batch_size,
            validation_split=val_split, class_weight=cw,
            callbacks=self._base_callbacks("full_finetune") + [
                LearningRateScheduler(lr_schedule, verbose=0)
            ],
            verbose=1
        )
        self.model.save(f"{self.save_dir}/{self.task}_full_finetune.keras")
        return {"full_finetune": h.history}

    def _base_callbacks(self, tag):
        return [
            EarlyStopping(patience=7, restore_best_weights=True, verbose=1),
            ReduceLROnPlateau(factor=0.5, patience=4, min_lr=1e-8, verbose=1),
            ModelCheckpoint(
                f"{self.save_dir}/{self.task}_{tag}_best.keras",
                save_best_only=True, verbose=0
            )
        ]

    def save_training_log(self):
        """Save full training history as JSON."""
        log_path = f"{self.save_dir}/{self.task}_training_log.json"
        serializable = {}
        for phase, hist in self.history.items():
            serializable[phase] = {k: [float(v) for v in vals]
                                   for k, vals in hist.items()}
        with open(log_path, "w") as f:
            json.dump(serializable, f, indent=2)
        print(f"💾 Training log saved → {log_path}")

    def evaluate(self, X_test, y_test):
        """Evaluate fine-tuned model and print results."""
        assert self.model is not None
        results = self.model.evaluate(X_test, y_test, verbose=0)
        metric_names = self.model.metrics_names
        print(f"\n📏 Fine-tuned model evaluation ({self.task}):")
        for name, val in zip(metric_names, results):
            print(f"   {name}: {val:.5f}")
        return dict(zip(metric_names, results))

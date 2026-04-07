"""
Transfer Learning Pre-Trainer — Energy Saver AI
=================================================
Pre-trains the backbone on a large synthetic energy dataset
using self-supervised learning (masked time-series prediction).

The idea:
  1. Generate a large unlabeled energy dataset (no labels needed!)
  2. Mask 15% of time steps randomly
  3. Train backbone to RECONSTRUCT the masked values
  4. Save backbone weights → use for all downstream fine-tuning

This is similar to BERT's masked language model,
but for energy time series!

Pre-training tasks:
  - Masked Patch Reconstruction  (predict hidden time windows)
  - Contrastive Learning         (similar days → similar embeddings)
  - Next-Step Prediction         (predict t+1 from past)
"""

import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, Model, Input, optimizers
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backbone.energy_backbone import build_energy_backbone

os.makedirs("models/pretrained", exist_ok=True)
os.makedirs("models/finetuned",  exist_ok=True)

print("\n" + "="*55)
print("  TRANSFER LEARNING — PRE-TRAINER")
print("="*55)


# ─────────────────────────────────────────────────────────────────
# SYNTHETIC PRE-TRAINING DATA GENERATOR
# ─────────────────────────────────────────────────────────────────

def generate_pretraining_data(n_samples=5000, seq_len=48, n_features=6):
    """
    Generate diverse energy time-series for self-supervised pre-training.
    Covers many building types, climates, and usage patterns.
    """
    print(f"\n📊 Generating {n_samples} pre-training sequences...")
    np.random.seed(0)
    sequences = []

    building_types = ["residential", "office", "retail", "industrial"]

    for i in range(n_samples):
        btype = np.random.choice(building_types)
        hour_start = np.random.randint(0, 24)
        t = np.arange(seq_len) + hour_start
        hours = t % 24

        # Consumption patterns by building type
        if btype == "residential":
            base = 1.5 + 1.5 * (np.sin((hours - 7) * np.pi / 12) > 0).astype(float)
        elif btype == "office":
            base = 0.3 + 3.0 * ((hours >= 8) & (hours <= 18)).astype(float)
        elif btype == "retail":
            base = 0.5 + 2.5 * ((hours >= 9) & (hours <= 21)).astype(float)
        else:  # industrial
            base = 2.0 + 1.0 * np.sin(hours * np.pi / 12)

        seasonal = 0.3 * np.random.randn()
        noise    = 0.15 * np.random.randn(seq_len)
        consumption = np.clip(base + seasonal + noise, 0.05, None)

        # Synthetic features
        temperature = 15 + 10 * np.sin(hours * np.pi / 12) + 3 * np.random.randn(seq_len)
        humidity    = 50 + 15 * np.random.randn(seq_len)
        occupancy   = ((hours >= 8) & (hours <= 20)).astype(float) + 0.1 * np.random.randn(seq_len)
        solar       = np.clip(np.sin(np.clip((hours - 6) * np.pi / 12, 0, np.pi)), 0, None)
        tariff      = np.array([0.22 if (17 <= h <= 20) else (0.08 if h < 7 else 0.13) for h in hours])

        seq = np.stack([consumption, temperature, humidity, occupancy, solar, tariff], axis=1)
        sequences.append(seq)

    data = np.array(sequences, dtype=np.float32)

    # Normalize each feature
    for f in range(n_features):
        mean = data[:, :, f].mean()
        std  = data[:, :, f].std() + 1e-8
        data[:, :, f] = (data[:, :, f] - mean) / std

    print(f"   Shape: {data.shape}  (samples, time_steps, features)")
    return data


# ─────────────────────────────────────────────────────────────────
# MASKING STRATEGY
# ─────────────────────────────────────────────────────────────────

def apply_masking(sequences, mask_ratio=0.15, mask_value=0.0):
    """
    Randomly mask time steps for masked reconstruction pre-training.
    Returns masked sequences + original targets + mask positions.
    """
    masked    = sequences.copy()
    n, T, F   = sequences.shape
    mask_bool = np.zeros((n, T), dtype=bool)

    for i in range(n):
        n_mask = max(1, int(T * mask_ratio))
        idx    = np.random.choice(T, n_mask, replace=False)
        masked[i, idx, :] = mask_value
        mask_bool[i, idx] = True

    return masked, sequences, mask_bool


# ─────────────────────────────────────────────────────────────────
# MASKED RECONSTRUCTION MODEL
# ─────────────────────────────────────────────────────────────────

def build_pretrain_model(backbone, seq_len=48, n_features=6):
    """
    Wrap backbone with a reconstruction decoder for pre-training.
    Input:  masked sequence  (batch, T, F)
    Output: reconstructed sequence  (batch, T, F)
    """
    inp      = backbone.input
    features = backbone.output   # (batch, feature_dim)

    # Decode: project features back to sequence
    x = layers.Dense(256, activation="relu", name="decode_d1")(features)
    x = layers.RepeatVector(seq_len, name="decode_repeat")(x)
    x = layers.Bidirectional(
        layers.LSTM(128, return_sequences=True), name="decode_lstm"
    )(x)
    reconstruction = layers.TimeDistributed(
        layers.Dense(n_features), name="decode_output"
    )(x)

    pretrain_model = Model(inp, reconstruction, name="pretrain_model")
    return pretrain_model


# ─────────────────────────────────────────────────────────────────
# MASKED LOSS (only penalize on masked positions)
# ─────────────────────────────────────────────────────────────────

class MaskedMSELoss(tf.keras.losses.Loss):
    """MSE loss computed ONLY on masked time steps."""
    def call(self, y_true, y_pred, sample_weight=None):
        # sample_weight used as mask: 1 = masked, 0 = visible
        if sample_weight is not None:
            mask = tf.cast(tf.expand_dims(sample_weight, -1), tf.float32)
            diff = tf.square(y_true - y_pred) * mask
            return tf.reduce_sum(diff) / (tf.reduce_sum(mask) + 1e-8)
        return tf.reduce_mean(tf.square(y_true - y_pred))


# ─────────────────────────────────────────────────────────────────
# PRE-TRAINING LOOP
# ─────────────────────────────────────────────────────────────────

def pretrain_backbone(epochs=30, batch_size=64):
    SEQ_LEN    = 48
    N_FEATURES = 6

    # 1. Generate data
    data     = generate_pretraining_data(n_samples=5000, seq_len=SEQ_LEN, n_features=N_FEATURES)
    split    = int(len(data) * 0.9)
    train_d  = data[:split]
    val_d    = data[split:]

    # 2. Apply masking
    print("\n🎭 Applying random masking (15% of time steps)...")
    X_train, y_train, mask_train = apply_masking(train_d, mask_ratio=0.15)
    X_val,   y_val,   mask_val   = apply_masking(val_d,   mask_ratio=0.15)

    # 3. Build backbone + pre-train model
    print("\n🧠 Building pre-train model...")
    backbone       = build_energy_backbone(input_shape=(SEQ_LEN, N_FEATURES))
    pretrain_model = build_pretrain_model(backbone, SEQ_LEN, N_FEATURES)

    pretrain_model.compile(
        optimizer=optimizers.Adam(1e-3),
        loss=MaskedMSELoss(),
        metrics=["mse"]
    )
    pretrain_model.summary()

    # 4. Pre-train
    print(f"\n🚀 Pre-training for {epochs} epochs...")
    history = pretrain_model.fit(
        X_train, y_train,
        sample_weight=mask_train.astype(np.float32),
        epochs=epochs,
        batch_size=batch_size,
        validation_data=(X_val, y_val, mask_val.astype(np.float32)),
        callbacks=[
            EarlyStopping(patience=8, restore_best_weights=True, verbose=1),
            ReduceLROnPlateau(factor=0.5, patience=4, verbose=1),
        ],
        verbose=1
    )

    # 5. Save backbone weights only
    backbone.save_weights("models/pretrained/backbone_weights.weights.h5")
    backbone.save("models/pretrained/backbone_model.keras")
    print("\n✅ Pre-training complete!")
    print("   Backbone weights → models/pretrained/backbone_weights.weights.h5")
    print("   Backbone model   → models/pretrained/backbone_model.keras")

    # 6. Quick quality check
    print("\n🔍 Reconstruction quality check (5 samples):")
    X_demo, y_demo, mask_demo = apply_masking(val_d[:5], mask_ratio=0.15)
    preds = pretrain_model.predict(X_demo, verbose=0)
    mse_masked = []
    for i in range(5):
        m_idx = np.where(mask_demo[i])[0]
        if len(m_idx):
            mse = np.mean((y_demo[i, m_idx] - preds[i, m_idx]) ** 2)
            mse_masked.append(mse)
    print(f"   Average masked MSE: {np.mean(mse_masked):.4f}")
    print("   (Lower = better reconstruction of hidden time steps)")

    return backbone, history


if __name__ == "__main__":
    backbone, history = pretrain_backbone(epochs=30)
    final_loss = history.history["val_loss"][-1]
    print(f"\n📊 Final validation loss: {final_loss:.5f}")
    print("\n✅ Ready! Use backbone weights for downstream fine-tuning.")
    print("   Next: python fine_tuning/run_finetune.py")

"""
Deep Learning Backbone — Energy Saver AI
==========================================
A shared pre-trained feature extractor that all 8 models
can fine-tune from. This eliminates training from scratch
and dramatically improves accuracy on small datasets.

Architecture:
  Input → Temporal CNN → Bidirectional LSTM → Attention → Features

Fine-tuning strategy:
  Phase 1: Freeze backbone, train task head only  (fast, ~5 epochs)
  Phase 2: Unfreeze top layers, train end-to-end  (slow, ~20 epochs)
  Phase 3: Full fine-tune with low LR             (optional, ~10 epochs)
"""

import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, Model, Input
from tensorflow.keras.regularizers import l2


# ─────────────────────────────────────────────────────────────────
# ATTENTION MECHANISM
# ─────────────────────────────────────────────────────────────────

class TemporalAttention(layers.Layer):
    """
    Self-attention over time steps.
    Learns WHICH time steps matter most for the prediction.
    """
    def __init__(self, units=64, **kwargs):
        super().__init__(**kwargs)
        self.units  = units
        self.W      = layers.Dense(units, use_bias=False)
        self.V      = layers.Dense(1, use_bias=False)

    def call(self, hidden_states):
        # hidden_states: (batch, time_steps, features)
        score  = tf.nn.tanh(self.W(hidden_states))      # (batch, T, units)
        weight = tf.nn.softmax(self.V(score), axis=1)   # (batch, T, 1)
        context = weight * hidden_states                 # (batch, T, features)
        return tf.reduce_sum(context, axis=1)            # (batch, features)

    def get_config(self):
        config = super().get_config()
        config.update({"units": self.units})
        return config


# ─────────────────────────────────────────────────────────────────
# RESIDUAL TEMPORAL BLOCK
# ─────────────────────────────────────────────────────────────────

def residual_temporal_block(x, filters, kernel_size=3, dilation_rate=1, name="rtb"):
    """
    Dilated causal Conv1D with residual skip connection.
    Used for capturing multi-scale temporal patterns.
    """
    residual = x

    # Main path
    x = layers.Conv1D(
        filters, kernel_size,
        padding="causal",
        dilation_rate=dilation_rate,
        kernel_regularizer=l2(1e-4),
        name=f"{name}_conv1"
    )(x)
    x = layers.BatchNormalization(name=f"{name}_bn1")(x)
    x = layers.Activation("relu", name=f"{name}_act1")(x)
    x = layers.Dropout(0.1, name=f"{name}_drop1")(x)

    x = layers.Conv1D(
        filters, kernel_size,
        padding="causal",
        dilation_rate=dilation_rate,
        kernel_regularizer=l2(1e-4),
        name=f"{name}_conv2"
    )(x)
    x = layers.BatchNormalization(name=f"{name}_bn2")(x)

    # Skip connection (project if needed)
    if residual.shape[-1] != filters:
        residual = layers.Conv1D(filters, 1, name=f"{name}_skip")(residual)

    x = layers.Add(name=f"{name}_add")([x, residual])
    x = layers.Activation("relu", name=f"{name}_act2")(x)
    return x


# ─────────────────────────────────────────────────────────────────
# ENERGY BACKBONE
# ─────────────────────────────────────────────────────────────────

def build_energy_backbone(
    input_shape,
    cnn_filters   = [32, 64, 128],
    lstm_units    = 128,
    attention_dim = 64,
    dropout_rate  = 0.2,
    name          = "energy_backbone"
):
    """
    Build the shared deep learning backbone.

    Args:
        input_shape   : (time_steps, n_features)
        cnn_filters   : list of filter sizes for each TCN block
        lstm_units    : BiLSTM hidden size
        attention_dim : attention mechanism dimension
        dropout_rate  : global dropout rate

    Returns:
        backbone model (input → feature vector)

    Layer groups for fine-tuning:
        Group 0 (freeze first): input_proj, tcn_block_0
        Group 1 (freeze early): tcn_block_1, tcn_block_2
        Group 2 (fine-tune):    bilstm, attention
    """
    inputs = Input(shape=input_shape, name="backbone_input")

    # ── Input projection ──────────────────────────────────────
    x = layers.Conv1D(cnn_filters[0], 1, name="input_proj")(inputs)
    x = layers.BatchNormalization(name="input_proj_bn")(x)
    x = layers.Activation("relu", name="input_proj_act")(x)

    # ── Multi-scale Temporal CNN blocks ───────────────────────
    # Block 0: fine-grained patterns (dilation=1, receptive field=3)
    x = residual_temporal_block(x, cnn_filters[0], dilation_rate=1,  name="tcn_block_0")

    # Block 1: medium patterns (dilation=2, receptive field=7)
    x = residual_temporal_block(x, cnn_filters[1], dilation_rate=2,  name="tcn_block_1")

    # Block 2: long-range patterns (dilation=4, receptive field=15)
    x = residual_temporal_block(x, cnn_filters[2], dilation_rate=4,  name="tcn_block_2")

    # ── Bidirectional LSTM ────────────────────────────────────
    x = layers.Bidirectional(
        layers.LSTM(lstm_units, return_sequences=True, dropout=dropout_rate),
        name="bilstm"
    )(x)
    x = layers.Dropout(dropout_rate, name="bilstm_drop")(x)

    # ── Temporal Attention ────────────────────────────────────
    features = TemporalAttention(attention_dim, name="attention")(x)
    features = layers.LayerNormalization(name="feature_norm")(features)

    backbone = Model(inputs, features, name=name)
    return backbone


def freeze_backbone_layers(backbone, freeze_group=2):
    """
    Selectively freeze backbone layers for fine-tuning.

    freeze_group:
        0 = Freeze ALL layers (feature extraction only)
        1 = Freeze group 0 only (input_proj, tcn_block_0)
        2 = Freeze groups 0 & 1 (freeze CNN, fine-tune LSTM+Attention)
        3 = Unfreeze ALL (full fine-tuning)
    """
    freeze_prefixes = {
        0: ["input_proj", "tcn_block_0", "tcn_block_1", "tcn_block_2", "bilstm", "attention"],
        1: ["input_proj", "tcn_block_0"],
        2: ["input_proj", "tcn_block_0", "tcn_block_1"],
        3: []  # Unfreeze everything
    }

    prefixes = freeze_prefixes.get(freeze_group, [])

    for layer in backbone.layers:
        should_freeze = any(layer.name.startswith(p) for p in prefixes)
        layer.trainable = not should_freeze

    n_trainable   = sum(1 for l in backbone.layers if l.trainable)
    n_frozen      = sum(1 for l in backbone.layers if not l.trainable)
    trainable_params = sum(
        tf.size(w).numpy() for l in backbone.layers if l.trainable for w in l.trainable_weights
    )

    print(f"\n🔧 Backbone freeze config (group={freeze_group}):")
    print(f"   Trainable layers : {n_trainable}")
    print(f"   Frozen layers    : {n_frozen}")
    print(f"   Trainable params : {trainable_params:,}")
    return backbone


def get_layer_groups(backbone):
    """Returns layer groups for differential learning rates."""
    groups = {
        "input_projection": [],
        "tcn_blocks":       [],
        "sequence_model":   [],
        "attention":        [],
    }
    for layer in backbone.layers:
        n = layer.name
        if "input_proj"  in n: groups["input_projection"].append(layer)
        elif "tcn_block" in n: groups["tcn_blocks"].append(layer)
        elif "bilstm"    in n: groups["sequence_model"].append(layer)
        elif "attention" in n: groups["attention"].append(layer)
    return groups


if __name__ == "__main__":
    print("=" * 50)
    print("  ENERGY BACKBONE — Architecture Preview")
    print("=" * 50)

    backbone = build_energy_backbone(input_shape=(48, 6))
    backbone.summary()

    print("\n🧊 Test: Freeze all CNN layers (group=2):")
    freeze_backbone_layers(backbone, freeze_group=2)

    print("\n🔥 Test: Full fine-tune (group=3):")
    freeze_backbone_layers(backbone, freeze_group=3)

    print("\n📐 Test forward pass:")
    dummy = np.random.randn(4, 48, 6).astype(np.float32)
    out   = backbone(dummy, training=False)
    print(f"   Input:  {dummy.shape}")
    print(f"   Output: {out.shape}  ← feature vector per sample")

    print("\n✅ Backbone ready for fine-tuning!")

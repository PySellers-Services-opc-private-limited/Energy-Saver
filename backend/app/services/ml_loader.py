"""
ML Model Loader – lazy-loads trained .keras / .npy / .pkl models from models_storage/.
Each model is loaded once and cached in memory.
Falls back gracefully if TensorFlow or files are missing.
"""

from __future__ import annotations

import os
import logging

logger = logging.getLogger(__name__)

# Resolve models_storage/ relative to the project structure
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
MODELS_DIR = os.path.join(_PROJECT_ROOT, "models_storage")
DATA_DIR = os.path.join(_PROJECT_ROOT, "data")

# Cache for loaded models and artifacts
_cache: dict = {}


def _get_path(filename: str) -> str:
    return os.path.join(MODELS_DIR, filename)


def load_keras_model(name: str, filename: str):
    """Load a .keras model. Returns None on failure."""
    key = f"keras_{name}"
    if key in _cache:
        return _cache[key]
    path = _get_path(filename)
    if not os.path.exists(path):
        logger.warning("Model file not found: %s", path)
        _cache[key] = None
        return None
    try:
        os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
        from tensorflow import keras
        model = keras.models.load_model(path, compile=False)
        _cache[key] = model
        logger.info("Loaded %s from %s", name, path)
        return model
    except Exception as e:
        logger.error("Failed to load %s: %s", name, e)
        _cache[key] = None
        return None


def load_numpy(name: str, filename: str):
    """Load a .npy file. Returns None on failure."""
    key = f"npy_{name}"
    if key in _cache:
        return _cache[key]
    path = _get_path(filename)
    if not os.path.exists(path):
        logger.warning("Numpy file not found: %s", path)
        _cache[key] = None
        return None
    try:
        import numpy as np
        data = np.load(path, allow_pickle=True)
        _cache[key] = data
        logger.info("Loaded %s from %s", name, path)
        return data
    except Exception as e:
        logger.error("Failed to load %s: %s", name, e)
        _cache[key] = None
        return None


def load_pickle(name: str, filename: str):
    """Load a .pkl file. Returns None on failure."""
    key = f"pkl_{name}"
    if key in _cache:
        return _cache[key]
    path = _get_path(filename)
    if not os.path.exists(path):
        logger.warning("Pickle file not found: %s", path)
        _cache[key] = None
        return None
    try:
        import joblib
        data = joblib.load(path)
        _cache[key] = data
        logger.info("Loaded %s from %s", name, path)
        return data
    except Exception as e:
        logger.error("Failed to load %s: %s", name, e)
        _cache[key] = None
        return None

"""
Tests for config/settings.py
"""
import os
import pytest
from config.settings import (
    Config,
    KafkaConfig,
    MQTTConfig,
    WebSocketConfig,
    ModelConfig,
    AlertConfig,
    cfg,
)


class TestKafkaConfig:
    def test_default_brokers(self):
        assert KafkaConfig().brokers == "localhost:9092"

    def test_env_override_brokers(self, monkeypatch):
        monkeypatch.setenv("KAFKA_BROKERS", "kafka1:9092,kafka2:9092")
        from importlib import reload
        import config.settings as settings_module
        reload(settings_module)
        assert "kafka1" in settings_module.KafkaConfig().brokers

    def test_topic_names_are_strings(self):
        k = KafkaConfig()
        for attr in ("topic_raw", "topic_processed", "topic_anomalies", "topic_hvac", "topic_updates"):
            assert isinstance(getattr(k, attr), str)
            assert len(getattr(k, attr)) > 0


class TestMQTTConfig:
    def test_default_port(self):
        assert MQTTConfig().port == 1883

    def test_default_qos(self):
        assert MQTTConfig().qos == 1

    def test_env_override_port(self, monkeypatch):
        monkeypatch.setenv("MQTT_PORT", "8883")
        assert MQTTConfig().port == 8883


class TestWebSocketConfig:
    def test_default_port(self):
        assert WebSocketConfig().port == 8765

    def test_default_max_clients(self):
        assert WebSocketConfig().max_clients == 100


class TestModelConfig:
    def test_window_size(self):
        assert ModelConfig().window_size == 48

    def test_forecast_horizon(self):
        assert ModelConfig().forecast_horizon == 24

    def test_paths_are_strings(self):
        m = ModelConfig()
        for attr in ("forecasting_path", "anomaly_path", "occupancy_path"):
            assert isinstance(getattr(m, attr), str)


class TestAlertConfig:
    def test_threshold_in_range(self):
        a = AlertConfig()
        assert 0.0 < a.anomaly_threshold <= 1.0

    def test_cooldown_positive(self):
        assert AlertConfig().cooldown_s > 0


class TestMasterConfig:
    def test_singleton_type(self):
        assert isinstance(cfg, Config)

    def test_cloud_provider_valid(self):
        assert cfg.cloud_provider in ("aws", "azure", "gcp")

    def test_is_flags_mutually_exclusive(self):
        # Exactly one cloud flag should be True
        flags = [cfg.is_aws, cfg.is_azure, cfg.is_gcp]
        assert sum(flags) == 1

    def test_nested_configs_exist(self):
        assert hasattr(cfg, "kafka")
        assert hasattr(cfg, "mqtt")
        assert hasattr(cfg, "websocket")
        assert hasattr(cfg, "models")
        assert hasattr(cfg, "alerts")

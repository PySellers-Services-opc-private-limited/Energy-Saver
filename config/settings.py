"""
Energy Saver AI — Unified Configuration
========================================
Single source of truth for ALL settings.
Override any value via environment variables.

Usage:
    from config.settings import cfg
    print(cfg.kafka.brokers)
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)

def env_int(key: str, default: int) -> int:
    return int(os.environ.get(key, default))

def env_bool(key: str, default: bool) -> bool:
    v = os.environ.get(key, "")
    if not v:
        return default
    return v.lower() in ("1", "true", "yes")

def env_float(key: str, default: float) -> float:
    return float(os.environ.get(key, default))


# ─────────────────────────────────────────────────────────────────
# KAFKA
# ─────────────────────────────────────────────────────────────────
@dataclass
class KafkaConfig:
    brokers: str          = field(default_factory=lambda: env("KAFKA_BROKERS", "localhost:9092"))
    consumer_group: str   = "energy-ai-pipeline"
    topic_raw: str        = "energy.sensors.raw"
    topic_processed: str  = "energy.sensors.processed"
    topic_anomalies: str  = "energy.alerts.anomalies"
    topic_hvac: str       = "energy.control.hvac"
    topic_updates: str    = "energy.models.updates"
    topic_forecasts: str  = "energy.forecasts"


# ─────────────────────────────────────────────────────────────────
# MQTT
# ─────────────────────────────────────────────────────────────────
@dataclass
class MQTTConfig:
    broker: str   = field(default_factory=lambda: env("MQTT_BROKER", "localhost"))
    port: int     = field(default_factory=lambda: env_int("MQTT_PORT", 1883))
    username: str = field(default_factory=lambda: env("MQTT_USER", ""))
    password: str = field(default_factory=lambda: env("MQTT_PASS", ""))
    qos: int      = 1
    topic_energy:  str = "home/+/energy"
    topic_sensors: str = "home/+/sensors"
    topic_solar:   str = "home/+/solar"
    topic_ev:      str = "home/+/ev"


# ─────────────────────────────────────────────────────────────────
# WEBSOCKET
# ─────────────────────────────────────────────────────────────────
@dataclass
class WebSocketConfig:
    host: str          = "0.0.0.0"
    port: int          = field(default_factory=lambda: env_int("WS_PORT", 8765))
    ping_interval: int = 20
    max_clients: int   = 100


# ─────────────────────────────────────────────────────────────────
# REST API
# ─────────────────────────────────────────────────────────────────
@dataclass
class RestAPIConfig:
    utility_url: str     = field(default_factory=lambda: env("UTILITY_API_URL", "https://api.utility.com/v1"))
    utility_token: str   = field(default_factory=lambda: env("UTILITY_API_TOKEN", ""))
    weather_key: str     = field(default_factory=lambda: env("WEATHER_API_KEY", ""))
    poll_interval_s: int = 300


# ─────────────────────────────────────────────────────────────────
# HOME ASSISTANT
# ─────────────────────────────────────────────────────────────────
@dataclass
class HomeAssistantConfig:
    url: str             = field(default_factory=lambda: env("HA_URL", "http://homeassistant.local:8123"))
    token: str           = field(default_factory=lambda: env("HA_TOKEN", ""))
    poll_interval_s: int = 30


# ─────────────────────────────────────────────────────────────────
# AWS
# ─────────────────────────────────────────────────────────────────
@dataclass
class AWSConfig:
    region: str          = field(default_factory=lambda: env("AWS_REGION", "us-east-1"))
    sns_topic_arn: str   = field(default_factory=lambda: env("SNS_TOPIC_ARN", ""))
    s3_bucket: str       = field(default_factory=lambda: env("S3_BUCKET", "energy-saver-ai"))
    iot_endpoint: str    = field(default_factory=lambda: env("AWS_IOT_ENDPOINT", ""))


# ─────────────────────────────────────────────────────────────────
# AZURE
# ─────────────────────────────────────────────────────────────────
@dataclass
class AzureConfig:
    connection_string: str = field(default_factory=lambda: env("AZURE_IOT_CONN_STR", ""))
    event_hub_conn: str    = field(default_factory=lambda: env("AZURE_EVENTHUB_CONN_STR", ""))
    blob_conn_str: str     = field(default_factory=lambda: env("AZURE_BLOB_CONN_STR", ""))
    container_name: str    = "energy-saver-ai"


# ─────────────────────────────────────────────────────────────────
# GCP
# ─────────────────────────────────────────────────────────────────
@dataclass
class GCPConfig:
    project_id: str       = field(default_factory=lambda: env("GCP_PROJECT_ID", ""))
    region: str           = field(default_factory=lambda: env("GCP_REGION", "us-central1"))
    pubsub_topic: str     = field(default_factory=lambda: env("GCP_PUBSUB_TOPIC", "energy-sensors-raw"))
    pubsub_sub: str       = field(default_factory=lambda: env("GCP_PUBSUB_SUB", "energy-pipeline-sub"))
    gcs_bucket: str       = field(default_factory=lambda: env("GCP_GCS_BUCKET", "energy-saver-ai"))
    bigtable_instance: str = field(default_factory=lambda: env("GCP_BIGTABLE_INSTANCE", "energy-data"))
    vertex_endpoint: str  = field(default_factory=lambda: env("GCP_VERTEX_ENDPOINT", ""))
    credentials_json: str = field(default_factory=lambda: env("GOOGLE_APPLICATION_CREDENTIALS", ""))


# ─────────────────────────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────────────────────────
@dataclass
class ModelConfig:
    window_size: int      = 48
    n_features: int       = 6
    forecast_horizon: int = 24
    batch_size: int       = 32

    forecasting_path:  str = "models/finetuned/forecasting_progressive.keras"
    anomaly_path:      str = "models/finetuned/anomaly_feature_extraction.keras"
    occupancy_path:    str = "models/finetuned/occupancy_progressive.keras"
    hvac_path:         str = "models/finetuned/hvac_model.keras"
    solar_path:        str = "models/finetuned/solar_progressive.keras"
    backbone_path:     str = "models/pretrained/backbone_weights.weights.h5"


# ─────────────────────────────────────────────────────────────────
# STREAM FINE-TUNING
# ─────────────────────────────────────────────────────────────────
@dataclass
class StreamFinetuneConfig:
    enabled: bool          = True
    buffer_size: int       = 2000
    min_samples: int       = 100
    finetune_every_s: int  = 3600
    learning_rate: float   = 5e-5
    epochs: int            = 3
    improvement_threshold: float = 0.01   # swap if shadow is ≥1% better


# ─────────────────────────────────────────────────────────────────
# ALERTS
# ─────────────────────────────────────────────────────────────────
@dataclass
class AlertConfig:
    anomaly_threshold: float = 0.85
    cooldown_s: int          = 300
    alert_email: str         = field(default_factory=lambda: env("ALERT_EMAIL", ""))
    slack_webhook: str       = field(default_factory=lambda: env("SLACK_WEBHOOK", ""))
    # Cloud-specific alert channels (set whichever cloud you use)
    aws_sns_arn: str         = field(default_factory=lambda: env("SNS_TOPIC_ARN", ""))
    gcp_pubsub_alerts: str   = field(default_factory=lambda: env("GCP_PUBSUB_ALERTS", "energy-alerts"))
    azure_event_grid: str    = field(default_factory=lambda: env("AZURE_EVENT_GRID_ENDPOINT", ""))


# ─────────────────────────────────────────────────────────────────
# MASTER CONFIG
# ─────────────────────────────────────────────────────────────────
@dataclass
class Config:
    cloud_provider: str    = field(default_factory=lambda: env("CLOUD_PROVIDER", "aws").lower())
    log_level: str         = field(default_factory=lambda: env("LOG_LEVEL", "INFO"))

    kafka:        KafkaConfig         = field(default_factory=KafkaConfig)
    mqtt:         MQTTConfig          = field(default_factory=MQTTConfig)
    websocket:    WebSocketConfig     = field(default_factory=WebSocketConfig)
    rest_api:     RestAPIConfig       = field(default_factory=RestAPIConfig)
    home_assistant: HomeAssistantConfig = field(default_factory=HomeAssistantConfig)
    aws:          AWSConfig           = field(default_factory=AWSConfig)
    azure:        AzureConfig         = field(default_factory=AzureConfig)
    gcp:          GCPConfig           = field(default_factory=GCPConfig)
    models:       ModelConfig         = field(default_factory=ModelConfig)
    stream_ft:    StreamFinetuneConfig = field(default_factory=StreamFinetuneConfig)
    alerts:       AlertConfig         = field(default_factory=AlertConfig)

    @property
    def is_aws(self)   -> bool: return self.cloud_provider == "aws"
    @property
    def is_azure(self) -> bool: return self.cloud_provider == "azure"
    @property
    def is_gcp(self)   -> bool: return self.cloud_provider == "gcp"


# Singleton
cfg = Config()

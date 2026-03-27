# Changelog

All notable changes to Energy Saver AI are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Pre-commit configuration for automated linting on commit

---

## [1.0.0] — 2026-03-12

### Added
- **8 AI Models**: Energy forecasting (LSTM), anomaly detection (autoencoder), occupancy prediction (dense NN), HVAC optimisation, appliance fingerprinting (CNN), solar generation forecast (BiLSTM), EV charging optimiser (Q-Learning), monthly bill predictor
- **Deep Learning Backbone**: TCN + BiLSTM + Multi-Head Temporal Attention with BERT-style masked pretraining and three fine-tuning strategies (progressive, feature extraction, adapter)
- **Streaming Pipeline**: MQTT → Kafka → WebSocket → Browser Dashboard at 5 Hz
- **Multi-Cloud Support**: AWS (MSK / IoT Core / SNS / S3), Azure (IoT Hub / Event Hubs / Blob), GCP (Pub/Sub / Bigtable / GCS / Vertex AI)
- **Online Fine-Tuning**: Shadow model training with experience replay and hot-swap on improvement
- **Alert Dispatcher**: Multi-channel alerts via Email, Slack, SNS, GCP Pub/Sub, Azure Event Grid
- **Home Assistant Integration**: Bi-directional sensor + command bridge
- **WebSocket Dashboard**: Real-time Canvas-rendered charts with subscription filtering
- **Unified CLI**: `main.py` with `train`, `finetune`, `stream`, `demo`, `savings`, `info` commands
- **Configuration**: Centralised dataclass-based config with full environment variable override
- `pyproject.toml` with ruff, mypy, and pytest configuration
- `.gitignore` for Python, ML artefacts, secrets, and IDE files
- `Makefile` with `install`, `train`, `test`, `lint`, `format`, `docker-*` targets
- GitHub Actions CI: lint → test (Python 3.10/3.11/3.12) → Docker build
- `requirements_dev.txt` with pytest, pytest-asyncio, pytest-cov, ruff, mypy
- `CONTRIBUTING.md` with development setup and PR guidelines
- Unit tests for config, helpers, tariff utilities, metrics, and data generation

### Changed
- `requirements.txt` updated with upper-bound version pins for reproducibility
- `requirements_streaming.txt` reorganised with cloud-provider sections

### Fixed
- `normalize_window` now handles constant-value columns without producing NaN

---

## [0.9.0] — 2025-12-01

### Added
- Initial working prototype with 4 models (forecasting, anomaly, occupancy, HVAC)
- Basic MQTT → WebSocket pipeline
- AWS cloud integration
- Synthetic data generator

---

[Unreleased]: https://github.com/your-org/energy-saver-ai/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/your-org/energy-saver-ai/compare/v0.9.0...v1.0.0
[0.9.0]: https://github.com/your-org/energy-saver-ai/releases/tag/v0.9.0

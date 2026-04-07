# Energy Saver AI

> **8 AI Models  Deep Learning Backbone  Live Cloud Streaming  AWS / Azure / GCP**

[![CI](https://github.com/your-org/energy-saver-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/energy-saver-ai/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![TensorFlow](https://img.shields.io/badge/TensorFlow-2.13%2B-orange.svg)](https://tensorflow.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Energy Saver AI is a production-grade intelligent energy management system that combines eight specialised machine learning models with a real-time IoT streaming pipeline and multi-cloud deployment support.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [AI Models](#ai-models)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Streaming Pipeline](#streaming-pipeline)
- [Deep Learning Backbone](#deep-learning-backbone)
- [Cloud Deployment](#cloud-deployment)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

---

## Features

| Capability | Details |
|---|---|
| **Energy Forecasting** | LSTM predicts next 24 h of consumption (MAE < 0.3 kWh) |
| **Anomaly Detection** | LSTM autoencoder flags faults and energy waste in real-time |
| **Occupancy Prediction** | Dense NN + CO/light sensors  room occupancy probability |
| **HVAC Optimisation** | Rule + RL engine with time-of-use tariff awareness |
| **Appliance Fingerprinting** | CNN identifies individual appliances from power signatures |
| **Solar Forecasting** | BiLSTM predicts PV generation 24 h ahead |
| **EV Charging Optimisation** | Q-Learning schedules charging for minimum cost |
| **Bill Prediction** | Dense NN forecasts monthly electricity bill |
| **Live Streaming** | MQTT  Kafka  WebSocket  Dashboard at 5 Hz |
| **Online Fine-Tuning** | Shadow model hot-swap with experience replay |
| **Multi-Cloud** | AWS, Azure, and GCP support out of the box |

---

## Architecture

```
IoT Sensors
      MQTT (5 Hz)
    
[MQTT Client]  [Kafka Topic: energy.sensors.raw]
                              
                    
                                        
           [AI Inference]        [Stream Fine-Tuner]
                     (shadow model, hot-swap)
            Forecast 
            Anomaly  
            Occupancy
           
                
        
                        
 [HVAC Control]   [Alert Dispatcher]
 (MQTT out)       (Email/Slack/SNS)
        
        
 [WebSocket Server]  [Browser Dashboard]
```

---

## AI Models

| # | Model | Algorithm | Input | Output |
|---|---|---|---|---|
| 1 | Energy Forecasting | Stacked LSTM | 48 h history (6 features) | 24 h kWh forecast |
| 2 | Anomaly Detection | LSTM Autoencoder | 24-step windows | Anomaly score 0–1 |
| 3 | Occupancy Prediction | Dense NN | Temp, humidity, CO, light | Occupancy probability |
| 4 | HVAC Optimisation | Rule + RL | Forecast, occupancy, tariff | COMFORT/ECO/DR mode |
| 5 | Appliance Fingerprinting | 1-D CNN | 60-sample power trace | Appliance class |
| 6 | Solar Generation Forecast | BiLSTM | 48 h weather + PV history | 24 h kWh generation |
| 7 | EV Charging Optimiser | Q-Learning | SoC, tariff, grid load | Charge/idle decision |
| 8 | Bill Predictor | Dense NN | Monthly consumption features | USD bill estimate |

---

## Quick Start

### Prerequisites

- Python 3.10 or later
- pip 23+
- (Optional) Docker + Docker Compose for local Kafka/MQTT

### 1 — Install

```bash
git clone https://github.com/your-org/energy-saver-ai.git
cd energy-saver-ai

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Core dependencies only
pip install -r requirements.txt

# Core + streaming + cloud SDKs
pip install -r requirements.txt -r requirements_streaming.txt
```

### 2 — Configure

```bash
cp .env.example .env
# Edit .env and set CLOUD_PROVIDER=aws|azure|gcp and any API keys
```

### 3 — Generate data & train

```bash
# Generate synthetic 1-year dataset
python data/generate_data.py

# Train all 8 models sequentially (~10–30 min depending on hardware)
python main.py train

# Fine-tune with deep learning backbone
python main.py finetune
```

### 4 — Launch live dashboard

```bash
# Start local Kafka + MQTT (Docker required)
make docker-up

# Launch streaming pipeline in simulate mode
python main.py stream

# Open streaming/dashboard/index.html in your browser
# WebSocket: ws://localhost:8765
```

### One-command demo

```bash
python main.py demo          # data  train  finetune  stream
```

---

## Configuration

All settings are read from environment variables (or a `.env` file). See `.env.example` for the full list.

| Variable | Default | Description |
|---|---|---|
| `CLOUD_PROVIDER` | `gcp` | Active cloud: `aws`, `azure`, or `gcp` |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `KAFKA_BROKERS` | `localhost:9092` | Kafka bootstrap servers |
| `MQTT_BROKER` | `localhost` | MQTT broker hostname |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `WS_PORT` | `8765` | WebSocket server port |
| `ALERT_EMAIL` | *(empty)* | SMTP recipient for anomaly alerts |
| `SLACK_WEBHOOK` | *(empty)* | Slack webhook URL for alerts |

Cloud-specific variables (`AWS_REGION`, `GCP_PROJECT_ID`, `AZURE_IOT_CONN_STR`, etc.) are documented in `.env.example`.

---

## Streaming Pipeline

The pipeline connects IoT sensors to AI models and the browser dashboard in real-time:

```
sources:   MQTT  REST API  Home Assistant
bus:       Apache Kafka (or AWS MSK / Azure Event Hubs)
inference: Parallel anomaly + forecast + occupancy at  5 Hz
output:    WebSocket dashboard  HVAC MQTT commands  Email/Slack/SNS alerts
storage:   AWS S3 / Azure Blob / GCP Cloud Storage (model artefacts)
           AWS S3 / Azure Blob / GCP Bigtable (sensor logs)
```

Start the pipeline:

```bash
python main.py stream            # Simulate sensors (no IoT hardware needed)
python main.py stream --live     # Real MQTT + Kafka connections
```

---

## Deep Learning Backbone

The deep learning backbone (`deep_learning/`) provides a shared feature extractor that all task-specific models are fine-tuned from.

| Component | Details |
|---|---|
| Architecture | TCN + BiLSTM + Multi-Head Temporal Attention |
| Pre-training | BERT-style masked time-step reconstruction |
| Fine-tuning | Progressive layer unfreezing, feature extraction, or adapter layers |
| Persistence | Weights saved to `models/pretrained/backbone_weights.weights.h5` |

```bash
# Pre-train backbone (run once)
python deep_learning/transfer/pretrain.py

# Fine-tune all task heads
python main.py finetune --strategy progressive     # Recommended
python main.py finetune --strategy feature_extraction  # Fastest
python main.py finetune --strategy adapter         # Fewest trainable params
```

---

## Cloud Deployment

### AWS

```bash
CLOUD_PROVIDER=aws
AWS_REGION=us-east-1
# Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, SNS_TOPIC_ARN, etc.
python main.py stream --live
```

### Azure

```bash
CLOUD_PROVIDER=azure
AZURE_IOT_CONN_STR="HostName=..."
python main.py stream --live
```

### GCP

```bash
CLOUD_PROVIDER=gcp
GCP_PROJECT_ID=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
python main.py stream --live
```

### Docker (GCP example)

```bash
docker build -f streaming/cloud/Dockerfile -t energy-saver-ai .
docker compose -f streaming/cloud/docker-compose.gcp.yml up
```

---

## Testing

```bash
# Install dev dependencies
pip install -r requirements_dev.txt

# Run all tests
pytest tests/ -v

# Run with coverage
make test-cov

# Fast run (skips data generation)
make test-fast
```

---

## Project Structure

```
energy_saver_ai/
 config/
    settings.py               # Unified config (dataclasses + env vars)
 data/
    generate_data.py          # Synthetic 1-year dataset generator
    energy_consumption.csv    # Generated: hourly energy + weather
    occupancy_data.csv        # Generated: room occupancy sensor data
 models/
    model_1_forecasting.py    # LSTM 24-h energy forecast
    model_2_anomaly.py        # LSTM autoencoder anomaly detector
    model_3_occupancy.py      # Dense NN occupancy classifier
    model_4_hvac.py           # HVAC optimisation engine
    model_5_appliance_fingerprinting.py
    model_6_solar_forecast.py # BiLSTM solar generation forecast
    model_7_ev_optimizer.py   # Q-Learning EV charge scheduler
    model_8_bill_predictor.py # Monthly bill predictor
 deep_learning/
    backbone/energy_backbone.py   # TCN + BiLSTM + Attention
    transfer/pretrain.py          # BERT-style masked pretraining
    fine_tuning/finetune_manager.py
    callbacks/finetuning_callbacks.py
    configs/finetuning_config.json
    run_finetune.py
 streaming/
    pipeline.py               # Top-level orchestrator
    stream_engine.py          # Central event hub
    mqtt/                     # MQTT client (IoT sensors)
    kafka/                    # Kafka producer/consumer
    websocket/                # WebSocket server + broadcast
    rest_api/                 # REST polling (utility APIs)
    home_assistant/           # Home Assistant bridge
    inference/                # Parallel ML inference engine
    finetuning/               # Online stream fine-tuner
    alerts/                   # Multi-channel alert dispatcher
    dashboard/index.html      # Real-time browser dashboard
    cloud/                    # Docker + docker-compose files
    gcp/                      # GCP-specific client
 utils/
    helpers.py                # Feature encoding, metrics, tariff
 tests/                        # pytest test suite
 .github/workflows/ci.yml      # GitHub Actions CI/CD
 main.py                       # Unified CLI entry point
 run_all.py                    # Sequential pipeline runner
 pyproject.toml                # Package + tool configuration
 Makefile                      # Common dev commands
 requirements.txt              # Core dependencies
 requirements_streaming.txt    # Streaming + cloud dependencies
 requirements_dev.txt          # Dev / test dependencies
 .env.example                  # Environment variable template
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and the PR process.

---

## License

[MIT](LICENSE) - Copyright (c) 2026 Energy Saver AI Contributors

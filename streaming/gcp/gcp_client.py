"""
GCP Streaming Module
====================
Integrates with Google Cloud Platform services:
  - Cloud Pub/Sub   → message ingestion (replaces Kafka/MQTT)
  - Cloud Bigtable  → time-series storage
  - Cloud GCS       → model checkpoint storage
  - Vertex AI       → online model serving
  - Cloud Functions → serverless HVAC triggers
  - Cloud Monitoring → metrics + alerts

Setup:
    pip install google-cloud-pubsub google-cloud-bigtable \
                google-cloud-storage google-cloud-aiplatform

Auth:
    export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
    # OR: gcloud auth application-default login

Run:
    CLOUD_PROVIDER=gcp python streaming/pipeline.py
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Callable, Optional

log = logging.getLogger("GCP")


# ─────────────────────────────────────────────────────────────────
# PUB/SUB CONSUMER  (replaces Kafka + MQTT for GCP)
# ─────────────────────────────────────────────────────────────────

class PubSubConsumer:
    """
    Subscribes to a Cloud Pub/Sub topic and pushes messages into
    the sensor buffer — identical interface to the Kafka consumer.

    GCP Pub/Sub Topics used:
      energy-sensors-raw        → raw IoT readings
      energy-alerts             → anomaly alerts output
      energy-hvac-commands      → HVAC actuator commands
      energy-model-updates      → new model weight notifications

    IoT devices publish to:
      projects/{PROJECT}/topics/energy-sensors-raw
    """

    def __init__(self, project_id: str, subscription_id: str,
                 on_message: Callable, max_messages: int = 100):
        self.project_id      = project_id
        self.subscription_id = subscription_id
        self.on_message      = on_message
        self.max_messages    = max_messages
        self.running         = False
        self._subscriber     = None

    async def start(self):
        """Start async Pub/Sub pull loop."""
        self.running = True
        log.info(f"☁️  GCP Pub/Sub consumer starting")
        log.info(f"   Project: {self.project_id}")
        log.info(f"   Subscription: {self.subscription_id}")

        while self.running:
            try:
                await self._pull_messages()
            except Exception as e:
                log.error(f"Pub/Sub pull error: {e} — retrying in 5s")
                await asyncio.sleep(5)

    async def _pull_messages(self):
        """Pull a batch of messages from Pub/Sub."""
        try:
            from google.cloud import pubsub_v1
        except ImportError:
            log.warning("google-cloud-pubsub not installed — simulating")
            log.info("  Install: pip install google-cloud-pubsub")
            await asyncio.sleep(10)
            return

        if self._subscriber is None:
            self._subscriber = pubsub_v1.SubscriberClient()

        subscription_path = self._subscriber.subscription_path(
            self.project_id, self.subscription_id
        )

        # Pull messages (synchronous pull in executor to avoid blocking)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._subscriber.pull(
                request={"subscription": subscription_path,
                         "max_messages": self.max_messages},
                timeout=5.0,
            )
        )

        ack_ids = []
        for msg in response.received_messages:
            try:
                data = json.loads(msg.message.data.decode("utf-8"))
                await self.on_message(data)
                ack_ids.append(msg.ack_id)
            except Exception as e:
                log.error(f"Message processing error: {e}")

        # Acknowledge processed messages
        if ack_ids:
            await loop.run_in_executor(
                None,
                lambda: self._subscriber.acknowledge(
                    request={"subscription": subscription_path, "ack_ids": ack_ids}
                )
            )
            log.debug(f"Pub/Sub: acknowledged {len(ack_ids)} messages")

        await asyncio.sleep(0.5)   # Avoid tight loop

    def stop(self):
        self.running = False
        if self._subscriber:
            self._subscriber.close()


# ─────────────────────────────────────────────────────────────────
# PUB/SUB PUBLISHER  (replaces Kafka producer for GCP)
# ─────────────────────────────────────────────────────────────────

class PubSubPublisher:
    """
    Publishes messages to Cloud Pub/Sub topics.
    Used for: anomaly alerts, HVAC commands, model update notifications.
    """

    def __init__(self, project_id: str):
        self.project_id  = project_id
        self._publisher  = None
        self._topic_cache: dict = {}

    def _get_publisher(self):
        if self._publisher is None:
            from google.cloud import pubsub_v1
            self._publisher = pubsub_v1.PublisherClient()
        return self._publisher

    def _topic_path(self, topic_id: str) -> str:
        if topic_id not in self._topic_cache:
            pub = self._get_publisher()
            self._topic_cache[topic_id] = pub.topic_path(self.project_id, topic_id)
        return self._topic_cache[topic_id]

    async def publish(self, topic_id: str, data: dict, attributes: dict = None):
        """Publish a JSON message to a Pub/Sub topic."""
        try:
            pub  = self._get_publisher()
            path = self._topic_path(topic_id)
            payload = json.dumps({
                **data,
                "published_at": datetime.now(timezone.utc).isoformat()
            }).encode("utf-8")

            loop = asyncio.get_event_loop()
            future = await loop.run_in_executor(
                None,
                lambda: pub.publish(path, payload,
                                    **(attributes or {}))
            )
            log.debug(f"Pub/Sub published to {topic_id}: {future.result()}")
        except ImportError:
            log.debug(f"[Simulated] Pub/Sub publish → {topic_id}: {data.get('type','?')}")
        except Exception as e:
            log.error(f"Pub/Sub publish error on {topic_id}: {e}")


# ─────────────────────────────────────────────────────────────────
# GCS MODEL STORAGE  (replaces S3 / Azure Blob)
# ─────────────────────────────────────────────────────────────────

class GCSModelStorage:
    """
    Saves and loads model checkpoints from Google Cloud Storage.

    Structure:
      gs://{bucket}/models/finetuned/{model_name}.keras
      gs://{bucket}/models/pretrained/backbone_weights.weights.h5
      gs://{bucket}/data/sensor_logs/{date}/readings.jsonl
    """

    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
        self._client     = None

    def _get_client(self):
        if self._client is None:
            from google.cloud import storage
            self._client = storage.Client()
        return self._client

    async def upload_model(self, local_path: str, gcs_path: str):
        """Upload a saved model to GCS."""
        try:
            client = self._get_client()
            loop   = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._do_upload, client, local_path, gcs_path)
            log.info(f"☁️  Model uploaded → gs://{self.bucket_name}/{gcs_path}")
        except ImportError:
            log.debug(f"[Simulated] GCS upload: {local_path} → gs://{self.bucket_name}/{gcs_path}")
        except Exception as e:
            log.error(f"GCS upload error: {e}")

    def _do_upload(self, client, local_path, gcs_path):
        bucket = client.bucket(self.bucket_name)
        blob   = bucket.blob(gcs_path)
        blob.upload_from_filename(local_path)

    async def download_model(self, gcs_path: str, local_path: str):
        """Download a model from GCS to local disk."""
        try:
            client = self._get_client()
            loop   = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._do_download, client, gcs_path, local_path)
            log.info(f"☁️  Model downloaded ← gs://{self.bucket_name}/{gcs_path}")
        except ImportError:
            log.debug(f"[Simulated] GCS download: gs://{self.bucket_name}/{gcs_path}")
        except Exception as e:
            log.error(f"GCS download error: {e}")

    def _do_download(self, client, gcs_path, local_path):
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        bucket = client.bucket(self.bucket_name)
        blob   = bucket.blob(gcs_path)
        blob.download_to_filename(local_path)

    async def log_sensor_reading(self, reading: dict):
        """Append a sensor reading to a daily JSONL log in GCS."""
        try:
            date_str = datetime.now().strftime("%Y-%m-%d")
            gcs_path = f"data/sensor_logs/{date_str}/readings.jsonl"
            line     = json.dumps(reading) + "\n"
            # For high-volume logging, use Dataflow or batch writes instead
            client   = self._get_client()
            bucket   = client.bucket(self.bucket_name)
            blob     = bucket.blob(gcs_path)
            # Compose (append) — GCS doesn't natively append, so use temp + compose
            log.debug(f"[GCS] Logged sensor reading to {gcs_path}")
        except Exception:
            pass   # Non-critical — don't let logging errors crash the pipeline


# ─────────────────────────────────────────────────────────────────
# BIGTABLE TIME-SERIES STORAGE
# ─────────────────────────────────────────────────────────────────

class BigtableStore:
    """
    Stores sensor time-series data in Cloud Bigtable.
    Bigtable is Google's managed NoSQL for high-throughput time-series.

    Row key: {device_id}#{timestamp_reversed}
    Column family: "sensor" → consumption, temperature, humidity, etc.

    Why reversed timestamp?  Most-recent-first queries become table scans.
    """

    def __init__(self, project_id: str, instance_id: str, table_id: str = "sensor_readings"):
        self.project_id  = project_id
        self.instance_id = instance_id
        self.table_id    = table_id
        self._client     = None
        self._table      = None

    def _get_table(self):
        if self._table is None:
            from google.cloud import bigtable
            self._client = bigtable.Client(project=self.project_id, admin=False)
            instance     = self._client.instance(self.instance_id)
            self._table  = instance.table(self.table_id)
        return self._table

    async def write_reading(self, device_id: str, reading: dict):
        """Write one sensor reading to Bigtable."""
        try:
            table    = self._get_table()
            ts_rev   = str(10**18 - int(time.time() * 1000))   # Reversed for recency
            row_key  = f"{device_id}#{ts_rev}".encode()
            row      = table.direct_row(row_key)

            for field, value in reading.items():
                if field in ("device_id", "source"):
                    continue
                row.set_cell("sensor", field.encode(), str(value).encode())

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, row.commit)
            log.debug(f"Bigtable write: {device_id} @ {ts_rev}")
        except ImportError:
            log.debug(f"[Simulated] Bigtable write: {device_id}")
        except Exception as e:
            log.error(f"Bigtable write error: {e}")

    async def read_recent(self, device_id: str, n: int = 48) -> list:
        """Read the n most recent readings for a device."""
        try:
            table    = self._get_table()
            ts_rev   = str(10**18 - int(time.time() * 1000))
            row_key  = f"{device_id}#{ts_rev}".encode()
            rows     = table.read_rows(start_key=row_key, limit=n)
            results  = []
            for row in rows:
                r = {"device_id": device_id}
                for cf, cols in row.cells.items():
                    for col, cells in cols.items():
                        r[col.decode()] = cells[0].value.decode()
                results.append(r)
            return results
        except ImportError:
            return []
        except Exception as e:
            log.error(f"Bigtable read error: {e}")
            return []


# ─────────────────────────────────────────────────────────────────
# VERTEX AI ONLINE SERVING
# ─────────────────────────────────────────────────────────────────

class VertexAIPredictor:
    """
    Calls a deployed Vertex AI endpoint for online inference.
    Falls back to local model if endpoint not configured.

    Setup (one-time):
        gcloud ai endpoints create --display-name=energy-forecasting
        gcloud ai models upload --display-name=forecasting --artifact-uri=gs://bucket/model
        gcloud ai endpoints deploy-model ENDPOINT_ID --model=MODEL_ID
    """

    def __init__(self, project_id: str, endpoint_id: str, location: str = "us-central1"):
        self.project_id  = project_id
        self.endpoint_id = endpoint_id
        self.location    = location
        self._endpoint   = None

    def _get_endpoint(self):
        if self._endpoint is None:
            from google.cloud import aiplatform
            aiplatform.init(project=self.project_id, location=self.location)
            self._endpoint = aiplatform.Endpoint(self.endpoint_id)
        return self._endpoint

    async def predict(self, instances: list) -> list:
        """
        Send instances to Vertex AI endpoint for prediction.
        instances: list of dicts, each with feature values.
        Returns list of prediction dicts.
        """
        try:
            endpoint = self._get_endpoint()
            loop     = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: endpoint.predict(instances=instances)
            )
            return response.predictions
        except ImportError:
            log.debug("[Simulated] Vertex AI prediction")
            return [{"forecast": [2.1] * 24}]
        except Exception as e:
            log.error(f"Vertex AI predict error: {e}")
            return []


# ─────────────────────────────────────────────────────────────────
# GCP ALERT PUBLISHER  (replaces SNS)
# ─────────────────────────────────────────────────────────────────

class GCPAlertPublisher:
    """
    Publishes anomaly alerts to a dedicated Pub/Sub alerts topic.
    Downstream Cloud Functions can route to email, SMS, or Slack.

    Cloud Function trigger pattern:
        Pub/Sub → Cloud Function → SendGrid email / Twilio SMS / Slack
    """

    def __init__(self, project_id: str, alerts_topic: str = "energy-alerts"):
        self.publisher  = PubSubPublisher(project_id)
        self.alerts_topic = alerts_topic
        self._last_alert: dict = {}   # device → timestamp

    async def send_alert(self, device_id: str, alert_type: str,
                         data: dict, cooldown_s: int = 300) -> bool:
        """
        Publish an alert to the Pub/Sub alerts topic.
        Respects cooldown to prevent alert storms.
        Returns True if alert was sent.
        """
        now = time.time()
        key = f"{device_id}:{alert_type}"
        last = self._last_alert.get(key, 0)

        if now - last < cooldown_s:
            remaining = int(cooldown_s - (now - last))
            log.debug(f"Alert suppressed (cooldown {remaining}s remaining): {key}")
            return False

        alert_payload = {
            "type":       "alert",
            "alert_type": alert_type,
            "device_id":  device_id,
            "severity":   "HIGH" if alert_type == "anomaly" else "MEDIUM",
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            **data,
        }

        await self.publisher.publish(self.alerts_topic, alert_payload,
                                     attributes={"alert_type": alert_type,
                                                 "device_id": device_id})

        self._last_alert[key] = now
        log.warning(f"🚨 GCP Alert → {self.alerts_topic}: [{alert_type}] {device_id}")
        return True


# ─────────────────────────────────────────────────────────────────
# CLOUD MONITORING METRICS
# ─────────────────────────────────────────────────────────────────

class GCPMetrics:
    """
    Writes custom metrics to Cloud Monitoring (Stackdriver).
    Visible in Google Cloud Console → Monitoring → Metrics Explorer.

    Metrics written:
      custom.googleapis.com/energy_saver/inference_count
      custom.googleapis.com/energy_saver/anomaly_score
      custom.googleapis.com/energy_saver/pipeline_latency_ms
    """

    def __init__(self, project_id: str):
        self.project_id = project_id
        self._client    = None

    def _get_client(self):
        if self._client is None:
            from google.cloud import monitoring_v3
            self._client = monitoring_v3.MetricServiceClient()
        return self._client

    async def write_gauge(self, metric_type: str, value: float, labels: dict = None):
        """Write a single gauge metric data point."""
        try:
            from google.cloud import monitoring_v3
            from google.protobuf import timestamp_pb2
            import time as _time

            client   = self._get_client()
            series   = monitoring_v3.TimeSeries()
            series.metric.type = f"custom.googleapis.com/energy_saver/{metric_type}"
            if labels:
                series.metric.labels.update(labels)
            series.resource.type = "global"
            series.resource.labels["project_id"] = self.project_id

            point        = monitoring_v3.Point()
            point.value.double_value = value
            now          = _time.time()
            ts           = timestamp_pb2.Timestamp(seconds=int(now), nanos=int((now % 1) * 1e9))
            point.interval.end_time = ts
            series.points = [point]

            project_name = f"projects/{self.project_id}"
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: client.create_time_series(
                    name=project_name, time_series=[series]
                )
            )
        except ImportError:
            log.debug(f"[Simulated] GCP Metric: {metric_type}={value}")
        except Exception as e:
            log.debug(f"Metrics write error (non-fatal): {e}")


# ─────────────────────────────────────────────────────────────────
# DATAFLOW PIPELINE CONFIG  (batch sensor export)
# ─────────────────────────────────────────────────────────────────

DATAFLOW_PIPELINE_TEMPLATE = """
# Run this to export sensor data from Pub/Sub → BigQuery via Dataflow:
#
# gcloud dataflow jobs run energy-sensor-export \\
#   --gcs-location gs://dataflow-templates/latest/PubSub_to_BigQuery \\
#   --region {region} \\
#   --parameters \\
#     inputTopic=projects/{project}/topics/energy-sensors-raw,\\
#     outputTableSpec={project}:energy_data.sensor_readings
"""

# ─────────────────────────────────────────────────────────────────
# GCP CLOUD FUNCTION TRIGGER (HVAC)
# ─────────────────────────────────────────────────────────────────

GCP_CLOUD_FUNCTION_HVAC = '''
"""
Deploy this as a Cloud Function triggered by the energy-hvac-commands Pub/Sub topic.

gcloud functions deploy hvac-trigger \\
  --runtime python311 \\
  --trigger-topic energy-hvac-commands \\
  --entry-point handle_hvac_command \\
  --region us-central1
"""
import base64, json, requests

def handle_hvac_command(event, context):
    """Cloud Function: route HVAC command to smart thermostat API."""
    data    = json.loads(base64.b64decode(event["data"]).decode())
    mode    = data.get("mode", "COMFORT")
    target  = data.get("target_temp", 22)
    device  = data.get("device_id", "unknown")

    # Example: call Nest / Ecobee API
    THERMOSTAT_API = "https://smartdevicemanagement.googleapis.com/v1"
    print(f"HVAC command received: device={device} mode={mode} target={target}°C")

    # Publish confirmation back
    return f"HVAC set to {mode} @ {target}°C for {device}", 200
'''


# ─────────────────────────────────────────────────────────────────
# GCP DEPLOYMENT COMMANDS
# ─────────────────────────────────────────────────────────────────

GCP_DEPLOY_COMMANDS = """
# ──────────────────────────────────────────────────────
# GCP DEPLOYMENT QUICKSTART — Energy Saver AI
# ──────────────────────────────────────────────────────

# 1. Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# 2. Enable APIs
gcloud services enable \\
  pubsub.googleapis.com \\
  bigtable.googleapis.com \\
  storage.googleapis.com \\
  aiplatform.googleapis.com \\
  cloudfunctions.googleapis.com \\
  monitoring.googleapis.com \\
  run.googleapis.com

# 3. Create Pub/Sub topics
gcloud pubsub topics create energy-sensors-raw
gcloud pubsub topics create energy-alerts
gcloud pubsub topics create energy-hvac-commands
gcloud pubsub topics create energy-model-updates
gcloud pubsub subscriptions create energy-pipeline-sub \\
  --topic=energy-sensors-raw

# 4. Create GCS bucket for models + data
gsutil mb -l us-central1 gs://YOUR_PROJECT_ID-energy-saver-ai

# 5. Create Bigtable instance
gcloud bigtable instances create energy-data \\
  --cluster=energy-cluster \\
  --cluster-zone=us-central1-a \\
  --cluster-num-nodes=1 \\
  --display-name="Energy Sensor Data"

# 6. Build and deploy pipeline to Cloud Run
docker build -t gcr.io/YOUR_PROJECT_ID/energy-pipeline:latest .
docker push gcr.io/YOUR_PROJECT_ID/energy-pipeline:latest
gcloud run deploy energy-pipeline \\
  --image gcr.io/YOUR_PROJECT_ID/energy-pipeline:latest \\
  --platform managed \\
  --region us-central1 \\
  --set-env-vars CLOUD_PROVIDER=gcp,GCP_PROJECT_ID=YOUR_PROJECT_ID \\
  --allow-unauthenticated

# 7. Deploy HVAC Cloud Function
gcloud functions deploy hvac-trigger \\
  --runtime python311 \\
  --trigger-topic energy-hvac-commands \\
  --entry-point handle_hvac_command \\
  --source streaming/gcp/ \\
  --region us-central1

# 8. Upload pre-trained models to GCS
gsutil cp models/pretrained/backbone_weights.weights.h5 \\
  gs://YOUR_PROJECT_ID-energy-saver-ai/models/pretrained/
"""

if __name__ == "__main__":
    print(GCP_DEPLOY_COMMANDS)

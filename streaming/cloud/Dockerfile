# ============================================================
# Energy Saver AI -- Production Dockerfile
# Multi-stage build for minimal image size
# ============================================================

# ---- Build stage ----
FROM python:3.11-slim AS builder

WORKDIR /build

# System build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
 && rm -rf /var/lib/apt/lists/*

# Copy and install Python deps into a local prefix
COPY requirements.txt requirements_streaming.txt ./
RUN pip install --no-cache-dir --prefix=/install \
    -r requirements.txt \
    -r requirements_streaming.txt


# ---- Runtime stage ----
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="Energy Saver AI"
LABEL org.opencontainers.image.description="8-model AI energy management with live streaming"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Create non-root user for security
RUN adduser --disabled-password --gecos '' appuser \
 && chown -R appuser:appuser /app
USER appuser

# Create writable directories for models and outputs
RUN mkdir -p models/pretrained models/finetuned outputs logs data

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('localhost',8765)); s.close()" || exit 1

CMD ["python", "main.py", "stream"]

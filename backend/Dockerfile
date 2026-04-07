FROM python:3.11-slim AS base

WORKDIR /app

# Install backend dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy project source
COPY config/   /app/config/
COPY utils/    /app/utils/
COPY models/   /app/models/
COPY backend/  /app/backend/

ENV PYTHONPATH=/app:/app/backend
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/app/backend"]

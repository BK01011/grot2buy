FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc openssl curl && \
    rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Create directories
RUN mkdir -p /app/data /app/certs /app/static /app/templates

# Volumes
VOLUME ["/app/data", "/app/certs"]

EXPOSE 8899

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f https://localhost:8899/health --insecure || exit 1

# Auto-generate self-signed cert if none exists
RUN if [ ! -f /app/certs/server.crt ]; then \
      openssl req -x509 -newkey rsa:2048 -nodes \
        -keyout /app/certs/server.key -out /app/certs/server.crt \
        -days 3650 -subj "/CN=shopping-list" 2>/dev/null; \
    fi

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8899", \
     "--ssl-keyfile", "/app/certs/server.key", "--ssl-certfile", "/app/certs/server.crt"]

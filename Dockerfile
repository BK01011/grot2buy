FROM python:3.12-slim

WORKDIR /app

# System dependencies (nur openssl + curl, gcc nicht benötigt wegen wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssl curl && \
    rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Prepare directories
RUN mkdir -p /app/data /app/certs /app/static /app/templates && \
    if [ ! -f /app/certs/server.crt ]; then \
        openssl req -x509 -newkey rsa:2048 -nodes \
          -keyout /app/certs/server.key -out /app/certs/server.crt \
          -days 3650 -subj "/CN=shopping-list" 2>/dev/null; \
    fi

VOLUME ["/app/data", "/app/certs"]

EXPOSE 8899

HEALTHCHECK --interval=30s --timeout=15s --retries=5 \
    CMD curl -f https://localhost:8899/health --insecure || exit 1

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8899", \
     "--ssl-keyfile", "/app/certs/server.key", "--ssl-certfile", "/app/certs/server.crt"]

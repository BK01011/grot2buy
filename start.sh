#!/usr/bin/env bash
# Grot2Buy — Startskript
# Startet den Server nativ (Python) oder via Docker.
# Nutzung: ./start.sh [docker|native]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ "${1:-}" = "docker" ]; then
    echo "🚀 Starte Grot2Buy via Docker..."
    docker compose up -d
    echo "✅ Läuft unter https://localhost:8899"
elif [ "${1:-}" = "native" ]; then
    echo "🚀 Starte Grot2Buy nativ..."
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt
    else
        source venv/bin/activate
    fi
    python main.py
else
    echo "Nutzung: $0 [docker|native]"
    echo ""
    echo "  docker  — Start via Docker Compose (empfohlen)"
    echo "  native  — Start via Python (venv)"
    exit 1
fi

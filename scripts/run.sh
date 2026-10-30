#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then echo 'Primero ejecuta .venv/bin/python scripts/setup.py'; exit 1; fi
.venv/bin/python scripts/scheduler.py &
scheduler_pid=$!
trap 'kill "$scheduler_pid" 2>/dev/null || true' EXIT INT TERM
.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8443 --workers 3 --threads 4 --timeout 30 --pid .local/gunicorn.pid --certfile .local/tls-cert.pem --keyfile .local/tls-key.pem --access-logfile /dev/null --error-logfile -

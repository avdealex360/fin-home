#!/bin/bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/fin-home}"
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

cd "$APP_DIR"

echo "==> Fetch latest code"
git fetch origin main
git reset --hard origin/main

if [ ! -f .env ]; then
    echo "ERROR: .env not found. Copy from .env.example and configure secrets."
    exit 1
fi

mkdir -p data/backups

echo "==> Build and start containers"
$COMPOSE up -d --build

echo "==> Run database migrations"
$COMPOSE exec -T budget-app alembic upgrade head

echo "==> Health check"
$COMPOSE ps
$COMPOSE exec -T budget-app python -c "
import urllib.error, urllib.request
try:
    urllib.request.urlopen('http://127.0.0.1:8000/')
except urllib.error.HTTPError as e:
    if e.code not in (200, 401):
        raise
"

echo "==> Deploy complete"

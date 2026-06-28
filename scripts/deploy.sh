#!/bin/bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/fin-home}"

cd "$APP_DIR"

compose() {
    if docker compose version &>/dev/null; then
        docker compose -f docker-compose.yml -f docker-compose.prod.yml "$@"
    elif command -v docker-compose &>/dev/null; then
        docker-compose -f docker-compose.yml -f docker-compose.prod.yml "$@"
    else
        echo "ERROR: docker compose not found. As root run: apt install docker-compose-plugin"
        exit 1
    fi
}

echo "==> Fetch latest code"
git fetch origin main
git reset --hard origin/main

if [ ! -f .env ]; then
    echo "ERROR: .env not found. Copy from .env.example and configure secrets."
    exit 1
fi

mkdir -p data/backups

echo "==> Build and start containers"
compose up -d --build

echo "==> Run database migrations"
compose exec -T budget-app python -c "from app.migrations import run_migrations; run_migrations()"

echo "==> Health check"
compose ps
compose exec -T budget-app python -c "
import urllib.error, urllib.request
try:
    urllib.request.urlopen('http://127.0.0.1:8000/')
except urllib.error.HTTPError as e:
    if e.code not in (200, 401):
        raise
"

echo "==> Deploy complete"

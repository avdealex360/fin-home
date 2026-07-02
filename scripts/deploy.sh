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

wait_for_app() {
    local i
    echo "==> Waiting for budget-app (up to 60s)"
    for i in $(seq 1 30); do
        if compose exec -T budget-app python -c "
import urllib.error, urllib.request
try:
    urllib.request.urlopen('http://127.0.0.1:8000/', timeout=2)
except urllib.error.HTTPError as e:
    if e.code in (200, 401):
        raise SystemExit(0)
    raise
except Exception:
    raise SystemExit(1)
" 2>/dev/null; then
            echo "App ready (attempt $i)"
            return 0
        fi
        echo "  ... not ready yet ($i/30)"
        sleep 2
    done
    echo "ERROR: budget-app did not start"
    compose logs --tail=80 budget-app
    return 1
}

# --- git pull (once); re-exec so bash runs the updated script ---
if [ -z "${FIN_HOME_DEPLOY_REEXEC:-}" ]; then
    echo "==> Fetch latest code"
    git fetch origin main
    git reset --hard origin/main
    chmod +x scripts/*.sh 2>/dev/null || true
    export FIN_HOME_DEPLOY_REEXEC=1
    exec bash "$0" "$@"
fi

echo "==> Deploy fin-home ($(git rev-parse --short HEAD))"

if [ ! -f .env ]; then
    echo "ERROR: .env not found. Copy from .env.example and configure secrets."
    exit 1
fi

mkdir -p data/backups

if [ ! -f certs/cert.pem ]; then
    echo "==> Generate TLS certs"
    ./scripts/gen-certs.sh
fi

echo "==> Build and start containers"
export GIT_COMMIT="$(git rev-parse HEAD)"
compose build budget-app
compose up -d --force-recreate

wait_for_app

# Migrations run in app lifespan on startup; no separate exec needed.

echo "==> Health check"
compose ps
./scripts/prod-check.sh

echo "==> Deploy complete"

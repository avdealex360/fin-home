#!/bin/bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/fin-home}"
cd "$APP_DIR"

compose() {
    if docker compose version &>/dev/null; then
        docker compose -f docker-compose.yml -f docker-compose.prod.yml "$@"
    else
        docker-compose -f docker-compose.yml -f docker-compose.prod.yml "$@"
    fi
}

echo "==> budget-app (внутри сети)"
compose exec -T budget-app python -c "
import urllib.error
import urllib.request
try:
    urllib.request.urlopen('http://127.0.0.1:8000/')
except urllib.error.HTTPError as e:
    if e.code not in (200, 401):
        raise
"
echo "OK"

echo "==> caddy :443"
if compose exec -T caddy wget -qO- --timeout=5 --no-check-certificate https://127.0.0.1/ >/dev/null 2>&1; then
    echo "OK"
else
    echo "FAIL — см. make prod-logs"
    exit 1
fi

echo "==> caddy :80 (redirect)"
compose exec -T caddy wget -qSO- --timeout=5 http://127.0.0.1/ 2>&1 | head -5

echo "==> All checks passed"

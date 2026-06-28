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

wait_for_app() {
    local i
    for i in 1 2 3 4 5 6 7 8 9 10; do
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
            return 0
        fi
        sleep 2
    done
    return 1
}

echo "==> budget-app (внутри сети)"
if ! wait_for_app; then
    echo "FAIL — приложение не отвечает, см. make prod-logs"
    exit 1
fi
echo "OK"

echo "==> caddy :443 (budget-app → caddy по docker-сети)"
compose exec -T budget-app python -c "
import ssl
import urllib.error
import urllib.request

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
try:
    urllib.request.urlopen('https://caddy/', context=ctx, timeout=5)
except urllib.error.HTTPError as e:
    if e.code not in (200, 401):
        raise
"
echo "OK"

echo "==> caddy :443 (с хоста VPS)"
code="$(curl -ks -o /dev/null -w '%{http_code}' --connect-timeout 5 https://127.0.0.1/ || true)"
if [ "$code" = "401" ] || [ "$code" = "200" ]; then
    echo "OK (HTTP $code)"
else
    echo "FAIL — HTTP $code (ожидали 401 или 200)"
    exit 1
fi

echo "==> caddy :80 (redirect)"
curl -ksI --connect-timeout 5 http://127.0.0.1/ | head -3

echo "==> All checks passed"

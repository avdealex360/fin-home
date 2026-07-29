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

echo "==> caddy :443 (TLS + домен coin.lunalis.tech, с хоста VPS)"
# Caddy обслуживает только домен (Let's Encrypt), поэтому стучимся с
# SNI=coin.lunalis.tech на локальный caddy через --resolve. На «чужой» SNI
# (caddy / 127.0.0.1) сертификата нет → TLS alert, это НЕ признак сбоя.
# /api/health публичный → 200. Ретраи гасят задержку выпуска ACME-сертификата.
ok=""
for i in 1 2 3 4 5 6; do
    code="$(curl -s -o /dev/null -w '%{http_code}' \
        --resolve coin.lunalis.tech:443:127.0.0.1 \
        --connect-timeout 8 https://coin.lunalis.tech/api/health || true)"
    if [ "$code" = "200" ]; then ok=1; break; fi
    echo "  ... TLS/домен ещё не готов (HTTP $code), попытка $i/6"
    sleep 5
done
if [ -n "$ok" ]; then
    echo "OK (HTTP 200 via https://coin.lunalis.tech, Let's Encrypt)"
else
    echo "FAIL — https://coin.lunalis.tech/api/health не отвечает 200 (cert/DNS/Caddy)"
    exit 1
fi

echo "==> caddy :80 (redirect)"
curl -ksI --connect-timeout 5 http://127.0.0.1/ | head -3

echo "==> All checks passed"

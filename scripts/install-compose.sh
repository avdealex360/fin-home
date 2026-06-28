#!/bin/bash
# Install Docker Compose v2 plugin. Run as root on Ubuntu.
# Works when docker-compose-plugin is not in default apt repos.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root: sudo bash $0"
    exit 1
fi

if docker compose version &>/dev/null; then
    echo "Already installed: $(docker compose version)"
    exit 0
fi

echo "==> Try apt (Docker official repo)"
apt-get update
apt-get install -y ca-certificates curl

if [ ! -f /etc/apt/keyrings/docker.asc ]; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
fi

if [ ! -f /etc/apt/sources.list.d/docker.list ]; then
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${VERSION_CODENAME:-noble}") stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update
fi

if apt-get install -y docker-compose-plugin 2>/dev/null && docker compose version &>/dev/null; then
    echo "Installed via apt: $(docker compose version)"
    exit 0
fi

echo "==> Fallback: download compose binary"
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64) COMPOSE_ARCH="x86_64" ;;
    aarch64|arm64) COMPOSE_ARCH="aarch64" ;;
    *)
        echo "Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

PLUGIN_DIR="/usr/local/lib/docker/cli-plugins"
mkdir -p "$PLUGIN_DIR"
curl -fsSL "https://github.com/docker/compose/releases/download/v2.32.4/docker-compose-linux-${COMPOSE_ARCH}" \
    -o "${PLUGIN_DIR}/docker-compose"
chmod +x "${PLUGIN_DIR}/docker-compose"

if docker compose version &>/dev/null; then
    echo "Installed binary: $(docker compose version)"
    exit 0
fi

echo "ERROR: docker compose still not working. Check: docker --version"
exit 1

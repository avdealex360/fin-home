#!/bin/bash
# One-time VPS setup for fin-home. Run as root on Ubuntu 24.04.
# Usage: bash vps-setup.sh
set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-deploy}"
APP_DIR="${APP_DIR:-/opt/fin-home}"
REPO_URL="${REPO_URL:-https://github.com/avdealex360/fin-home.git}"
VPN_CIDR="${VPN_CIDR:-}"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root: sudo bash $0"
    exit 1
fi

echo "==> Install Docker"
if ! command -v docker &>/dev/null; then
    apt-get update
    apt-get install -y ca-certificates curl git ufw sqlite3
    curl -fsSL https://get.docker.com | sh
fi

echo "==> Create deploy user"
if ! id "$DEPLOY_USER" &>/dev/null; then
    useradd -m -s /bin/bash "$DEPLOY_USER"
    usermod -aG docker "$DEPLOY_USER"
fi

echo "==> Configure firewall"
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'

if [ -n "$VPN_CIDR" ]; then
    ufw allow from "$VPN_CIDR" to any port 80 proto tcp comment 'HTTP via VPN'
    ufw allow from "$VPN_CIDR" to any port 443 proto tcp comment 'HTTPS via VPN'
else
    ufw allow 80/tcp comment 'HTTP'
    ufw allow 443/tcp comment 'HTTPS'
fi

ufw --force enable

echo "==> Clone repository"
mkdir -p "$(dirname "$APP_DIR")"
if [ ! -d "$APP_DIR/.git" ]; then
    git clone "$REPO_URL" "$APP_DIR"
fi
chown -R "$DEPLOY_USER:$DEPLOY_USER" "$APP_DIR"

echo "==> Prepare data directory"
sudo -u "$DEPLOY_USER" mkdir -p "$APP_DIR/data/backups"
chmod +x "$APP_DIR/scripts/"*.sh 2>/dev/null || true

echo ""
echo "Setup complete."
echo ""
echo "Next steps:"
echo "  1. Add SSH public key for GitHub Actions to /home/$DEPLOY_USER/.ssh/authorized_keys"
echo "  2. As $DEPLOY_USER:"
echo "       cd $APP_DIR"
echo "       cp .env.example .env && nano .env"
echo "       docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build"
echo "  3. Add GitHub Secrets: VPS_HOST, VPS_USER, VPS_SSH_KEY"
echo "  4. Open https://194.154.29.93 (accept self-signed certificate warning)"
echo ""
if [ -n "$VPN_CIDR" ]; then
    echo "Note: HTTP/HTTPS restricted to VPN CIDR: $VPN_CIDR"
fi

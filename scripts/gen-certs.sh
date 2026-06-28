#!/bin/bash
# Self-signed TLS certificate for VPS IP (tls internal не работает на :443 без домена).
set -euo pipefail

IP="${VPS_IP:-194.154.29.93}"
CERT_DIR="${CERT_DIR:-./certs}"

mkdir -p "$CERT_DIR"

if [ -f "$CERT_DIR/cert.pem" ] && [ -f "$CERT_DIR/key.pem" ]; then
    echo "Certs already exist: $CERT_DIR"
    exit 0
fi

echo "Generating self-signed certificate for $IP"
openssl req -x509 -newkey rsa:2048 \
    -keyout "$CERT_DIR/key.pem" \
    -out "$CERT_DIR/cert.pem" \
    -days 825 -nodes \
    -subj "/CN=$IP" \
    -addext "subjectAltName=IP:$IP,DNS:$IP"

chmod 600 "$CERT_DIR/key.pem"
echo "OK: $CERT_DIR/cert.pem"

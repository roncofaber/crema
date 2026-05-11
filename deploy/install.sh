#!/bin/bash
# Install CREMA systemd services.
# Run from the repo root: bash deploy/install.sh

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_DIR=/etc/systemd/system

echo "Installing services from $REPO_DIR"

sudo cp "$REPO_DIR/deploy/crema-kiosk.service" "$SERVICE_DIR/"
sudo cp "$REPO_DIR/deploy/crema-api.service"   "$SERVICE_DIR/"

# Patch WorkingDirectory and ExecStart to use the actual repo path
PYTHON="$REPO_DIR/venv/bin/python"
CREMA="$REPO_DIR/venv/bin/crema"

sudo sed -i "s|WorkingDirectory=.*|WorkingDirectory=$REPO_DIR|g" \
    "$SERVICE_DIR/crema-kiosk.service" \
    "$SERVICE_DIR/crema-api.service"

sudo sed -i "s|ExecStart=.*/python main.py|ExecStart=$PYTHON main.py|g" \
    "$SERVICE_DIR/crema-kiosk.service"

sudo sed -i "s|ExecStart=.*/crema serve|ExecStart=$CREMA serve|g" \
    "$SERVICE_DIR/crema-api.service"

sudo systemctl daemon-reload
sudo systemctl enable crema-kiosk crema-api
sudo systemctl start  crema-kiosk crema-api

echo "Done. Check status with: sudo systemctl status crema-kiosk crema-api"

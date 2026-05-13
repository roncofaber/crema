#!/bin/bash
# Install CREMA systemd services.
# Run from the repo root: bash deploy/install.sh

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_DIR=/etc/systemd/system

echo "Installing services from $REPO_DIR"

sudo cp "$REPO_DIR/deploy/crema-kiosk.service"  "$SERVICE_DIR/"
sudo cp "$REPO_DIR/deploy/crema-browser.service" "$SERVICE_DIR/"

# Patch WorkingDirectory and ExecStart to use the actual repo path
PYTHON="$REPO_DIR/venv/bin/python"

sudo sed -i "s|WorkingDirectory=.*|WorkingDirectory=$REPO_DIR|g" \
    "$SERVICE_DIR/crema-kiosk.service"

sudo sed -i "s|ExecStart=.*/python main.py|ExecStart=$PYTHON main.py|g" \
    "$SERVICE_DIR/crema-kiosk.service"

sudo systemctl daemon-reload
sudo systemctl enable crema-kiosk crema-browser
sudo systemctl start  crema-kiosk crema-browser

echo "Done. Check status with: sudo systemctl status crema-kiosk crema-browser"

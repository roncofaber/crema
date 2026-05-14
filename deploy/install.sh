#!/bin/bash
# Install CREMA: build deps, dashboard, and systemd services.
# Run from the repo root: bash deploy/install.sh

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_DIR=/etc/systemd/system
PYTHON="$REPO_DIR/venv/bin/python"

echo "Installing CREMA from $REPO_DIR"

# Check prerequisites
if ! command -v node &>/dev/null; then
    echo "ERROR: Node.js not found. Install with: curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash - && sudo apt-get install -y nodejs"
    exit 1
fi
if ! command -v npm &>/dev/null; then
    echo "ERROR: npm not found. Install Node.js 18+."
    exit 1
fi

# Python venv + package
if [ ! -d "$REPO_DIR/venv" ]; then
    python3 -m venv "$REPO_DIR/venv"
fi
"$REPO_DIR/venv/bin/pip" install -e "$REPO_DIR" --quiet

# React dashboard
cd "$REPO_DIR/dashboard"
npm install --silent
npm run build

# Systemd service files
cd "$REPO_DIR"
sudo cp deploy/crema-kiosk.service  "$SERVICE_DIR/"
sudo cp deploy/crema-browser.service "$SERVICE_DIR/"

sudo sed -i "s|WorkingDirectory=.*|WorkingDirectory=$REPO_DIR|g" \
    "$SERVICE_DIR/crema-kiosk.service"

sudo sed -i "s|ExecStart=.*/python main.py|ExecStart=$PYTHON main.py|g" \
    "$SERVICE_DIR/crema-kiosk.service"

sudo systemctl daemon-reload
sudo systemctl enable crema-kiosk crema-browser
sudo systemctl start  crema-kiosk crema-browser

echo "Done. Check status with: sudo systemctl status crema-kiosk crema-browser"
echo ""
echo "Optional: set API token in /etc/systemd/system/crema-kiosk.service.d/env.conf"
echo "  [Service]"
echo "  Environment=CREMA_API_TOKEN=your-secret-token"
echo "Then: sudo systemctl daemon-reload && sudo systemctl restart crema-kiosk"

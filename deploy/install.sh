#!/bin/bash
# Install CREMA: build deps, dashboard, and systemd services.
# Run from the repo root: bash deploy/install.sh

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_DIR=/etc/systemd/system
PYTHON="$REPO_DIR/venv/bin/python"
SERVICE_USER="$(id -un)"

echo "Installing CREMA from $REPO_DIR"

# Check prerequisites
if ! command -v node &>/dev/null; then
    echo "ERROR: Node.js not found. Install Node.js 22.12 or newer."
    exit 1
fi
if ! node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit((major === 20 && minor >= 19) || (major === 22 && minor >= 12) || major >= 23 ? 0 : 1)'; then
    echo "ERROR: Node.js 20.19+ or 22.12+ is required. Found $(node --version)."
    exit 1
fi
if ! command -v npm &>/dev/null; then
    echo "ERROR: npm not found. Install Node.js 20.19+ or 22.12+."
    exit 1
fi

# Python venv + package
if [ ! -d "$REPO_DIR/venv" ]; then
    python3 -m venv "$REPO_DIR/venv"
fi
"$REPO_DIR/venv/bin/pip" install -e "$REPO_DIR" --quiet

# React dashboard
cd "$REPO_DIR/dashboard"
npm ci --silent
if [ -n "${CREMA_API_TOKEN:-}" ] && [ -z "${VITE_API_TOKEN:-}" ]; then
    export VITE_API_TOKEN="$CREMA_API_TOKEN"
fi
npm run build

# Systemd service files
cd "$REPO_DIR"
sudo cp deploy/crema-kiosk.service  "$SERVICE_DIR/"
sudo cp deploy/crema-browser.service "$SERVICE_DIR/"

sudo sed -i "s|WorkingDirectory=.*|WorkingDirectory=$REPO_DIR|g" \
    "$SERVICE_DIR/crema-kiosk.service"

sudo sed -i "s|User=.*|User=$SERVICE_USER|g" \
    "$SERVICE_DIR/crema-kiosk.service" \
    "$SERVICE_DIR/crema-browser.service"

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
echo "Then rebuild with CREMA_API_TOKEN exported so the browser uses the same token."

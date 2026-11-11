#!/bin/bash
# Pull latest code, rebuild dashboard, restart services.
# Run from the repo root: bash deploy/update.sh

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_USER="$(id -un)"
SERVICE_DIR=/etc/systemd/system
DB_PATH="${CREMA_DB_PATH:-$REPO_DIR/data/espresso.db}"
BACKUP_PATH="${CREMA_BACKUP_DIR:-${BACKUP_DIR:-$REPO_DIR/data/backups}}"

echo "Updating CREMA from $REPO_DIR"

if [ -x "$REPO_DIR/venv/bin/crema" ] && [ -f "$DB_PATH" ]; then
    CREMA_DB_PATH="$DB_PATH" CREMA_BACKUP_DIR="$BACKUP_PATH" \
        "$REPO_DIR/venv/bin/crema" db backup
fi

git -C "$REPO_DIR" pull

cd "$REPO_DIR/dashboard"
npm ci --silent
if [ -n "${CREMA_API_TOKEN:-}" ] && [ -z "${VITE_API_TOKEN:-}" ]; then
    export VITE_API_TOKEN="$CREMA_API_TOKEN"
fi
npm run build

cd "$REPO_DIR"
"$REPO_DIR/venv/bin/pip" install -e . --quiet

if systemctl is-active --quiet crema-api.service 2>/dev/null; then
    sudo systemctl stop crema-api.service
fi
if systemctl is-enabled --quiet crema-api.service 2>/dev/null; then
    sudo systemctl disable crema-api.service
fi
sudo rm -f "$SERVICE_DIR/crema-api.service"

# Sync service files in case they changed, re-applying path patches
PYTHON="$REPO_DIR/venv/bin/python"
sudo cp deploy/crema-kiosk.service "$SERVICE_DIR/"
sudo cp deploy/crema-browser.service "$SERVICE_DIR/"
sudo sed -i "s|WorkingDirectory=.*|WorkingDirectory=$REPO_DIR|g" \
    "$SERVICE_DIR/crema-kiosk.service"
sudo sed -i "s|User=.*|User=$SERVICE_USER|g" \
    "$SERVICE_DIR/crema-kiosk.service" \
    "$SERVICE_DIR/crema-browser.service"
sudo sed -i "s|ExecStart=.*/python main.py|ExecStart=$PYTHON main.py|g" \
    "$SERVICE_DIR/crema-kiosk.service"
sudo systemctl daemon-reload

sudo systemctl restart crema-kiosk crema-browser
sudo systemctl status crema-kiosk crema-browser --no-pager

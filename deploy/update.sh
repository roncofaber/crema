#!/bin/bash
# Pull latest code, rebuild dashboard, restart services.
# Run from the repo root: bash deploy/update.sh

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "Updating CREMA from $REPO_DIR"

git -C "$REPO_DIR" pull

cd "$REPO_DIR/dashboard"
npm install --silent
npm run build

cd "$REPO_DIR"
"$REPO_DIR/venv/bin/pip" install -e . --quiet

# Sync service files in case they changed, re-applying path patches
PYTHON="$REPO_DIR/venv/bin/python"
sudo cp deploy/crema-kiosk.service  /etc/systemd/system/
sudo cp deploy/crema-browser.service /etc/systemd/system/
sudo sed -i "s|WorkingDirectory=.*|WorkingDirectory=$REPO_DIR|g" \
    /etc/systemd/system/crema-kiosk.service
sudo sed -i "s|ExecStart=.*/python main.py|ExecStart=$PYTHON main.py|g" \
    /etc/systemd/system/crema-kiosk.service
sudo systemctl daemon-reload

sudo systemctl restart crema-kiosk crema-browser
sudo systemctl status crema-kiosk crema-browser --no-pager

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
pip install -e . --quiet

sudo systemctl restart crema-kiosk crema-api
sudo systemctl status crema-kiosk crema-api --no-pager

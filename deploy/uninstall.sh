#!/bin/bash
# Remove CREMA systemd services.
# Run from the repo root: bash deploy/uninstall.sh

set -e

SERVICE_DIR=/etc/systemd/system
SERVICES="crema-kiosk crema-browser crema-api"

echo "Stopping and disabling CREMA services..."
for svc in $SERVICES; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        sudo systemctl stop "$svc"
    fi
    if systemctl is-enabled --quiet "$svc" 2>/dev/null; then
        sudo systemctl disable "$svc"
    fi
    if [ -f "$SERVICE_DIR/$svc.service" ]; then
        sudo rm "$SERVICE_DIR/$svc.service"
        echo "  Removed $svc.service"
    fi
done

sudo systemctl daemon-reload
echo "Done. Re-install with: bash deploy/install.sh"

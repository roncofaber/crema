# CREMA - Deployment

## Target

Raspberry Pi 4 running Raspberry Pi OS (bookworm). Python 3.11+. Node 20.19+ or 22.12+ for building the dashboard.

## Services

Two systemd units:

| Service | File | What it runs |
|---|---|---|
| `crema-kiosk` | `deploy/crema-kiosk.service` | `python main.py` - hardware + API in one process |
| `crema-browser` | `deploy/crema-browser.service` | Chromium in kiosk mode at `http://localhost:8000/kiosk` |

`crema-browser` starts 5 s after `crema-kiosk` to give the API time to bind.

> `crema-api.service` (legacy) is retired. Do not enable it.

## Uninstall / fresh start

```bash
bash deploy/uninstall.sh   # stops, disables, and removes all service files
bash deploy/install.sh     # re-install from scratch
```

`uninstall.sh` also removes the legacy `crema-api` service if present.

## First-time install

```bash
git clone <repo> ~/crema
cd ~/crema
./deploy/install.sh
```

The script:
1. Creates `~/crema/venv` (if absent) and installs Python deps (`pip install -e .`)
2. Builds the React dashboard (`npm ci && npm run build` in `dashboard/`)
3. Copies service files to `/etc/systemd/system/`
4. Enables and starts `crema-kiosk` and `crema-browser`

## Updates

```bash
cd ~/crema
./deploy/update.sh
```

Pulls latest code, rebuilds dashboard, reinstalls package, restarts both services.

If the live database exists, the update script creates a consistent timestamped backup in `data/backups/` before pulling code.

## Environment

Set `CREMA_API_TOKEN` in `/etc/systemd/system/crema-kiosk.service.d/env.conf` (create the drop-in):

```ini
[Service]
Environment=CREMA_API_TOKEN=your-secret-token
```

Then: `sudo systemctl daemon-reload && sudo systemctl restart crema-kiosk`

The browser bundle also needs the token when authentication is enabled. Export the same value before installing or updating so the build receives it automatically:

```bash
export CREMA_API_TOKEN=your-secret-token
./deploy/update.sh
```

The token is embedded in the browser bundle. Use this mode only on a trusted local network. Use network-level access controls if the service is reachable outside that network.

## I2C setup

```bash
sudo raspi-config  # Interface Options, then I2C, then Enable
sudo reboot
```

## Logs

```bash
crema logs kiosk    # follow crema-kiosk journal
crema logs all      # both services

# Or directly:
journalctl -fu crema-kiosk
journalctl -fu crema-browser
```

## Manual service commands

```bash
sudo systemctl status crema-kiosk
sudo systemctl restart crema-kiosk
sudo systemctl stop crema-browser   # kill Chromium
```

Readiness can be checked locally with:

```bash
curl --fail http://localhost:8000/health
```

## Python dependencies (hardware-only)

`adafruit-circuitpython-adxl34x` requires the Pi's I2C bus and CircuitPython board abstraction (`board`, `busio`). These are available on Pi OS but not on a development laptop. The sensor imports them only when its hardware thread connects, so tests can run without them.

## Dashboard env vars (optional)

Set in `dashboard/.env.local` for local dev, or bake into the build:

| Var | Purpose |
|---|---|
| `VITE_API_URL` | API base URL (default: same origin) |
| `VITE_API_TOKEN` | Bearer token for API calls |

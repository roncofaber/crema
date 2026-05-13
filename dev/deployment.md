# CREMA — Deployment

## Target

Raspberry Pi 4 running Raspberry Pi OS (bookworm). Python 3.11+. Node 18+ for building the dashboard.

## Services

Two systemd units:

| Service | File | What it runs |
|---|---|---|
| `crema-kiosk` | `deploy/crema-kiosk.service` | `python main.py` — hardware + API in one process |
| `crema-browser` | `deploy/crema-browser.service` | Chromium in kiosk mode at `http://localhost:8000/kiosk` |

`crema-browser` starts 5 s after `crema-kiosk` to give the API time to bind.

> `crema-api.service` (legacy) is retired. Do not enable it.

## First-time install

```bash
git clone <repo> ~/crema
cd ~/crema
./deploy/install.sh
```

The script:
1. Creates `~/crema/venv` and installs Python deps (`pip install -e .`)
2. Builds the React dashboard (`npm ci && npm run build` in `dashboard/`)
3. Copies service files to `/etc/systemd/system/`
4. Enables and starts `crema-kiosk` and `crema-browser`

## Updates

```bash
cd ~/crema
./deploy/update.sh
```

Pulls latest code, rebuilds dashboard, reinstalls package, restarts both services.

## Environment

Set `CREMA_API_TOKEN` in `/etc/systemd/system/crema-kiosk.service.d/env.conf` (create the drop-in):

```ini
[Service]
Environment=CREMA_API_TOKEN=your-secret-token
```

Then: `sudo systemctl daemon-reload && sudo systemctl restart crema-kiosk`

## SPI setup

```bash
sudo raspi-config  # Interface Options → SPI → Enable
sudo reboot
```

## Logs

```bash
crema logs kiosk    # follow crema-kiosk journal
crema logs api      # (same service now, alias kept for muscle memory)
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

## Python dependencies (hardware-only)

`adafruit-circuitpython-adxl34x` requires the Pi's SPI bus and CircuitPython board abstraction (`board`, `busio`, `digitalio`). These are available on Pi OS but not on a dev laptop — the sensor import is guarded in `hardware/sensor.py` inside `start()` so tests can run without them.

## Dashboard env vars (optional)

Set in `dashboard/.env.local` for local dev, or bake into the build:

| Var | Purpose |
|---|---|
| `VITE_API_URL` | API base URL (default: same origin) |
| `VITE_API_TOKEN` | Bearer token for API calls |

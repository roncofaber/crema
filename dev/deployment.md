# CREMA - Deployment

## Target

Raspberry Pi 4 running Raspberry Pi OS (bookworm). Python 3.11+. Node 24.15.0 or newer for building the dashboard.

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

If the live database exists, the update script creates a consistent, integrity-verified timestamped backup before pulling code, then applies configured retention. Export the same `CREMA_DB_PATH` and `CREMA_BACKUP_DIR` values used by the service so maintenance targets the configured database rather than only the default paths. `CREMA_BACKUP_RETENTION_COUNT` defaults to 14; `CREMA_BACKUP_RETENTION_DAYS` defaults to 0, which disables age pruning. Stop `crema-kiosk` before `crema db restore`; restore acquires the service lock and refuses to replace the database while it's running. See `docs/operations.md` for retention and recovery details.

## Environment

The service binds to `127.0.0.1` by default, which is sufficient for the local Chromium kiosk. To expose the dashboard on the LAN, set `CREMA_HOST` and `CREMA_API_TOKEN` in `/etc/systemd/system/crema-kiosk.service.d/env.conf` (create the drop-in):

```ini
[Service]
Environment=CREMA_HOST=0.0.0.0
Environment=CREMA_API_TOKEN=your-secret-token
```

Then: `sudo systemctl daemon-reload && sudo systemctl restart crema-kiosk`

Non-loopback startup fails without a token or complete session-auth configuration unless `CREMA_ALLOW_INSECURE=1` is explicitly configured. Keep that override limited to controlled networks.

For optional password sessions, use this drop-in instead of embedding a browser token:

```ini
[Service]
Environment=CREMA_HOST=0.0.0.0
Environment=CREMA_AUTH_MODE=session
Environment=CREMA_ADMIN_PASSWORD=replace-with-a-long-password
Environment=CREMA_SESSION_SECRET=replace-with-at-least-32-random-bytes
```

The dashboard and kiosk use an HttpOnly, Strict session cookie. In this mode, the touch kiosk displays a compact administrator sign-in screen before enabling controls; an expired or revoked session returns it to that screen. `CREMA_SESSION_TTL` defaults to 43200 seconds. Session cookies default to HTTPS-only, so deploy HTTPS for LAN access or, only for local HTTP development, set `CREMA_COOKIE_SECURE=0`. Do not disable the secure-cookie requirement on an untrusted network.

The kiosk unit uses `Restart=always`. A fatal hardware-loop error requests a graceful `SIGTERM`, and systemd starts a fresh owner after five seconds; a clean stop still terminates the process and would also be restarted unless the service is stopped through systemctl.

In token mode, the browser bundle also needs the token. Export the same value before installing or updating so the build receives it automatically:

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

## Logs and monitoring

Set `CREMA_LOG_LEVEL`, `CREMA_LOG_FORMAT=jsonl`, and optionally `CREMA_LOG_FILE` in the kiosk service drop-in for structured runtime logs. The default text output continues to flow to the journal. File logs are append-only and need external rotation. The passive `crema-monitor` command can record selected metrics and systemd state without controlling either service. Configuration, Prometheus scraping, and JSONL examples are in `docs/operations.md`.

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

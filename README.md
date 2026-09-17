# CREMA

Coffee Realtime Event Monitoring Application - the kiosk and dashboard for **Caffè Cabrini**.

A Raspberry Pi kiosk that tracks who makes espresso, how many shots, and for how long. Users scan a QR code (email) before using the machine; an accelerometer detects each brew cycle and logs it to SQLite. A web dashboard shows live stats, a leaderboard, and recent brews. A touch UI on the 5" kiosk display lets users control shot type, decaf, and rate their brew.

## Hardware

- Raspberry Pi 4
- FREENOVE 5" MIPI DSI touchscreen (800×480, capacitive touch) - driver-free, plug-and-play
- ADXL345 3-axis accelerometer (GY-291) via I2C
- MINJCODE MJ2818A USB HID QR code scanner

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

The scanner is detected automatically by device name. The database is created at `data/espresso.db` on first run. Enable I2C (`raspi-config` then Interface Options then I2C) before running on the Pi.

For API-only local development, frontend setup, isolated test databases, and verification commands, see [`dev/development.md`](dev/development.md).

## CLI

All commands are available through the `crema` entry point.

```
crema serve       Start the combined hardware + API server (default: 0.0.0.0:8000)
crema logs        View live service logs
crema stats       Show the stats dashboard (terminal)
crema users       User management
crema db          Database utilities
crema sensor      Live ADXL345 accelerometer monitor (calibration tool)
```

### `crema serve`

```bash
crema serve [--host HOST] [--port PORT] [--reload]
```

Starts the FastAPI server. The React dashboard is served at `/ui`; the kiosk touch UI at `/kiosk`.

### `crema sensor`

Live terminal readout of the ADXL345 accelerometer - useful for calibrating `ADXL_BREW_THRESHOLD`:

```
ADXL345 - live readout  (Ctrl+C to quit)
───────────────────────────────────────────
  X: +0.123  Y: -9.812  Z: +1.045 m/s²  mag: 9.899  peak:12.341  [ACTIVE]  [████████░░░░░░░░░░░░░░░░░░░░]
```

### `crema logs`

```bash
crema logs all    # Follow both kiosk and browser logs
crema logs kiosk  # Follow kiosk (hardware + API) logs only

# Show more history before following:
crema logs all -n 200
```

### `crema users`

```bash
crema users list
crema users show <name>
crema users rename <name> <new-name>
crema users edit <name>     # opens $EDITOR
crema users delete <name>
```

### `crema db`

Database maintenance utilities:

```bash
crema db backup [OUTPUT]
crema db check [DATABASE]
crema db restore BACKUP
crema db export [OUTPUT]
crema db reclassify
```

## API

FastAPI server at port 8000. Full reference: [`dev/api-reference.md`](dev/api-reference.md).

| Path | Description |
|---|---|
| `GET /` | Health check |
| `GET /health` | Database and hardware readiness |
| `GET /status` | Current machine state and active user |
| `GET /brews/` | Recent brew records |
| `GET /stats/` | Aggregate totals |
| `GET /stats/daily` | Per-day brew counts (last 30 days) |
| `GET /users/` | All registered users |
| `POST /kiosk/logout` | Force end current session |
| `POST /kiosk/brew-options` | Set shot type / decaf for session |
| `POST /kiosk/rate` | Submit 1–5 star rating for a brew |
| `WS /ws/kiosk` | Real-time state stream (no auth) |
| `/ui` | React dashboard (SPA) |
| `/kiosk` | Touch kiosk UI (SPA) |

**Authentication:** set `CREMA_API_TOKEN` in the service environment. When building the browser UI, set `VITE_API_TOKEN` to the same value or export `CREMA_API_TOKEN` before running the deployment scripts. Data and control REST routes then require `Authorization: Bearer <token>`; `/`, `/health`, and the WebSocket remain public. Browser tokens are visible to users, so use this mode only on a trusted local network.

## Dashboard

The React dashboard at `/ui` refreshes live data periodically and shows:

- Live brewing strip when the machine is active
- Stats cards (total brews, total time, users)
- Leaderboard
- Daily brew chart (last 30 days)
- Recent brews with relative timestamps

## Kiosk touch UI

The kiosk UI at `/kiosk` runs full-screen on the 5" DSI touchscreen via Chromium. It connects to `/ws/kiosk` for real-time state and shows:

- **Idle**: waiting for QR scan
- **Armed**: user name, brew count, shot type / decaf toggles, logout button, session timeout bar
- **Brewing**: brew counter, elapsed time, progress bar, adjustable shot type / decaf
- **Summary**: session brew count, brew time, and average rating
- **Rating prompt**: 1–5 stars after each brew (auto-dismisses after 15 s)

## Deployment

### First-time setup

```bash
./deploy/install.sh
```

Creates a Python venv, builds the dashboard, installs `crema` into the venv, and installs + starts the `crema-kiosk` and `crema-browser` systemd services.

### Updates

```bash
./deploy/update.sh
```

Pulls latest code, rebuilds the dashboard, reinstalls the package, and restarts both services.

### Services

| Service | Description |
|---|---|
| `crema-kiosk` | Hardware loop + FastAPI server (single merged process) |
| `crema-browser` | Chromium kiosk mode at `http://localhost:8000/kiosk` |

Set `CREMA_API_TOKEN` in the service environment to enable auth. See [`dev/deployment.md`](dev/deployment.md) for details.

## Project layout

```
api/          FastAPI app (routers, auth, deps, schemas)
cli/          Click CLI commands
core/         events, state machine, database, kiosk singleton
dashboard/    React + Vite frontend (dashboard + kiosk UI)
deploy/       systemd service files and install/update scripts
dev/          Developer documentation (architecture, FSM, API, hardware)
hardware/     QR scanner and ADXL345 accelerometer drivers
tests/        pytest suite
config.py     all tuneable constants
main.py       entry point - hardware + API in one process
```

## Configuration

Configuration defaults live in `config.py` and can be overridden through environment variables.

| Environment variable | Default | Description |
|---|---|---|
| `CREMA_ADXL_BREW_THRESHOLD` | 11.5 m/s² | Magnitude above this = machine active |
| `CREMA_ADXL_SAMPLE_RATE` | 50 Hz | Accelerometer polling rate |
| `CREMA_MIN_BREW_DURATION` | 10 s | Below this, vibration logged as noise |
| `CREMA_BREW_END_SILENCE` | 10 s | Silence needed to end a brew cycle |
| `CREMA_MIN_VIBRATION_PULSE` | 0.5 s | Minimum high pulse to reset the silence timer |
| `CREMA_BREW_CONFIRM_WINDOW` | 2 s | Sustained vibration before BrewStart fires |
| `CREMA_ARMED_TIMEOUT` | 120 s | Time to wait for the machine after scanning |
| `CREMA_SESSION_TIMEOUT` | 300 s | Idle time after the last brew |
| `CREMA_SUMMARY_DURATION` | 5 s | Summary screen duration |
| `CREMA_SCANNER_DEVICE_NAME` | MINJCODE device name | USB scanner name |
| `CREMA_DB_PATH` | `data/espresso.db` | SQLite database path |
| `CREMA_BACKUP_DIR` | `data/backups` | Automatic backup directory |

## Further reading

- [`dev/architecture.md`](dev/architecture.md) - process model, module map, sync/async bridge
- [`dev/development.md`](dev/development.md) - local setup, API-only mode, tests, and visual checks
- [`dev/state-machine.md`](dev/state-machine.md) - FSM states, transitions, snapshot payload
- [`dev/api-reference.md`](dev/api-reference.md) - all REST and WebSocket endpoints
- [`dev/hardware.md`](dev/hardware.md) - wiring, calibration, sensor driver internals
- [`dev/kiosk-ui.md`](dev/kiosk-ui.md) - React kiosk UI, screens, WebSocket hook
- [`dev/deployment.md`](dev/deployment.md) - systemd services, install, env vars

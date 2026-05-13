# CREMA

Coffee Realtime Event Monitoring Application — the kiosk and dashboard for **Caffè Cabrini**.

A Raspberry Pi kiosk that tracks who makes espresso, how many shots, and for how long. Users scan a QR code (email) before using the machine; an accelerometer detects each brew cycle and logs it to SQLite. A web dashboard shows live stats, a leaderboard, and recent brews. A touch UI on the 5" kiosk display lets users control shot type, decaf, and rate their brew.

## Hardware

- Raspberry Pi 4
- FREENOVE 5" MIPI DSI touchscreen (800×480, capacitive touch) — driver-free, plug-and-play
- ADXL345 3-axis accelerometer (GY-291) via SPI on CE1
- MINJCODE MJ2818A USB HID QR code scanner

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

The scanner is detected automatically by device name. The database is created at `data/espresso.db` on first run. Enable SPI (`raspi-config → Interface Options → SPI`) before running on the Pi.

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

Live terminal readout of the ADXL345 accelerometer — useful for calibrating `ADXL_BREW_THRESHOLD`:

```
ADXL345 — live readout  (Ctrl+C to quit)
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

Database initialisation and migration utilities.

## API

FastAPI server at port 8000. Full reference: [`dev/api-reference.md`](dev/api-reference.md).

| Path | Description |
|---|---|
| `GET /` | Health check |
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

**Authentication:** set `CREMA_API_TOKEN` in the environment. All REST routes then require `Authorization: Bearer <token>`. The WebSocket has no auth.

## Dashboard

The React dashboard at `/ui` auto-refreshes every 5 seconds and shows:

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
- **Summary**: session summary with average brew rating
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
tests/        pytest suite (81 tests)
config.py     all tuneable constants
main.py       entry point — hardware + API in one process
```

## Configuration

All thresholds and timeouts are in `config.py`.

| Constant | Default | Description |
|---|---|---|
| `ADXL_BREW_THRESHOLD` | 11.5 m/s² | Magnitude above this = machine active |
| `ADXL_SAMPLE_RATE` | 50 Hz | Accelerometer polling rate |
| `MIN_BREW_DURATION` | 10 s | Below this, vibration logged as noise |
| `BREW_END_SILENCE` | 10 s | Silence needed to end a brew cycle |
| `MIN_VIBRATION_PULSE` | 0.5 s | Minimum HIGH pulse to reset silence timer |
| `BREW_CONFIRM_WINDOW` | 2 s | Sustained vibration before BrewStart fires |
| `ARMED_TIMEOUT` | 120 s | Time to wait for machine after scan (no brew yet) |
| `SESSION_TIMEOUT` | 300 s | Idle time after last brew before auto-logout |
| `SUMMARY_DURATION` | 5 s | Summary screen shown after session ends |

## Further reading

- [`dev/architecture.md`](dev/architecture.md) — process model, module map, sync/async bridge
- [`dev/state-machine.md`](dev/state-machine.md) — FSM states, transitions, snapshot payload
- [`dev/api-reference.md`](dev/api-reference.md) — all REST and WebSocket endpoints
- [`dev/hardware.md`](dev/hardware.md) — wiring, calibration, sensor driver internals
- [`dev/kiosk-ui.md`](dev/kiosk-ui.md) — React kiosk UI, screens, WebSocket hook
- [`dev/deployment.md`](dev/deployment.md) — systemd services, install, env vars

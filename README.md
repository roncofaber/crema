# CREMA

Coffee Realtime Event Monitoring Application — the kiosk and dashboard for **Caffè Cabrini**.

A Raspberry Pi kiosk that tracks who makes espresso, how many shots, and for how long. Users scan a QR code (email) before using the machine; a vibration sensor detects each brew cycle and logs it to SQLite. A web dashboard shows live stats, a leaderboard, and recent brews.

## Hardware

- Raspberry Pi 4
- Waveshare ST7789 240×320 SPI LCD
- SW-420 vibration sensor (GPIO pin 17)
- USB HID QR code scanner (MINJCODE MJ2818A)

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

The scanner is detected automatically by device name (`MINJCODE MJ2818A`). The database is created at `data/espresso.db` on first run.

## CLI

All commands are available through the `crema` entry point.

```
crema serve       Start the API server (default: 0.0.0.0:8000)
crema logs        View live service logs
crema stats       Show the stats dashboard (terminal)
crema users       User management
crema db          Database utilities
crema sensor      Live vibration sensor monitor
```

### `crema serve`

```bash
crema serve [--host HOST] [--port PORT] [--reload]
```

Starts the FastAPI server. The dashboard is served at `/ui`.

### `crema logs`

```bash
crema logs all    # Follow both kiosk and API logs
crema logs kiosk  # Follow kiosk logs only
crema logs api    # Follow API logs only

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

### `crema sensor`

Live terminal readout of the vibration sensor — useful for calibrating thresholds.

## API

The FastAPI server exposes a REST API and serves the React dashboard.

| Path | Description |
|---|---|
| `GET /` | Health check |
| `GET /status` | Current machine state and active user |
| `GET /brews` | Recent brew records |
| `GET /stats/overall` | Aggregate totals |
| `GET /stats/daily` | Per-day brew counts (last 30 days) |
| `GET /stats/leaderboard` | Users ranked by brew count |
| `GET /users` | All registered users |
| `/ui` | React dashboard (SPA) |

**Authentication:** set `CREMA_API_TOKEN` in the environment. All API routes then require `Authorization: Bearer <token>`. If the variable is unset, auth is disabled.

## Dashboard

The React dashboard at `/ui` auto-refreshes every 5 seconds and shows:

- Live brewing strip when the machine is active
- Stats cards (total brews, total time, users)
- Leaderboard
- Daily brew chart (last 30 days)
- Recent brews with relative timestamps

## Deployment

### First-time setup

```bash
./deploy/install.sh
```

Creates a Python venv, builds the dashboard, installs `crema` into the venv, and installs + starts the `crema-kiosk` and `crema-api` systemd services.

### Updates

```bash
./deploy/update.sh
```

Pulls latest code, rebuilds the dashboard, reinstalls the package, and restarts both services.

### Services

| Service | Command | Description |
|---|---|---|
| `crema-kiosk` | `crema-kiosk` | Sensor + scanner + display state machine |
| `crema-api` | `crema serve` | FastAPI server + dashboard |

Set `CREMA_API_TOKEN` in the service environment file to enable auth.

## Project layout

```
api/          FastAPI app (routers, auth, deps)
cli/          Click CLI commands
core/         events, state machine, database
dashboard/    React + Vite frontend
deploy/       systemd service files and install/update scripts
hardware/     display, scanner, sensor drivers
tests/        pytest suite
config.py     all tuneable constants
main.py       kiosk entry point
```

## Configuration

All thresholds and timeouts are in `config.py`.

| Constant | Default | Description |
|---|---|---|
| `MIN_BREW_DURATION` | 10 s | Below this, vibration logged as noise |
| `BREW_END_SILENCE` | 10 s | Silence needed to end a brew cycle |
| `MIN_VIBRATION_PULSE` | 0.5 s | Minimum HIGH pulse to reset silence timer |
| `BREW_CONFIRM_WINDOW` | 2 s | Sustained vibration before BrewStart fires |
| `ARMED_TIMEOUT` | 120 s | Time to wait for machine after scan |
| `SESSION_TIMEOUT` | 300 s | Idle time before auto-logout |
| `SUMMARY_DURATION` | 5 s | Summary screen shown after session ends |

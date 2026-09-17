# CREMA development

## Prerequisites

- Python 3.11 or newer
- Node.js 20.19.x, or Node.js 22.12 or newer
- npm

Physical scanner and sensor hardware are optional for local development.

## Initial setup

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -e . pytest
cd dashboard
npm ci
```

The deployment scripts use `venv/`, while local development in this repository commonly uses `.venv/`. Both paths are ignored by Git.

## Run locally without hardware

Start FastAPI with an isolated database and leave `CREMA_START_HARDWARE` unset:

```bash
CREMA_DB_PATH=/tmp/crema-dev.db .venv/bin/uvicorn api.main:app --reload --port 8000
```

In another terminal:

```bash
cd dashboard
npm run dev
```

Open these development routes:

- Dashboard: `http://localhost:5173/ui/`
- Kiosk UI: `http://localhost:5173/ui/kiosk`
- API documentation: `http://localhost:8000/docs`
- Readiness: `http://localhost:8000/health`

Vite proxies API and WebSocket traffic to port 8000. The production kiosk path is `/kiosk`, but `/ui/kiosk` is used by the Vite development server so it does not conflict with the `/kiosk` API proxy.

Configuration is read when Python imports `config.py`, so set environment variables before starting the process. The complete list is in the root `README.md`.

## Run with hardware

On a configured Raspberry Pi, either command starts the hardware owners and API together:

```bash
.venv/bin/python main.py
```

```bash
.venv/bin/crema serve
```

Do not run both simultaneously. Only one process can exclusively grab the QR scanner and own the sensor event stream.

## Verification

Backend:

```bash
.venv/bin/pytest -q
.venv/bin/python -m compileall -q api cli core hardware main.py config.py
```

Frontend:

```bash
cd dashboard
npm run lint
npm run build
npm audit --audit-level=high
```

Deployment scripts and patch hygiene:

```bash
bash -n deploy/install.sh deploy/update.sh deploy/uninstall.sh
git diff --check
```

## Kiosk visual checks

The target display is 800 x 480. Test the affected kiosk states at that exact viewport and confirm:

- The document is exactly one viewport with no scrolling.
- Text does not clip with realistic long user names and maximum-value counters.
- The hardware warning does not cover controls, timers, or overlays.
- Buttons remain large enough for touch input.
- Reconnecting and rating overlays remain above the active screen.

Temporary screenshots and browser traces belong under `output/`.

## Database fixtures

Never run tests against `data/espresso.db`. Tests use temporary databases through `tests/conftest.py` and API dependency overrides. For manual API work, set `CREMA_DB_PATH` to a file under `/tmp` before starting the process.

Useful maintenance commands:

```bash
.venv/bin/crema db backup
.venv/bin/crema db check
.venv/bin/crema db export /tmp/crema-brews.csv
```

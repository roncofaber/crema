# CREMA development

## Prerequisites

- Python 3.11 or newer
- Node.js 24.15.0 or newer
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

API-only startup creates or migrates the schema without closing sessions owned by a running kiosk. Stale-session recovery runs only when the hardware service acquires its exclusive ownership lock.

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

Configuration is read when Python imports `config.py`, so set environment variables before starting the process. The main list is in the root `README.md`; monitoring, JSONL logging, backup retention, and recovery are covered in `docs/operations.md`.

For a stateful browser development server without hardware, use the isolated simulator:

```bash
CREMA_DB_PATH=/tmp/crema-simulator.db python3 -m devsim --host ::1 --port 8010
```

The simulator enables development-only scenario routes and never starts the real scanner or sensor. Do not combine it with `CREMA_START_HARDWARE=1`.

## Generated API contracts

After changing API schemas, routes, parameters, or responses, regenerate both the OpenAPI document and frontend types from the repository root:

```bash
.venv/bin/python scripts/export_openapi.py
npm --prefix dashboard run generate:api
```

Use `.venv/bin/python scripts/export_openapi.py --check` to detect a stale schema without writing it. Review both generated files with the source changes rather than editing them by hand.

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
.venv/bin/pytest -q -W error
.venv/bin/python -m compileall -q api cli core hardware main.py config.py devsim ops
.venv/bin/python scripts/export_openapi.py --check
```

Frontend:

```bash
cd dashboard
npm test
npm run lint
npm run build
npm audit --audit-level=high
```

Real Chromium scenarios use the production build and two isolated simulator servers:

```bash
cd dashboard
npx playwright install chromium
npm run test:e2e
```

Playwright starts and stops both servers itself, using fresh databases under a unique `output/e2e/run-*` directory. Set `CREMA_E2E_ARTIFACTS` to change the artifact parent or `CREMA_E2E_HOST` to override the default `::1` loopback host. The suite covers dashboard and kiosk session authentication, session revocation, 375px dashboard filters, 800 x 480 kiosk states, stale reconnection, handoff protection, and browser-local audio settings. It never opens real GPIO or hardware devices.

`CREMA_E2E_REUSE=1` may reuse already-running local servers outside CI, but then their configuration and database lifecycle are the caller's responsibility. Do not reuse a production server.

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

Temporary screenshots and browser traces belong under `output/`. The audio settings dialog and mobile filter toolbar also require browser checks at their target viewports. `.github/workflows/ci.yml` runs the backend matrix, generated-contract checks, frontend tests, lint, production build, Chromium suite with simulator dependencies, and npm audit. Failed browser runs upload their screenshots and traces.

## Database fixtures

Never run tests against `data/espresso.db`. Tests use temporary databases through `tests/conftest.py` and API dependency overrides. For manual API work, set `CREMA_DB_PATH` to a file under `/tmp` before starting the process.

Useful maintenance commands:

```bash
.venv/bin/crema db backup
.venv/bin/crema db check
.venv/bin/crema db export /tmp/crema-brews.csv
```

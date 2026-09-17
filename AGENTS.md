# CREMA agent guide

## Project purpose

CREMA is a Raspberry Pi espresso kiosk. One Python service owns the QR scanner, ADXL345 sensor, session state machine, SQLite database, REST API, and WebSocket broadcaster. A React bundle provides both the desktop dashboard and the 800 x 480 touch interface.

## Sources of truth

- `core/state.py` defines session and brew behavior.
- `core/db.py` defines the live schema and database operations.
- `api/main.py` defines runtime startup and exposed routers.
- `dashboard/src/kiosk/hooks/useKioskSocket.ts` defines the frontend snapshot contract.
- `config.py` defines configuration defaults and environment overrides.
- `dev/` documents the current system.
- `docs/superpowers/` contains historical plans and specifications. Use them for background only, and verify every claim against current code.

## Runtime invariants

- Only one process may own the physical scanner and sensor. `main.py` and `crema serve` set `CREMA_START_HARDWARE=1`; plain `uvicorn api.main:app` is API-only development mode.
- Hardware threads emit events into a synchronous queue. `SessionState` owns all business transitions. Do not update session state directly from API or hardware code.
- SQLite timestamps are Unix seconds. Brew durations are derived from `ended_at - started_at`.
- A WebSocket snapshot change must be reflected in the Python producer, the TypeScript `KioskSnapshot` type, relevant UI states, API documentation, and tests.
- The production kiosk is exactly 800 x 480. Any kiosk UI change must be checked at that viewport with no page scrolling, clipped controls, or touch targets smaller than the existing controls.
- `/`, `/health`, and `/ws/kiosk` are public. Data and control REST endpoints use optional bearer authentication through `CREMA_API_TOKEN`. `/health` returns HTTP 503 when expected hardware is degraded.

## Database safety

- Use `core.db.get_connection()` so foreign keys, the busy timeout, and shared path handling remain consistent.
- Use SQLite's backup API through `crema db backup`; do not copy a live WAL database with a plain file copy.
- Preserve forward-compatible, idempotent migrations in `init_db()` and test upgrades from legacy schemas when changing tables.
- `init_db()` closes sessions left open after an unclean shutdown. Do not call it as a general request-time helper.
- Tests must point `core.db.DB_PATH` and any imported API path at a temporary database.

## Hardware behavior

- Missing hardware must not prevent API-only development or tests.
- Scanner and sensor failures should update health state and retry without terminating the kiosk loop.
- A missing sensor sample must not be interpreted as silence because that can falsely finish a brew.
- Keep hardware imports inside connection or startup paths so non-Pi environments can import the modules.

## Frontend behavior

- Production routes are `/ui` for the dashboard and `/kiosk` for the touch UI.
- Vite development routes are `/ui/` and `/ui/kiosk`; API and WebSocket requests are proxied to port 8000.
- Keep touch interactions usable without hover and preserve high contrast on the warm cream palette.
- Hardware warnings must remain visible without covering session controls or modal overlays.

## Development workflow

Install Python dependencies into a virtual environment and frontend dependencies with `npm ci` in `dashboard/`. See `dev/development.md` for the complete setup.

Run the relevant checks after changes:

```bash
.venv/bin/pytest -q
.venv/bin/python -m compileall -q api cli core hardware main.py config.py
cd dashboard && npm run lint
cd dashboard && npm run build
cd dashboard && npm audit --audit-level=high
bash -n deploy/install.sh deploy/update.sh deploy/uninstall.sh
git diff --check
```

For kiosk UI work, run the API and built frontend, then inspect every affected state at 800 x 480 in a real browser. Save temporary captures under `output/`, which is ignored by Git.

## Change discipline

- Keep changes scoped and preserve unrelated work in the tree.
- Add or update tests with behavior changes.
- Update current documentation when commands, environment variables, routes, schemas, state transitions, or deployment steps change.
- Do not edit generated `dashboard/dist/` assets directly.
- Do not treat the default database in `data/` as disposable test data.
- Avoid comments that restate code. Document operational behavior and non-obvious constraints in `dev/` instead.

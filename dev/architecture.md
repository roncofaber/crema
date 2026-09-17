# CREMA - Architecture

## Process model

A single Python service (`main.py`) owns the hardware, state machine, database, and API at runtime. Chromium is a separate systemd service that displays the frontend but owns no application state.

```
main.py
  ├── enables hardware startup
  └── uvicorn.run(app, ...)     - FastAPI (blocks)
        └── lifespan
              ├── db.init_db()
              ├── kiosk.start()
              └── kiosk.broadcast_loop()
```

There is no IPC between Python components. The hardware loop and API share the same in-process `SessionState` singleton through `core/kiosk.py`.

## Module map

```
config.py           All tuneable constants (thresholds, timeouts, paths)

core/
  db.py             SQLite schema, migrations, backup, restore, and CRUD
  events.py         Dataclasses: QRScanned, BrewStart, BrewEnd
  state.py          SessionState FSM - all business logic
  kiosk.py          Singleton glue: hardware → FSM → WebSocket broadcast

hardware/
  scanner.py        QRScanner - reads USB HID device, emits QRScanned
  sensor.py         VibrationSensor - ADXL345 over I2C, emits BrewStart/BrewEnd

api/
  main.py           FastAPI app, CORS, static files, startup lifecycle
  auth.py           Bearer token middleware (CREMA_API_TOKEN env var)
  deps.py           SQLite DB dependency for routes
  schemas.py        Pydantic response models
  routers/
    users.py        CRUD for /users/
    brews.py        GET /brews/
    stats.py        GET /stats/
    health.py       GET /health readiness and device status
    status.py       GET /status live machine state
    kiosk.py        WS /ws/kiosk, POST /kiosk/{logout,brew-options,rate}

cli/
  main.py           Click entry point (`crema` command)
  sensor.py         `crema sensor` - live ADXL345 terminal readout
  logs.py, stats.py, users.py, db.py  - management subcommands

dashboard/
  src/
    App.tsx         Routes: /kiosk → KioskApp, else dashboard
    kiosk/          Touch kiosk UI (screens + WebSocket hook)
    components/     Dashboard widgets
```

## Sync → async bridge

The hardware threads are synchronous. WebSocket broadcasting is async. They communicate via a `queue.Queue(maxsize=50)`:

```
Hardware thread                 Asyncio event loop
──────────────                  ──────────────────
SessionState._broadcast()  →    kiosk._on_broadcast()
                                  puts snapshot on _snapshot_q
                                kiosk.broadcast_loop() (task)
                                  drains queue, sends ws.send_json()
```

Snapshots are best-effort. If the queue is full during a burst, the new update is dropped. Clients resynchronize from the next 1 Hz snapshot.

## Authentication

`CREMA_API_TOKEN` environment variable:

- Unset: auth is disabled for local development or trusted LAN use.
- Set: data and control REST routes require `Authorization: Bearer <token>`.

The browser bundle must receive the same value as `VITE_API_TOKEN` at build time. Browser tokens are visible to users, so this mode is intended for trusted local networks. `/`, `/health`, and `/ws/kiosk` remain public so the browser and service monitors can connect.

## Database

SQLite defaults to `data/espresso.db` and can be moved with `CREMA_DB_PATH`. The schema is created and migrated idempotently by `init_db()` on startup.

Tables: `users`, `sessions`, `brews`, `schema_migrations`.

Connections enable foreign keys and a five-second busy timeout. Startup enables WAL mode, records the schema version, and closes sessions left open by an unclean shutdown. Maintenance uses SQLite's online backup API through `crema db backup`, `crema db check`, and `crema db restore`.

## Hardware lifecycle and readiness

`CREMA_START_HARDWARE=1` makes the FastAPI lifespan start the scanner, sensor, and kiosk loop. Plain API development leaves it unset. Both device drivers retry after connection failures and expose state through `core.kiosk.get_health()`.

`GET /health` reports database connectivity, process mode, loop status, and device connectivity. In hardware mode it returns HTTP 503 with `degraded` status until the loop and both devices are ready. The WebSocket includes the same hardware state so the kiosk can display a non-blocking warning.

## Static files

The built React bundle (`dashboard/dist/`) is mounted at `/ui` by FastAPI:

```python
app.mount("/ui", StaticFiles(directory=".../dashboard/dist", html=True))
```

The kiosk UI is served at `/kiosk` from the same bundle, with path selection handled in `App.tsx`. Vite development uses `/ui/` and `/ui/kiosk`; see `development.md`.

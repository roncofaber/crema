# CREMA — Architecture

## Process model

A single Python process (`main.py`) owns everything at runtime:

```
main.py
  ├── db.init_db()              — schema migration
  ├── kiosk.start()             — spawns hardware threads + kiosk loop
  └── uvicorn.run(app, ...)     — FastAPI (blocks)
        └── startup task: kiosk.broadcast_loop()  — asyncio loop draining snapshot queue
```

There are **no separate processes** and **no IPC**. The hardware loop and the API share the same in-process `SessionState` singleton via `core/kiosk.py`.

## Module map

```
config.py           All tuneable constants (thresholds, timeouts, paths)

core/
  db.py             SQLite helpers — schema, CRUD
  events.py         Dataclasses: QRScanned, BrewStart, BrewEnd
  state.py          SessionState FSM — all business logic
  kiosk.py          Singleton glue: hardware → FSM → WebSocket broadcast

hardware/
  scanner.py        QRScanner — reads USB HID device, emits QRScanned
  sensor.py         VibrationSensor — ADXL345 over SPI, emits BrewStart/BrewEnd

api/
  main.py           FastAPI app, CORS, static files, startup lifecycle
  auth.py           Bearer token middleware (CREMA_API_TOKEN env var)
  deps.py           SQLite DB dependency for routes
  schemas.py        Pydantic response models
  routers/
    users.py        CRUD for /users/
    brews.py        GET /brews/
    stats.py        GET /stats/
    status.py       GET /status
    kiosk.py        WS /ws/kiosk, POST /kiosk/{logout,brew-options,rate}

cli/
  main.py           Click entry point (`crema` command)
  sensor.py         `crema sensor` — live ADXL345 terminal readout
  logs.py, stats.py, users.py, db.py  — management subcommands

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

Snapshots are best-effort: if the queue is full (burst), the oldest update is dropped. Clients re-sync via the next snapshot.

## Authentication

`CREMA_API_TOKEN` env var:
- Unset → auth disabled (local dev / LAN use)
- Set → all REST routes require `Authorization: Bearer <token>`

The WebSocket (`/ws/kiosk`) has **no auth** — it is local-display-only and streams no secrets.

## Database

SQLite at `data/espresso.db`. Schema is created / migrated idempotently by `init_db()` on every startup.

Tables: `users`, `sessions`, `brews`

`init_db()` also closes any sessions left open by an unclean shutdown (`ended_at IS NULL`).

## Static files

The built React bundle (`dashboard/dist/`) is mounted at `/ui` by FastAPI:

```python
app.mount("/ui", StaticFiles(directory=".../dashboard/dist", html=True))
```

The kiosk UI is served at `/kiosk` (same bundle, different path handled client-side in `App.tsx`).

# Espresso Tracker — Design Spec
_2026-05-10_

## Overview

A Raspberry Pi 4 kiosk that tracks who makes coffee and how many they make. Users scan a QR code (their email) before using the machine; a vibration sensor detects each brew cycle and logs it to SQLite. An LCD gives real-time feedback. A future web dashboard will surface stats.

---

## Hardware

| Component | Details |
|-----------|---------|
| Display | Waveshare ST7789, 240×320, SPI, landscape (rotated 90°) |
| QR scanner | USB HID — acts as a keyboard, outputs text + Enter |
| Vibration sensor | SW-420 digital output on a GPIO pin |

---

## Architecture

```
hardware/scanner.py  ─┐
hardware/sensor.py   ─┼──► queue.Queue(events) ──► core/state.py ──► core/db.py
                      │                                  │
                      └──────────────────────────────────┴──► hardware/display.py
```

Three layers:

- **Hardware layer** (`hardware/`) — scanner and sensor daemon threads produce typed events, push onto a shared `queue.Queue`. Display is write-only, called by the state machine.
- **Core layer** (`core/`) — state machine consumes events, updates state, writes to DB, drives display. No hardware imports.
- **Data layer** (`core/db.py`) — SQLite. Designed to also serve a future web dashboard.

`main.py` wires everything: creates the queue, instantiates components, starts threads, runs the drain loop.

---

## Concurrency model

Thread-per-device + shared event queue (Approach A).

- `QRScanner` — daemon thread, blocking `evdev` read
- `VibrationSensor` — daemon thread, 10ms polling loop
- Main thread — drains queue every second, calls `state.on_tick()` for timeouts

---

## Data layer

```sql
users    (id, token TEXT UNIQUE, name TEXT)
sessions (id, user_id INTEGER, started_at REAL, ended_at REAL)
brews    (id, session_id INTEGER, started_at REAL, ended_at REAL, duration REAL, kind TEXT)
```

- `token` — raw email string from QR scan
- `name` — local part of email by default; can be backfilled to real names later
- `user_id NULL` on sessions → anonymous session
- `kind` on brews: `'brew'` (≥ threshold) or `'noise'` (< threshold) — all vibration cycles are logged for threshold tuning
- One session can have multiple brews (one scan covers a run of coffees)

### Key functions

| Function | Behaviour |
|----------|-----------|
| `get_or_create_user(token)` | Validates email, extracts local part as name, inserts on first scan |
| `start_session(user_id)` | Opens session; `None` for anonymous |
| `end_session(session_id)` | Stamps `ended_at` |
| `log_brew(session_id, started_at, ended_at, kind)` | One row per vibration cycle |
| `get_user_stats(user_id)` | Total brews + total brew time for summary screen |

---

## State machine

### States

| State | Meaning |
|-------|---------|
| `IDLE` | No active user |
| `ARMED` | User scanned, waiting for machine |
| `BREWING` | Machine running, attributed to current user |
| `ANON_BREW` | Machine running, no user scanned |

### Transitions

| Current state | Event | Next state | Action |
|---------------|-------|------------|--------|
| IDLE | QRScanned (valid email) | ARMED | open session, show armed screen |
| IDLE | BrewStart | ANON_BREW | record brew start |
| ARMED | BrewStart | BREWING | record brew start |
| ARMED | QRScanned (same user) | IDLE | close session (cancelled) |
| ARMED | QRScanned (different user) | ARMED | close old session, open new one |
| ARMED | armed timeout (120s, no brew yet) | IDLE | close session, show idle (no summary — nothing happened) |
| ARMED | inactivity timeout (5min since last brew, ≥1 brew logged) | IDLE | close session, show summary |
| BREWING | BrewEnd | ARMED | log brew (kind based on duration), update display |
| BREWING | QRScanned | — | queue new user; apply after BrewEnd |
| ANON_BREW | BrewEnd | IDLE | log brew (kind based on duration), show idle |

Non-email QR tokens (badge numbers, garbage) are silently dropped before reaching the state machine.

---

## Hardware drivers

### VibrationSensor

Polls GPIO pin every 10ms. Tracks two timers:

- `vibration_start` — stamped on first HIGH; `BrewStart` event posted after signal stays HIGH for a 2s confirmation window (avoids false triggers)
- `last_vibration` — updated on every HIGH pulse that lasts ≥ `MIN_VIBRATION_PULSE` (0.5s); when silence exceeds `BREW_END_SILENCE` (10s), posts `BrewEnd(duration)`

Brew duration stored = `vibration_start` → last HIGH (full window, not confirmed-start to end).

### QRScanner

Reads from USB HID device via `evdev` (exclusive access — no keystrokes leak to OS). Assembles characters into a buffer, flushes on `KEY_ENTER`. Validates result is an email before posting `QRScanned(token)`.

---

## Display screens

All screens: white-on-black, PIL + ST7789, landscape (rotate 90°).

| Screen | Content |
|--------|---------|
| `show_idle` | Espresso logo centred + "Scan to start" small font |
| `show_armed(name)` | "Hi, [name]!" large + "Start the machine" small |
| `show_brewing(name, count, elapsed)` | Name top-left small · brew count centre large · elapsed bottom small |
| `show_anon_brewing(elapsed)` | Same as brewing, name = "Anonymous" |
| `show_summary(name, count, total_time)` | "See ya, [name]!" large · "X coffees · Xm Xs" small · shown 5s then idle |

Display is driven exclusively by the state machine. `hardware/display.py` exposes only `_new_canvas` and `_send` as primitives.

---

## Config

All tuneable constants live in `config.py`:

```python
VIBRATION_PIN       = 17    # SW-420 GPIO pin
MIN_BREW_DURATION   = 20    # seconds — threshold for brew vs noise kind
BREW_END_SILENCE    = 10    # seconds of silence before BrewEnd fires
MIN_VIBRATION_PULSE = 0.5   # seconds — minimum pulse to reset silence timer
ARMED_TIMEOUT       = 120   # seconds waiting for machine after scan
SESSION_TIMEOUT     = 300   # seconds inactivity before auto-logout
SUMMARY_DURATION    = 5     # seconds to show summary screen
```

---

## Main loop

```python
queue = Queue()
db.init_db()
display = Display()
state   = SessionState(queue, display)
scanner = QRScanner(queue)
sensor  = VibrationSensor(queue)

scanner.start()
sensor.start()

while True:
    state.on_tick()
    while not queue.empty():
        state.handle(queue.get_nowait())
    sleep(1)
```

`on_tick` (every second): handles armed/inactivity timeouts, refreshes elapsed time on brewing screen.  
`handle(event)`: single dispatch entry point — routes to the right transition based on current state.

---

## Out of scope (this phase)

- Web dashboard
- Real name backfill UI
- Admin interface
- Notifications / alerts

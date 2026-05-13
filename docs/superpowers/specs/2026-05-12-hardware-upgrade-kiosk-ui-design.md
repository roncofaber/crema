# CREMA Hardware Upgrade & Kiosk UI — Design Spec

**Date:** 2026-05-12
**Scope:** Replace SW-420 vibration sensor with ADXL345 accelerometer, replace ST7789 SPI LCD with FREENOVE 5" DSI touchscreen, add interactive React kiosk UI with WebSocket-driven state and per-brew annotations.

---

## 1. Overview

Three parallel changes land together:

1. **Sensor swap** — ADXL345 3-axis accelerometer over SPI replaces the SW-420 binary vibration switch. Same event interface (`BrewStart`/`BrewEnd` on the Queue), new threshold algorithm based on acceleration magnitude.
2. **Display swap** — ST7789 SPI LCD and its Python driver are deleted. A Chromium browser running fullscreen on the FREENOVE 5" MIPI DSI display (800×480) replaces it. Chromium points at a new `/kiosk` route in the existing FastAPI + React app.
3. **Kiosk UI** — The `/kiosk` React route is a dedicated fullscreen touchscreen interface that mirrors the kiosk state machine in real time via WebSocket and lets users interact: set shot type, toggle decaf, log out, and rate completed brews.

The Python kiosk process (`crema-kiosk`) continues to own all hardware: sensor, scanner, state machine. It gains a WebSocket broadcaster and new REST endpoints for touch actions. The rest of `main.py` and `core/state.py` are unchanged except for removing all `display.*` calls.

---

## 2. ADXL345 Sensor Driver

**File:** `hardware/sensor.py` (replaces current SW-420 implementation entirely)

**Connection:** SPI (MOSI/MISO/SCLK/CE1). CE0 is left free for future use. Uses `adafruit-circuitpython-adxl34x` — consistent with the Adafruit ecosystem already in the project.

**Configuration (added to `config.py`):**
```python
ADXL_RANGE          = 4      # ±4g — good sensitivity for machine vibration
ADXL_SAMPLE_RATE    = 50     # Hz — more than sufficient for second-scale brew detection
ADXL_BREW_THRESHOLD = 1.15   # g magnitude above baseline — tunable via `crema sensor`
```

**Algorithm:**
1. Poll ADXL345 at 50 Hz in a background thread.
2. Compute scalar magnitude `m = √(x² + y² + z²)` per sample. Magnitude is orientation-independent — the sensor can be mounted in any direction.
3. Apply the existing temporal gating logic from `config.py` unchanged:
   - `BREW_CONFIRM_WINDOW`: sustained signal above threshold before `BrewStart` fires.
   - `BREW_END_SILENCE`: consecutive quiet samples before `BrewEnd` fires.
   - `MIN_VIBRATION_PULSE`: minimum above-threshold burst to reset the silence timer.
   - `MIN_BREW_DURATION`: distinguishes `kind='brew'` from `kind='noise'`.
4. Push `BrewStart` and `BrewEnd` events onto the Queue — identical to the current driver.

**Public interface:** `VibrationSensor(queue)` with `.start()` / `.stop()`. `main.py` requires no changes.

**Dependency added to `pyproject.toml`:** `adafruit-circuitpython-adxl34x`

---

## 3. ADXL345 Debug Utility (`crema sensor`)

**File:** `cli/sensor.py` (replaces current GPIO readout)

Live terminal readout for threshold calibration. Updated at ~10 Hz using `\r` line overwrite — no new dependencies (no `curses` needed).

**Display:**
```
ADXL345 — live readout  (Ctrl+C to quit)
─────────────────────────────────────────
  X:  +0.021 g   Y:  -0.013 g   Z:  +1.002 g
  magnitude:  1.003 g   peak: 1.847 g

  threshold: 1.15 g   [QUIET]
  ████░░░░░░░░░░░░░░░░░░░░░░░░  (bar = magnitude / 2g)
```

Fields:
- **X/Y/Z** — raw axis readings in g.
- **Magnitude** — current `√(x²+y²+z²)`.
- **Peak** — highest magnitude seen since launch (useful for finding threshold with machine running).
- **Status** — `[ACTIVE]` when above `ADXL_BREW_THRESHOLD`, `[QUIET]` otherwise.
- **Bar** — ASCII fill proportional to magnitude up to 2g; threshold marked with a `|` character.

---

## 4. Display Removal

- `hardware/display.py` — deleted.
- All `self._display.*` calls removed from `core/state.py` (`SessionState`).
- `Display` import and instantiation removed from `main.py`.
- `config.py` display constants (`DISPLAY_WIDTH`, `DISPLAY_HEIGHT`, `FONT_PATH`, `FONT_SIZE_*`) — removed.
- Adafruit RGB display dependency removed from `pyproject.toml`.

`SessionState` is otherwise unchanged: same states, same transitions, same event handling.

---

## 5. Chromium Kiosk Mode

**How the DSI display works:** The FREENOVE 5" MIPI DSI display connects to the Pi's dedicated display ribbon connector. It appears as the primary framebuffer at the OS level — no Python driver needed. The capacitive touch controller appears as an evdev input device (handled natively by Chromium).

**Systemd service `crema-kiosk` is updated** (or a new `crema-browser` service is added) to launch Chromium after the desktop environment is available:

```bash
chromium-browser \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --touch-events=enabled \
  --no-first-run \
  http://localhost:8000/kiosk
```

Chromium runs fullscreen on the DSI display, pointed at the local FastAPI server. No window manager interaction — kiosk mode suppresses all chrome.

---

## 6. WebSocket — Real-Time State

**Endpoint:** `GET /ws/kiosk` (added to FastAPI, likely in a new `api/routers/kiosk.py`)

**State snapshot** — pushed to all connected clients on every state transition and on every 1-second tick while in `armed` or `brewing`/`anon_brew` states:

```json
{
  "state": "armed",
  "user": "Fabrice",
  "brew_count": 2,
  "time_remaining": 74.3,
  "timeout": 120.0,
  "elapsed": null,
  "shot_type": "double",
  "decaf": false,
  "last_brew_id": 42,
  "avg_rating": 3.5
}
```

Field notes:
- `time_remaining` / `timeout`: populated in `armed` state (countdown or session idle timer). `null` in other states.
- `elapsed`: seconds since brew started. Populated in `brewing` / `anon_brew`. `null` otherwise.
- `last_brew_id`: ID of the most recently completed brew with `kind='brew'` — used by the rating overlay to POST the correct brew. Updated only on real brews, not noise; this ensures the rating overlay never fires for noise events.
- `avg_rating`: session average rating so far (for summary screen). `null` if no rated brews yet.
- `shot_type`: current sticky selection (`"single"` or `"double"`). Default: `"double"`.
- `decaf`: current sticky selection. Default: `false`.

**Broadcaster:** `SessionState` holds a `set[WebSocket]`. On each push call it iterates the set, sends JSON, and silently removes any connection that raises. The push is non-blocking (fire-and-forget). The FastAPI WS endpoint registers/deregisters connections on connect/disconnect.

---

## 7. New REST Endpoints

Added to `api/routers/kiosk.py`. All require the same optional bearer auth as other routes.

| Method | Path | Body | Effect |
|---|---|---|---|
| `POST` | `/kiosk/logout` | — | Calls `state.force_logout()` → ends session, transitions to IDLE |
| `POST` | `/kiosk/brew-options` | `{"shot_type": "single"\|"double", "decaf": bool}` | Updates sticky options on `SessionState`; broadcast immediately |
| `POST` | `/kiosk/rate` | `{"brew_id": int, "rating": int}` | Writes rating (1–5) to `brews.rating` for given brew |

`force_logout()` is a new method on `SessionState` that ends the session cleanly and transitions to IDLE, equivalent to the armed timeout path.

---

## 8. Database Migration

Three nullable columns added to the `brews` table:

```sql
ALTER TABLE brews ADD COLUMN shot_type TEXT;    -- 'single' | 'double'
ALTER TABLE brews ADD COLUMN decaf INTEGER;     -- 0 | 1
ALTER TABLE brews ADD COLUMN rating INTEGER;    -- 1–5, NULL if not rated
```

`db.log_brew()` signature extended: `log_brew(session_id, started_at, ended_at, kind, shot_type, decaf)` — values come from `SessionState`'s current sticky options at brew-end time.

`db.rate_brew(brew_id, rating)` — new helper that sets `brews.rating`.

Migration runs in `db.init_db()` using `ALTER TABLE … ADD COLUMN IF NOT EXISTS` (SQLite 3.35+, available on current Pi OS).

---

## 9. React Kiosk Route

**Location:** `dashboard/src/kiosk/`

```
kiosk/
  KioskApp.tsx          # top-level: owns WS hook, renders active screen
  hooks/
    useKioskSocket.ts   # WebSocket connection, auto-reconnect, exposes snapshot
  screens/
    Idle.tsx
    Armed.tsx           # includes shot type + decaf toggles, logout button
    Brewing.tsx         # includes shot type + decaf toggles (changeable until brew ends)
    AnonBrewing.tsx
    Summary.tsx         # shows brew count, total time, avg rating
  overlays/
    RatingPrompt.tsx    # 1–5 stars, auto-dismiss 15 s, posts to /kiosk/rate
    Reconnecting.tsx    # subtle overlay shown when WS is disconnected
```

**Routing:** `/kiosk` is added as a route in `App.tsx` (or via React Router if the project adds it). The kiosk route renders `KioskApp` which is a completely separate full-screen layout — no dashboard header/footer.

**Styling:** All components use existing Tailwind CSS variables (`bg-bg`, `text-ink`, `text-crema-400`, `font-display`, `font-plex`, etc.) defined in `index.css`. No new CSS infrastructure.

**Screen → state mapping:**

| `snapshot.state` | Screen rendered |
|---|---|
| `idle` | `Idle` |
| `armed` | `Armed` |
| `brewing` | `Brewing` |
| `anon_brew` | `AnonBrewing` |
| `summary` | `Summary` |
| WS disconnected | Last screen + `Reconnecting` overlay |

**Rating overlay:** Appears when `snapshot.state` transitions from `brewing` to `armed` and `snapshot.last_brew_id` changes (indicating a real brew, not noise). Dismissed by: tapping a star (POSTs rating), tapping skip, or 15-second auto-dismiss. During the overlay, the underlying armed screen is visible but touch-blocked.

**Brew option controls:**
- Present on both `Armed` and `Brewing` screens.
- `POST /kiosk/brew-options` on every toggle tap — the server updates sticky state and broadcasts immediately.
- Options default to `double` / `decaf: false` at session start. Sticky for the rest of the session.
- Locked (read-only display) on the `RatingPrompt` and `Summary` screens.

**ANON_BREW transition:** When a QR scan arrives mid-anonymous-brew, the state machine queues the token (existing behaviour). The kiosk UI stays on `AnonBrewing` until the state snapshot changes — no special handling needed; the WebSocket push drives the transition automatically.

**`useKioskSocket` behaviour:**
- Connects to `ws://localhost:8000/ws/kiosk` on mount.
- On disconnect: waits 2 s, retries with exponential backoff (max 15 s interval).
- While disconnected: sets `connected: false`, last known snapshot is preserved (stale but visible).
- `Reconnecting` overlay is shown whenever `connected === false`.

---

## 10. Summary Screen — Average Rating

The `Summary` screen (shown at session end) displays:
- User name ("Grazie, *Fabrice*")
- Brew count for the session
- Total brew time for the session
- Average star rating for rated brews this session (e.g. "★ 3.8 avg" — omitted if no brews were rated)

`avg_rating` is computed by a `db.get_session_avg_rating(session_id)` query when `SessionState` transitions to `summary`, and included in the snapshot. Returns `null` if no brews in the session were rated.

---

## Out of Scope

- Text notes / comments (requires keyboard input)
- Guest registration via kiosk
- Admin controls on-device
- Ristretto / lungo volume tracking
- Dashboard changes (the existing `/ui` dashboard is unchanged)

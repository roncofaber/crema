# CREMA — State Machine

Implemented in `core/state.py` as `SessionState`.

## States

| State | Meaning |
|---|---|
| `IDLE` | No user logged in, machine available |
| `ARMED` | User authenticated, waiting for brew (or between brews) |
| `BREWING` | Authenticated brew cycle in progress |
| `ANON_BREW` | Brew detected without a logged-in user |
| `SUMMARY` | Session ended, showing summary before returning to IDLE |

## Transitions

```
IDLE ──QRScanned──────────────────► ARMED
IDLE ──BrewStart──────────────────► ANON_BREW

ARMED ──BrewStart─────────────────► BREWING
ARMED ──timeout (ARMED_TIMEOUT)───► IDLE          (if no brew yet)
ARMED ──timeout (SESSION_TIMEOUT)─► SUMMARY       (after last brew)
ARMED ──QRScanned (other user)────► ARMED         (handoff)
ARMED ──force_logout()────────────► IDLE

BREWING ──BrewEnd─────────────────► ARMED
BREWING ──BrewEnd + pending QR────► ARMED         (handoff after brew)
BREWING ──QRScanned───────────────── (queued, applied on BrewEnd)

ANON_BREW ──BrewEnd───────────────► IDLE

SUMMARY ──SUMMARY_DURATION elapsed► IDLE
```

## Events

All events originate from hardware threads and are put on `hw_queue`:

| Event | Source | Fields |
|---|---|---|
| `QRScanned` | `hardware/scanner.py` | `token: str` |
| `BrewStart` | `hardware/sensor.py` | _(none)_ |
| `BrewEnd` | `hardware/sensor.py` | `started_at: float`, `ended_at: float`, `duration: float` |

## Brew classification

When a `BrewEnd` arrives:

```python
kind = "brew" if event.duration >= MIN_BREW_DURATION else "noise"
```

Only `kind='brew'` increments `brew_count`, sets `last_brew_at`, and stores `shot_type`/`decaf` in the DB. `kind='noise'` is logged for completeness but doesn't affect session state.

## Timeout logic

In `ARMED` state, `on_tick()` runs the timer at 1 Hz:

- **No brew yet**: countdown from `ARMED_TIMEOUT` (120 s). Expire → close session → `IDLE`.
- **After a brew**: countdown from `SESSION_TIMEOUT` (300 s) since `last_brew_at`. Expire → compute avg rating → `SUMMARY` → wait `SUMMARY_DURATION` (5 s) → close session → `IDLE`.

## Brew options

`_shot_type` ("single"|"double") and `_decaf` (bool) are sticky per session:
- Default on new session: `shot_type="double"`, `decaf=False`
- Reset to defaults on every user handoff
- Changeable via `set_brew_options()` up until the session ends
- Written to the `brews` table only for `kind='brew'`

## Snapshot payload

`_snapshot()` returns the dict pushed to WebSocket clients:

```json
{
  "state": "armed",
  "user": "alice",
  "brew_count": 2,
  "time_remaining": 87.3,
  "timeout": 120.0,
  "elapsed": null,
  "shot_type": "double",
  "decaf": false,
  "last_brew_id": 42,
  "avg_rating": null
}
```

`time_remaining` and `timeout` are `null` in all states except `ARMED`.
`elapsed` is non-null only in `BREWING` / `ANON_BREW`.
`last_brew_id` is `null` if no brew in this session yet (or if the brew was noise).
`avg_rating` is non-null only in `SUMMARY`.

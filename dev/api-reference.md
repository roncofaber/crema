# CREMA — API Reference

Base URL: `http://<pi>:8000`

Auth: `Authorization: Bearer <CREMA_API_TOKEN>` on all REST endpoints when the env var is set.

---

## Status

### `GET /status`

Current machine state.

```json
{
  "state": "ready",
  "user": "alice",
  "session_started_at": 1715000000.0
}
```

`state` values: `"idle"` | `"ready"` (= ARMED) | `"brewing"` | `"anon_brew"` | `"summary"`

---

## Users

### `GET /users/`

All users with aggregate stats.

```json
[{"name": "alice", "token": "alice@example.com", "total_brews": 12}]
```

### `GET /users/{name}`

Single user. `404` if not found.

### `PATCH /users/{name}`

Rename user. Body: `{"name": "Alice"}`. `409` if name already taken.

### `DELETE /users/{name}`

Delete user and all their brews. `204` on success, `404` if not found.

### `GET /users/{name}/brews`

Brews for one user. Accepts `?kind=brew` filter.

---

## Brews

### `GET /brews/`

Recent brews. Query params:
- `limit` (default 20)
- `kind` (default `"brew"`, pass empty string to get all)
- `user` — filter by user name

```json
[{"id": 1, "user": "alice", "kind": "brew", "duration": 28.4,
  "shot_type": "double", "decaf": 0, "rating": 4,
  "started_at": 1715000000.0, "ended_at": 1715000028.4}]
```

---

## Stats

### `GET /stats/`

Overall totals.

```json
{"total_brews": 42, "total_users": 5, "top_brewer": "alice"}
```

### `GET /stats/daily?days=30`

Per-day brew counts (last N days, default 30).

```json
[{"date": "2024-05-07", "brews": 3}]
```

---

## Kiosk — REST

These endpoints control the live kiosk and require auth when `CREMA_API_TOKEN` is set.

### `POST /kiosk/logout`

Force-end the current session. Only works in `ARMED` state; no-ops otherwise.

```json
{"ok": true}
```

`503` if kiosk hardware is not running.

### `POST /kiosk/brew-options`

Set sticky shot type and decaf flag for the current session.

Body:
```json
{"shot_type": "single", "decaf": true}
```

`shot_type` must be `"single"` or `"double"`.

### `POST /kiosk/rate`

Submit a 1–5 star rating for a brew.

Body:
```json
{"brew_id": 42, "rating": 4}
```

`422` if `rating` is outside 1–5.

---

## Kiosk — WebSocket

### `WS /ws/kiosk`

Real-time state stream. **No auth required.**

Connect and receive JSON snapshots on every state change or 1 Hz tick. The server sends the current snapshot immediately on connect.

Snapshot shape:
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

The client should keep the connection open (send nothing; server ignores incoming messages). Implement exponential backoff reconnect — see `dashboard/src/kiosk/hooks/useKioskSocket.ts` for a reference implementation (2 s initial, ×1.5 multiplier, 15 s cap).

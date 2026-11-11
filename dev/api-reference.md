# CREMA - API Reference

Base URL: `http://<pi>:8000`

Auth: data, control, and metrics REST endpoints accept `Authorization: Bearer <CREMA_API_TOKEN>` when a token is configured. With `CREMA_AUTH_MODE=session`, they also accept the signed `crema_session` cookie after password login. `/`, `/health`, and `/auth/session` remain public. `/ws/kiosk` has no bearer token but requires a same-host or explicitly allowed Origin. Non-loopback serving requires a bearer token or a complete session-auth configuration unless `CREMA_ALLOW_INSECURE=1` is explicitly set. The generated machine-readable contract is `api/openapi.json`; regenerate it and the frontend types after API changes.

---

## Authentication

### `GET /auth/session`

Returns `{"mode":"token","authenticated":false}` in token mode. In session mode it reports whether the current signed cookie is valid and unexpired.

### `POST /auth/login`

Available only with `CREMA_AUTH_MODE=session`. Body: `{"password":"..."}`. A valid administrator password returns an HttpOnly, same-site Strict `crema_session` cookie and its expiration timestamp. Invalid passwords return 401; repeated failures can return 429 with `Retry-After`. Login and logout require a same-host or explicitly allowed Origin when an Origin header is present.

### `POST /auth/logout`

Clears the browser session and returns `{"ok":true}`. In token mode it is a no-op. Session-authenticated non-read API requests use the same Origin check. A configured bearer token remains available for automation in either mode.

---

## Metrics

### `GET /api/metrics`

Returns authenticated Prometheus text format `0.0.4`. Labels are limited to HTTP methods, status codes, registered route templates, finite kiosk states/events, brew kinds, and bounded disconnect reasons. No usernames, user tokens, session tokens, request query strings, or raw unmatched paths are exported. Process counters reset on restart; database gauges represent persisted records. See `docs/operations.md` for scraping and passive JSONL monitoring.

---

## Health

### `GET /health`

Reports database connectivity, process mode, kiosk loop state, and scanner and sensor connectivity. This endpoint does not require authentication so service monitors can use it.

Returns HTTP 200 with `status: "ok"` when ready. In hardware mode, a stopped kiosk loop, disconnected device, dead device thread, or sensor without a successful reading in the last five seconds returns HTTP 503 with `status: "degraded"`. `thread_alive` reports owner liveness and sensor `stale_age` is measured in seconds.

```json
{
  "status": "ok",
  "mode": "hardware",
  "database": {"connected": true},
  "kiosk": {
    "running": true,
    "scanner": {"connected": true, "error": null, "last_scan_at": null, "thread_alive": true},
    "sensor": {"connected": true, "error": null, "last_read_at": 1715000000.0, "thread_alive": true, "stale_age": 0.02}
  }
}
```

---

## Status

### `GET /status`

Current machine state.

```json
{
  "state": "ready",
  "user": "alice",
  "session_started_at": 1715000000.0,
  "brew_started_at": null
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

Rename user. Body: `{"name": "Alice"}`. Names are trimmed, nonempty, and limited to 80 characters. Tokens are trimmed, lowercased, and must be valid email addresses of at most 254 characters. `409` if the normalized name or token is already taken.

### `DELETE /users/{name}`

Delete user and all their brews. `204` on success, `404` if not found, and `409` if the user has an open session. Close or hand off the kiosk session before deletion.

### `GET /users/{name}/brews`

Brews for one user. Accepts `?kind=brew` filter.

---

## Brews

### `GET /brews/`

Recent brews. Query params:

- `limit` (default 50, range 1 to 500)
- `kind` (optional, typically `"brew"` or `"noise"`)
- `user` - exact, case-sensitive displayed user name; `anonymous` includes records without a user
- `shot_type` - optional `single` or `double`
- `decaf` - optional boolean
- `from_ts` and `to_ts` - optional inclusive Unix timestamps

Omit `kind` to return both brew and noise records.

```json
[{"id": 1, "user": "alice", "kind": "brew", "duration": 28.4,
  "shot_type": "double", "decaf": false, "rating": 4,
  "started_at": 1715000000.0, "ended_at": 1715000028.4}]
```

---

## Stats

### `GET /stats/`

Overall totals.

```json
{"total_brews": 42, "total_users": 5, "total_brew_time": 1176.0, "today_brews": 6,
 "top_brewer": "alice", "average_duration": 28.0, "average_rating": 4.3, "decaf_brews": 5}
```

### `GET /stats/daily?days=30`

Per-day brew counts (last N days, default 30).

```json
[{"date": "2024-05-07", "brews": 3}]
```

---

## Kiosk - REST

These endpoints control the live kiosk and require auth when `CREMA_API_TOKEN` is set.

### `POST /kiosk/logout`

Force-end the current session. Only works in `ARMED` state.

Body:
```json
{"session_started_at": 1715000000.0}
```

`session_started_at` must match the current session snapshot, preventing a delayed logout from ending the next user's session after handoff. A stale session or a state that does not accept logout returns `409`.

```json
{"ok": true}
```

`503` if kiosk hardware is not running.

### `POST /kiosk/brew-options`

Set sticky shot type and decaf flag for the current session.

Body:
```json
{"shot_type": "single", "decaf": true, "session_started_at": 1715000000.0}
```

`shot_type` must be `"single"` or `"double"`. `session_started_at` must match the current session snapshot, which prevents a delayed request from a previous user changing options after handoff. A stale session or a state that does not accept options returns `409`; refresh from the next snapshot before retrying.

### `POST /kiosk/rate`

Submit a 1–5 star rating for a brew.

Body:
```json
{"brew_id": 42, "rating": 4}
```

`404` if the brew does not exist or is a noise event. `422` if `rating` is outside 1 to 5.

---

## Kiosk - WebSocket

### `WS /ws/kiosk`

Real-time state stream. No bearer token is required, but the request Origin must match the service host or an entry in `CREMA_CORS_ORIGINS`.

Connect and receive JSON snapshots on every state change or 1 Hz tick. The server sends the current snapshot immediately on connect. If no kiosk state exists, the server closes the connection with a service-restarting code so the client can retry without showing a synthetic idle state.

Snapshot shape:
```json
{
  "state": "armed",
  "user": "alice",
  "brew_count": 2,
  "session_brew_time": 54.2,
  "time_remaining": 87.3,
  "timeout": 120.0,
  "elapsed": null,
  "shot_type": "double",
  "decaf": false,
  "last_brew_id": 42,
  "avg_rating": null,
  "session_started_at": 1715000000.0,
  "brew_started_at": null,
  "hardware": {
    "running": true,
    "scanner": {"connected": true, "error": null, "last_scan_at": 1715000000.0, "thread_alive": true},
    "sensor": {"connected": true, "error": null, "last_read_at": 1715000028.4, "thread_alive": true, "stale_age": 0.02}
  }
}
```

The client should keep the connection open (send nothing; server ignores incoming messages). Implement exponential backoff reconnect; see `dashboard/src/kiosk/hooks/useKioskSocket.ts` for a reference implementation (2 s initial, ×1.5 multiplier, 15 s cap).

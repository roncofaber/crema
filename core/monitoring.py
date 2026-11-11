from collections import Counter
import threading
import time


_STARTED_AT = time.time()
_LOCK = threading.Lock()
_HTTP_REQUESTS: Counter[tuple[str, str, str]] = Counter()
_KIOSK_EVENTS: Counter[str] = Counter()
_KIOSK_TRANSITIONS: Counter[tuple[str, str]] = Counter()
_BREWS: Counter[str] = Counter()
_DROPPED_SNAPSHOTS = Counter()
_WEBSOCKET_DROPS = Counter()
_RECOVERED_SESSIONS = Counter()
_METHODS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}
_EVENTS = {"QRScanned", "BrewStart", "BrewEnd"}
_STATES = {"idle", "armed", "brewing", "anon_brew", "summary"}


def record_http_request(method: str, route: str | None, status: int) -> None:
    method = method.upper() if method.upper() in _METHODS else "OTHER"
    route = route or "unmatched"
    with _LOCK:
        _HTTP_REQUESTS[(method, route, str(status))] += 1


def record_kiosk_event(name: str) -> None:
    with _LOCK:
        _KIOSK_EVENTS[name if name in _EVENTS else "unknown"] += 1


def record_transition(source: str, destination: str) -> None:
    source = source.lower()
    destination = destination.lower()
    if source not in _STATES or destination not in _STATES:
        return
    with _LOCK:
        _KIOSK_TRANSITIONS[(source, destination)] += 1


def record_brew(kind: str) -> None:
    if kind not in {"brew", "noise"}:
        return
    with _LOCK:
        _BREWS[kind] += 1


def record_dropped_snapshot() -> None:
    with _LOCK:
        _DROPPED_SNAPSHOTS["queue_full"] += 1


def record_websocket_drop(reason: str) -> None:
    reason = reason if reason in {"send_failed", "simulator"} else "other"
    with _LOCK:
        _WEBSOCKET_DROPS[reason] += 1


def record_recovered_sessions(count: int) -> None:
    with _LOCK:
        _RECOVERED_SESSIONS["startup"] += count


def _labels(values: dict[str, str]) -> str:
    def escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    return ",".join(f'{key}="{escape(str(value))}"' for key, value in values.items())


def _sample(name: str, value: int | float, labels: dict[str, str] | None = None) -> str:
    suffix = f"{{{_labels(labels)}}}" if labels else ""
    number = str(value) if isinstance(value, int) else format(value, ".12g")
    return f"{name}{suffix} {number}"


def render_prometheus(con=None) -> str:
    import core.kiosk as kiosk

    health = kiosk.get_health()
    snapshot = kiosk.get_snapshot()
    lines = [
        "# HELP crema_up Whether the API process is serving metrics.",
        "# TYPE crema_up gauge",
        _sample("crema_up", 1),
        "# HELP crema_process_uptime_seconds Seconds since metrics collection started.",
        "# TYPE crema_process_uptime_seconds gauge",
        _sample("crema_process_uptime_seconds", max(0, time.time() - _STARTED_AT)),
        "# HELP crema_http_requests_total Completed HTTP requests by bounded route template.",
        "# TYPE crema_http_requests_total counter",
    ]
    with _LOCK:
        http_requests = list(_HTTP_REQUESTS.items())
        kiosk_events = list(_KIOSK_EVENTS.items())
        transitions = list(_KIOSK_TRANSITIONS.items())
        brew_results = dict(_BREWS)
        dropped_snapshots = dict(_DROPPED_SNAPSHOTS)
        websocket_drops = dict(_WEBSOCKET_DROPS)
        recovered_sessions = dict(_RECOVERED_SESSIONS)

    for (method, route, status), value in sorted(http_requests):
        lines.append(_sample("crema_http_requests_total", value, {
            "method": method, "route": route, "status": status,
        }))
    lines.extend([
        "# HELP crema_kiosk_events_total Hardware events accepted by the kiosk loop.",
        "# TYPE crema_kiosk_events_total counter",
    ])
    for event, value in sorted(kiosk_events):
        lines.append(_sample("crema_kiosk_events_total", value, {"event": event}))
    lines.extend([
        "# HELP crema_kiosk_transitions_total Session state transitions.",
        "# TYPE crema_kiosk_transitions_total counter",
    ])
    for (source, destination), value in sorted(transitions):
        lines.append(_sample("crema_kiosk_transitions_total", value, {
            "from": source, "to": destination,
        }))
    lines.extend([
        "# HELP crema_kiosk_brew_results_total Brew and noise events observed in this process.",
        "# TYPE crema_kiosk_brew_results_total counter",
    ])
    for kind in ("brew", "noise"):
        lines.append(_sample("crema_kiosk_brew_results_total", brew_results.get(kind, 0), {"kind": kind}))
    lines.extend([
        "# HELP crema_kiosk_snapshot_drops_total Snapshots dropped before websocket delivery.",
        "# TYPE crema_kiosk_snapshot_drops_total counter",
    ])
    lines.append(_sample("crema_kiosk_snapshot_drops_total", dropped_snapshots.get("queue_full", 0)))
    lines.extend([
        "# HELP crema_kiosk_websocket_drops_total Disconnected websocket clients by bounded reason.",
        "# TYPE crema_kiosk_websocket_drops_total counter",
    ])
    for reason in ("send_failed", "simulator"):
        lines.append(_sample("crema_kiosk_websocket_drops_total", websocket_drops.get(reason, 0), {"reason": reason}))
    lines.extend([
        "# HELP crema_sessions_recovered_total Open sessions closed during exclusive startup recovery.",
        "# TYPE crema_sessions_recovered_total counter",
        _sample("crema_sessions_recovered_total", recovered_sessions.get("startup", 0)),
        "# HELP crema_kiosk_running Whether the kiosk hardware loop is running.",
        "# TYPE crema_kiosk_running gauge",
        _sample("crema_kiosk_running", int(health["running"])),
        "# HELP crema_kiosk_scanner_connected Whether the QR scanner is connected.",
        "# TYPE crema_kiosk_scanner_connected gauge",
        _sample("crema_kiosk_scanner_connected", int(health["scanner"]["connected"])),
        "# HELP crema_kiosk_sensor_connected Whether the vibration sensor is connected.",
        "# TYPE crema_kiosk_sensor_connected gauge",
        _sample("crema_kiosk_sensor_connected", int(health["sensor"]["connected"])),
        "# HELP crema_kiosk_websocket_clients Current registered websocket clients.",
        "# TYPE crema_kiosk_websocket_clients gauge",
        _sample("crema_kiosk_websocket_clients", len(kiosk._ws_clients)),
    ])
    if snapshot is not None:
        lines.extend([
            "# HELP crema_kiosk_state Current session state, with exactly one active finite state.",
            "# TYPE crema_kiosk_state gauge",
        ])
        for state in sorted(_STATES):
            lines.append(_sample("crema_kiosk_state", int(snapshot["state"] == state), {"state": state}))
        lines.extend([
            "# HELP crema_kiosk_active_session Whether a user session is active. No identity is exported.",
            "# TYPE crema_kiosk_active_session gauge",
            _sample("crema_kiosk_active_session", int(snapshot["user"] is not None)),
        ])
    stale_age = health["sensor"].get("stale_age")
    if isinstance(stale_age, (int, float)) and stale_age >= 0:
        lines.extend([
            "# HELP crema_kiosk_sensor_stale_seconds Age of the most recent sensor sample.",
            "# TYPE crema_kiosk_sensor_stale_seconds gauge",
            _sample("crema_kiosk_sensor_stale_seconds", float(stale_age)),
        ])
    if con is not None:
        rows = con.execute("SELECT kind, COUNT(*) FROM brews GROUP BY kind").fetchall()
        stored = {row[0]: row[1] for row in rows if row[0] in {"brew", "noise"}}
        lines.extend([
            "# HELP crema_database_brews Persisted records by kind.",
            "# TYPE crema_database_brews gauge",
        ])
        for kind in ("brew", "noise"):
            lines.append(_sample("crema_database_brews", stored.get(kind, 0), {"kind": kind}))
        open_sessions = con.execute("SELECT COUNT(*) FROM sessions WHERE ended_at IS NULL").fetchone()[0]
        lines.extend([
            "# HELP crema_database_open_sessions Persisted sessions without an end timestamp.",
            "# TYPE crema_database_open_sessions gauge",
            _sample("crema_database_open_sessions", open_sessions),
        ])
    return "\n".join(lines) + "\n"

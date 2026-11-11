import asyncio
import logging
import os
import signal
import threading
from queue import Empty, Full, Queue

from core import monitoring

log = logging.getLogger(__name__)

_state = None
_ws_clients: set = set()
_snapshot_q: Queue = Queue(maxsize=50)
_hw_thread: threading.Thread | None = None
_scanner = None
_sensor = None
_stop = threading.Event()
_maintenance_lock = None
_simulator_active = False
_simulator_available = True


def get_state():
    """Return the live SessionState, or None if hardware not started."""
    return _state


def get_health() -> dict:
    running = bool(_hw_thread and _hw_thread.is_alive())
    scanner = _scanner.status() if _scanner is not None else {
        "connected": False,
        "last_scan_at": None,
        "error": "not started",
        "thread_alive": False,
    }
    sensor = _sensor.status() if _sensor is not None else {
        "connected": False,
        "last_read_at": None,
        "error": "not started",
        "thread_alive": False,
        "stale_age": None,
    }
    return {
        "running": running,
        "scanner": scanner,
        "sensor": sensor,
    }


def get_snapshot() -> dict | None:
    state = _state
    if state is None or (_simulator_active and not _simulator_available):
        return None
    snapshot = state._snapshot()
    snapshot["hardware"] = get_health()
    return snapshot


def register_ws(ws):
    """Register a WebSocket client to receive state snapshots."""
    _ws_clients.add(ws)


def unregister_ws(ws):
    """Remove a WebSocket client."""
    _ws_clients.discard(ws)


def _on_broadcast(snapshot: dict):
    """Called from the sync hardware thread to queue an async update."""
    snapshot = {**snapshot, "hardware": get_health()}
    try:
        _snapshot_q.put_nowait(snapshot)
    except Full:
        monitoring.record_dropped_snapshot()
        log.debug("snapshot queue full - dropping update")
    except Exception:
        log.exception("Could not queue kiosk snapshot")


async def broadcast_loop():
    """Drain the snapshot queue and push updates to WebSocket clients."""
    while True:
        try:
            snapshot = _snapshot_q.get_nowait()
        except Empty:
            await asyncio.sleep(0.05)
            continue
        dead = set()
        for ws in list(_ws_clients):
            try:
                await ws.send_json(snapshot)
            except Exception as exc:
                monitoring.record_websocket_drop("send_failed")
                log.debug("WebSocket send failed, dropping client: %s", exc)
                dead.add(ws)
        _ws_clients.difference_update(dead)


def _request_process_restart():
    os.kill(os.getpid(), signal.SIGTERM)


def _run_loop(state, hw_queue):
    try:
        log.info("Kiosk hardware loop started")
        while not _stop.is_set():
            state.on_tick()
            while True:
                try:
                    event = hw_queue.get_nowait()
                except Empty:
                    break
                state.handle(event)
                event_type = type(event).__name__
                monitoring.record_kiosk_event(event_type)
                log.info(
                    "Kiosk input processed",
                    extra={"event": "kiosk_input", "event_type": event_type},
                )
            _on_broadcast(state._snapshot())
            _stop.wait(1)
    except Exception:
        log.exception("Kiosk hardware loop failed; requesting supervised restart")
        _stop.set()
        _request_process_restart()
    finally:
        log.info("Kiosk hardware loop stopped")


def start():
    """Acquire the sole hardware ownership lock and start all hardware owners."""
    global _state, _hw_thread, _scanner, _sensor, _maintenance_lock

    if _hw_thread and _hw_thread.is_alive():
        return
    if any(owner is not None for owner in (_state, _hw_thread, _scanner, _sensor)):
        raise RuntimeError("previous kiosk hardware owners have not fully stopped")

    import core.db as db
    from core.state import SessionState
    from hardware.scanner import QRScanner
    from hardware.sensor import VibrationSensor

    _stop.clear()
    lock = db.maintenance_lock()
    try:
        lock.__enter__()
        _maintenance_lock = lock
        recovered = db.recover_open_sessions()
        monitoring.record_recovered_sessions(recovered)
        if recovered:
            log.info(
                "Recovered open sessions",
                extra={"event": "session_recovery", "count": recovered},
            )

        hw_queue = Queue()
        _state = SessionState(on_broadcast=_on_broadcast)
        _scanner = QRScanner(hw_queue, device_path=None)
        _sensor = VibrationSensor(hw_queue)
        _scanner.start()
        _sensor.start()
        _hw_thread = threading.Thread(
            target=_run_loop,
            args=(_state, hw_queue),
            daemon=True,
            name="kiosk-loop",
        )
        _hw_thread.start()
    except Exception:
        if _maintenance_lock is not None:
            stop()
        raise


def start_simulator(scanner, sensor):
    """Start the real kiosk state loop with caller-provided simulated devices."""
    global _state, _hw_thread, _scanner, _sensor

    if _hw_thread and _hw_thread.is_alive():
        raise RuntimeError("kiosk loop is already running")
    if any(owner is not None for owner in (_state, _hw_thread, _scanner, _sensor)):
        raise RuntimeError("previous kiosk owners have not fully stopped")

    from core.state import SessionState

    _stop.clear()
    _state = SessionState(on_broadcast=_on_broadcast)
    _scanner = scanner
    _sensor = sensor
    set_simulator_available(True)
    try:
        _scanner.start()
        _sensor.start()
        _hw_thread = threading.Thread(
            target=_run_loop,
            args=(_state, Queue()),
            daemon=True,
            name="kiosk-simulator-loop",
        )
        _hw_thread.start()
    except Exception:
        stop()
        raise
    return _state


def broadcast_now() -> None:
    state = _state
    if state is not None:
        _on_broadcast(state._snapshot())


def set_simulator_available(available: bool) -> None:
    global _simulator_active, _simulator_available
    _simulator_active = True
    _simulator_available = available


async def disconnect_clients() -> None:
    clients = list(_ws_clients)
    _ws_clients.clear()
    for ws in clients:
        monitoring.record_websocket_drop("simulator")
        try:
            await ws.close(code=1012, reason="Simulator connection interrupted")
        except Exception as exc:
            log.debug("WebSocket disconnect failed: %s", exc)


def _device_thread_alive(device) -> bool:
    return bool(device is not None and device.status().get("thread_alive", False))


def _release_maintenance_lock():
    global _maintenance_lock
    lock = _maintenance_lock
    _maintenance_lock = None
    if lock is not None:
        lock.__exit__(None, None, None)


def stop():
    """Stop owners and shut down state only after every owner has exited."""
    global _state, _hw_thread, _scanner, _sensor, _simulator_active, _simulator_available
    _stop.set()

    if _scanner is not None:
        _scanner.stop()
    if _sensor is not None:
        _sensor.stop()
    if _hw_thread is not None and _hw_thread.is_alive():
        _hw_thread.join(timeout=3)

    live_owners = []
    if _hw_thread is not None and _hw_thread.is_alive():
        live_owners.append("kiosk loop")
    if _device_thread_alive(_scanner):
        live_owners.append("scanner")
    if _device_thread_alive(_sensor):
        live_owners.append("sensor")
    if live_owners:
        log.error("Kiosk owners still running after stop: %s", ", ".join(live_owners))
        return False

    try:
        if _state is not None:
            _state.shutdown()
    finally:
        _state = None
        _hw_thread = None
        _scanner = None
        _sensor = None
        _simulator_active = False
        _simulator_available = True
        _release_maintenance_lock()
    return True

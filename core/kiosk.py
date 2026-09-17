import asyncio
import logging
import threading
from queue import Queue, Empty

log = logging.getLogger(__name__)

# ── Globals ──────────────────────────────────────────────────────────────────
_state = None                        # SessionState singleton
_ws_clients: set = set()             # connected WebSocket objects
_snapshot_q: Queue = Queue(maxsize=50)  # sync→async bridge
_hw_thread: threading.Thread | None = None
_scanner = None
_sensor = None
_stop = threading.Event()


# ── Public API ────────────────────────────────────────────────────────────────

def get_state():
    """Return the live SessionState, or None if hardware not started."""
    return _state


def get_health() -> dict:
    running = bool(_hw_thread and _hw_thread.is_alive())
    scanner = _scanner.status() if _scanner is not None else {
        "connected": False,
        "last_scan_at": None,
        "error": "not started",
    }
    sensor = _sensor.status() if _sensor is not None else {
        "connected": False,
        "last_read_at": None,
        "error": "not started",
    }
    return {
        "running": running,
        "scanner": scanner,
        "sensor": sensor,
    }


def get_snapshot() -> dict | None:
    if _state is None:
        return None
    snapshot = _state._snapshot()
    snapshot["hardware"] = get_health()
    return snapshot


def register_ws(ws):
    """Register a WebSocket client to receive state snapshots."""
    _ws_clients.add(ws)


def unregister_ws(ws):
    """Remove a WebSocket client."""
    _ws_clients.discard(ws)


def _on_broadcast(snapshot: dict):
    """Called from the sync hardware thread — puts snapshot on async queue."""
    snapshot = {**snapshot, "hardware": get_health()}
    try:
        _snapshot_q.put_nowait(snapshot)
    except Exception:
        log.debug("snapshot queue full — dropping update")


async def broadcast_loop():
    """Drain snapshot queue and push to all WebSocket clients.
    Run as a FastAPI startup task via asyncio.create_task()."""
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
            except Exception as e:
                log.debug("WebSocket send failed, dropping client: %s", e)
                dead.add(ws)
        _ws_clients.difference_update(dead)


def start():
    """Initialize hardware and start the kiosk loop thread.
    Call before uvicorn.run() — hardware starts immediately,
    WebSocket broadcasting begins once the asyncio loop is running."""
    global _state, _hw_thread, _scanner, _sensor

    if _hw_thread and _hw_thread.is_alive():
        return
    _stop.clear()

    from core.state import SessionState
    from hardware.scanner import QRScanner
    from hardware.sensor import VibrationSensor

    hw_queue = Queue()
    _state = SessionState(on_broadcast=_on_broadcast)

    _scanner = QRScanner(hw_queue, device_path=None)
    _sensor = VibrationSensor(hw_queue)
    _scanner.start()
    _sensor.start()

    def _loop():
        log.info("Kiosk hardware loop started")
        while not _stop.is_set():
            _state.on_tick()
            while not hw_queue.empty():
                _state.handle(hw_queue.get_nowait())
            _on_broadcast(_state._snapshot())
            _stop.wait(1)
        log.info("Kiosk hardware loop stopped")

    _hw_thread = threading.Thread(target=_loop, daemon=True, name="kiosk-loop")
    _hw_thread.start()


def stop():
    """Signal the hardware loop to stop and wait for it."""
    global _state, _hw_thread, _scanner, _sensor
    _stop.set()
    if _scanner:
        _scanner.stop()
    if _sensor:
        _sensor.stop()
    if _hw_thread:
        _hw_thread.join(timeout=3)
    _state = None
    _hw_thread = None
    _scanner = None
    _sensor = None

import asyncio
import logging
import threading
import time
from queue import Queue, Empty

log = logging.getLogger(__name__)

# ── Globals ──────────────────────────────────────────────────────────────────
_state = None                        # SessionState singleton
_ws_clients: set = set()             # connected WebSocket objects
_snapshot_q: Queue = Queue(maxsize=50)  # sync→async bridge
_hw_thread: threading.Thread | None = None
_stop = threading.Event()


# ── Public API ────────────────────────────────────────────────────────────────

def get_state():
    """Return the live SessionState, or None if hardware not started."""
    return _state


def register_ws(ws):
    """Register a WebSocket client to receive state snapshots."""
    _ws_clients.add(ws)


def unregister_ws(ws):
    """Remove a WebSocket client."""
    _ws_clients.discard(ws)


def _on_broadcast(snapshot: dict):
    """Called from the sync hardware thread — puts snapshot on async queue."""
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
    global _state, _hw_thread

    from core.state import SessionState
    from hardware.scanner import QRScanner
    from hardware.sensor import VibrationSensor

    hw_queue = Queue()
    _state = SessionState(on_broadcast=_on_broadcast)

    scanner = QRScanner(hw_queue, device_path=None)
    sensor = VibrationSensor(hw_queue)
    scanner.start()
    sensor.start()

    def _loop():
        log.info("Kiosk hardware loop started")
        while not _stop.is_set():
            _state.on_tick()
            while not hw_queue.empty():
                _state.handle(hw_queue.get_nowait())
            time.sleep(1)
        log.info("Kiosk hardware loop stopped")

    _hw_thread = threading.Thread(target=_loop, daemon=True, name="kiosk-loop")
    _hw_thread.start()


def stop():
    """Signal the hardware loop to stop and wait for it."""
    _stop.set()
    if _hw_thread:
        _hw_thread.join(timeout=3)

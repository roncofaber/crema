import logging
import select
import threading
import time
from queue import Queue

from core.events import QRScanned
from core.identity import is_email, normalize_token

log = logging.getLogger(__name__)

POLL_TIMEOUT = 0.2


def _is_email(token: str) -> bool:
    return is_email(token)


class QRScanner:
    """
    Reads QR codes from a USB HID scanner.
    device_path=None automatically detects the configured scanner.
    device_path='/dev/input/eventX' reads exclusively via evdev.
    """

    def __init__(self, queue: Queue, device_path: str = None):
        self._queue = queue
        self._configured_path = device_path
        self._device = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="qr-scanner")
        self._connected = False
        self._last_scan_at = None
        self._last_error = None

    def start(self):
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)
        if self._thread.is_alive():
            log.error("scanner thread did not stop within 2 s")
            return False
        return True

    def status(self) -> dict:
        return {
            "connected": self._connected,
            "last_scan_at": self._last_scan_at,
            "error": self._last_error,
            "thread_alive": self._thread.is_alive(),
        }

    def _find_device_path(self) -> str | None:
        from evdev import InputDevice, list_devices
        from config import SCANNER_DEVICE_NAME
        for path in list_devices():
            try:
                device = InputDevice(path)
                try:
                    if device.name == SCANNER_DEVICE_NAME:
                        return path
                finally:
                    device.close()
            except Exception as exc:
                log.debug("could not open input device %s: %s", path, exc)
                continue
        return None

    def _run(self):
        while not self._stop.is_set():
            try:
                path = self._configured_path or self._find_device_path()
                if path:
                    log.info("scanner opened: %s", path)
                    self._run_evdev(path)
                    if not self._stop.is_set():
                        log.warning("scanner disconnected, retrying in 5 s")
                else:
                    self._last_error = "scanner not found"
                    log.debug("scanner not found, retrying in 5 s")
            except Exception as exc:
                self._last_error = str(exc)
                if not self._stop.is_set():
                    log.warning("scanner error: %s", exc)
            finally:
                self._connected = False
                if self._device is not None:
                    try:
                        self._device.ungrab()
                    except Exception:
                        pass
                    try:
                        self._device.close()
                    except Exception:
                        pass
                self._device = None
            self._stop.wait(5)

    def _run_evdev(self, path: str):
        from evdev import InputDevice, categorize, ecodes, KeyEvent

        keymap = {
            **{f"KEY_{c}": (c.lower(), c.upper()) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"},
            "KEY_1": ("1", "!"), "KEY_2": ("2", "@"), "KEY_3": ("3", "#"),
            "KEY_4": ("4", "$"), "KEY_5": ("5", "%"), "KEY_6": ("6", "^"),
            "KEY_7": ("7", "&"), "KEY_8": ("8", "*"), "KEY_9": ("9", "("),
            "KEY_0": ("0", ")"),
            "KEY_MINUS": ("-", "_"),
            "KEY_EQUAL": ("=", "+"),
            "KEY_DOT": (".", ">"),
            "KEY_AT": ("@", "@"),
        }
        shift_keys = {"KEY_LEFTSHIFT", "KEY_RIGHTSHIFT"}

        device = InputDevice(path)
        self._device = device
        device.grab()
        self._connected = True
        self._last_error = None
        buffer = []
        shifted = False

        while not self._stop.is_set():
            readable, _, _ = select.select([device], [], [], POLL_TIMEOUT)
            if not readable:
                continue
            for event in device.read():
                if event.type != ecodes.EV_KEY:
                    continue
                key = categorize(event)
                if key.keystate == KeyEvent.key_down:
                    code = key.keycode if isinstance(key.keycode, str) else key.keycode[0]
                    if code in shift_keys:
                        shifted = True
                    elif code == "KEY_ENTER":
                        self._handle_raw("".join(buffer))
                        buffer.clear()
                    elif code in keymap:
                        buffer.append(keymap[code][1 if shifted else 0])
                elif key.keystate == KeyEvent.key_up:
                    code = key.keycode if isinstance(key.keycode, str) else key.keycode[0]
                    if code in shift_keys:
                        shifted = False

    def _handle_raw(self, raw: str):
        token = normalize_token(raw)
        if _is_email(token):
            log.info("QR scan accepted: %s", token)
            self._last_scan_at = time.time()
            self._queue.put(QRScanned(token=token))
        elif token:
            log.debug("QR scan rejected (not email): %s", token)

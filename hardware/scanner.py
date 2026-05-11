import re
import threading
import sys
from queue import Queue
from core.events import QRScanned

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _is_email(token: str) -> bool:
    return bool(_EMAIL_RE.match(token.strip()))


def _readline() -> str:
    return sys.stdin.readline().strip()


class QRScanner:
    """
    Reads QR codes from a USB HID scanner.
    device_path=None → reads from stdin (useful for testing / dev without hardware).
    device_path='/dev/input/eventX' → reads exclusively via evdev.
    """

    def __init__(self, queue: Queue, device_path: str = None):
        self._queue       = queue
        self._device_path = device_path
        self._thread      = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def _find_device_path(self) -> str | None:
        from evdev import InputDevice, list_devices
        from config import SCANNER_DEVICE_NAME
        for path in list_devices():
            try:
                if InputDevice(path).name == SCANNER_DEVICE_NAME:
                    return path
            except Exception:
                continue
        return None

    def _run(self):
        path = self._device_path or self._find_device_path()
        if path:
            self._device_path = path
            self._run_evdev()
        else:
            self._run_stdin()

    def _run_stdin(self):
        while True:
            try:
                raw = _readline()
                self._handle_raw(raw)
            except EOFError:
                break

    def _run_evdev(self):
        from evdev import InputDevice, categorize, ecodes, KeyEvent

        _KEYMAP = {
            **{f"KEY_{c}": (c.lower(), c.upper()) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"},
            "KEY_1": ("1", "!"), "KEY_2": ("2", "@"), "KEY_3": ("3", "#"),
            "KEY_4": ("4", "$"), "KEY_5": ("5", "%"), "KEY_6": ("6", "^"),
            "KEY_7": ("7", "&"), "KEY_8": ("8", "*"), "KEY_9": ("9", "("),
            "KEY_0": ("0", ")"),
            "KEY_MINUS":  ("-", "_"),
            "KEY_EQUAL":  ("=", "+"),
            "KEY_DOT":    (".", ">"),
            "KEY_AT":     ("@", "@"),
        }
        _SHIFT_KEYS = {"KEY_LEFTSHIFT", "KEY_RIGHTSHIFT"}

        device  = InputDevice(self._device_path)
        device.grab()
        buffer  = []
        shifted = False

        for event in device.read_loop():
            if event.type != ecodes.EV_KEY:
                continue
            key = categorize(event)
            if key.keystate == KeyEvent.key_down:
                code = key.keycode if isinstance(key.keycode, str) else key.keycode[0]
                if code in _SHIFT_KEYS:
                    shifted = True
                elif code == "KEY_ENTER":
                    self._handle_raw("".join(buffer))
                    buffer.clear()
                elif code in _KEYMAP:
                    buffer.append(_KEYMAP[code][1 if shifted else 0])
            elif key.keystate == KeyEvent.key_up:
                code = key.keycode if isinstance(key.keycode, str) else key.keycode[0]
                if code in _SHIFT_KEYS:
                    shifted = False

    def _handle_raw(self, raw: str):
        token = raw.strip().lower()
        if _is_email(token):
            self._queue.put(QRScanned(token=token))

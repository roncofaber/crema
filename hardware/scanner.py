import threading


class QRScanner:
    """
    Reads QR codes from a USB HID scanner (acts as a keyboard, sends a line of text + Enter).
    Runs a background thread; calls on_scan(token) when a code is read.
    """

    def __init__(self, on_scan, device_path: str = None):
        """
        on_scan: callable(token: str)
        device_path: e.g. '/dev/input/event0' — if None, reads from stdin (useful for testing)
        """
        self.on_scan     = on_scan
        self.device_path = device_path
        self._thread     = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def _run(self):
        raise NotImplementedError

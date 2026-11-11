import threading
import time


class SimulatedDevice:
    def __init__(self):
        self.alive = False
        self.connected = True
        self.error = None

    def start(self):
        self.alive = True

    def stop(self):
        self.alive = False
        self.connected = False

    def degrade(self, degraded: bool):
        self.connected = not degraded
        self.error = "simulated offline" if degraded else None

    def status(self):
        return {
            "connected": self.connected,
            "error": self.error,
            "thread_alive": self.alive,
        }


class SimulatedScanner(SimulatedDevice):
    def __init__(self):
        super().__init__()
        self.last_scan_at = None

    def scanned(self):
        self.last_scan_at = time.time()

    def status(self):
        return {**super().status(), "last_scan_at": self.last_scan_at}


class SimulatedSensor(SimulatedDevice):
    def __init__(self):
        super().__init__()
        self.last_read_at = time.time()
        self.missing_samples = False
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="simulated-sensor")

    def start(self):
        super().start()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="simulated-sensor")
        self._thread.start()

    def stop(self):
        super().stop()
        self._stop_event.set()
        self._thread.join(timeout=1)

    def _run(self):
        while not self._stop_event.wait(0.25):
            if self.alive and self.connected and not self.missing_samples:
                self.last_read_at = time.time()

    def configure(self, *, degraded: bool, missing_samples: bool):
        self.degrade(degraded)
        self.missing_samples = missing_samples
        if not missing_samples and self.last_read_at is None:
            self.last_read_at = time.time()

    def status(self):
        last_read_at = None if self.missing_samples else self.last_read_at
        stale_age = None if last_read_at is None else max(0, time.time() - last_read_at)
        return {
            **super().status(),
            "last_read_at": last_read_at,
            "stale_age": stale_age,
            "thread_alive": self._thread.is_alive(),
        }

import logging
import math
import threading
import time
from queue import Queue

from config import (
    ADXL_BREW_THRESHOLD,
    ADXL_SAMPLE_RATE,
    BREW_CONFIRM_WINDOW,
    BREW_END_SILENCE,
    MIN_VIBRATION_PULSE,
)
from core.events import BrewEnd, BrewStart

log = logging.getLogger(__name__)

POLL_INTERVAL = 1.0 / ADXL_SAMPLE_RATE
MAX_SAMPLE_GAP = max(0.1, POLL_INTERVAL * 2.5)


class VibrationSensor:
    """
    Monitors an ADXL345 3-axis accelerometer over I2C.
    Posts BrewStart and BrewEnd events to a queue with debouncing:
      - MIN_VIBRATION_PULSE (0.5s): acceleration magnitude must stay above threshold this long to count
      - BREW_CONFIRM_WINDOW (2s): vibration must be sustained before BrewStart fires
      - BREW_END_SILENCE (10s): silence must last this long before BrewEnd fires
    """

    def __init__(self, queue: Queue):
        self._queue = queue
        self._thread = threading.Thread(target=self._run, daemon=True, name="vibration-sensor")
        self._stop = threading.Event()
        self._accel = None
        self._i2c = None
        self._connected = False
        self._last_read_at = None
        self._last_error = None

        self._vibration_start = None
        self._last_valid_high = None
        self._pulse_start = None
        self._silence_start = None
        self._last_sample_at = None
        self._brew_start_fired = False

    def start(self):
        if not self._thread.is_alive():
            self._thread.start()

    @staticmethod
    def _close_resource(resource, *method_names):
        if resource is None:
            return
        for method_name in method_names:
            method = getattr(resource, method_name, None)
            if callable(method):
                try:
                    method()
                except Exception as exc:
                    log.debug("ADXL345 resource cleanup failed: %s", exc)
                return

    def _release_device(self):
        accel = self._accel
        i2c = self._i2c
        self._accel = None
        self._i2c = None
        self._connected = False
        self._close_resource(accel, "close")
        self._close_resource(i2c, "deinit", "close")

    def _connect(self) -> bool:
        self._release_device()
        try:
            import board
            import busio
            import adafruit_adxl34x

            self._i2c = busio.I2C(board.SCL, board.SDA)
            self._accel = adafruit_adxl34x.ADXL345(self._i2c)
            self._connected = True
            self._last_error = None
            log.info("ADXL345 connected")
            return True
        except Exception as exc:
            self._release_device()
            self._last_error = str(exc)
            log.error("ADXL345 init failed: %s - retrying in 5 s", exc)
            return False

    def stop(self):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)
        if self._thread.is_alive():
            log.error("ADXL345 thread did not stop within 2 s")
            return False
        self._release_device()
        return True

    def status(self) -> dict:
        stale_age = None
        if self._last_read_at is not None:
            stale_age = max(0.0, time.time() - self._last_read_at)
        return {
            "connected": self._connected,
            "last_read_at": self._last_read_at,
            "error": self._last_error,
            "thread_alive": self._thread.is_alive(),
            "stale_age": stale_age,
        }

    def _magnitude(self):
        """Read acceleration from ADXL345 and return magnitude in m/s²."""
        if self._accel is None:
            return None
        try:
            x, y, z = self._accel.acceleration
            magnitude = math.sqrt(x * x + y * y + z * z)
            if not math.isfinite(magnitude):
                raise ValueError("non-finite acceleration reading")
            self._connected = True
            self._last_read_at = time.time()
            return magnitude
        except Exception as exc:
            self._release_device()
            self._last_error = str(exc)
            log.warning("I2C read error: %s - reconnecting", exc)
            return None

    def _run(self):
        try:
            while not self._stop.is_set():
                if self._accel is None and not self._connect():
                    self._stop.wait(5)
                    continue
                self._step()
                self._stop.wait(POLL_INTERVAL)
        finally:
            self._release_device()

    def _reset_partial_debounce(self):
        self._pulse_start = None
        self._silence_start = None
        if not self._brew_start_fired:
            self._vibration_start = None
            self._last_valid_high = None

    def _step(self, magnitude=None):
        """
        Core debouncing step.
        magnitude: optional value for testing; if None, reads from accelerometer
        """
        now = time.time()
        if magnitude is None:
            magnitude = self._magnitude()
        if magnitude is None:
            self._last_sample_at = None
            self._reset_partial_debounce()
            return

        if self._last_sample_at is not None:
            if now - self._last_sample_at > MAX_SAMPLE_GAP:
                self._reset_partial_debounce()
        self._last_sample_at = now
        is_high = magnitude > ADXL_BREW_THRESHOLD

        if is_high:
            if self._pulse_start is None:
                self._pulse_start = now

            pulse_duration = now - self._pulse_start
            if pulse_duration >= MIN_VIBRATION_PULSE:
                self._last_valid_high = now
                self._silence_start = None
                if self._vibration_start is None:
                    self._vibration_start = self._pulse_start

                if not self._brew_start_fired:
                    if now - self._vibration_start >= BREW_CONFIRM_WINDOW:
                        log.info("BrewStart fired")
                        self._queue.put(BrewStart())
                        self._brew_start_fired = True
        else:
            self._pulse_start = None
            if self._last_valid_high is not None:
                if self._silence_start is None:
                    self._silence_start = now
                silence = now - self._silence_start
                if silence >= BREW_END_SILENCE:
                    duration = self._last_valid_high - self._vibration_start
                    log.info("BrewEnd fired: duration=%.1fs silence=%.1fs", duration, silence)
                    self._queue.put(BrewEnd(
                        started_at=self._vibration_start,
                        ended_at=self._last_valid_high,
                    ))
                    self._vibration_start = None
                    self._last_valid_high = None
                    self._silence_start = None
                    self._brew_start_fired = False

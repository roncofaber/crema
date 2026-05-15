import logging
import threading
import time
import math
from queue import Queue
from core.events import BrewStart, BrewEnd
from config import (
    ADXL_BREW_THRESHOLD, ADXL_SAMPLE_RATE,
    BREW_END_SILENCE, MIN_VIBRATION_PULSE,
    BREW_CONFIRM_WINDOW,
)

log = logging.getLogger(__name__)

POLL_INTERVAL = 1.0 / ADXL_SAMPLE_RATE


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
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._accel = None

        self._vibration_start = None   # timestamp of first high magnitude in current cycle
        self._last_valid_high = None   # timestamp of last high magnitude >= MIN_VIBRATION_PULSE
        self._pulse_start = None       # timestamp when current high pulse began
        self._brew_start_fired = False # whether BrewStart has been posted this cycle

    def start(self):
        import board
        import busio
        import adafruit_adxl34x

        i2c = busio.I2C(board.SCL, board.SDA)
        try:
            self._accel = adafruit_adxl34x.ADXL345(i2c)
        except Exception as e:
            log.error("ADXL345 init failed: %s — sensor disabled", e)
            return
        self._thread.start()

    def stop(self):
        pass  # daemon thread exits with process

    def _magnitude(self):
        """Read acceleration from ADXL345 and return magnitude in m/s²."""
        if self._accel is None:
            return 0.0
        try:
            x, y, z = self._accel.acceleration
            return math.sqrt(x * x + y * y + z * z)
        except OSError as e:
            log.warning("I2C read error: %s — skipping sample", e)
            return 0.0

    def _run(self):
        while True:
            self._step()
            time.sleep(POLL_INTERVAL)

    def _step(self, magnitude=None):
        """
        Core debouncing step.
        magnitude: optional value for testing; if None, reads from accelerometer
        """
        now = time.time()
        if magnitude is None:
            magnitude = self._magnitude()

        is_high = magnitude > ADXL_BREW_THRESHOLD

        if is_high:
            if self._pulse_start is None:
                self._pulse_start = now

            pulse_duration = now - self._pulse_start

            if pulse_duration >= MIN_VIBRATION_PULSE:
                self._last_valid_high = now
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
                silence = now - self._last_valid_high
                if silence >= BREW_END_SILENCE:
                    duration = self._last_valid_high - self._vibration_start
                    log.info("BrewEnd fired: duration=%.1fs silence=%.1fs", duration, silence)
                    self._queue.put(BrewEnd(
                        started_at=self._vibration_start,
                        ended_at=self._last_valid_high,
                    ))
                    self._vibration_start = None
                    self._last_valid_high = None
                    self._brew_start_fired = False

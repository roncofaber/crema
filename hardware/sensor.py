import logging
import threading
import time
import RPi.GPIO as GPIO
from queue import Queue
from core.events import BrewStart, BrewEnd
from config import (
    VIBRATION_PIN, BREW_END_SILENCE, MIN_VIBRATION_PULSE,
    BREW_CONFIRM_WINDOW, SENSOR_POLL_INTERVAL,
)  # noqa: E402

log = logging.getLogger(__name__)


class VibrationSensor:
    """
    Monitors a digital vibration sensor (SW-420) on a GPIO pin.
    Posts BrewStart and BrewEnd events to a queue with debouncing:
      - MIN_VIBRATION_PULSE (0.5s): HIGH pulse must last this long to count as real vibration
      - BREW_CONFIRM_WINDOW (2s): vibration must be sustained before BrewStart fires
      - BREW_END_SILENCE (10s): silence must last this long before BrewEnd fires
    """

    def __init__(self, queue: Queue):
        self._queue          = queue
        self._thread         = threading.Thread(target=self._run, daemon=True)

        self._vibration_start  = None   # timestamp of first HIGH in current cycle
        self._last_valid_high  = None   # timestamp of last HIGH pulse >= MIN_VIBRATION_PULSE
        self._pulse_start      = None   # timestamp when current HIGH pulse began
        self._brew_start_fired = False  # whether BrewStart has been posted this cycle

    def start(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(VIBRATION_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        self._thread.start()

    def stop(self):
        GPIO.cleanup()

    def _run(self):
        while True:
            self._step()
            time.sleep(SENSOR_POLL_INTERVAL)

    def _step(self):
        now      = time.time()
        is_high  = GPIO.input(VIBRATION_PIN) == GPIO.HIGH

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
                    self._vibration_start  = None
                    self._last_valid_high  = None
                    self._brew_start_fired = False

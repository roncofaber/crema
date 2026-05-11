import threading
import time
import RPi.GPIO as GPIO
from config import VIBRATION_PIN, MIN_BREW_DURATION, BREW_END_SILENCE  # noqa: E402


class VibrationSensor:
    """
    Monitors a digital vibration sensor (SW-420) on a GPIO pin.
    Calls on_brew_start() / on_brew_end(duration) with debouncing:
      - vibration must be sustained for MIN_BREW_DURATION before on_brew_start fires
      - silence must last BREW_END_SILENCE seconds before on_brew_end fires
    """

    def __init__(self, on_brew_start, on_brew_end):
        self.on_brew_start = on_brew_start
        self.on_brew_end   = on_brew_end
        self._thread       = threading.Thread(target=self._run, daemon=True)

    def start(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(VIBRATION_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        self._thread.start()

    def stop(self):
        GPIO.cleanup()

    def _run(self):
        raise NotImplementedError

"""
Live monitor for the SW-420 vibration sensor.
Prints a timestamped line on every state change (LOW->HIGH or HIGH->LOW).
Run from the repo root: python tools/sensor_monitor.py
"""
import sys
import time
import RPi.GPIO as GPIO
from config import VIBRATION_PIN, SENSOR_POLL_INTERVAL

GPIO.setmode(GPIO.BCM)
GPIO.setup(VIBRATION_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

print(f"Monitoring GPIO pin {VIBRATION_PIN} (SW-420). Ctrl-C to quit.\n")

last = None
high_since = None

try:
    while True:
        state = GPIO.input(VIBRATION_PIN)
        now = time.time()

        if state != last:
            ts = time.strftime("%H:%M:%S")
            if state == GPIO.HIGH:
                high_since = now
                print(f"{ts}  HIGH", flush=True)
            else:
                duration = f"  ({now - high_since:.2f}s)" if high_since else ""
                print(f"{ts}  LOW{duration}", flush=True)
                high_since = None
            last = state

        time.sleep(SENSOR_POLL_INTERVAL)

except KeyboardInterrupt:
    pass
finally:
    GPIO.cleanup()

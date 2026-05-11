import time

import click


@click.command()
def sensor():
    """Live monitor for the SW-420 vibration sensor."""
    try:
        import RPi.GPIO as GPIO
    except ImportError:
        raise click.ClickException("RPi.GPIO not available — run this on the Pi.")

    from config import VIBRATION_PIN, SENSOR_POLL_INTERVAL

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(VIBRATION_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    click.echo(f"Monitoring GPIO pin {VIBRATION_PIN} (SW-420). Ctrl-C to quit.\n")

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
                    click.echo(f"{ts}  HIGH")
                else:
                    duration = f"  ({now - high_since:.2f}s)" if high_since else ""
                    click.echo(f"{ts}  LOW{duration}")
                    high_since = None
                last = state

            time.sleep(SENSOR_POLL_INTERVAL)

    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup()

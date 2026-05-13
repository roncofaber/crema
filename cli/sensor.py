import time
import math
import sys
import click


@click.command()
def sensor():
    """Live ADXL345 accelerometer monitor for calibrating brew threshold."""
    try:
        import board
        import busio
        import digitalio
        import adafruit_adxl34x
    except ImportError:
        raise click.ClickException("Hardware libs not available — run this on the Pi.")

    from config import ADXL_BREW_THRESHOLD, ADXL_RANGE

    spi = busio.SPI(board.SCLK, MOSI=board.MOSI, MISO=board.MISO)
    cs = digitalio.DigitalInOut(board.CE1)
    accel = adafruit_adxl34x.ADXL345(spi, cs)

    click.echo("ADXL345 — live readout  (Ctrl+C to quit)")
    click.echo("─" * 43)

    peak = 0.0

    try:
        while True:
            x, y, z = accel.acceleration
            mag = math.sqrt(x * x + y * y + z * z)
            peak = max(peak, mag)

            above = mag > ADXL_BREW_THRESHOLD
            status = "[ACTIVE]" if above else "[QUIET] "

            bar_max = 20.0
            filled = int(min(1.0, mag / bar_max) * 28)
            bar = "█" * filled + "░" * (28 - filled)

            line = (
                f"\r  X:{x:+7.3f}  Y:{y:+7.3f}  Z:{z:+7.3f} m/s²  "
                f"mag:{mag:6.3f}  peak:{peak:6.3f}  {status}  [{bar}]"
            )
            sys.stdout.write(line)
            sys.stdout.flush()
            time.sleep(0.1)

    except KeyboardInterrupt:
        click.echo()

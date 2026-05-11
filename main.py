import time
import core.db as db
from core.state import SessionState
from hardware.display import Display
from hardware.scanner import QRScanner
from hardware.sensor import VibrationSensor


def main():
    db.init_db()

    session = SessionState()
    display = Display()

    def on_qr(token: str):
        session.on_qr_scan(token)

    def on_brew_start():
        session.on_vibration_start()

    def on_brew_end(duration: float):
        session.on_vibration_end(duration)

    scanner = QRScanner(on_scan=on_qr)
    sensor  = VibrationSensor(on_brew_start=on_brew_start, on_brew_end=on_brew_end)

    scanner.start()
    sensor.start()

    display.show_idle()

    try:
        while True:
            session.on_tick()
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        sensor.stop()


if __name__ == "__main__":
    main()

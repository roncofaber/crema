import time
from queue import Queue

import core.db as db
from core.state import SessionState
from hardware.display import Display
from hardware.scanner import QRScanner
from hardware.sensor import VibrationSensor


def main():
    db.init_db()

    q       = Queue()
    display = Display()
    state   = SessionState(display)
    scanner = QRScanner(q, device_path=None)  # auto-detects by name; set explicitly to override
    sensor  = VibrationSensor(q)

    scanner.start()
    sensor.start()

    display.show_idle()

    try:
        while True:
            state.on_tick()
            while not q.empty():
                state.handle(q.get_nowait())
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        sensor.stop()


if __name__ == "__main__":
    main()

import queue
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from hardware.scanner import POLL_TIMEOUT, QRScanner, _is_email
from core.events import QRScanned


def test_is_email_valid():
    assert _is_email("alice@example.com")
    assert _is_email("john.doe+tag@company.org")


def test_is_email_rejects_badge_number():
    assert not _is_email("123456")


def test_is_email_rejects_garbage():
    assert not _is_email("notanemail")
    assert not _is_email("")
    assert not _is_email("@nodomain")


def test_scanner_posts_valid_email():
    q = queue.Queue()
    scanner = QRScanner(q, device_path=None)
    scanner._handle_raw("alice@example.com")
    event = q.get_nowait()
    assert isinstance(event, QRScanned)
    assert event.token == "alice@example.com"


def test_scanner_ignores_badge_number():
    q = queue.Queue()
    scanner = QRScanner(q, device_path=None)
    scanner._handle_raw("987654")
    assert q.empty()


def test_scanner_ignores_empty_input():
    q = queue.Queue()
    scanner = QRScanner(q, device_path=None)
    scanner._handle_raw("")
    assert q.empty()


def test_scanner_lowercases_email():
    q = queue.Queue()
    scanner = QRScanner(q, device_path=None)
    scanner._handle_raw("Alice@Example.COM")
    event = q.get_nowait()
    assert event.token == "alice@example.com"


def test_scanner_uses_shared_email_length_validation():
    q = queue.Queue()
    scanner = QRScanner(q)
    scanner._handle_raw(f"{'a' * 250}@example.com")
    assert q.empty()


def test_scanner_stop_does_not_close_device_from_another_thread():
    scanner = QRScanner(queue.Queue())
    device = MagicMock()
    scanner._device = device

    assert scanner.stop() is True
    device.close.assert_not_called()


def test_scanner_polling_wakes_for_shutdown_and_closes_in_worker():
    scanner = QRScanner(queue.Queue(), device_path="/fake/input")
    device = MagicMock()
    evdev = SimpleNamespace(
        InputDevice=MagicMock(return_value=device),
        categorize=MagicMock(),
        ecodes=SimpleNamespace(EV_KEY=1),
        KeyEvent=SimpleNamespace(key_down=1, key_up=0),
    )

    def select_timeout(devices, _readers, _writers, timeout):
        assert devices == [device]
        assert timeout == POLL_TIMEOUT
        scanner._stop.set()
        return [], [], []

    with patch.dict(sys.modules, {"evdev": evdev}):
        with patch("hardware.scanner.select.select", side_effect=select_timeout):
            scanner.start()
            scanner._thread.join(timeout=1)

    assert scanner.stop() is True
    device.read.assert_not_called()
    device.ungrab.assert_called_once_with()
    device.close.assert_called_once_with()


def test_scanner_discovery_closes_every_probed_device():
    scanner = QRScanner(queue.Queue())
    other = MagicMock()
    other.name = "other"
    matching = MagicMock()
    matching.name = "MINJCODE MINJCODE MJ2818A"
    devices = {"/dev/input/event0": other, "/dev/input/event1": matching}
    evdev = SimpleNamespace(
        InputDevice=lambda path: devices[path],
        list_devices=lambda: list(devices),
    )

    with patch.dict(sys.modules, {"evdev": evdev}), patch("config.SCANNER_DEVICE_NAME", matching.name):
        assert scanner._find_device_path() == "/dev/input/event1"

    other.close.assert_called_once_with()
    matching.close.assert_called_once_with()

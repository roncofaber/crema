import queue
from hardware.scanner import QRScanner, _is_email
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

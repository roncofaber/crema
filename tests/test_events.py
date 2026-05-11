from core.events import QRScanned, BrewStart, BrewEnd


def test_qr_scanned_holds_token():
    e = QRScanned(token="user@example.com")
    assert e.token == "user@example.com"


def test_brew_end_holds_timing():
    e = BrewEnd(started_at=1000.0, ended_at=1030.0, duration=30.0)
    assert e.duration == 30.0
    assert e.ended_at - e.started_at == 30.0


def test_brew_start_is_instantiable():
    e = BrewStart()
    assert isinstance(e, BrewStart)

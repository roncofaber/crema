import sys
import queue
from unittest.mock import patch, MagicMock

# Mock all hardware modules before hardware.sensor is imported (not available on non-Pi)
for mod in ["board", "busio", "digitalio", "adafruit_adxl34x"]:
    sys.modules.setdefault(mod, MagicMock())

from core.events import BrewStart, BrewEnd  # noqa: E402
from config import ADXL_BREW_THRESHOLD      # noqa: E402

POLL = 0.02  # seconds per step in tests
HIGH = ADXL_BREW_THRESHOLD + 1.0   # clearly above threshold
LOW = 0.0                           # clearly below


def run_steps(magnitude_sequence):
    """
    Runs the sensor _step loop against a sequence of magnitude values.
    magnitude_sequence: list of (magnitude_value, duration_seconds) tuples
    Returns the list of events posted to the queue.
    """
    q = queue.Queue()
    readings = []
    for mag, dur in magnitude_sequence:
        readings.extend([mag] * max(1, int(dur / POLL)))

    t = [0.0]

    def fake_time():
        val = t[0]
        t[0] += POLL
        return val

    with patch("hardware.sensor.time") as mock_time:
        mock_time.sleep = MagicMock()
        mock_time.time.side_effect = fake_time

        from hardware.sensor import VibrationSensor
        s = VibrationSensor(q)

        # Run enough iterations to process the whole sequence plus silence window
        for mag in readings + [LOW] * 1000:
            s._step(magnitude=mag)

    events = []
    while not q.empty():
        events.append(q.get_nowait())
    return events


def test_long_vibration_posts_brew_start_then_end():
    # 30 seconds HIGH (> BREW_CONFIRM_WINDOW=2s), then 15s LOW (> BREW_END_SILENCE=10s)
    events = run_steps([(HIGH, 30), (LOW, 15)])
    types = [type(e).__name__ for e in events]
    assert "BrewStart" in types
    assert "BrewEnd" in types
    brew_end = next(e for e in events if isinstance(e, BrewEnd))
    assert brew_end.duration >= 28  # approximately 30s


def test_short_spike_does_not_post_brew_start():
    # 0.2s HIGH (< MIN_VIBRATION_PULSE=0.5s), then 15s LOW
    events = run_steps([(HIGH, 0.2), (LOW, 15)])
    assert not any(isinstance(e, BrewStart) for e in events)


def test_cleanup_vibration_below_confirm_window():
    # 1s HIGH (> MIN_VIBRATION_PULSE but < BREW_CONFIRM_WINDOW=2s), then 15s LOW
    events = run_steps([(HIGH, 1.0), (LOW, 15)])
    assert not any(isinstance(e, BrewStart) for e in events)
    # BrewEnd still fires (cleanup logged as noise by state machine)
    assert any(isinstance(e, BrewEnd) for e in events)


def test_brief_silence_does_not_end_brew():
    # 5s HIGH, 2s LOW (< BREW_END_SILENCE=10s), 5s HIGH, 15s LOW
    events = run_steps([(HIGH, 5), (LOW, 2), (HIGH, 5), (LOW, 15)])
    brew_ends = [e for e in events if isinstance(e, BrewEnd)]
    assert len(brew_ends) == 1  # only one brew end


def test_post_brew_spike_does_not_reset_timer():
    # 30s HIGH, 0.3s LOW, 0.3s HIGH spike, 15s LOW
    # The 0.3s spike is < MIN_VIBRATION_PULSE, so silence timer shouldn't reset
    events = run_steps([(HIGH, 30), (LOW, 0.3), (HIGH, 0.3), (LOW, 15)])
    brew_ends = [e for e in events if isinstance(e, BrewEnd)]
    assert len(brew_ends) == 1

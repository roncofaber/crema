import sys
import time
import queue
from unittest.mock import patch, MagicMock

# Mock RPi.GPIO before hardware.sensor is imported (not available on non-Pi)
_gpio_mock = MagicMock()
_gpio_mock.HIGH = 1
_gpio_mock.LOW  = 0
sys.modules.setdefault("RPi",     MagicMock())
sys.modules.setdefault("RPi.GPIO", _gpio_mock)

from core.events import BrewStart, BrewEnd  # noqa: E402


def run_sensor_loop(gpio_sequence, poll_interval=0.01):
    """
    Runs the sensor _step loop against a fake GPIO sequence.
    gpio_sequence: list of (value, duration_seconds) tuples.
    Returns the list of events posted to the queue.
    """
    q = queue.Queue()
    readings = []
    for value, duration in gpio_sequence:
        count = max(1, int(duration / poll_interval))
        readings.extend([value] * count)

    call_count = [0]

    def fake_input(pin):
        idx = call_count[0]
        call_count[0] += 1
        if idx < len(readings):
            return readings[idx]
        return 0  # LOW after sequence ends

    with patch("hardware.sensor.GPIO") as mock_gpio, \
         patch("hardware.sensor.time") as mock_time:

        mock_gpio.HIGH = 1
        mock_gpio.LOW  = 0
        mock_gpio.BCM  = 11
        mock_gpio.PUD_DOWN = 21
        mock_gpio.IN   = 1
        mock_gpio.input.side_effect = fake_input
        mock_time.sleep = MagicMock()

        # Replace time.time with a counter advancing by poll_interval per call
        t = [0.0]
        def fake_time():
            val = t[0]
            t[0] += poll_interval
            return val
        mock_time.time.side_effect = fake_time

        from hardware.sensor import VibrationSensor
        s = VibrationSensor(q)

        # Run enough iterations to process the whole sequence
        for _ in range(len(readings) + 1500):  # extra for silence window
            s._step()

    events = []
    while not q.empty():
        events.append(q.get_nowait())
    return events


def test_long_vibration_posts_brew_start_then_end():
    # 30 seconds HIGH (> BREW_CONFIRM_WINDOW=2s), then 15s LOW (> BREW_END_SILENCE=10s)
    events = run_sensor_loop([(1, 30), (0, 15)])
    types = [type(e).__name__ for e in events]
    assert "BrewStart" in types
    assert "BrewEnd" in types
    brew_end = next(e for e in events if isinstance(e, BrewEnd))
    assert brew_end.duration >= 28  # approximately 30s


def test_short_spike_does_not_post_brew_start():
    # 0.2s HIGH (< MIN_VIBRATION_PULSE=0.5s), then 15s LOW
    events = run_sensor_loop([(1, 0.2), (0, 15)])
    assert not any(isinstance(e, BrewStart) for e in events)


def test_cleanup_vibration_below_confirm_window():
    # 1s HIGH (> MIN_VIBRATION_PULSE but < BREW_CONFIRM_WINDOW=2s), then 15s LOW
    events = run_sensor_loop([(1, 1.0), (0, 15)])
    assert not any(isinstance(e, BrewStart) for e in events)
    # BrewEnd still fires (cleanup logged as noise by state machine)
    assert any(isinstance(e, BrewEnd) for e in events)


def test_brief_silence_does_not_end_brew():
    # 5s HIGH, 2s LOW (< BREW_END_SILENCE=10s), 5s HIGH, 15s LOW
    events = run_sensor_loop([(1, 5), (0, 2), (1, 5), (0, 15)])
    brew_ends = [e for e in events if isinstance(e, BrewEnd)]
    assert len(brew_ends) == 1  # only one brew end


def test_post_brew_spike_does_not_reset_timer():
    # 30s HIGH, 0.3s LOW, 0.3s HIGH spike, 15s LOW
    # The 0.3s spike is < MIN_VIBRATION_PULSE, so silence timer shouldn't reset
    events = run_sensor_loop([(1, 30), (0, 0.3), (1, 0.3), (0, 15)])
    brew_ends = [e for e in events if isinstance(e, BrewEnd)]
    assert len(brew_ends) == 1

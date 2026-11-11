import sys
import queue
from unittest.mock import patch, MagicMock

import pytest

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


def test_start_disables_sensor_when_i2c_bus_is_unavailable():
    from hardware.sensor import VibrationSensor

    sensor = VibrationSensor(queue.Queue())
    sys.modules["busio"].I2C.side_effect = OSError("I2C unavailable")
    try:
        assert sensor._connect() is False
    finally:
        sys.modules["busio"].I2C.side_effect = None
    assert sensor._accel is None
    assert sensor.status()["connected"] is False


def step_at(sensor, now, magnitude):
    with patch("hardware.sensor.time.time", return_value=now):
        if magnitude is None:
            with patch.object(sensor, "_magnitude", return_value=None):
                sensor._step()
        else:
            sensor._step(magnitude=magnitude)


def continuous_steps(sensor, start, end, magnitude):
    count = round((end - start) / POLL)
    for index in range(count + 1):
        step_at(sensor, start + index * POLL, magnitude)


def queued_events(q):
    events = []
    while not q.empty():
        events.append(q.get_nowait())
    return events


def test_failed_sample_resets_partial_confirmation():
    from hardware.sensor import VibrationSensor

    q = queue.Queue()
    sensor = VibrationSensor(q)
    continuous_steps(sensor, 0.0, 0.6, HIGH)
    step_at(sensor, 0.62, None)

    continuous_steps(sensor, 20.0, 21.98, HIGH)
    assert q.empty()

    step_at(sensor, 22.02, HIGH)
    assert [type(event) for event in queued_events(q)] == [BrewStart]


def test_outage_does_not_count_toward_end_silence():
    from hardware.sensor import VibrationSensor

    q = queue.Queue()
    sensor = VibrationSensor(q)
    continuous_steps(sensor, 0.0, 2.12, HIGH)
    assert isinstance(q.get_nowait(), BrewStart)
    step_at(sensor, 2.14, None)

    continuous_steps(sensor, 30.0, 39.92, LOW)
    assert q.empty()
    step_at(sensor, 40.0, LOW)

    event = q.get_nowait()
    assert isinstance(event, BrewEnd)
    assert event.started_at == 0.0
    assert event.ended_at == pytest.approx(2.12)


def test_late_sample_resets_partial_silence_debounce():
    from hardware.sensor import VibrationSensor

    q = queue.Queue()
    sensor = VibrationSensor(q)
    continuous_steps(sensor, 0.0, 2.12, HIGH)
    assert isinstance(q.get_nowait(), BrewStart)
    continuous_steps(sensor, 2.14, 5.0, LOW)

    step_at(sensor, 30.0, LOW)
    assert q.empty()
    continuous_steps(sensor, 30.02, 39.92, LOW)
    assert q.empty()
    step_at(sensor, 40.0, LOW)
    assert isinstance(q.get_nowait(), BrewEnd)


def test_stop_releases_i2c_resources():
    from hardware.sensor import VibrationSensor

    sensor = VibrationSensor(queue.Queue())
    accel = MagicMock()
    i2c = MagicMock()
    sensor._accel = accel
    sensor._i2c = i2c
    sensor._connected = True

    assert sensor.stop() is True
    accel.close.assert_called_once_with()
    i2c.deinit.assert_called_once_with()
    assert sensor._i2c is None
    assert sensor.status()["connected"] is False

# CREMA

Coffee Realtime Event Monitoring Application.

A Raspberry Pi kiosk that tracks who makes espresso, how many shots, and for how long. Users scan a QR code (email) before using the machine; a vibration sensor detects each brew cycle and logs it to SQLite.

## Hardware

- Raspberry Pi 4
- Waveshare ST7789 240x320 SPI LCD
- SW-420 vibration sensor (GPIO pin 17)
- USB HID QR code scanner (MINJCODE MJ2818A)

## Setup

```bash
pip install RPi.GPIO evdev adafruit-circuitpython-rgb-display Pillow
python main.py
```

The scanner is detected automatically by device name. To override, set `device_path` explicitly in `main.py`.

## Project layout

```
core/       events, state machine, database
hardware/   display, scanner, sensor drivers
tests/      pytest suite
config.py   all tuneable constants
main.py     entry point
```

## Configuration

All thresholds and timeouts are in `config.py`. Key values:

| Constant | Default | Description |
|---|---|---|
| `MIN_BREW_DURATION` | 20s | Below this, vibration logged as noise |
| `BREW_END_SILENCE` | 10s | Silence needed to end a brew cycle |
| `ARMED_TIMEOUT` | 120s | Time to wait for machine after scan |
| `SESSION_TIMEOUT` | 300s | Idle time before auto-logout |

# CREMA — Hardware

## Bill of materials

| Component | Model | Interface |
|---|---|---|
| SBC | Raspberry Pi 4 | — |
| Display | FREENOVE 5" MIPI DSI touchscreen (800×480, 5-point capacitive) | MIPI DSI ribbon |
| Accelerometer | AOICRIE GY-291 ADXL345 3-axis | SPI (CE1) |
| QR scanner | MINJCODE MJ2818A | USB HID |

## ADXL345 wiring (SPI)

| GY-291 pin | Pi pin | GPIO |
|---|---|---|
| VCC | 3.3 V (pin 1) | — |
| GND | GND (pin 6) | — |
| CS | CE1 (pin 26) | GPIO 7 |
| SDO/MISO | MISO (pin 21) | GPIO 9 |
| SDA/MOSI | MOSI (pin 19) | GPIO 10 |
| SCL/CLK | SCLK (pin 23) | GPIO 11 |

Enable SPI in `raspi-config` → Interface Options → SPI.

## Display

The FREENOVE 5" display connects via MIPI DSI ribbon cable — no driver setup needed; it is detected automatically by the Pi OS. Chromium is launched in kiosk mode on the DSI framebuffer by `crema-browser.service`.

## Sensor calibration

Run `crema sensor` with the espresso machine operating to observe live magnitude values:

```
ADXL345 — live readout  (Ctrl+C to quit)
───────────────────────────────────────────
  X: +0.123  Y: -9.812  Z: +1.045 m/s²  mag: 9.899  peak:12.341  [ACTIVE]  [████████░░░░░░░░░░░░░░░░░░░░]
```

Adjust `ADXL_BREW_THRESHOLD` in `config.py` so that:
- Machine idle → magnitude well below threshold (`[QUIET]`)
- Machine brewing → magnitude reliably above threshold (`[ACTIVE]`)

Typical range: 10–14 m/s². Default is 11.5.

## Sensor driver (`hardware/sensor.py`)

The `VibrationSensor` polls at `ADXL_SAMPLE_RATE` Hz (default 50 Hz) and applies three debounce gates before emitting events:

| Parameter | Default | Purpose |
|---|---|---|
| `MIN_VIBRATION_PULSE` | 0.5 s | Pulse must last this long to count |
| `BREW_CONFIRM_WINDOW` | 2 s | Sustained vibration before `BrewStart` fires |
| `BREW_END_SILENCE` | 10 s | Silence before `BrewEnd` fires |

The `_step(magnitude=None)` method accepts an optional magnitude value for unit testing without hardware.

## QR scanner (`hardware/scanner.py`)

Reads a USB HID device matching `SCANNER_DEVICE_NAME` (config). Each scan emits a `QRScanned(token=...)` event. Expected token format: `user@domain.com` (email). The local part before `@` becomes the display name.

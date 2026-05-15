# CREMA — Hardware

## Bill of materials

| Component | Model | Interface |
|---|---|---|
| SBC | Raspberry Pi 4 | — |
| Display | FREENOVE 5" MIPI DSI touchscreen (800×480, 5-point capacitive) | MIPI DSI ribbon |
| Accelerometer | AOICRIE GY-291 ADXL345 3-axis | I2C (0x53) |
| QR scanner | MINJCODE MJ2818A | USB HID |

## ADXL345 wiring (I2C)

| GY-291 pin | Pi pin | GPIO | Notes |
|---|---|---|---|
| GND | GND (pin 6) | — | |
| VCC | 3.3V (pin 1) | — | |
| CS  | 3.3V (pin 1) | — | must be HIGH to select I2C mode |
| SDO | GND (pin 6)  | — | sets I2C address to 0x53 |
| SDA | SDA (pin 3)  | GPIO 2 | |
| SCL | SCL (pin 5)  | GPIO 3 | |
| INT1 | — | not connected | |
| INT2 | — | not connected | |

Enable I2C in `raspi-config` → Interface Options → I2C.

Verify the chip is visible before running software:
```
i2cdetect -y 1   # should show 53 at row 50, col 3
```

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

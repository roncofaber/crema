# CREMA - Hardware

## Bill of materials

| Component | Model | Interface |
|---|---|---|
| SBC | Raspberry Pi 4 | - |
| Display | FREENOVE 5" MIPI DSI touchscreen (800×480, 5-point capacitive) | MIPI DSI ribbon |
| Accelerometer | AOICRIE GY-291 ADXL345 3-axis | I2C (0x53) |
| QR scanner | MINJCODE MJ2818A | USB HID |

## ADXL345 wiring (I2C)

| GY-291 pin | Pi pin | GPIO | Notes |
|---|---|---|---|
| GND | GND (pin 6) | - | |
| VCC | 3.3V (pin 1) | - | |
| CS  | 3.3V (pin 1) | - | must be HIGH to select I2C mode |
| SDO | GND (pin 6)  | - | sets I2C address to 0x53 |
| SDA | SDA (pin 3)  | GPIO 2 | |
| SCL | SCL (pin 5)  | GPIO 3 | |
| INT1 | - | not connected | |
| INT2 | - | not connected | |

Enable I2C in `raspi-config` → Interface Options → I2C.

Verify the chip is visible before running software:
```
i2cdetect -y 1   # should show 53 at row 50, col 3
```

## Display

The FREENOVE 5" display connects via MIPI DSI ribbon cable. No driver setup is needed; it is detected automatically by the Pi OS. Chromium is launched in kiosk mode on the DSI framebuffer by `crema-browser.service`.

## Sensor calibration

Run `crema sensor` with the espresso machine operating to observe live magnitude values:

```
ADXL345 - live readout  (Ctrl+C to quit)
───────────────────────────────────────────
  X: +0.123  Y: -9.812  Z: +1.045 m/s²  mag: 9.899  peak:12.341  [ACTIVE]  [████████░░░░░░░░░░░░░░░░░░░░]
```

Set `CREMA_ADXL_BREW_THRESHOLD` in the service environment so that:

- Machine idle: magnitude remains well below the threshold (`[QUIET]`).
- Machine brewing: magnitude remains reliably above the threshold (`[ACTIVE]`).

Typical range: 10–14 m/s². Default is 11.5.

## Sensor driver (`hardware/sensor.py`)

The `VibrationSensor` polls at `ADXL_SAMPLE_RATE` Hz (default 50 Hz) and applies three debounce gates before emitting events:

| Parameter | Default | Purpose |
|---|---|---|
| `MIN_VIBRATION_PULSE` | 0.5 s | Pulse must last this long to count |
| `BREW_CONFIRM_WINDOW` | 2 s | Sustained vibration before `BrewStart` fires |
| `BREW_END_SILENCE` | 10 s | Silence before `BrewEnd` fires |

The `_step(magnitude=None)` method accepts an optional magnitude value for unit testing without hardware.

The driver reconnects every five seconds after initialization or I2C read failures. Failed reads are skipped rather than treated as silence, preventing a transient disconnect from falsely ending a brew. Connection state, the last successful read, and the latest error are exposed through `/health` and the kiosk WebSocket.

## QR scanner (`hardware/scanner.py`)

Reads a USB HID device matching `SCANNER_DEVICE_NAME` (config). Each scan emits a `QRScanned(token=...)` event. Expected token format: `user@domain.com` (email). The local part before `@` becomes the display name.

The scanner exclusively grabs the matching input device and reconnects every five seconds if it is missing or disconnected. Override the device name with `CREMA_SCANNER_DEVICE_NAME`. Connection state, the last accepted scan, and the latest error are exposed through `/health` and the kiosk WebSocket.

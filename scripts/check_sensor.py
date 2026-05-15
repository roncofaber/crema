#!/usr/bin/env python3
"""Quick diagnostic: verify ADXL345 I2C communication and read live data."""
import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import board
    import busio
    import adafruit_adxl34x
except ImportError as e:
    print(f"Missing library: {e}")
    print("Run: pip install adafruit-circuitpython-adxl34x")
    sys.exit(1)

i2c = busio.I2C(board.SCL, board.SDA)

try:
    accel = adafruit_adxl34x.ADXL345(i2c)
except Exception as e:
    print(f"ADXL345 init failed: {e}")
    print()
    print("Check wiring:")
    print("  SDA → SDA (Pi pin 3)")
    print("  SCL → SCL (Pi pin 5)")
    print("  CS  → 3.3V (Pi pin 1)  ← selects I2C mode")
    print("  SDO → GND  (Pi pin 6)  ← sets address 0x53")
    print("  VCC → 3.3V (Pi pin 1)")
    print("  GND → GND  (Pi pin 6)")
    print()
    print("Also verify I2C is enabled: raspi-config → Interface Options → I2C")
    print("Check device visible: i2cdetect -y 1  (should show 0x53)")
    sys.exit(1)

x, y, z = accel.acceleration
mag = math.sqrt(x*x + y*y + z*z)
print("ADXL345: ✓ responding over I2C")
print(f"Accel:  X={x:+.3f}  Y={y:+.3f}  Z={z:+.3f}  mag={mag:.3f} m/s²")
print(f"        {'✓ looks good (gravity ~9.8)' if 8.0 < mag < 11.5 else '⚠ magnitude unexpected — check orientation or calibration'}")

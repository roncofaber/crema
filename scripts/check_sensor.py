#!/usr/bin/env python3
"""Quick diagnostic: verify ADXL345 SPI communication and read live data."""
import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import board
import busio
import digitalio
from hardware.adxl345 import ADXL345SPI

spi = busio.SPI(board.SCLK, MOSI=board.MOSI, MISO=board.MISO)
cs  = digitalio.DigitalInOut(board.CE1)
dev = ADXL345SPI(spi, cs)

devid = dev._read(0x00, 1)[0]
print(f"DEVID:  0x{devid:02x}  {'✓ OK' if devid == 0xe5 else '✗ FAIL — expected 0xe5'}")

if devid != 0xe5:
    print()
    print("SPI is not reaching the chip. Check:")
    print("  SDO  → MISO (Pi pin 21)")
    print("  SDA  → MOSI (Pi pin 19)")
    print("  SCL  → SCLK (Pi pin 23)")
    print("  CS   → CE1  (Pi pin 26)")
    print("  VCC  → 3.3V (Pi pin 1)")
    print("  GND  → GND  (Pi pin 6)")
    sys.exit(1)

x, y, z = dev.acceleration
mag = math.sqrt(x*x + y*y + z*z)
print(f"Accel:  X={x:+.3f}  Y={y:+.3f}  Z={z:+.3f}  mag={mag:.3f} m/s²")
print(f"        {'✓ looks good (gravity ~9.8)' if 8.0 < mag < 11.5 else '⚠ magnitude unexpected — check orientation or calibration'}")

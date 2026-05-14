#!/usr/bin/env python3
"""Raw spidev diagnostic — bypasses adafruit layer to isolate hardware vs library issues."""
import sys

try:
    import spidev
except ImportError:
    print("spidev not installed. Run: pip install spidev")
    sys.exit(1)

spi = spidev.SpiDev()
spi.open(0, 1)  # bus 0, CE1 (pin 26)
spi.max_speed_hz = 1_000_000
spi.mode = 3

result = spi.xfer2([0x80, 0x00])  # read DEVID register 0x00
devid = result[1]
spi.close()

print(f"DEVID: 0x{devid:02x}  {'✓ chip responding' if devid == 0xe5 else '✗ FAIL — expected 0xe5'}")

if devid == 0xe5:
    print("Raw SPI works — issue is in the adafruit SPIDevice layer.")
elif devid == 0x00:
    print("MISO is low — chip not driving data back. Check:")
    print("  SCL  → SCLK (Pi pin 23)  ← most likely off by one pin")
    print("  SDO  → MISO (Pi pin 21)")
    print("  VCC  → 3.3V (Pi pin  1)  ← measure with multimeter")
elif devid == 0xff:
    print("MISO is high — possible short to 3.3V or wiring issue.")
else:
    print(f"Unexpected value 0x{devid:02x} — partial SPI communication, check all data lines.")

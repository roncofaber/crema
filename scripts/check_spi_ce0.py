#!/usr/bin/env python3
"""Test ADXL345 using CE0 (pin 24) instead of CE1 (pin 26).
Move CS wire to pin 24 before running this."""
import spidev

print("Testing CE0 (pin 24) — make sure CS wire is on pin 24")
print()

for mode in [3, 0]:
    spi = spidev.SpiDev()
    spi.open(0, 0)  # CE0
    spi.max_speed_hz = 500_000
    spi.mode = mode
    result = spi.xfer2([0x80, 0x00])
    devid = result[1]
    ok = "✓  ← working!" if devid == 0xe5 else ""
    print(f"mode {mode}: 0x{devid:02x}  {ok}")
    spi.close()

print()
print("If still 0x00: likely bad solder joint on breakout board.")
print("If 0xe5: CE1 is faulty — keep CS on pin 24 and update config.")

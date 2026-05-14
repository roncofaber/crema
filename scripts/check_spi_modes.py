#!/usr/bin/env python3
"""Try all SPI modes to find which one the ADXL345 responds to."""
import spidev

for mode in [0, 1, 2, 3]:
    spi = spidev.SpiDev()
    spi.open(0, 1)  # bus 0, CE1
    spi.max_speed_hz = 500_000
    spi.mode = mode
    result = spi.xfer2([0x80, 0x00])  # read DEVID
    devid = result[1]
    ok = "✓  ← use this mode" if devid == 0xe5 else ""
    print(f"mode {mode}: 0x{devid:02x}  {ok}")
    spi.close()

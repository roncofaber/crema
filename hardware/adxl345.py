import struct

_REG_POWER_CTL   = 0x2D
_REG_DATA_FORMAT = 0x31
_REG_DATAX0      = 0x32

_SCALE = 0.004 * 9.80665  # LSB → m/s²  (full-resolution mode, any range)


class ADXL345SPI:
    """Minimal ADXL345 driver over SPI (4-wire, mode 3)."""

    def __init__(self, spi, cs, baudrate=5_000_000):
        from adafruit_bus_device.spi_device import SPIDevice
        self._dev = SPIDevice(spi, cs, baudrate=baudrate, polarity=1, phase=1)
        self._write(_REG_DATA_FORMAT, 0x0B)  # full resolution, ±16 g
        self._write(_REG_POWER_CTL,   0x08)  # start measuring

    def _write(self, reg, value):
        buf = bytearray([reg & 0x7F, value])
        with self._dev as spi:
            spi.write(buf)

    def _read(self, reg, length):
        out = bytearray(length + 1)
        out[0] = reg | 0x80 | (0x40 if length > 1 else 0x00)
        inp = bytearray(length + 1)
        with self._dev as spi:
            spi.write_readinto(out, inp)
        return inp[1:]

    @property
    def acceleration(self):
        data = self._read(_REG_DATAX0, 6)
        x, y, z = struct.unpack_from("<hhh", data)
        return x * _SCALE, y * _SCALE, z * _SCALE

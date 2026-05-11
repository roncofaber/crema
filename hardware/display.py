import board
import busio
import digitalio
from adafruit_rgb_display import st7789
from PIL import Image, ImageDraw, ImageFont
from config import DISPLAY_WIDTH, DISPLAY_HEIGHT, FONT_PATH, FONT_SIZE_SMALL, FONT_SIZE_LARGE  # noqa: E402


class Display:
    def __init__(self):
        cs  = digitalio.DigitalInOut(board.CE0)
        dc  = digitalio.DigitalInOut(board.D25)
        rst = digitalio.DigitalInOut(board.D27)
        bl  = digitalio.DigitalInOut(board.D18)

        bl.direction = digitalio.Direction.OUTPUT
        bl.value = True

        spi = busio.SPI(clock=board.SCLK, MOSI=board.MOSI)
        self.disp = st7789.ST7789(spi, cs=cs, dc=dc, rst=rst,
                                  width=240, height=320,
                                  baudrate=24000000)

        self.font_small = ImageFont.truetype(FONT_PATH, FONT_SIZE_SMALL)
        self.font_large = ImageFont.truetype(FONT_PATH, FONT_SIZE_LARGE)

    def _new_canvas(self, bg=(0, 0, 0)) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        img  = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=bg)
        draw = ImageDraw.Draw(img)
        return img, draw

    def _send(self, img: Image.Image):
        self.disp.image(img.rotate(90, expand=True))

    # -- screens --

    def show_idle(self):
        raise NotImplementedError

    def show_armed(self, user_name: str):
        raise NotImplementedError

    def show_brewing(self, user_name: str, brew_count: int, elapsed: float):
        raise NotImplementedError

    def show_anon_brewing(self, elapsed: float):
        raise NotImplementedError

    def show_summary(self, user_name: str, brew_count: int, total_time: float):
        raise NotImplementedError

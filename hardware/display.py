import board
import busio
import digitalio
from adafruit_rgb_display import st7789
from PIL import Image, ImageDraw, ImageFont
from config import DISPLAY_WIDTH, DISPLAY_HEIGHT, FONT_PATH, FONT_SIZE_SMALL, FONT_SIZE_LARGE

_BLACK = (0, 0, 0)
_WHITE = (255, 255, 255)
_GREY  = (160, 160, 160)


class Display:
    def __init__(self):
        cs  = digitalio.DigitalInOut(board.CE0)
        dc  = digitalio.DigitalInOut(board.D25)
        rst = digitalio.DigitalInOut(board.D27)
        bl  = digitalio.DigitalInOut(board.D18)

        bl.direction = digitalio.Direction.OUTPUT
        bl.value = True

        spi = busio.SPI(clock=board.SCLK, MOSI=board.MOSI)
        self.disp = st7789.ST7789(
            spi, cs=cs, dc=dc, rst=rst,
            width=240, height=320,
            baudrate=24000000,
        )

        self._font_s = ImageFont.truetype(FONT_PATH, FONT_SIZE_SMALL)
        self._font_l = ImageFont.truetype(FONT_PATH, FONT_SIZE_LARGE)
        self._logo   = self._load_logo()

    def _load_logo(self):
        try:
            img = Image.open("assets/pxArt.png").convert("RGBA")
            return img.resize((80, 80))
        except FileNotFoundError:
            return None

    def _new_canvas(self, bg=_BLACK):
        img  = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=bg)
        draw = ImageDraw.Draw(img)
        return img, draw

    def _send(self, img: Image.Image):
        self.disp.image(img.rotate(90, expand=True))

    def _center_text(self, draw, y, text, font, color=_WHITE):
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        draw.text(((DISPLAY_WIDTH - w) // 2, y), text, fill=color, font=font)

    def _fmt_time(self, seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s:02d}s" if m else f"{s}s"

    def show_idle(self):
        img, draw = self._new_canvas()
        if self._logo:
            x = (DISPLAY_WIDTH - self._logo.width) // 2
            img.paste(self._logo, (x, 60), mask=self._logo)
        self._center_text(draw, 170, "Scan to start", self._font_s, _GREY)
        self._send(img)

    def show_armed(self, user_name: str, brew_count: int = 0):
        img, draw = self._new_canvas()
        self._center_text(draw, 70, f"Hi, {user_name}!", self._font_l)
        self._center_text(draw, 130, "Start the machine", self._font_s, _GREY)
        if brew_count > 0:
            self._center_text(draw, 170, f"{brew_count} coffee{'s' if brew_count != 1 else ''} so far", self._font_s, _GREY)
        self._send(img)

    def show_brewing(self, user_name: str, brew_count: int, elapsed: float):
        img, draw = self._new_canvas()
        draw.text((10, 10), user_name, fill=_GREY, font=self._font_s)
        count_str = f"x{brew_count + 1}"
        self._center_text(draw, 80, count_str, self._font_l)
        self._center_text(draw, 190, self._fmt_time(elapsed), self._font_s, _GREY)
        self._send(img)

    def show_anon_brewing(self, elapsed: float):
        img, draw = self._new_canvas()
        draw.text((10, 10), "Anonymous", fill=_GREY, font=self._font_s)
        self._center_text(draw, 80, "x1", self._font_l)
        self._center_text(draw, 190, self._fmt_time(elapsed), self._font_s, _GREY)
        self._send(img)

    def show_summary(self, user_name: str, brew_count: int, total_time: float):
        img, draw = self._new_canvas()
        self._center_text(draw, 60, f"See ya, {user_name}!", self._font_l)
        label = f"{brew_count} coffee{'s' if brew_count != 1 else ''}"
        self._center_text(draw, 140, label, self._font_s)
        self._center_text(draw, 175, self._fmt_time(total_time) + " total", self._font_s, _GREY)
        self._send(img)

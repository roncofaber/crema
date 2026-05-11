import board
import busio
import digitalio
from adafruit_rgb_display import st7789
from PIL import Image, ImageDraw, ImageFont
from config import DISPLAY_WIDTH, DISPLAY_HEIGHT, FONT_PATH

# Warm espresso palette — mirrors the web dashboard theme
_BG       = ( 26,  15,   8)   # deep espresso
_SURFACE  = ( 48,  29,  12)   # dark roast surface
_AMBER    = (184, 112,  24)   # crema gold
_AMBER_DK = (110,  65,  14)   # deeper amber (accent bars when idle)
_CREAM    = (236, 224, 209)   # warm cream
_MUTED    = (150, 114,  89)   # warm muted
_FAINT    = ( 78,  58,  40)   # very faint

_BREW_MAX_S = 180  # progress bar fills over this many seconds (~3 cups)


class Display:
    def __init__(self):
        cs  = digitalio.DigitalInOut(board.CE0)
        dc  = digitalio.DigitalInOut(board.D25)
        rst = digitalio.DigitalInOut(board.D27)
        bl  = digitalio.DigitalInOut(board.D18)

        bl.direction = digitalio.Direction.OUTPUT
        bl.value = True

        spi = busio.SPI(clock=board.SCLK, MOSI=board.MOSI)
        # Driver takes physical portrait dimensions (240×320); the canvas is
        # drawn landscape (320×240) and rotated 90° in _send to fit.
        self.disp = st7789.ST7789(
            spi, cs=cs, dc=dc, rst=rst,
            width=240, height=320,
            baudrate=24000000,
        )

        self._f12 = ImageFont.truetype(FONT_PATH, 12)
        self._f16 = ImageFont.truetype(FONT_PATH, 16)
        self._f22 = ImageFont.truetype(FONT_PATH, 22)
        self._f32 = ImageFont.truetype(FONT_PATH, 32)
        self._f52 = ImageFont.truetype(FONT_PATH, 52)
        self._logo = self._load_logo()

    def _load_logo(self):
        try:
            img = Image.open("assets/pxArt.png").convert("RGBA")
            return img.resize((80, 80))
        except FileNotFoundError:
            return None

    def _new_canvas(self, bg=_BG):
        img  = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=bg)
        draw = ImageDraw.Draw(img)
        return img, draw

    def _send(self, img: Image.Image):
        self.disp.image(img.rotate(90, expand=True))

    def _cx(self, draw, y, text, font, color=_CREAM, pad=12):
        text = self._truncate(draw, text, font, DISPLAY_WIDTH - pad * 2)
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        draw.text((max(pad, (DISPLAY_WIDTH - w) // 2), y), text, fill=color, font=font)

    def _rule(self, draw, y, color=_FAINT, pad=28):
        draw.line([(pad, y), (DISPLAY_WIDTH - pad, y)], fill=color, width=1)

    def _accent_bars(self, draw, color=_AMBER):
        draw.rectangle([0, 0, DISPLAY_WIDTH, 5], fill=color)
        draw.rectangle([0, DISPLAY_HEIGHT - 5, DISPLAY_WIDTH, DISPLAY_HEIGHT], fill=color)

    def _bottom_strip(self, draw, text, font=None, color=_MUTED):
        font = font or self._f16
        draw.rectangle([0, DISPLAY_HEIGHT - 52, DISPLAY_WIDTH, DISPLAY_HEIGHT - 5], fill=_SURFACE)
        self._cx(draw, DISPLAY_HEIGHT - 42, text, font, color)

    def _progress_bar(self, draw, y, elapsed, max_s=_BREW_MAX_S, h=8, pad=24):
        w = DISPLAY_WIDTH - pad * 2
        fill = min(1.0, elapsed / max_s)
        draw.rectangle([pad, y, pad + w, y + h], fill=_FAINT)
        if fill > 0:
            draw.rectangle([pad, y, pad + max(h, int(w * fill)), y + h], fill=_AMBER)

    def _fmt_time(self, seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s:02d}s" if m else f"{s}s"

    def _truncate(self, draw, text, font, max_w):
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_w:
            return text
        while len(text) > 1:
            text = text[:-1]
            bbox = draw.textbbox((0, 0), text + "…", font=font)
            if bbox[2] - bbox[0] <= max_w:
                return text + "…"
        return text

    # ------------------------------------------------------------------ states

    def show_idle(self):
        img, draw = self._new_canvas()
        self._accent_bars(draw, _AMBER_DK)

        if self._logo:
            x = (DISPLAY_WIDTH - self._logo.width) // 2
            img.paste(self._logo, (x, 20), mask=self._logo)

        self._cx(draw, 112, "CAFFÈ CABRINI", self._f16, _CREAM)
        self._rule(draw, 136, _FAINT, pad=40)
        self._cx(draw, 143, "C R E M A", self._f12, _AMBER)

        self._bottom_strip(draw, "scan to brew")
        self._send(img)

    def show_armed(self, user_name: str, brew_count: int = 0):
        img, draw = self._new_canvas()
        self._accent_bars(draw)

        self._cx(draw, 56, "CIAO,", self._f16, _MUTED)
        name = self._truncate(draw, user_name.upper(), self._f32, DISPLAY_WIDTH - 24)
        self._cx(draw, 82, name, self._f32, _CREAM)

        self._rule(draw, 136, _FAINT)
        self._cx(draw, 150, "Start the machine", self._f16, _MUTED)
        if brew_count > 0:
            label = f"{brew_count} coffee{'s' if brew_count != 1 else ''} so far"
            self._bottom_strip(draw, label)
        else:
            self._cx(draw, 176, "when ready", self._f16, _FAINT)

        self._send(img)

    def show_brewing(self, user_name: str, brew_count: int, elapsed: float):
        img, draw = self._new_canvas()

        # Header strip with user name
        draw.rectangle([0, 0, DISPLAY_WIDTH, 38], fill=_SURFACE)
        name = self._truncate(draw, user_name.upper(), self._f22, DISPLAY_WIDTH - 16)
        self._cx(draw, 7, name, self._f22, _MUTED)

        # Brew counter — the hero element
        self._cx(draw, 72, f"\xd7{brew_count + 1}", self._f52, _CREAM)

        # Elapsed time
        self._cx(draw, 166, self._fmt_time(elapsed), self._f32, _AMBER)

        # Progress bar
        self._progress_bar(draw, 220, elapsed)

        # Bottom accent
        draw.rectangle([0, DISPLAY_HEIGHT - 5, DISPLAY_WIDTH, DISPLAY_HEIGHT], fill=_AMBER)

        self._send(img)

    def show_anon_brewing(self, elapsed: float):
        img, draw = self._new_canvas()

        draw.rectangle([0, 0, DISPLAY_WIDTH, 38], fill=_SURFACE)
        self._cx(draw, 7, "ANONYMOUS", self._f22, _FAINT)

        self._cx(draw, 72, "\xd71", self._f52, _CREAM)
        self._cx(draw, 166, self._fmt_time(elapsed), self._f32, _AMBER)
        self._progress_bar(draw, 220, elapsed)
        draw.rectangle([0, DISPLAY_HEIGHT - 5, DISPLAY_WIDTH, DISPLAY_HEIGHT], fill=_AMBER_DK)

        self._send(img)

    def show_summary(self, user_name: str, brew_count: int, total_time: float):
        img, draw = self._new_canvas()
        self._accent_bars(draw)

        self._cx(draw, 52, "GRAZIE,", self._f22, _AMBER)
        name = self._truncate(draw, user_name.upper(), self._f32, DISPLAY_WIDTH - 24)
        self._cx(draw, 86, name, self._f32, _CREAM)

        self._rule(draw, 136, _FAINT)

        label = f"{brew_count} coffee{'s' if brew_count != 1 else ''}"
        self._cx(draw, 150, label, self._f22, _MUTED)
        self._cx(draw, 184, self._fmt_time(total_time) + " total", self._f22, _FAINT)

        self._bottom_strip(draw, "alla prossima!")
        self._send(img)

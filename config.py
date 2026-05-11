# GPIO pins
VIBRATION_PIN = 17          # SW-420 signal pin

# Vibration thresholds
MIN_BREW_DURATION   = 20    # seconds — below this is noise/cleanup
BREW_END_SILENCE    = 10    # seconds of no vibration before brew is considered done

# Session timeouts
ARMED_TIMEOUT       = 120   # seconds to wait for machine after QR scan
SESSION_TIMEOUT     = 300   # seconds of inactivity before auto-logout

# Display
DISPLAY_WIDTH       = 320
DISPLAY_HEIGHT      = 240
FONT_PATH           = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_SIZE_SMALL     = 20
FONT_SIZE_LARGE     = 40

# Database
DB_PATH = "data/espresso.db"

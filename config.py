# GPIO pins
VIBRATION_PIN = 17          # SW-420 signal pin

# Vibration thresholds
MIN_BREW_DURATION    = 20   # seconds — below this → kind='noise'
BREW_END_SILENCE     = 10   # seconds of silence before BrewEnd fires
MIN_VIBRATION_PULSE  = 0.5  # seconds — minimum HIGH pulse to reset silence timer
BREW_CONFIRM_WINDOW  = 2    # seconds of sustained vibration before BrewStart fires
SENSOR_POLL_INTERVAL = 0.01 # seconds between GPIO reads (10 ms)

# Session timeouts
ARMED_TIMEOUT   = 120   # seconds waiting for machine after scan (no brew yet)
SESSION_TIMEOUT = 300   # seconds of inactivity after last brew before auto-logout
SUMMARY_DURATION = 5    # seconds to display summary screen before returning to idle

# Display
DISPLAY_WIDTH    = 320
DISPLAY_HEIGHT   = 240
FONT_PATH        = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_SIZE_SMALL  = 20
FONT_SIZE_LARGE  = 40

# Database
DB_PATH = "data/espresso.db"

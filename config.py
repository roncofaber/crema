# ADXL345 accelerometer
ADXL_BREW_THRESHOLD = 11.5   # m/s² magnitude — tune with `crema sensor`
ADXL_SAMPLE_RATE    = 50     # Hz polling rate
ADXL_RANGE          = 4      # ±4g range setting

# Vibration thresholds
MIN_BREW_DURATION    = 10   # seconds — below this → kind='noise'
BREW_END_SILENCE     = 10   # seconds of silence before BrewEnd fires
MIN_VIBRATION_PULSE  = 0.5  # seconds — minimum HIGH pulse to reset silence timer
BREW_CONFIRM_WINDOW  = 2    # seconds of sustained vibration before BrewStart fires

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

# Hardware
SCANNER_DEVICE_NAME = "MINJCODE MINJCODE MJ2818A"

# Database
import os as _os
DB_PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "data", "espresso.db")

import os
from pathlib import Path


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


_ROOT = Path(__file__).resolve().parent

# ADXL345 accelerometer
ADXL_BREW_THRESHOLD = _float("CREMA_ADXL_BREW_THRESHOLD", 11.5)
ADXL_SAMPLE_RATE = _int("CREMA_ADXL_SAMPLE_RATE", 50)

# Vibration thresholds
MIN_BREW_DURATION = _float("CREMA_MIN_BREW_DURATION", 10)
BREW_END_SILENCE = _float("CREMA_BREW_END_SILENCE", 10)
MIN_VIBRATION_PULSE = _float("CREMA_MIN_VIBRATION_PULSE", 0.5)
BREW_CONFIRM_WINDOW = _float("CREMA_BREW_CONFIRM_WINDOW", 2)

# Session timeouts
ARMED_TIMEOUT = _float("CREMA_ARMED_TIMEOUT", 120)
SESSION_TIMEOUT = _float("CREMA_SESSION_TIMEOUT", 300)
SUMMARY_DURATION = _float("CREMA_SUMMARY_DURATION", 5)

# Hardware
SCANNER_DEVICE_NAME = os.getenv("CREMA_SCANNER_DEVICE_NAME", "MINJCODE MINJCODE MJ2818A")

# Database
DB_PATH = os.getenv("CREMA_DB_PATH", str(_ROOT / "data" / "espresso.db"))
BACKUP_DIR = os.getenv("CREMA_BACKUP_DIR", str(_ROOT / "data" / "backups"))

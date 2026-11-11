import math
import os
from pathlib import Path


def _float(
    name: str,
    default: float,
    *,
    minimum: float = 0.0,
    exclusive_minimum: bool = False,
) -> float:
    raw = os.getenv(name, default)
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number; got {raw!r}") from exc
    invalid_range = value <= minimum if exclusive_minimum else value < minimum
    if not math.isfinite(value) or invalid_range:
        operator = ">" if exclusive_minimum else ">="
        raise ValueError(
            f"{name} must be a finite number {operator} {minimum}; got {raw!r}"
        )
    return value


def _int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name, default)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer >= {minimum}; got {raw!r}") from exc
    if value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}; got {raw!r}")
    return value


_ROOT = Path(__file__).resolve().parent

# ADXL345 accelerometer
ADXL_BREW_THRESHOLD = _float("CREMA_ADXL_BREW_THRESHOLD", 11.5, exclusive_minimum=True)
ADXL_SAMPLE_RATE = _int("CREMA_ADXL_SAMPLE_RATE", 50, minimum=1)

# Vibration thresholds
MIN_BREW_DURATION = _float("CREMA_MIN_BREW_DURATION", 10)
BREW_END_SILENCE = _float("CREMA_BREW_END_SILENCE", 10, exclusive_minimum=True)
MIN_VIBRATION_PULSE = _float("CREMA_MIN_VIBRATION_PULSE", 0.5, exclusive_minimum=True)
BREW_CONFIRM_WINDOW = _float("CREMA_BREW_CONFIRM_WINDOW", 2, exclusive_minimum=True)

# Session timeouts
ARMED_TIMEOUT = _float("CREMA_ARMED_TIMEOUT", 120, exclusive_minimum=True)
SESSION_TIMEOUT = _float("CREMA_SESSION_TIMEOUT", 300, exclusive_minimum=True)
SUMMARY_DURATION = _float("CREMA_SUMMARY_DURATION", 5)

# Hardware
SCANNER_DEVICE_NAME = os.getenv("CREMA_SCANNER_DEVICE_NAME", "MINJCODE MINJCODE MJ2818A")

# Database
DB_PATH = os.getenv("CREMA_DB_PATH", str(_ROOT / "data" / "espresso.db"))
BACKUP_DIR = os.getenv("CREMA_BACKUP_DIR", str(_ROOT / "data" / "backups"))
BACKUP_RETENTION_COUNT = _int("CREMA_BACKUP_RETENTION_COUNT", 14, minimum=1)
BACKUP_RETENTION_DAYS = _int("CREMA_BACKUP_RETENTION_DAYS", 0)

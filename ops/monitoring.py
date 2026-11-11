import argparse
from datetime import datetime, timezone
import json
import math
import os
import shlex
import subprocess
import sys
import threading
import time
from urllib.request import Request, urlopen


_METRIC_NAMES = {
    "crema_up": "api_up",
    "crema_kiosk_running": "kiosk_running",
    "crema_kiosk_scanner_connected": "scanner_connected",
    "crema_kiosk_sensor_connected": "sensor_connected",
    "crema_kiosk_sensor_stale_seconds": "sensor_stale_seconds",
    "crema_kiosk_websocket_clients": "websocket_clients",
}


def parse_metrics(text: str) -> dict[str, int | float]:
    values = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        name, separator, raw_value = line.partition(" ")
        if not separator or name not in _METRIC_NAMES:
            continue
        try:
            value = float(raw_value)
        except ValueError:
            continue
        if math.isfinite(value):
            values[_METRIC_NAMES[name]] = value
    return values


def unit_path(unit: str) -> str:
    escaped = "".join(
        character if "a" <= character <= "z" or "A" <= character <= "Z" or "0" <= character <= "9"
        else f"_{ord(character):02x}"
        for character in unit
    )
    return f"/org/freedesktop/systemd1/unit/{escaped}"


def probe_unit(unit: str, *, timeout: float = 5) -> dict[str, str]:
    result = subprocess.run(
        [
            "busctl", "--system", "get-property", "org.freedesktop.systemd1",
            unit_path(unit), "org.freedesktop.systemd1.Unit", "ActiveState", "SubState",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"busctl exited with status {result.returncode}")
    fields = shlex.split(result.stdout)
    values = fields[1::2]
    if len(values) != 2:
        raise RuntimeError("unexpected busctl property response")
    return {"active_state": values[0], "sub_state": values[1]}


def sample(url: str, *, token: str = "", unit: str | None = "crema-kiosk.service", timeout: float = 5) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "event": "monitoring_sample",
    }
    errors = []
    try:
        with urlopen(Request(url, headers=headers), timeout=timeout) as response:
            record.update(parse_metrics(response.read().decode("utf-8")))
            record["http_status"] = response.status
    except Exception as exc:
        errors.append(f"metrics: {type(exc).__name__}: {exc}")
    if unit:
        try:
            record["service"] = {"unit": unit, **probe_unit(unit, timeout=timeout)}
        except Exception as exc:
            errors.append(f"dbus: {type(exc).__name__}: {exc}")
    record["status"] = "error" if "api_up" not in record else "degraded" if errors else "ok"
    if errors:
        record["errors"] = errors
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Passively record CREMA Prometheus and systemd D-Bus status as JSONL.")
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/metrics")
    parser.add_argument("--interval", type=float, default=60)
    parser.add_argument("--output", help="Append JSONL to this file instead of stdout.")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--no-service", action="store_true", help="Do not query systemd over D-Bus.")
    parser.add_argument("--service", default="crema-kiosk.service")
    args = parser.parse_args(argv)
    if not math.isfinite(args.interval) or args.interval <= 0:
        parser.error("--interval must be a finite positive number")
    destination = open(args.output, "a", encoding="utf-8") if args.output else sys.stdout
    stopped = threading.Event()
    try:
        while True:
            record = sample(
                args.url,
                token=os.getenv("CREMA_API_TOKEN", ""),
                unit=None if args.no_service else args.service,
            )
            destination.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            destination.flush()
            if args.once or stopped.wait(args.interval):
                break
    except KeyboardInterrupt:
        pass
    finally:
        if args.output:
            destination.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

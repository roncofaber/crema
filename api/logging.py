from datetime import datetime, timezone
import json
import logging
import os
import sys


_RESERVED = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", "log"),
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key != "event" and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))


def _options() -> tuple[int, str, str | None]:
    level_name = os.getenv("CREMA_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        raise ValueError("CREMA_LOG_LEVEL must be a standard logging level")
    output = os.getenv("CREMA_LOG_FORMAT", "text").strip().lower()
    if output not in {"text", "jsonl"}:
        raise ValueError("CREMA_LOG_FORMAT must be 'text' or 'jsonl'")
    return level, output, os.getenv("CREMA_LOG_FILE")


def configure_logging() -> None:
    level, output, log_file = _options()
    formatter = JsonFormatter() if output == "jsonl" else logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    for handler in handlers:
        handler.setFormatter(formatter)
    logging.basicConfig(level=level, handlers=handlers, force=True)


def uvicorn_log_config() -> dict[str, object]:
    level, output, log_file = _options()
    application_formatter: dict[str, object] = {"()": "api.logging.JsonFormatter"}
    if output == "text":
        application_formatter = {
            "()": "logging.Formatter",
            "format": "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S%z",
        }
    handlers: dict[str, object] = {
        "application_console": {
            "class": "logging.StreamHandler",
            "formatter": "application",
            "stream": "ext://sys.stdout",
        },
    }
    root_handlers = ["application_console"]
    if log_file:
        handlers["application_file"] = {
            "class": "logging.FileHandler",
            "formatter": "application",
            "filename": log_file,
            "encoding": "utf-8",
        }
        root_handlers.append("application_file")
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {"()": "uvicorn.logging.DefaultFormatter", "use_colors": False},
            "access": {"()": "uvicorn.logging.AccessFormatter", "use_colors": False},
            "application": application_formatter,
        },
        "handlers": handlers,
        "root": {"level": level, "handlers": root_handlers},
        "loggers": {
            "uvicorn": {"handlers": [], "propagate": True},
            "uvicorn.error": {"handlers": [], "propagate": True},
            "uvicorn.access": {"handlers": [], "propagate": True},
            "uvicorn.asgi": {"handlers": [], "propagate": True},
        },
    }

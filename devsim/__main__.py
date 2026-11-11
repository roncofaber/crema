import argparse
import os
from pathlib import Path
import tempfile


def main():
    parser = argparse.ArgumentParser(description="Run CREMA with its isolated development simulator.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--reset", action="store_true", help="Reset the default simulator database before startup.")
    args = parser.parse_args()

    default_directory = Path(tempfile.gettempdir()) / "crema-simulator"
    configured_database = os.getenv("CREMA_DB_PATH")
    if args.reset and configured_database:
        parser.error("--reset only supports the default simulator database; remove a custom test database explicitly")

    database = Path(configured_database or default_directory / "espresso.db")
    os.environ["CREMA_DB_PATH"] = str(database)
    os.environ.setdefault("CREMA_BACKUP_DIR", str(default_directory / "backups"))
    os.environ["CREMA_DEV_SIMULATOR"] = "1"
    os.environ["CREMA_START_HARDWARE"] = "0"

    if args.reset:
        for suffix in ("", "-wal", "-shm", ".lock"):
            Path(f"{database}{suffix}").unlink(missing_ok=True)
    database.parent.mkdir(parents=True, exist_ok=True)

    from api.auth import require_safe_binding
    from api.logging import configure_logging, uvicorn_log_config
    import uvicorn

    configure_logging()
    require_safe_binding(args.host)
    uvicorn.run(
        "api.main:app", host=args.host, port=args.port, reload=args.reload,
        log_config=uvicorn_log_config(),
    )


if __name__ == "__main__":
    main()

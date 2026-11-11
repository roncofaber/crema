import os
import uvicorn


def main():
    from api.auth import require_safe_binding
    from api.logging import configure_logging, uvicorn_log_config

    configure_logging()
    host = os.getenv("CREMA_HOST", "127.0.0.1")
    require_safe_binding(host)
    os.environ["CREMA_START_HARDWARE"] = "1"
    uvicorn.run(
        "api.main:app", host=host, port=8000, log_level="warning",
        log_config=uvicorn_log_config(),
    )


if __name__ == "__main__":
    main()

import logging
import os
import uvicorn

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def main():
    os.environ["CREMA_START_HARDWARE"] = "1"
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, log_level="warning")


if __name__ == "__main__":
    main()

import logging
import uvicorn
import core.db as db
import core.kiosk as kiosk
from api.main import app  # noqa: F401 — imported for side-effects (route registration)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def main():
    db.init_db()
    kiosk.start()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")


if __name__ == "__main__":
    main()

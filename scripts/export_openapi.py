import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "api" / "openapi.json"


def main():
    parser = argparse.ArgumentParser(description="Export the production CREMA OpenAPI schema.")
    parser.add_argument("--check", action="store_true", help="Fail if the committed schema is stale.")
    args = parser.parse_args()

    os.environ.pop("CREMA_DEV_SIMULATOR", None)
    os.environ.pop("CREMA_START_HARDWARE", None)
    sys.path.insert(0, str(ROOT))

    from api.main import app

    rendered = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    if args.check:
        if not SCHEMA_PATH.exists() or SCHEMA_PATH.read_text() != rendered:
            raise SystemExit("api/openapi.json is stale; run python3 scripts/export_openapi.py")
        print("OpenAPI schema is up to date.")
        return
    SCHEMA_PATH.write_text(rendered)
    print(f"Wrote {SCHEMA_PATH}")


if __name__ == "__main__":
    main()

"""Import the NASA OSD-575 CMP CSV into the SENTINEL SQLite database.

Usage (from Backend/):  .venv/Scripts/python scripts/import_nasa.py [path/to/csv]
Re-running with the same file is safe: duplicate ingestion is skipped.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings  # noqa: E402
from app.db import Base, make_engine, make_session_factory  # noqa: E402
from app.importers.osd575 import import_csv, import_if_available  # noqa: E402


def main() -> int:
    settings = Settings()
    engine = make_engine(settings.db_url)
    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as db:
        result = import_csv(db, settings, Path(sys.argv[1])) if len(sys.argv) > 1 else import_if_available(db, settings)
    print(json.dumps(asdict(result), indent=2))
    return 0 if result.outcome in ("imported", "skipped_duplicate") else 1


if __name__ == "__main__":
    raise SystemExit(main())

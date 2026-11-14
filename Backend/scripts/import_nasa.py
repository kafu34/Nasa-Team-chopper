"""Import NASA research files into the SENTINEL SQLite database.

Usage (from Backend/):
  .venv/Scripts/python scripts/import_nasa.py                 # OSD-575 CMP CSV + OSD-195 / OSD-546 processed files
  .venv/Scripts/python scripts/import_nasa.py path/to/csv     # a specific OSD-575 CMP CSV
  .venv/Scripts/python scripts/import_nasa.py --dataset OSD-195
Re-running with the same files is safe: duplicate ingestion is skipped. Missing files are reported, never invented.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings  # noqa: E402
from app.db import Base, make_engine, make_session_factory  # noqa: E402
from app.importers import expression, osd656, radlab  # noqa: E402
from app.importers.osd575 import import_csv, import_if_available  # noqa: E402

OK = ("imported", "skipped_duplicate")


def main() -> int:
    settings = Settings()
    engine = make_engine(settings.db_url)
    Base.metadata.create_all(engine)
    args = sys.argv[1:]
    report: dict[str, list[dict]] = {}
    with make_session_factory(engine)() as db:
        if "--dataset" in args:
            dataset_id = args[args.index("--dataset") + 1]
            if dataset_id == "OSD-575":
                report["OSD-575"] = [asdict(import_if_available(db, settings))]
            elif dataset_id == "OSD-656":
                report["OSD-656"] = [asdict(osd656.import_if_available(db, settings))]
            elif dataset_id == "NASA-RADLAB":
                report["NASA-RADLAB"] = [asdict(radlab.import_if_available(db, settings))]
            else:
                report[dataset_id] = [asdict(r) for r in expression.import_dataset(db, settings, dataset_id)]
        elif args:
            report["OSD-575"] = [asdict(import_csv(db, settings, Path(args[0])))]
        else:
            report["OSD-575"] = [asdict(import_if_available(db, settings))]
            report["OSD-656"] = [asdict(osd656.import_if_available(db, settings))]
            report["NASA-RADLAB"] = [asdict(radlab.import_if_available(db, settings))]
            for dataset_id, results in expression.import_all_available(db, settings).items():
                report[dataset_id] = [asdict(r) for r in results]
    print(json.dumps(report, indent=2))
    # Exit 1 only when a present file failed to import; missing optional (P1) files are reported, not errors.
    failed = [r for rs in report.values() for r in rs if r["outcome"] == "failed"]
    p0_missing = report.get("OSD-575", [{"outcome": "imported"}])[0]["outcome"] not in OK
    return 1 if failed or p0_missing else 0


if __name__ == "__main__":
    raise SystemExit(main())

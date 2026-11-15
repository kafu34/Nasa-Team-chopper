"""Run a movement scenario against an isolated temporary database and print estimate vs ground truth.

Usage: .venv/Scripts/python scripts/simulate_movement.py [SCENARIO_ID ...]
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


def main(ids: list[str]) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(db_url=f"sqlite:///{Path(tmp, 'sim.db').as_posix()}", var_dir=Path(tmp),
                            auto_import_nasa=False)
        with TestClient(create_app(settings)) as c:
            scenarios = ids or [s["scenario_id"] for s in c.app.state.fixture["movement_scenarios"]]
            for sid in scenarios:
                out = c.post("/api/v1/simulation/movement", json={"scenario_id": sid, "astronaut_id": "DEMO-001"}).json()
                ev = out["evaluation"]
                print(f"{sid}: {ev['zone_matches']}/{ev['tick_count']} ticks in an acceptable zone, "
                      f"{ev['unavailable_ticks']} unavailable")
                for t, g, p in zip(out["ticks"], ev["ground_truth"], ev["per_tick"]):
                    truth = g["true_zone_id"] or f"passage {g['passage_id']}"
                    e = t["estimate"]
                    print(f"  tick {t['tick']:>2} truth {truth:<22} estimate {str(e['zone_id']):<14} "
                          f"conf {e['confidence']:.2f} {e['source']:<24} {'ok' if p['match'] else 'MISMATCH'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

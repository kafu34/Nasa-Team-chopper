"""Real-HTTP smoke test: starts uvicorn on a temporary database and runs the canonical scenario.

Usage (from Backend/):  .venv/Scripts/python scripts/http_smoke.py [--port 8765]
Uses a throwaway database under Backend/var/http-smoke/ so the main demo database is untouched.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parent.parent


def ts(seconds_ago: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()


def main() -> int:
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8765
    work = BACKEND / "var" / "http-smoke"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    env = {**os.environ, "SENTINEL_DB_URL": f"sqlite:///{(work / 'smoke.db').as_posix()}",
           "SENTINEL_VAR_DIR": str(work)}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
                            cwd=BACKEND, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    results: list[tuple[str, bool, str]] = []

    def check(name: str, cond: bool, info: str = "") -> None:
        results.append((name, bool(cond), info))

    try:
        for _ in range(60):
            try:
                if httpx.get(f"{base}/healthz", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.25)
        c = httpx.Client(base_url=base, timeout=10)
        check("GET /healthz", c.get("/healthz").json()["status"] == "ok")
        boot = c.get("/api/v1/demo/bootstrap").json()
        check("GET /api/v1/demo/bootstrap", boot["astronaut"]["astronaut_id"] == "DEMO-001")
        s = boot["demo_inputs"]["symptom"]
        sym = c.post("/api/v1/symptoms", json={"astronaut_id": "DEMO-001", "region_id": s["region_id"],
                                               "laterality": s["laterality"], "severity": s["severity"],
                                               "onset": ts(s["onset_minutes_ago"] * 60), "note": s["note"]})
        check("POST /api/v1/symptoms", sym.status_code == 201, sym.json().get("case_state", ""))
        case_id = sym.json()["case_id"]
        loc = c.post("/api/v1/location/estimate", json={"astronaut_id": "DEMO-001", "observations": [
            {"anchor_id": o["anchor_id"], "rssi_dbm": o["rssi_dbm"], "observed_at": ts(o["age_seconds"])}
            for o in boot["demo_inputs"]["ble_observations"]]}).json()
        check("POST /api/v1/location/estimate", loc["zone_id"] == "crew-quarters", f"conf={loc['confidence']}")
        eq = c.post("/api/v1/equipment/recommend", json={"case_id": case_id, "zone_id": loc["zone_id"],
                                                          "capability": "blood_pressure"}).json()
        check("POST /api/v1/equipment/recommend", eq.get("equipment_id") == "EQ-BP-01", "->".join(eq["route_zone_ids"]))
        proc_def = c.get("/api/v1/procedures/PROC-BP-01").json()
        check("GET /api/v1/procedures/PROC-BP-01", len(proc_def["steps"]) == 6)
        ses = c.post("/api/v1/procedure-sessions", json={"case_id": case_id, "procedure_id": "PROC-BP-01",
                                                          "actor_id": "DEMO-001", "mode": "self"})
        check("POST /api/v1/procedure-sessions", ses.status_code == 201)
        sid = ses.json()["session_id"]
        for st in proc_def["steps"]:
            last = c.post(f"/api/v1/procedure-sessions/{sid}/steps",
                          json={"step_id": st["step_id"], "completion_source": "self_confirmed"}).json()
        check("POST /api/v1/procedure-sessions/{id}/steps", last["status"] == "completed")
        mv = boot["demo_inputs"]["measurement"]
        meas = c.post("/api/v1/measurements", json={"case_id": case_id, "session_id": sid, "astronaut_id": "DEMO-001",
                                                    "type": mv["type"], "value": mv["value"], "unit": mv["unit"],
                                                    "source": mv["source"], "observed_at": ts(1)})
        check("POST /api/v1/measurements", meas.status_code == 201, meas.json().get("case_state", ""))
        case = c.get(f"/api/v1/cases/{case_id}").json()
        check("GET /api/v1/cases/{id}", case["state"] == "monitoring" and len(case["follow_ups"]) == 1)
        res = c.get("/api/v1/research/osd-575").json()
        check("GET /api/v1/research/osd-575", res.get("total") == 531, f"total={res.get('total')}")
        check("GET /api/v1/research/datasets", len(c.get("/api/v1/research/datasets").json()["datasets"]) == 10)
        check("GET /api/v1/research/datasets/OSD-575", c.get("/api/v1/research/datasets/OSD-575").json()["status"] == "IMPORTED")
        check("GET /api/v1/research/datasets/OSD-575/records",
              len(c.get("/api/v1/research/datasets/OSD-575/records", params={"limit": 5}).json()["records"]) == 5)
        for ds_id, st in (("OSD-195", "HUMAN_GROUND_ANALOGUE"), ("OSD-546", "HUMAN_DERIVED_CELLS"),
                          ("OSD-656", "HUMAN_SPACEFLIGHT")):
            d = c.get(f"/api/v1/research/datasets/{ds_id}").json()
            check(f"GET /api/v1/research/datasets/{ds_id}", d["study_type"] == st, d["status"])
        check("GET /api/v1/environment/timeseries (503 expected)", c.get("/api/v1/environment/timeseries").status_code == 503)
        check("GET /api/v1/radiation/timeseries (503 expected)", c.get("/api/v1/radiation/timeseries").status_code == 503)
        emg = c.post("/api/v1/emergencies", json=boot["demo_inputs"]["emergency"])
        check("POST /api/v1/emergencies", emg.status_code == 201 and emg.json()["priority"] == "urgent")
        cors = c.options("/api/v1/demo/bootstrap", headers={"Origin": "http://127.0.0.1:5173",
                                                            "Access-Control-Request-Method": "GET"})
        check("CORS preflight from 127.0.0.1:5173", cors.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173")
        reset = c.post("/api/v1/demo/reset").json()
        check("POST /api/v1/demo/reset", reset["research_records_after"] == reset["research_records_before"] >= 531)
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    for name, ok, info in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {info}")
    passed = sum(ok for _, ok, _ in results)
    print(f"\n{passed}/{len(results)} HTTP checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

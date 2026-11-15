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
    server_log = open(work / "server.log", "wb")  # a file, so a full pipe can never block the server
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
                            cwd=BACKEND, env=env, stdout=server_log, stderr=subprocess.STDOUT)
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
        c = httpx.Client(base_url=base, timeout=30)
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
        stored = c.get(f"/api/v1/equipment/recommendations/{eq['recommendation_id']}").json()
        check("GET /api/v1/equipment/recommendations/{id}", stored["status"] == "active")
        sim = c.post("/api/v1/simulation/movement", json={"scenario_id": "SIM-WALK-CQ-MED",
                                                           "astronaut_id": "DEMO-002"}).json()
        check("POST /api/v1/simulation/movement", sim["evaluation"]["zone_matches"] == sim["evaluation"]["tick_count"],
              f"{sim['evaluation']['zone_matches']}/{sim['evaluation']['tick_count']}")
        hatch = c.post("/api/v1/habitats/HAB-01/hatches/H-CQ-LAB", json={"state": "closed", "actor_id": "DEMO-002",
                                                                         "reason": "Smoke test"}).json()
        check("POST /api/v1/habitats/HAB-01/hatches/{id}", hatch["changed"] and hatch["state_version"] == 2)
        latest = c.get("/api/v1/location/DEMO-001/latest").json()
        check("GET /api/v1/location/{id}/latest", latest["display_mode"] == "zone_only", latest["label"])
        hab_map = c.get("/api/v1/habitats/HAB-01/map").json()
        check("GET /api/v1/habitats/HAB-01/map", hab_map["map_version"] == eq["route_geometry"]["map_version"]
              and len(hab_map["passages"]) == 4, f"route {eq['route_hatch_ids']}")
        proc_def = c.get("/api/v1/procedures/PROC-BP-01").json()
        check("GET /api/v1/procedures/PROC-BP-01", len(proc_def["steps"]) == 6
              and len({s["visual"]["action_id"] for s in proc_def["steps"]}) == 6, proc_def["validation_level"])
        ses = c.post("/api/v1/procedure-sessions", json={"case_id": case_id, "procedure_id": "PROC-BP-01",
                                                          "actor_id": "DEMO-001", "mode": "self",
                                                          "equipment_id": eq["equipment_id"]})
        check("POST /api/v1/procedure-sessions", ses.status_code == 201
              and ses.json()["equipment"]["equipment_id"] == eq["equipment_id"])
        sid = ses.json()["session_id"]
        views = [c.post(f"/api/v1/procedure-sessions/{sid}/events",
                        json={"step_id": st["step_id"], "event_type": "animation_viewed",
                              "visual_action_id": st["visual"]["action_id"], "actor_id": "DEMO-001"}).status_code
                 for st in proc_def["steps"]]
        check("POST /api/v1/procedure-sessions/{id}/events", views == [201] * len(proc_def["steps"]))
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
                          ("OSD-656", "HUMAN_SPACEFLIGHT"), ("OSD-817", "HUMAN_DERIVED_CELLS")):
            d = c.get(f"/api/v1/research/datasets/{ds_id}").json()
            check(f"GET /api/v1/research/datasets/{ds_id}", d["study_type"] == st, d["status"])
        check("GET /api/v1/environment/timeseries (503 expected)", c.get("/api/v1/environment/timeseries").status_code == 503)
        rad = c.get("/api/v1/radiation/timeseries", params={"instrument_id": "DosTel1", "limit": 5})
        check("GET /api/v1/radiation/timeseries (RadLab snapshot)", rad.status_code == 200
              and len(rad.json()["points"]) == 5, f"total={rad.json().get('total')}")
        emg = c.post("/api/v1/emergencies", json=boot["demo_inputs"]["emergency"])
        check("POST /api/v1/emergencies", emg.status_code == 201 and emg.json()["priority"] == "urgent")
        batch = c.post("/api/v1/observations/batch", json={"observations": [
            {"astronaut_id": "DEMO-001", "type": "heart_rate", "value": v, "unit": "bpm",
             "source": "SIMULATED_WEARABLE", "observed_at": ts(sec)} for v, sec in ((84, 1800), (86, 1200), (88, 600))]})
        opened = batch.json().get("concern_ids_opened", []) if batch.status_code == 200 else []
        check("POST /api/v1/observations/batch (DET-1.1 concern)", len(opened) == 1, ",".join(opened))
        mon = c.get("/api/v1/astronauts/DEMO-001/monitoring").json()
        check("GET /api/v1/astronauts/{id}/monitoring", len(mon["concerns"]) == 1 and mon["ruleset_version"] == "DET-1.1")
        con = c.get(f"/api/v1/monitoring-concerns/{opened[0]}").json() if opened else {}
        check("GET /api/v1/monitoring-concerns/{id}", con.get("status") == "open", con.get("rule_id", ""))
        frozen = c.post("/api/v1/astronauts/DEMO-001/baselines/heart_rate/recompute",
                        json={"actor_id": "DEMO-002", "reason": "smoke test"})
        check("POST baselines/{type}/recompute (409 frozen expected)", frozen.status_code == 409)
        procs = [p["procedure_id"] for p in c.get("/api/v1/procedures").json()]
        check("GET /api/v1/procedures", procs == ["PROC-BP-01", "PROC-PO-01", "PROC-TEMP-01"], ",".join(procs))
        po = c.get("/api/v1/procedures/PROC-PO-01").json()
        check("GET /api/v1/procedures/PROC-PO-01", len(po.get("visual_requirements", [])) == 5)
        hist = c.get("/api/v1/astronauts/DEMO-001/observations", params={"type": "heart_rate", "limit": 5}).json()
        check("GET /api/v1/astronauts/{id}/observations", hist["total"] >= 12 and len(hist["items"]) == 5,
              f"total={hist['total']}")
        role = c.post(f"/api/v1/monitoring-concerns/{opened[0]}/review",
                      json={"actor_id": "DEMO-001", "decision": "close", "note": "smoke"}) if opened else None
        check("POST monitoring-concerns/{id}/review by crew member (403 expected)",
              role is not None and role.status_code == 403)
        for scn in ("SCN-REASSESSMENT-DUE", "SCN-URGENT-DURING-PROCEDURE", "SCN-EMERGENCY-DURING-PROCEDURE"):
            sc = c.post(f"/api/v1/demo/scenarios/{scn}")
            check(f"POST /api/v1/demo/scenarios/{scn}", sc.status_code == 200 and sc.json()["reset_first"])
        cors = c.options("/api/v1/demo/bootstrap", headers={"Origin": "http://127.0.0.1:5173",
                                                            "Access-Control-Request-Method": "GET"})
        check("CORS preflight from 127.0.0.1:5173", cors.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173")
        reset = c.post("/api/v1/demo/reset").json()
        check("POST /api/v1/demo/reset", reset["research_records_after"] == reset["research_records_before"] >= 531)
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        server_log.close()
    for name, ok, info in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {info}")
    passed = sum(ok for _, ok, _ in results)
    print(f"\n{passed}/{len(results)} HTTP checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

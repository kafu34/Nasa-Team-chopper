"""Integrated canonical scenario (master prompt section 15) over persisted API state."""
from tests.conftest import now_iso


def test_canonical_scenario(harness):
    harness.add_real_csv()
    c = harness.start(auto_import=True)
    fx = c.app.state.fixture

    # 1-2. Load DEMO-001 in HAB-01 with a scheduled non-invasive assessment due.
    boot = c.get("/api/v1/demo/bootstrap").json()
    assert boot["astronaut"]["astronaut_id"] == "DEMO-001" and boot["habitat"]["habitat_id"] == "HAB-01"
    assert boot["scheduled_assessments"][0]["is_due"] and boot["scheduled_assessments"][0]["procedure_id"] == "PROC-BP-01"

    # 3-4. Symptom from the Anatomical Twin creates a fictional case.
    s = boot["demo_inputs"]["symptom"]
    sym = c.post("/api/v1/symptoms", json={"astronaut_id": "DEMO-001", "region_id": s["region_id"],
                                           "laterality": s["laterality"], "severity": s["severity"],
                                           "onset": now_iso(s["onset_minutes_ago"] * 60), "note": s["note"]})
    assert sym.status_code == 201
    case_id = sym.json()["case_id"]
    assert sym.json()["case_state"] == "awaiting_assessment"

    # 5-6. Simulated wireless observations -> estimated zone.
    obs = [{"anchor_id": o["anchor_id"], "rssi_dbm": o["rssi_dbm"], "observed_at": now_iso(o["age_seconds"])}
           for o in boot["demo_inputs"]["ble_observations"]]
    loc = c.post("/api/v1/location/estimate", json={"astronaut_id": "DEMO-001", "observations": obs}).json()
    assert loc["zone_id"] == boot["demo_inputs"]["expected_zone_id"] == "crew-quarters"

    # 7-8. Suitable blood-pressure equipment with verified readiness and a valid route.
    eq = c.post("/api/v1/equipment/recommend", json={"case_id": case_id, "zone_id": loc["zone_id"],
                                                      "capability": "blood_pressure"}).json()
    assert eq["equipment_id"] == "EQ-BP-01" and eq["readiness"] == "verified_ready"
    zone_ids = {z["zone_id"] for z in boot["habitat"]["zones"]}
    assert eq["route_zone_ids"][0] == "crew-quarters" and eq["route_zone_ids"][-1] == eq["zone_id"]
    assert set(eq["route_zone_ids"]) <= zone_ids

    # 9. Procedure.
    proc = c.get(f"/api/v1/procedures/{eq['procedure_id']}").json()
    assert proc["procedure_id"] == "PROC-BP-01"

    # 10-11. Session and confirmed steps.
    ses = c.post("/api/v1/procedure-sessions", json={"case_id": case_id, "procedure_id": "PROC-BP-01",
                                                      "actor_id": "DEMO-001", "mode": "self"}).json()
    for step in proc["steps"]:
        last = c.post(f"/api/v1/procedure-sessions/{ses['session_id']}/steps",
                      json={"step_id": step["step_id"], "completion_source": "self_confirmed"}).json()
    assert last["status"] == "completed"

    # 12-13. Simulated measurement validated; case updated.
    mv = fx["demo_measurement"]
    meas = c.post("/api/v1/measurements", json={"case_id": case_id, "session_id": ses["session_id"],
                                                "astronaut_id": "DEMO-001", "type": mv["type"], "value": mv["value"],
                                                "unit": mv["unit"], "source": mv["source"],
                                                "observed_at": now_iso(1)})
    assert meas.status_code == 201, meas.text
    assert meas.json()["case_state"] == "monitoring" and meas.json()["follow_up_created"]

    # 14. Latest case and follow-up state, persisted across a restart.
    c = harness.restart(auto_import=True)
    case = c.get(f"/api/v1/cases/{case_id}").json()
    assert case["state"] == "monitoring" and case["follow_up_status"] == "scheduled"
    assert len(case["follow_ups"]) == 1 and len(case["measurements"]) == 1 and case["session_ids"] == [ses["session_id"]]

    # 15. Actual OSD-575 records, independent of the case.
    res = c.get("/api/v1/research/osd-575").json()
    assert res["total"] == 531 and res["records"][0]["data_category"] == "NASA_RESEARCH"
    assert c.get("/api/v1/research/datasets").json()["datasets"][0]["status"] == "IMPORTED"

    # 16. Urgent assistance works with localisation unavailable.
    none = c.post("/api/v1/location/estimate", json={"astronaut_id": "DEMO-001", "observations": []}).json()
    assert none["source"] == "unavailable"
    emg = c.post("/api/v1/emergencies", json=boot["demo_inputs"]["emergency"])
    assert emg.status_code == 201 and emg.json()["priority"] == "urgent" and emg.json()["case_state"] == "escalated"

    # Reset restores synthetic state and keeps research data.
    reset = c.post("/api/v1/demo/reset").json()
    assert reset["research_records_after"] == 531
    assert c.get(f"/api/v1/cases/{case_id}").status_code == 404

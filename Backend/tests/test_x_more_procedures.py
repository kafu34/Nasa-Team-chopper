"""Contract 2.8.0: PROC-PO-01 (pulse oximeter) and PROC-TEMP-01 (infrared thermometer), plan step 34."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from app import models as m
from app.services import surface_sites
from tests.conftest import now_iso
from tests.test_u_health_intelligence import API, obs

NEW = {"PROC-PO-01": ("pulse_oximetry", "EQ-PO-01", 5), "PROC-TEMP-01": ("body_temperature", "EQ-THERM-01", 5)}
ALL = ["PROC-BP-01", *NEW]


def proc(client, pid):
    r = client.get(f"{API}/procedures/{pid}")
    assert r.status_code == 200, r.text
    return r.json()


def test_procedure_list(client):
    out = client.get(f"{API}/procedures").json()
    assert [p["procedure_id"] for p in out] == sorted(ALL)
    boot = {p["procedure_id"] for p in client.get(f"{API}/demo/bootstrap").json()["procedures"]}
    assert boot == set(ALL)


@pytest.mark.parametrize("pid", list(NEW))
def test_visual_contract_is_complete(client, fixture_data, pid):
    p = proc(client, pid)
    cap, _, n = NEW[pid]
    assert p["validation_level"] == "EDUCATIONAL_DEMONSTRATION" and p["content_status"] == "EDUCATIONAL_DEMO_ONLY"
    assert p["required_capability"] == cap and len(p["steps"]) == n
    assert [r["action_id"] for r in p["visual_requirements"]] == [s["visual"]["action_id"] for s in p["steps"]]
    sources = {s["source_id"] for s in p["instruction_sources"]}
    assert all(not s["reviewed_by_flight_surgeon"] for s in p["instruction_sources"])
    regions = {r["region_id"] for r in fixture_data["anatomical_regions"]}
    models = {e["device_model"] for e in fixture_data["equipment"] if e["capability"] == cap}
    for s in p["steps"]:
        v = s["visual"]
        assert v["expected_visible_action"] and v["replay_allowed"] and v["pause_allowed"]
        assert s["requires_confirmation"] and set(s["instruction_source_ids"]) <= sources
        assert s["target_region_id"] in regions and v["camera"]["target_region_id"] in regions
        if s["target_site_id"]:
            site = surface_sites.SITES[s["target_site_id"]]
            assert (site["region_id"], site["laterality"]) == (s["target_region_id"], s["target_laterality"])
        assert s["equipment"]["required_capability"] == cap and set(s["equipment"]["compatible_device_models"]) <= models
    text = json.dumps(p).lower()
    assert "not a diagnosis" in text and "not reviewed by a flight surgeon" in text
    assert any("microgravity" in w.lower() for s in p["steps"] for w in s["warnings"])


def test_action_ids_are_unique_across_all_procedures(client):
    ids = [s["visual"]["action_id"] for pid in ALL for s in proc(client, pid)["steps"]]
    assert len(ids) == len(set(ids)) == 16
    assert all(a.startswith(("VA-BP-", "VA-PO-", "VA-TEMP-")) for a in ids)


def test_bp_procedure_is_unchanged(client, fixture_data):
    with client.app.state.session_factory() as db:
        assert db.get(m.ProcedureDefinition, "PROC-BP-01").definition == fixture_data["procedure"]
    assert proc(client, "PROC-BP-01")["version"] == "1.1.0-demo"


def _run(client, pid, value, unit, type_, equipment=True):
    """Concern-free path: a symptom case, then the given procedure (the case requests BP, so we clear it)."""
    sym = {"astronaut_id": "DEMO-001", "region_id": "head", "laterality": "midline", "severity": 3,
           "onset": now_iso(600)}
    case_id = client.post(f"{API}/symptoms", json=sym).json()["case_id"]
    with client.app.state.session_factory() as db:
        db.get(m.MedicalCase, case_id).requested_assessment = None
        db.commit()
    body = {"case_id": case_id, "procedure_id": pid, "actor_id": "DEMO-001", "mode": "self"}
    if equipment:
        body["equipment_id"] = NEW[pid][1]
    s = client.post(f"{API}/procedure-sessions", json=body)
    assert s.status_code == 201, s.text
    sid = s.json()["session_id"]
    for st in proc(client, pid)["steps"]:
        assert client.post(f"{API}/procedure-sessions/{sid}/steps",
                           json={"step_id": st["step_id"], "completion_source": "self_confirmed"}).status_code == 200
    r = client.post(f"{API}/measurements", json={"case_id": case_id, "session_id": sid, "astronaut_id": "DEMO-001",
                                                 "type": type_, "value": value, "unit": unit,
                                                 "source": "SIMULATED_DEVICE", "observed_at": now_iso(1)})
    return case_id, sid, r


def test_pulse_oximetry_run_records_spo2_and_pulse(client):
    case_id, sid, r = _run(client, "PROC-PO-01", {"spo2": 97, "pulse": 68}, "%", "pulse_oximetry")
    assert r.status_code == 201, r.text
    out = r.json()
    assert "measurement_type_matches_procedure" in out["validation"]["checks"]
    assert out["validation"]["clinical_interpretation"] is None
    assert out["follow_up"]["title"] == "Repeat demonstration pulse-oximeter reading"
    case = client.get(f"{API}/cases/{case_id}").json()
    assert "Simulated SpO2 97 %, pulse 68 bpm" in [e["summary"] for e in case["evidence"]]
    hist = client.get(f"{API}/astronauts/DEMO-001/observations").json()["items"]
    derived = {(i["type"], i["value"]) for i in hist if i["origin"] == "procedure_measurement"}
    assert derived == {("spo2", 97), ("heart_rate", 68)}
    session = client.get(f"{API}/procedure-sessions/{sid}").json()
    assert session["equipment"]["equipment_id"] == "EQ-PO-01"


def test_temperature_run_records_temperature(client):
    case_id, _, r = _run(client, "PROC-TEMP-01", {"temperature": 36.9}, "degC", "body_temperature")
    assert r.status_code == 201, r.text
    hist = client.get(f"{API}/astronauts/DEMO-001/observations", params={"type": "body_temperature"}).json()
    assert hist["items"][0]["value"] == 36.9 and hist["items"][0]["origin"] == "procedure_measurement"


@pytest.mark.parametrize("pid,type_,value,unit,status,code", [
    ("PROC-PO-01", "blood_pressure", {"systolic": 118, "diastolic": 76}, "mmHg", 422, "MEASUREMENT_TYPE_MISMATCH"),
    ("PROC-PO-01", "pulse_oximetry", {"spo2": 101}, "%", 422, "MEASUREMENT_IMPLAUSIBLE"),
    ("PROC-PO-01", "pulse_oximetry", {"spo2": 97, "pulse": 300}, "%", 422, "MEASUREMENT_IMPLAUSIBLE"),
    ("PROC-PO-01", "pulse_oximetry", {"spo2": 97}, "mmHg", 422, "VALIDATION_ERROR"),
    ("PROC-PO-01", "pulse_oximetry", {"temperature": 36.5}, "%", 422, "VALIDATION_ERROR"),
    ("PROC-PO-01", "pulse_oximetry", {"spo2": 97.5}, "%", 422, "VALIDATION_ERROR"),
    ("PROC-TEMP-01", "body_temperature", {"temperature": 45.0}, "degC", 422, "MEASUREMENT_IMPLAUSIBLE"),
    ("PROC-TEMP-01", "pulse_oximetry", {"spo2": 97}, "%", 422, "MEASUREMENT_TYPE_MISMATCH"),
])
def test_measurement_validation(client, pid, type_, value, unit, status, code):
    _, _, r = _run(client, pid, value, unit, type_)
    assert r.status_code == status and r.json()["error"]["code"] == code, r.text


def test_bp_measurement_on_bp_procedure_still_works(client, symptom_payload):
    from tests.test_d_procedures import _complete, _meas, _session

    case_id, s = _session(client, symptom_payload)
    _complete(client, s["session_id"])
    r = client.post(f"{API}/measurements", json=_meas(case_id, s["session_id"]))
    assert r.status_code == 201 and "measurement_type_matches_procedure" in r.json()["validation"]["checks"]


def test_devices_link_to_the_new_procedures(client, symptom_payload):
    case_id = client.post(f"{API}/symptoms", json=symptom_payload).json()["case_id"]
    rec = client.post(f"{API}/equipment/recommend", json={"case_id": case_id, "capability": "pulse_oximetry",
                                                          "zone_id": "medical"}).json()
    assert rec["equipment_id"] == "EQ-PO-01" and rec["procedure_id"] == "PROC-PO-01"
    rec = client.post(f"{API}/equipment/recommend", json={"case_id": case_id, "capability": "body_temperature",
                                                          "zone_id": "crew-quarters"}).json()
    assert rec["equipment_id"] == "EQ-THERM-01" and rec["procedure_id"] == "PROC-TEMP-01"


def test_spo2_concern_requests_the_oximeter_and_completes_through_it(client):
    down = [obs(client, 94, 9 - 2 * i, "spo2", "%") for i in range(3)]
    d = down[-1]["detection"]
    assert d["ruleset_version"] == "DET-1.1" and d["outcome"] == "concern_opened"
    case = client.get(f"{API}/cases/{d['case_id']}").json()
    assert case["requested_assessment"]["procedure_id"] == "PROC-PO-01"
    assert "not a clinical indication" in case["requested_assessment"]["configured_reason"]
    bp = client.post(f"{API}/procedure-sessions", json={"case_id": d["case_id"], "procedure_id": "PROC-BP-01",
                                                        "actor_id": "DEMO-001", "mode": "self"})
    assert bp.status_code == 409 and bp.json()["error"]["code"] == "PROCEDURE_MISMATCH"
    s = client.post(f"{API}/procedure-sessions", json={"case_id": d["case_id"], "procedure_id": "PROC-PO-01",
                                                       "actor_id": "DEMO-001", "mode": "self",
                                                       "equipment_id": "EQ-PO-01"}).json()
    assert client.get(f"{API}/cases/{d['case_id']}").json()["state"] == "awaiting_results"
    for st in proc(client, "PROC-PO-01")["steps"]:
        client.post(f"{API}/procedure-sessions/{s['session_id']}/steps",
                    json={"step_id": st["step_id"], "completion_source": "self_confirmed"})
    r = client.post(f"{API}/measurements", json={"case_id": d["case_id"], "session_id": s["session_id"],
                                                 "astronaut_id": "DEMO-001", "type": "pulse_oximetry",
                                                 "value": {"spo2": 97, "pulse": 66}, "unit": "%",
                                                 "source": "SIMULATED_DEVICE", "observed_at": now_iso(1)})
    assert r.status_code == 201, r.text
    case = client.get(f"{API}/cases/{d['case_id']}").json()
    assert case["state"] == "monitoring" and case["requested_assessment"]["status"] == "completed"
    concern = client.get(f"{API}/monitoring-concerns/{d['concern_id']}").json()
    assert concern["status"] == "open"  # the assessment does not close the concern


def test_temperature_rule_requests_the_thermometer(client):
    ups = [obs(client, 37.6, 30 - 10 * i, "body_temperature", "degC") for i in range(3)]
    d = ups[-1]["detection"]
    assert d["outcome"] == "concern_opened"
    assert client.get(f"{API}/cases/{d['case_id']}").json()["requested_assessment"]["procedure_id"] == "PROC-TEMP-01"


def test_older_database_receives_procedures_and_device_links(harness):
    harness.start()
    harness.stop()
    db = Path(harness.db_url.removeprefix("sqlite:///"))
    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM procedure_definitions WHERE procedure_id IN ('PROC-PO-01', 'PROC-TEMP-01')")
        conn.execute("UPDATE equipment SET compatible_procedure_ids = '[]' WHERE equipment_id IN "
                     "('EQ-PO-01', 'EQ-THERM-01')")
    c = harness.start()
    assert [p["procedure_id"] for p in c.get(f"{API}/procedures").json()] == sorted(ALL)
    with c.app.state.session_factory() as s:
        assert s.get(m.Equipment, "EQ-PO-01").compatible_procedure_ids == ["PROC-PO-01"]
        assert s.get(m.Equipment, "EQ-THERM-01").compatible_procedure_ids == ["PROC-TEMP-01"]

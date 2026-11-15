"""Contract 2.9.0: preventive screening (step 35) and the role-based access matrix (step 36)."""
from __future__ import annotations

from datetime import timedelta

from app import models as m
from app.db import utcnow
from tests.conftest import now_iso
from tests.test_u_health_intelligence import API, open_concern


def assessments(client):
    return {a["assessment_id"]: a for a in client.get(f"{API}/astronauts/DEMO-001/assessments").json()["assessments"]}


def _finish(client, start, value, unit, type_):
    sid = start["session"]["session_id"]
    for st in client.get(f"{API}/procedures/{start['session']['procedure_id']}").json()["steps"]:
        client.post(f"{API}/procedure-sessions/{sid}/steps",
                    json={"step_id": st["step_id"], "completion_source": "self_confirmed"})
    return client.post(f"{API}/measurements", json={"case_id": start["case_id"], "session_id": sid,
                                                    "astronaut_id": "DEMO-001", "type": type_, "value": value,
                                                    "unit": unit, "source": "SIMULATED_DEVICE",
                                                    "observed_at": now_iso(1)})


# --------------------------------------------------------------------------- step 35

def test_three_screening_types_with_due_states(client):
    a = assessments(client)
    assert {k: v["due_state"] for k, v in a.items()} == {"SA-BP-001": "due", "SA-PO-001": "upcoming",
                                                         "SA-TEMP-001": "overdue"}
    assert a["SA-PO-001"]["interval_hours"] == 24 and a["SA-TEMP-001"]["overdue_at"] is not None
    assert a["SA-BP-001"]["symptom_linked"] and not a["SA-PO-001"]["symptom_linked"]
    boot = client.get(f"{API}/demo/bootstrap").json()["scheduled_assessments"]
    assert [x["assessment_id"] for x in boot] == ["SA-BP-001", "SA-PO-001", "SA-TEMP-001"]


def test_symptoms_still_link_only_the_bp_schedule(client, symptom_payload):
    case = client.get(f"{API}/cases/" + client.post(f"{API}/symptoms", json=symptom_payload).json()["case_id"]).json()
    assert case["requested_assessment"]["assessment_id"] == "SA-BP-001"


def test_reminders_are_durable_deduplicated_and_acknowledged_without_completion(client):
    rem = client.get(f"{API}/astronauts/DEMO-001/reminders").json()["reminders"]
    assert {(r["assessment_id"], r["kind"]) for r in rem} == {("SA-BP-001", "due"), ("SA-TEMP-001", "due"),
                                                              ("SA-TEMP-001", "overdue")}
    again = client.get(f"{API}/astronauts/DEMO-001/reminders").json()["reminders"]
    assert len(again) == 3
    r = client.post(f"{API}/reminders/REM-SA-TEMP-001-overdue/acknowledge", json={"actor_id": "DEMO-001"}).json()
    assert r["status"] == "acknowledged" and r["acknowledged_by"] == "DEMO-001"
    assert assessments(client)["SA-TEMP-001"]["due_state"] == "overdue"
    assert client.post(f"{API}/reminders/REM-NOPE/acknowledge", json={"actor_id": "DEMO-001"}).status_code == 404


def test_upcoming_becomes_due_and_gets_a_reminder(client):
    with client.app.state.session_factory() as db:
        db.get(m.ScheduledAssessment, "SA-PO-001").due_at = utcnow() - timedelta(minutes=1)
        db.commit()
    assert assessments(client)["SA-PO-001"]["due_state"] == "due"
    kinds = {(r["assessment_id"], r["kind"]) for r in client.get(f"{API}/astronauts/DEMO-001/reminders").json()["reminders"]}
    assert ("SA-PO-001", "due") in kinds


def test_start_screening_without_symptom_and_complete_it(client):
    client.get(f"{API}/astronauts/DEMO-001/reminders")  # the overdue reminder exists before completion
    r = client.post(f"{API}/assessments/SA-TEMP-001/start", json={"actor_id": "DEMO-002", "mode": "responder",
                                                                  "equipment_id": "EQ-THERM-01"})
    assert r.status_code == 201, r.text
    start = r.json()
    assert start["case_state"] == "awaiting_results" and start["session"]["procedure_id"] == "PROC-TEMP-01"
    case = client.get(f"{API}/cases/{start['case_id']}").json()
    assert case["symptoms"] == [] and case["requested_assessment"]["assessment_id"] == "SA-TEMP-001"
    assert any(a["action"] == "case.created" and a["details"]["rule"] == "R-SCR-01" for a in case["audit"])
    m_ = _finish(client, start, {"temperature": 36.8}, "degC", "body_temperature")
    assert m_.status_code == 201, m_.text
    a = assessments(client)
    assert a["SA-TEMP-001"]["due_state"] == "completed"
    assert a["SA-TEMP-001"]["completed_by_measurement_id"] == m_.json()["measurement"]["measurement_id"]
    nxt = a["SA-TEMP-001-2"]
    assert nxt["due_state"] == "upcoming" and nxt["series_id"] == "SA-TEMP-001" and nxt["sequence"] == 2
    rem = {r["reminder_id"]: r["status"] for r in client.get(f"{API}/astronauts/DEMO-001/reminders").json()["reminders"]}
    assert rem["REM-SA-TEMP-001-overdue"] == "closed_by_completion"
    again = client.post(f"{API}/assessments/SA-TEMP-001/start", json={"actor_id": "DEMO-001"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "ASSESSMENT_COMPLETED"


def test_screening_conflicts_with_a_different_pending_request(client, symptom_payload):
    client.post(f"{API}/symptoms", json=symptom_payload)  # case requests PROC-BP-01
    r = client.post(f"{API}/assessments/SA-TEMP-001/start", json={"actor_id": "DEMO-001"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "CASE_HAS_PENDING_ASSESSMENT"
    ok = client.post(f"{API}/assessments/SA-BP-001/start", json={"actor_id": "DEMO-001"})
    assert ok.status_code == 201 and ok.json()["session"]["procedure_id"] == "PROC-BP-01"


def test_a_bp_symptom_reading_completes_the_bp_screening_and_schedules_the_next(client, symptom_payload):
    from tests.test_d_procedures import _complete, _meas, _session

    case_id, s = _session(client, symptom_payload)
    _complete(client, s["session_id"])
    client.post(f"{API}/measurements", json=_meas(case_id, s["session_id"]))
    a = assessments(client)
    assert a["SA-BP-001"]["due_state"] == "completed" and a["SA-BP-001-2"]["interval_hours"] == 168


def test_existing_database_receives_the_screening_schedule(harness):
    import sqlite3
    from pathlib import Path

    harness.start()
    harness.stop()
    db = Path(harness.db_url.removeprefix("sqlite:///"))
    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM scheduled_assessments WHERE assessment_id != 'SA-BP-001'")
        conn.execute("DROP TABLE assessment_reminders")
        for col in ("interval_hours", "grace_hours", "series_id", "sequence", "symptom_linked",
                    "completed_by_measurement_id"):
            conn.execute(f"ALTER TABLE scheduled_assessments DROP COLUMN {col}")
    c = harness.start()
    a = assessments(c)
    assert set(a) == {"SA-BP-001", "SA-PO-001", "SA-TEMP-001"} and a["SA-BP-001"]["interval_hours"] == 168


# --------------------------------------------------------------------------- step 36

def test_access_matrix_is_published(client):
    out = client.get(f"{API}/access/roles").json()
    assert set(out["role_codes"]) == {"crew_member", "crew_medical_officer", "flight_surgeon", "ground_support"}
    people = {p["person_id"]: (p["role_code"], p["kind"]) for p in out["personnel"]}
    assert people == {"DEMO-001": ("crew_member", "crew"), "DEMO-002": ("crew_medical_officer", "crew"),
                      "GND-FS-01": ("flight_surgeon", "ground"), "GND-SUP-01": ("ground_support", "ground")}
    assert "not security" in out["limitation"]


def test_flight_surgeon_can_close_a_concern_and_ground_support_cannot(client):
    sc = client.post(f"{API}/demo/scenarios/SCN-REASSESSMENT-DUE").json()
    from tests.test_u_health_intelligence import obs
    for i in range(3):
        obs(client, 66, 0.3 - 0.1 * i)
    url = f"{API}/monitoring-concerns/{sc['concern_id']}/review"
    gs = client.post(url, json={"actor_id": "GND-SUP-01", "decision": "close", "note": "not my role"})
    assert gs.status_code == 403 and gs.json()["error"]["details"]["role_code"] == "ground_support"
    gs2 = client.post(url, json={"actor_id": "GND-SUP-01", "decision": "continue_monitoring", "note": "not my role"})
    assert gs2.status_code == 403
    fs = client.post(url, json={"actor_id": "GND-FS-01", "decision": "close", "note": "Reviewed by flight surgeon"})
    assert fs.status_code == 200 and fs.json()["closed_by"] == "GND-FS-01"


def test_sensitive_reads_with_a_viewer(client, symptom_payload):
    case_id = client.post(f"{API}/symptoms", json=symptom_payload).json()["case_id"]
    url = f"{API}/cases/{case_id}"
    assert client.get(url).status_code == 200  # no viewer: demonstration behaviour
    for viewer, status in (("DEMO-001", 200), ("DEMO-002", 200), ("GND-FS-01", 200), ("GND-SUP-01", 403),
                           ("NOBODY", 404)):
        assert client.get(url, params={"viewer_id": viewer}).status_code == status, viewer
    hist = f"{API}/astronauts/DEMO-001/observations"
    assert client.get(hist, params={"viewer_id": "GND-SUP-01"}).status_code == 403
    assert client.get(f"{API}/astronauts/DEMO-002/monitoring", params={"viewer_id": "DEMO-001"}).status_code == 403
    assert client.get(f"{API}/astronauts/DEMO-001/monitoring", params={"viewer_id": "DEMO-001"}).status_code == 200
    with client.app.state.session_factory() as db:
        actions = [e.action for e in db.query(m.AuditEvent).filter(m.AuditEvent.actor.in_(["GND-SUP-01", "GND-FS-01"]))]
    assert "access.denied" in actions and "record.viewed" in actions


def test_acknowledge_and_baseline_roles(client, symptom_payload):
    case_id = client.post(f"{API}/symptoms", json=symptom_payload).json()["case_id"]
    ack = f"{API}/cases/{case_id}/acknowledge"
    assert client.post(ack, json={"actor_id": "GND-SUP-01"}).status_code == 403
    assert client.post(ack, json={"actor_id": "GND-FS-01"}).json()["acknowledged_by"] == "GND-FS-01"
    rec = client.post(f"{API}/astronauts/DEMO-001/baselines/spo2/recompute",
                      json={"actor_id": "GND-FS-01", "reason": "flight surgeon recompute"})
    assert rec.status_code == 201 and rec.json()["created_by"] == "GND-FS-01"


def test_ground_personnel_cannot_operate_hatches(client):
    r = client.post(f"{API}/habitats/HAB-01/hatches/H-CQ-EX", json={"state": "closed", "actor_id": "GND-FS-01",
                                                                   "reason": "remote attempt"})
    assert r.status_code == 403

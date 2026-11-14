"""Contract 2.4.0: procedure session state for the visual Procedure Coach (v3.1 §5 Claude requirements)."""
from __future__ import annotations

import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest

from app import models as m
from app.db import utcnow
from tests.conftest import iso, now_iso

STEPS = ["S1", "S2", "S3", "S4", "S5", "S6"]
ACTIONS = {"S1": "VA-BP-01-PREPARE-EQUIPMENT", "S2": "VA-BP-02-EXPOSE-UPPER-ARM", "S3": "VA-BP-03-WRAP-CUFF",
           "S4": "VA-BP-04-SUPPORT-ARM", "S5": "VA-BP-05-START-MEASUREMENT", "S6": "VA-BP-06-RECORD-RESULT"}


def start(client, symptom_payload, **extra):
    case_id = client.post("/api/v1/symptoms", json=symptom_payload).json()["case_id"]
    r = client.post("/api/v1/procedure-sessions", json={"case_id": case_id, "procedure_id": "PROC-BP-01",
                                                         "actor_id": "DEMO-001", "mode": "self", **extra})
    return case_id, r


def event(client, sid, step, kind, **extra):
    body = {"step_id": step, "event_type": kind, "visual_action_id": ACTIONS[step], "actor_id": "DEMO-001", **extra}
    return client.post(f"/api/v1/procedure-sessions/{sid}/events", json=body)


def stage(session, name):
    return next(s for s in session["stages"] if s["stage"] == name)


def run_all(client, sid):
    for st in STEPS:
        assert event(client, sid, st, "instruction_displayed").status_code == 201
        assert event(client, sid, st, "animation_viewed").status_code == 201
        r = client.post(f"/api/v1/procedure-sessions/{sid}/steps",
                        json={"step_id": st, "completion_source": "self_confirmed"})
        assert r.status_code == 200
    return r.json()


def measure(client, case_id, sid, **extra):
    return client.post("/api/v1/measurements", json={
        "case_id": case_id, "session_id": sid, "astronaut_id": "DEMO-001", "type": "blood_pressure",
        "value": {"systolic": 118, "diastolic": 76, "pulse": 70}, "unit": "mmHg", "source": "SIMULATED_DEVICE",
        "observed_at": now_iso(1), **extra})


def test_session_binds_recommended_device(client, symptom_payload):
    _, r = start(client, symptom_payload, equipment_id="EQ-BP-01")
    assert r.status_code == 201, r.text
    eq = r.json()["equipment"]
    assert eq["equipment_id"] == "EQ-BP-01" and eq["device_model"] == "Demo Automatic Upper-Arm BP Monitor A1"
    assert eq["zone_id_at_start"] == "medical" and eq["readiness_at_start"] == "verified_ready"


@pytest.mark.parametrize("equipment_id,status,code", [
    ("EQ-PO-01", 422, "EQUIPMENT_INCOMPATIBLE"),
    ("EQ-BP-02", 409, "EQUIPMENT_NOT_READY"),  # readiness unknown
    ("EQ-BP-03", 409, "EQUIPMENT_NOT_READY"),  # cuff missing
    ("EQ-NOPE", 404, "NOT_FOUND"),
])
def test_unsuitable_devices_rejected(client, symptom_payload, equipment_id, status, code):
    _, r = start(client, symptom_payload, equipment_id=equipment_id)
    assert r.status_code == status and r.json()["error"]["code"] == code


def test_stale_readiness_rejected(client, symptom_payload):
    with client.app.state.session_factory() as db:
        db.get(m.Equipment, "EQ-BP-01").readiness_verified_at = utcnow() - timedelta(hours=25)
        db.commit()
    _, r = start(client, symptom_payload, equipment_id="EQ-BP-01")
    assert r.status_code == 409 and "readiness_check_stale" in r.json()["error"]["details"]["reasons"]


def test_reused_session_cannot_switch_device(client, symptom_payload):
    case_id, r = start(client, symptom_payload, equipment_id="EQ-BP-01")
    with client.app.state.session_factory() as db:  # make a second ready device
        e = db.get(m.Equipment, "EQ-BP-03")
        e.supplies = {**e.supplies, "cuff_adult_standard": True}
        db.commit()
    again = client.post("/api/v1/procedure-sessions", json={"case_id": case_id, "procedure_id": "PROC-BP-01",
                                                             "actor_id": "DEMO-001", "mode": "self",
                                                             "equipment_id": "EQ-BP-03"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "SESSION_EQUIPMENT_MISMATCH"


def test_device_can_be_bound_to_an_existing_session(client, symptom_payload):
    case_id, r = start(client, symptom_payload)
    assert r.json()["equipment"] is None
    again = client.post("/api/v1/procedure-sessions", json={"case_id": case_id, "procedure_id": "PROC-BP-01",
                                                             "actor_id": "DEMO-001", "mode": "self",
                                                             "equipment_id": "EQ-BP-01"})
    assert again.status_code == 200 and again.json()["equipment"]["equipment_id"] == "EQ-BP-01"


def test_events_are_recorded_separately_from_acknowledgement(client, symptom_payload):
    case_id, r = start(client, symptom_payload)
    sid = r.json()["session_id"]
    assert event(client, sid, "S3", "instruction_displayed").status_code == 201  # previewing a later step is allowed
    assert event(client, sid, "S3", "animation_viewed").status_code == 201
    assert event(client, sid, "S3", "animation_replayed").status_code == 201
    s = client.get(f"/api/v1/procedure-sessions/{sid}").json()
    s3 = next(x for x in s["step_states"] if x["step_id"] == "S3")
    assert (s3["view_count"], s3["replay_count"], s3["acknowledged_at"]) == (1, 1, None)
    assert s3["displayed_at"] is not None and s3["visual_action_id"] == "VA-BP-03-WRAP-CUFF"
    assert s["current_step_id"] == "S1" and s["status"] == "in_progress" and s["completed_count"] == 0
    assert client.get(f"/api/v1/cases/{case_id}").json()["state"] == "awaiting_results"
    assert stage(s, "animation_viewed")["status"] == "partial"
    assert "do not prove" in s["visual_note"]


@pytest.mark.parametrize("patch,code", [
    ({"step_id": "S9"}, "UNKNOWN_STEP"),
    ({"visual_action_id": "VA-GENERIC"}, "VALIDATION_OR_MISMATCH"),
    ({"actor_id": "NOBODY"}, "NOT_FOUND"),
    ({"occurred_at": iso(utcnow() + timedelta(minutes=10))}, "TIMESTAMP_IN_FUTURE"),
    ({"occurred_at": iso(utcnow() - timedelta(hours=2))}, "TIMESTAMP_OUTSIDE_SESSION"),
    ({"event_type": "step_done"}, "VALIDATION_ERROR"),
])
def test_invalid_events_rejected(client, symptom_payload, patch, code):
    _, r = start(client, symptom_payload)
    sid = r.json()["session_id"]
    body = {"step_id": "S1", "event_type": "animation_viewed", "visual_action_id": ACTIONS["S1"],
            "actor_id": "DEMO-001", **patch}
    if "step_id" in patch:
        body["visual_action_id"] = "VA-X"
    res = client.post(f"/api/v1/procedure-sessions/{sid}/events", json=body)
    expected = "VISUAL_ACTION_MISMATCH" if code == "VALIDATION_OR_MISMATCH" else code
    assert res.status_code in (404, 422) and res.json()["error"]["code"] == expected
    states = client.get(f"/api/v1/procedure-sessions/{sid}").json()["step_states"]
    assert all(x["view_count"] == 0 for x in states)


def test_client_event_id_is_idempotent(client, symptom_payload):
    _, r = start(client, symptom_payload)
    sid = r.json()["session_id"]
    first = event(client, sid, "S1", "animation_viewed", client_event_id="tab1-0001")
    again = event(client, sid, "S1", "animation_viewed", client_event_id="tab1-0001")
    assert first.status_code == 201 and again.status_code == 200 and again.json()["duplicate"] is True
    assert again.json()["event_id"] == first.json()["event_id"]
    assert client.get(f"/api/v1/procedure-sessions/{sid}").json()["step_states"][0]["view_count"] == 1


def test_visual_unavailable_marks_stage(client, symptom_payload):
    _, r = start(client, symptom_payload)
    sid = r.json()["session_id"]
    event(client, sid, "S5", "visual_unavailable", note="Scene not implemented")
    s = client.get(f"/api/v1/procedure-sessions/{sid}").json()
    assert next(x for x in s["step_states"] if x["step_id"] == "S5")["visual_unavailable"] is True
    st = stage(s, "animation_viewed")
    assert st["status"] == "unavailable" and "S5" in st["detail"]


def test_full_run_completes_every_stage_in_order(client, symptom_payload):
    case_id, r = start(client, symptom_payload, equipment_id="EQ-BP-01")
    sid = r.json()["session_id"]
    done = run_all(client, sid)
    for name in ("instruction_displayed", "animation_viewed", "steps_acknowledged"):
        assert stage(done, name)["status"] == "done"
    for name in ("device_reading_received", "technical_validation", "assessment_completed", "follow_up_created"):
        assert stage(done, name)["status"] == "pending"
    wrong = measure(client, case_id, sid, equipment_id="EQ-BP-03")
    assert wrong.status_code == 422 and wrong.json()["error"]["code"] == "EQUIPMENT_MISMATCH"
    res = measure(client, case_id, sid, equipment_id="EQ-BP-01")
    assert res.status_code == 201 and "device_matches_session" in res.json()["validation"]["checks"]
    s = client.get(f"/api/v1/procedure-sessions/{sid}").json()
    assert [x["status"] for x in s["stages"]] == ["done"] * 7
    assert "Not a clinical judgement" in stage(s, "technical_validation")["detail"]
    assert stage(s, "follow_up_created")["at"] is not None


def test_state_restored_after_restart_and_reset_clears_events(harness, symptom_payload):
    c = harness.start()
    case_id, r = start(c, symptom_payload, equipment_id="EQ-BP-01")
    sid = r.json()["session_id"]
    event(c, sid, "S1", "instruction_displayed")
    event(c, sid, "S1", "animation_viewed")
    event(c, sid, "S1", "animation_replayed")
    c.post(f"/api/v1/procedure-sessions/{sid}/steps", json={"step_id": "S1", "completion_source": "self_confirmed"})
    event(c, sid, "S2", "instruction_displayed")
    before = c.get(f"/api/v1/procedure-sessions/{sid}").json()
    c = harness.restart()
    after = c.get(f"/api/v1/procedure-sessions/{sid}").json()
    assert after["step_states"] == before["step_states"] and after["equipment"] == before["equipment"]
    assert after["current_step_id"] == "S2"
    assert sid in c.get(f"/api/v1/cases/{case_id}").json()["session_ids"]
    c.post("/api/v1/demo/reset")
    assert c.get(f"/api/v1/procedure-sessions/{sid}").status_code == 404
    with c.app.state.session_factory() as db:
        assert db.query(m.ProcedureStepEvent).count() == 0


def test_old_database_gets_session_columns(harness, symptom_payload):
    harness.start()
    harness.stop()
    db = Path(harness.db_url.removeprefix("sqlite:///"))
    with sqlite3.connect(db) as conn:
        conn.execute("ALTER TABLE procedure_sessions DROP COLUMN equipment_id")
        conn.execute("ALTER TABLE procedure_sessions DROP COLUMN equipment_snapshot")
    c = harness.start()
    _, r = start(c, symptom_payload, equipment_id="EQ-BP-01")
    assert r.status_code == 201 and r.json()["equipment"]["equipment_id"] == "EQ-BP-01"


def test_events_audited_as_visual_only(client, symptom_payload):
    case_id, r = start(client, symptom_payload)
    event(client, r.json()["session_id"], "S1", "animation_viewed")
    audit = client.get(f"/api/v1/cases/{case_id}").json()["audit"]
    rec = next(a for a in audit if a["action"] == "procedure_visual.animation_viewed")
    assert rec["details"]["note"] == "Visual record only; not clinical execution"

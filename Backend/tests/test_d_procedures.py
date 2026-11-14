"""Part D: procedure definition, sessions, step confirmation, measurement validation, follow-up."""
from datetime import timedelta

import pytest

from app import models as m
from app.db import utcnow
from tests.conftest import now_iso

STEPS = ["S1", "S2", "S3", "S4", "S5", "S6"]


def _session(client, symptom_payload, mode="self"):
    case_id = client.post("/api/v1/symptoms", json=symptom_payload).json()["case_id"]
    r = client.post("/api/v1/procedure-sessions", json={"case_id": case_id, "procedure_id": "PROC-BP-01",
                                                         "actor_id": "DEMO-001", "mode": mode})
    assert r.status_code == 201, r.text
    return case_id, r.json()


def _complete(client, session_id):
    for s in STEPS:
        r = client.post(f"/api/v1/procedure-sessions/{session_id}/steps",
                        json={"step_id": s, "completion_source": "self_confirmed"})
        assert r.status_code == 200, r.text
    return r.json()


def _meas(case_id, session_id, **patch):
    body = {"case_id": case_id, "session_id": session_id, "astronaut_id": "DEMO-001", "type": "blood_pressure",
            "value": {"systolic": 118, "diastolic": 76, "pulse": 70}, "unit": "mmHg", "source": "SIMULATED_DEVICE",
            "observed_at": now_iso(1)}
    body.update(patch)
    return body


def test_get_procedure(client):
    r = client.get("/api/v1/procedures/PROC-BP-01")
    assert r.status_code == 200
    p = r.json()
    assert p["version"] == "1.1.0-demo" and p["content_status"] == "EDUCATIONAL_DEMO_ONLY"
    assert p["required_capability"] == "blood_pressure" and [s["step_id"] for s in p["steps"]] == STEPS
    assert "upper_arm" in p["anatomical_region_ids"] and p["safety_limitations"]
    assert client.get("/api/v1/procedures/PROC-NOPE").status_code == 404


def test_session_creation_moves_case_to_awaiting_results(client, symptom_payload):
    case_id, s = _session(client, symptom_payload, mode="responder")
    assert s["mode"] == "responder" and s["current_step_id"] == "S1" and s["procedure_version"] == "1.1.0-demo"
    assert s["case_state"] == "awaiting_results" and s["total_steps"] == 6
    again = client.post("/api/v1/procedure-sessions", json={"case_id": case_id, "procedure_id": "PROC-BP-01",
                                                             "actor_id": "DEMO-001", "mode": "self"})
    assert again.status_code == 200 and again.json()["session_id"] == s["session_id"]


def test_session_validation(client, symptom_payload):
    case_id = client.post("/api/v1/symptoms", json=symptom_payload).json()["case_id"]
    base = {"case_id": case_id, "procedure_id": "PROC-BP-01", "actor_id": "DEMO-001", "mode": "self"}
    assert client.post("/api/v1/procedure-sessions", json={**base, "mode": "robot"}).status_code == 422
    assert client.post("/api/v1/procedure-sessions", json={**base, "case_id": "NOPE"}).status_code == 404
    assert client.post("/api/v1/procedure-sessions", json={**base, "actor_id": "NOPE"}).status_code == 404


def test_step_confirmation_order_and_idempotency(client, symptom_payload):
    _, s = _session(client, symptom_payload)
    sid = s["session_id"]
    r = client.post(f"/api/v1/procedure-sessions/{sid}/steps", json={"step_id": "S3", "completion_source": "self_confirmed"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "STEP_OUT_OF_ORDER"
    r = client.post(f"/api/v1/procedure-sessions/{sid}/steps", json={"step_id": "S9", "completion_source": "self_confirmed"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "UNKNOWN_STEP"
    r1 = client.post(f"/api/v1/procedure-sessions/{sid}/steps", json={"step_id": "S1", "completion_source": "demo_auto"})
    r2 = client.post(f"/api/v1/procedure-sessions/{sid}/steps", json={"step_id": "S1", "completion_source": "demo_auto"})
    assert r1.json()["completed_count"] == r2.json()["completed_count"] == 1
    assert r2.json()["current_step_id"] == "S2"
    done = _complete(client, sid)
    assert done["status"] == "completed" and done["current_step_id"] is None and done["completed_count"] == 6
    assert "does not prove" in done["confirmation_note"]


def test_measurement_requires_completed_session(client, symptom_payload):
    case_id, s = _session(client, symptom_payload)
    r = client.post("/api/v1/measurements", json=_meas(case_id, s["session_id"]))
    assert r.status_code == 409 and r.json()["error"]["code"] == "SESSION_INCOMPLETE"


@pytest.mark.parametrize("patch,status,code", [
    ({"value": {"systolic": 400, "diastolic": 76}}, 422, "MEASUREMENT_IMPLAUSIBLE"),
    ({"value": {"systolic": 70, "diastolic": 90}}, 422, "MEASUREMENT_IMPLAUSIBLE"),
    ({"value": {"systolic": "118", "diastolic": 76}}, 422, "VALIDATION_ERROR"),
    ({"value": {"systolic": 118}}, 422, "VALIDATION_ERROR"),
    ({"unit": "kPa"}, 422, "VALIDATION_ERROR"),
    ({"source": "REAL_DEVICE"}, 422, "VALIDATION_ERROR"),
    ({"type": "glucose"}, 422, "VALIDATION_ERROR"),
    ({"observed_at": "2026-11-14T10:00:00"}, 422, "VALIDATION_ERROR"),
    ({"observed_at": now_iso(-3600)}, 422, "TIMESTAMP_IN_FUTURE"),
    ({"observed_at": now_iso(7200)}, 422, "TIMESTAMP_OUTSIDE_SESSION"),
    ({"astronaut_id": "DEMO-002"}, 409, "ASTRONAUT_MISMATCH"),
])
def test_measurement_technical_validation(client, symptom_payload, patch, status, code):
    case_id, s = _session(client, symptom_payload)
    _complete(client, s["session_id"])
    r = client.post("/api/v1/measurements", json=_meas(case_id, s["session_id"], **patch))
    assert r.status_code == status and r.json()["error"]["code"] == code, r.text


def test_measurement_updates_case_and_creates_single_follow_up(client, symptom_payload):
    case_id, s = _session(client, symptom_payload)
    _complete(client, s["session_id"])
    r = client.post("/api/v1/measurements", json=_meas(case_id, s["session_id"]))
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["case_state"] == "monitoring" and b["follow_up_created"] is True
    assert b["validation"]["technical_checks_passed"] is True and b["validation"]["clinical_interpretation"] is None
    assert b["measurement"]["simulated"] is True and b["measurement"]["data_category"] == "SIMULATED_ASTRONAUT"
    assert b["follow_up"]["interrupt"] is False
    dup = client.post("/api/v1/measurements", json=_meas(case_id, s["session_id"]))
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "MEASUREMENT_ALREADY_RECORDED"
    # A second session + reading on the same case must not duplicate the follow-up task.
    with client.app.state.session_factory() as db:
        db.get(m.MedicalCase, case_id).requested_assessment = None
        db.commit()
    s2 = client.post("/api/v1/procedure-sessions", json={"case_id": case_id, "procedure_id": "PROC-BP-01",
                                                          "actor_id": "DEMO-001", "mode": "self"}).json()
    _complete(client, s2["session_id"])
    r2 = client.post("/api/v1/measurements", json=_meas(case_id, s2["session_id"]))
    assert r2.status_code == 201 and r2.json()["follow_up_created"] is False
    case = client.get(f"/api/v1/cases/{case_id}").json()
    assert len(case["follow_ups"]) == 1 and case["follow_up_status"] == "scheduled"
    assert case["requested_assessment"] is None or case["requested_assessment"]["status"] == "completed"
    boot = client.get("/api/v1/demo/bootstrap").json()
    assert boot["scheduled_assessments"][0]["status"] == "completed"
    st = {x["type"]: x["status"] for x in boot["observation_status"]}
    assert st["blood_pressure_systolic"] == "current"


def test_follow_up_becomes_due(client, symptom_payload):
    case_id, s = _session(client, symptom_payload)
    _complete(client, s["session_id"])
    client.post("/api/v1/measurements", json=_meas(case_id, s["session_id"]))
    with client.app.state.session_factory() as db:
        for fu in db.query(m.FollowUpTask).filter(m.FollowUpTask.case_id == case_id):
            fu.due_at = utcnow() - timedelta(minutes=1)
        db.commit()
    case = client.get(f"/api/v1/cases/{case_id}").json()
    assert case["state"] == "follow_up_due" and case["follow_up_status"] == "due"
    assert case["follow_ups"][0]["status"] == "due"

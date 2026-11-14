"""Part B: symptoms, case creation and transitions, duplicates, observation validation, acknowledgement."""
import pytest

from app.services.cases import TRANSITIONS, can_transition
from tests.conftest import now_iso


def test_symptom_creates_case_awaiting_assessment(client, symptom_payload):
    r = client.post("/api/v1/symptoms", json=symptom_payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["case_state"] == "awaiting_assessment" and body["duplicate"] is False
    assert "PROC-BP-01" in body["next_action"] and "not been clinically evaluated" in body["next_action"]
    case = client.get(f"/api/v1/cases/{body['case_id']}").json()
    assert case["requested_assessment"]["procedure_id"] == "PROC-BP-01"
    assert case["requested_assessment"]["assessment_id"] == "SA-BP-001"
    assert {e["type"] for e in case["evidence"]} == {"symptom", "scheduled_assessment"}
    assert case["attention"] == {"priority": "routine", "interrupt": False, "reason": case["attention"]["reason"]}
    transitions = [(a["details"]["from_state"], a["details"]["to_state"]) for a in case["audit"]
                   if a["action"] == "case.state_changed"]
    assert transitions == [("detected", "investigating"), ("investigating", "awaiting_assessment")]
    assert all(a["details"].get("ruleset_version", "RULESET-P0-1.0") == "RULESET-P0-1.0" for a in case["audit"])


def test_duplicate_symptom_is_deduplicated(client, symptom_payload):
    first = client.post("/api/v1/symptoms", json=symptom_payload).json()
    r = client.post("/api/v1/symptoms", json=symptom_payload)
    assert r.status_code == 200 and r.json()["duplicate"] is True
    assert r.json()["symptom_id"] == first["symptom_id"] and r.json()["case_id"] == first["case_id"]
    case = client.get(f"/api/v1/cases/{first['case_id']}").json()
    assert len(case["symptoms"]) == 1


def test_second_different_symptom_joins_same_case(client, symptom_payload):
    first = client.post("/api/v1/symptoms", json=symptom_payload).json()
    other = {**symptom_payload, "region_id": "lower_back", "laterality": "left", "severity": 2}
    second = client.post("/api/v1/symptoms", json=other).json()
    assert second["case_id"] == first["case_id"] and second["duplicate"] is False
    assert len(client.get(f"/api/v1/cases/{first['case_id']}").json()["symptoms"]) == 2


def test_high_severity_raises_priority(client, symptom_payload):
    body = client.post("/api/v1/symptoms", json={**symptom_payload, "severity": 9}).json()
    case = client.get(f"/api/v1/cases/{body['case_id']}").json()
    assert case["priority"] == "urgent" and case["attention"]["interrupt"] is True
    assert body["next_action"].startswith("High severity reported")


@pytest.mark.parametrize("patch,code", [
    ({"region_id": "spleen-xyz"}, "UNKNOWN_REGION"),
    ({"laterality": "left"}, "INVALID_LATERALITY"),
    ({"severity": 11}, "VALIDATION_ERROR"),
    ({"laterality": "sideways"}, "VALIDATION_ERROR"),
    ({"onset": "2026-11-14T10:00:00"}, "VALIDATION_ERROR"),
    ({"onset": now_iso(-3600)}, "TIMESTAMP_IN_FUTURE"),
    ({"unexpected": 1}, "VALIDATION_ERROR"),
])
def test_symptom_validation(client, symptom_payload, patch, code):
    r = client.post("/api/v1/symptoms", json={**symptom_payload, **patch})
    assert r.status_code == 422 and r.json()["error"]["code"] == code


def test_symptom_unknown_astronaut(client, symptom_payload):
    r = client.post("/api/v1/symptoms", json={**symptom_payload, "astronaut_id": "NOPE"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_case_not_found(client):
    r = client.get("/api/v1/cases/CASE-NONE")
    assert r.status_code == 404 and r.json()["error"]["details"]["id"] == "CASE-NONE"


def test_acknowledge_does_not_resolve(client, symptom_payload):
    case_id = client.post("/api/v1/symptoms", json=symptom_payload).json()["case_id"]
    r = client.post(f"/api/v1/cases/{case_id}/acknowledge", json={"actor_id": "DEMO-001"})
    assert r.status_code == 200
    assert r.json()["state"] == "awaiting_assessment" and r.json()["acknowledged_by"] == "DEMO-001"


def test_transition_table_rules():
    assert not can_transition("awaiting_assessment", "resolved")
    assert not can_transition("escalated", "detected")
    assert TRANSITIONS["resolved"] == set()
    assert all(dst in TRANSITIONS for dsts in TRANSITIONS.values() for dst in dsts)


def test_observation_valid_and_duplicate(client):
    obs = {"astronaut_id": "DEMO-001", "type": "heart_rate", "value": 71, "unit": "bpm",
           "source": "SIMULATED_WEARABLE", "observed_at": now_iso(10)}
    r = client.post("/api/v1/observations", json=obs)
    assert r.status_code == 201 and r.json()["simulated"] is True and r.json()["duplicate"] is False
    r2 = client.post("/api/v1/observations", json=obs)
    assert r2.status_code == 200 and r2.json()["duplicate"] is True
    assert r2.json()["observation_id"] == r.json()["observation_id"]


@pytest.mark.parametrize("patch,code", [
    ({"type": "brain_waves"}, "UNKNOWN_OBSERVATION_TYPE"),
    ({"unit": "Hz"}, "UNIT_MISMATCH"),
    ({"value": 900}, "VALUE_OUT_OF_TECHNICAL_RANGE"),
    ({"observed_at": now_iso(-7200)}, "TIMESTAMP_IN_FUTURE"),
    ({"source": "REAL_SENSOR"}, "VALIDATION_ERROR"),
    ({"value": "seventy"}, "VALIDATION_ERROR"),
])
def test_observation_validation(client, patch, code):
    obs = {"astronaut_id": "DEMO-001", "type": "heart_rate", "value": 71, "unit": "bpm",
           "source": "SIMULATED_WEARABLE", "observed_at": now_iso(10), **patch}
    r = client.post("/api/v1/observations", json=obs)
    assert r.status_code == 422 and r.json()["error"]["code"] == code

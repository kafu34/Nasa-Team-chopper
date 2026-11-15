"""Contract 2.6.0: urgent-priority protection (v3.1 §7 Scenario D) and reassessment / review (Scenario E)."""
from __future__ import annotations

import sqlite3
from datetime import timedelta
from pathlib import Path

from app import models as m
from app.db import utcnow
from tests.conftest import now_iso
from tests.test_d_procedures import _complete, _meas
from tests.test_u_health_intelligence import API, obs, open_concern

URGENT = "High severity reported: notify the crew medical officer now."


def _start(client, case_id):
    r = client.post(f"{API}/procedure-sessions", json={"case_id": case_id, "procedure_id": "PROC-BP-01",
                                                       "actor_id": "DEMO-001", "mode": "self"})
    assert r.status_code == 201, r.text
    return r.json()


def _urgent_symptom(client, symptom_payload):
    body = {**symptom_payload, "region_id": "chest", "laterality": "midline", "severity": 9, "onset": now_iso(30)}
    r = client.post(f"{API}/symptoms", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _due_now(client, case_id):
    with client.app.state.session_factory() as db:
        for fu in db.query(m.FollowUpTask).filter(m.FollowUpTask.case_id == case_id):
            fu.due_at = utcnow() - timedelta(minutes=6)  # earlier than the next readings
        db.commit()


# --------------------------------------------------------------------------- Scenario D

def test_scenario_d_urgent_event_during_routine_procedure_is_never_downgraded(client, symptom_payload):
    case_id = client.post(f"{API}/symptoms", json=symptom_payload).json()["case_id"]
    s = _start(client, case_id)
    assert s["case_priority"] == "routine" and s["attention"]["interrupt"] is False
    urgent = _urgent_symptom(client, symptom_payload)
    assert urgent["case_id"] == case_id
    during = client.get(f"{API}/procedure-sessions/{s['session_id']}").json()
    assert during["case_priority"] == "urgent" and during["attention"]["interrupt"] is True
    assert during["status"] == "in_progress"  # the routine session is not cancelled
    _complete(client, s["session_id"])
    r = client.post(f"{API}/measurements", json=_meas(case_id, s["session_id"]))
    assert r.status_code == 201, r.text
    assert r.json()["next_action"].startswith(URGENT)
    assert r.json()["follow_up"]["interrupt"] is True
    case = client.get(f"{API}/cases/{case_id}").json()
    assert case["state"] == "monitoring" and case["priority"] == "urgent"
    prot = case["priority_protection"]
    assert prot["automatic_downgrade_allowed"] is False and "R-SYM-04" in prot["reason"]
    assert prot["urgent_instruction"] == URGENT and prot["urgent_since"] is not None
    _due_now(client, case_id)
    due = client.get(f"{API}/cases/{case_id}").json()
    assert due["state"] == "follow_up_due" and due["priority"] == "urgent" and due["next_action"].startswith(URGENT)
    actions = [a["action"] for a in due["audit"]]
    assert actions.count("case.priority_raised") == 1


def test_urgent_raise_makes_existing_follow_ups_interrupt(client, symptom_payload):
    case_id = client.post(f"{API}/symptoms", json=symptom_payload).json()["case_id"]
    s = _start(client, case_id)
    _complete(client, s["session_id"])
    fu = client.post(f"{API}/measurements", json=_meas(case_id, s["session_id"])).json()["follow_up"]
    assert fu["interrupt"] is False
    _urgent_symptom(client, symptom_payload)
    case = client.get(f"{API}/cases/{case_id}").json()
    assert case["follow_ups"][0]["interrupt"] is True and case["attention"]["interrupt"] is True


def test_emergency_during_routine_procedure_is_shown_to_the_coach(client, symptom_payload):
    case_id = client.post(f"{API}/symptoms", json=symptom_payload).json()["case_id"]
    s = _start(client, case_id)
    emg = client.post(f"{API}/emergencies", json={"astronaut_id": "DEMO-001", "responder_id": "DEMO-002",
                                                  "trigger": "crew_collapse"}).json()
    during = client.get(f"{API}/procedure-sessions/{s['session_id']}").json()
    assert [e["case_id"] for e in during["urgent_events"]] == [emg["case_id"]]
    ev = during["urgent_events"][0]
    assert ev["kind"] == "emergency" and ev["attention"]["interrupt"] and ev["next_action"].startswith("URGENT")
    assert during["status"] == "in_progress" and during["case_priority"] == "routine"
    emergency_case = client.get(f"{API}/cases/{emg['case_id']}").json()
    assert emergency_case["priority_protection"]["reason"] == "Emergency activated: crew_collapse"


def test_second_urgent_event_keeps_priority_and_is_audited(client, symptom_payload):
    first = _urgent_symptom(client, symptom_payload)
    body = {**symptom_payload, "region_id": "head", "laterality": "midline", "severity": 8, "onset": now_iso(20)}
    client.post(f"{API}/symptoms", json=body)
    low = {**symptom_payload, "severity": 2, "onset": now_iso(10)}
    client.post(f"{API}/symptoms", json=low)  # a routine symptom joining the urgent case
    case = client.get(f"{API}/cases/{first['case_id']}").json()
    actions = [a["action"] for a in case["audit"]]
    assert actions.count("case.priority_raised") == 1 and actions.count("case.urgent_event_recorded") == 1
    assert case["priority"] == "urgent" and case["next_action"].startswith(URGENT)
    assert case["next_action"].count(URGENT) == 1


def test_detection_on_an_urgent_case_keeps_it_urgent(client, symptom_payload):
    case_id = _urgent_symptom(client, symptom_payload)["case_id"]
    d = open_concern(client)[-1]["detection"]
    assert d["case_id"] == case_id
    case = client.get(f"{API}/cases/{case_id}").json()
    assert case["priority"] == "urgent" and case["next_action"].startswith(URGENT)
    assert case["follow_ups"][-1]["task_type"] == "monitoring_reassessment" and case["follow_ups"][-1]["interrupt"]


# --------------------------------------------------------------------------- Scenario E

def test_scenario_e_no_premature_resolution_and_evidence_based_review(client):
    d = open_concern(client)[-1]["detection"]
    cid, case_id = d["concern_id"], d["case_id"]
    early = [obs(client, 66, 8 - 2 * i)["detection"] for i in range(3)]  # back in range before the reassessment
    assert {e["outcome"] for e in early} == {"within_baseline_concern_open"}
    c = client.get(f"{API}/monitoring-concerns/{cid}").json()
    assert c["status"] == "open" and c["consecutive_within_baseline"] == 3 and not c["reassessment_passed"]
    close = client.post(f"{API}/monitoring-concerns/{cid}/review",
                        json={"actor_id": "DEMO-002", "decision": "close", "note": "Looks fine"})
    assert close.status_code == 409 and close.json()["error"]["code"] == "CONCERN_NOT_READY_FOR_REVIEW"

    _due_now(client, case_id)
    assert client.get(f"{API}/monitoring-concerns/{cid}").json()["reassessment"]["status"] == "due"
    fair = obs(client, 65, 1, quality="fair")["detection"]  # fair quality cannot complete a reassessment
    assert fair["outcome"] == "within_baseline_concern_open"
    done = obs(client, 66, 0.5)["detection"]
    assert done["outcome"] == "concern_ready_for_review"
    c = client.get(f"{API}/monitoring-concerns/{cid}").json()
    assert c["status"] == "awaiting_review" and c["reassessment_passed"]
    assert c["reassessment"]["status"] == "completed" and c["reassessment"]["completion_evidence_id"]
    case = client.get(f"{API}/cases/{case_id}").json()
    assert case["state"] != "resolved" and "review" in case["next_action"]

    closed = client.post(f"{API}/monitoring-concerns/{cid}/review",
                         json={"actor_id": "DEMO-002", "decision": "close", "note": "Reviewed after reassessment"})
    assert closed.status_code == 200, closed.text
    c = closed.json()
    assert c["status"] == "closed" and c["closed_by"] == "DEMO-002" and not c["baseline_frozen"]
    case = client.get(f"{API}/cases/{case_id}").json()
    assert case["state"] != "resolved"
    assert any(a["action"] == "monitoring_concern.closed" for a in case["audit"])
    again = client.post(f"{API}/monitoring-concerns/{cid}/review",
                        json={"actor_id": "DEMO-002", "decision": "close", "note": "again"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "CONCERN_CLOSED"

    # The baseline can now be recomputed, and every reading observed during the concern is left out.
    r = client.post(f"{API}/astronauts/DEMO-001/baselines/heart_rate/recompute",
                    json={"actor_id": "DEMO-002", "reason": "After the closed concern"})
    assert r.status_code == 201, r.text
    # Excluded: 3 deviating + 3 early + 2 reassessment readings, and the 2 seeded fixture readings observed after
    # the first deviation. Only the fictional history remains (median 65).
    assert r.json()["version"] == 2 and r.json()["excluded_count"] == 10 and r.json()["centre"] == 65


def test_reassessment_with_persisting_change_schedules_another(client):
    d = open_concern(client)[-1]["detection"]
    _due_now(client, d["case_id"])
    r = obs(client, 90, 1)["detection"]
    assert r["outcome"] == "concern_updated"
    c = client.get(f"{API}/monitoring-concerns/{d['concern_id']}").json()
    assert c["status"] == "open" and c["reassessment"]["status"] == "scheduled"
    fus = client.get(f"{API}/cases/{d['case_id']}").json()["follow_ups"]
    assert [f["status"] for f in fus] == ["completed", "scheduled"]


def test_new_deviation_while_awaiting_review_reopens(client):
    d = open_concern(client)[-1]["detection"]
    _due_now(client, d["case_id"])
    for i in range(3):
        obs(client, 66, 5 - i)
    assert client.get(f"{API}/monitoring-concerns/{d['concern_id']}").json()["status"] == "awaiting_review"
    assert obs(client, 89, 1)["detection"]["outcome"] == "concern_updated"
    c = client.get(f"{API}/monitoring-concerns/{d['concern_id']}").json()
    assert c["status"] == "open" and not c["reassessment_passed"] and c["reassessment"]["status"] == "scheduled"


def test_continue_monitoring_decision(client):
    d = open_concern(client)[-1]["detection"]
    r = client.post(f"{API}/monitoring-concerns/{d['concern_id']}/review",
                    json={"actor_id": "DEMO-002", "decision": "continue_monitoring", "note": "Keep watching"})
    assert r.status_code == 200 and r.json()["status"] == "open" and r.json()["review_note"] == "Keep watching"
    assert client.post(f"{API}/monitoring-concerns/CON-NOPE/review",
                       json={"actor_id": "DEMO-002", "decision": "close", "note": "x x x"}).status_code == 404
    assert client.post(f"{API}/monitoring-concerns/{d['concern_id']}/review",
                       json={"actor_id": "NOBODY", "decision": "close", "note": "x x x"}).status_code == 404
    assert client.post(f"{API}/monitoring-concerns/{d['concern_id']}/review",
                       json={"actor_id": "DEMO-002", "decision": "ignore", "note": "x x x"}).status_code == 422


def test_concern_and_follow_up_state_survive_restart(harness):
    c = harness.start()
    d = open_concern(c)[-1]["detection"]
    obs(c, 66, 5)
    c = harness.restart()
    con = c.get(f"{API}/monitoring-concerns/{d['concern_id']}").json()
    assert con["status"] == "open" and con["consecutive_within_baseline"] == 1
    assert con["reassessment"]["status"] == "scheduled"
    assert c.get(f"{API}/astronauts/DEMO-001/monitoring").json()["types"][0]["open_concern_id"] == d["concern_id"]


def test_older_database_is_upgraded_with_baselines(harness):
    harness.start()
    harness.stop()
    db = Path(harness.db_url.removeprefix("sqlite:///"))
    with sqlite3.connect(db) as conn:
        conn.execute("DROP INDEX ix_follow_up_tasks_concern_id")
        conn.execute("DROP TABLE health_baselines")
        conn.execute("DROP TABLE monitoring_concerns")
        conn.execute("DELETE FROM health_observations WHERE observation_id LIKE 'OBS-HIST-%'")
        for table, col in (("health_observations", "detection"), ("medical_cases", "urgent_since"),
                           ("medical_cases", "priority_reason"), ("medical_cases", "urgent_instruction"),
                           ("follow_up_tasks", "concern_id"), ("follow_up_tasks", "completed_at"),
                           ("follow_up_tasks", "completion_evidence_id")):
            conn.execute(f"ALTER TABLE {table} DROP COLUMN {col}")
    c = harness.start()
    base = c.get(f"{API}/astronauts/DEMO-001/baselines").json()["baselines"]
    assert {b["type"] for b in base} == {"heart_rate", "spo2", "body_temperature"}
    assert open_concern(c)[-1]["detection"]["outcome"] == "concern_opened"

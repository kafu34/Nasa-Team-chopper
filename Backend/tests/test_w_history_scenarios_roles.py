"""Contract 2.7.0: observation history, isolated demo scenarios and the concern-review role check."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tests.conftest import iso
from tests.test_u_health_intelligence import API, obs, open_concern


# --------------------------------------------------------------------------- history (33.2)

def test_history_lists_every_reading_newest_first_with_origin(client):
    open_concern(client)
    h = client.get(f"{API}/astronauts/DEMO-001/observations", params={"type": "heart_rate"}).json()
    assert h["total"] == 7 + 2 + 3  # fictional history + fixture readings + ingested
    times = [i["observed_at"] for i in h["items"]]
    assert times == sorted(times, reverse=True)
    origins = [i["origin"] for i in h["items"]]
    assert origins.count("baseline_history") == 7 and origins.count("seed_fixture") == 2
    assert origins.count("ingested") == 3
    newest = next(i for i in h["items"] if i["origin"] == "ingested")  # fixture 72 bpm (5 min ago) is newer
    assert newest["detection"]["outcome"] == "concern_opened" and not newest["in_active_baseline"]
    hist = [i for i in h["items"] if i["origin"] == "baseline_history"]
    assert all(i["in_active_baseline"] and i["detection"] is None for i in hist)


def test_history_filters_and_paging(client):
    for i in range(5):
        obs(client, 65 + i, 50 - i)
    now = datetime.now(timezone.utc)
    base = f"{API}/astronauts/DEMO-001/observations"
    recent = client.get(base, params={"type": "heart_rate", "since": iso(now - timedelta(hours=1))}).json()
    assert recent["total"] == 7  # 5 new + the 2 fixture readings
    page = client.get(base, params={"type": "heart_rate", "limit": 2, "offset": 2}).json()
    full = client.get(base, params={"type": "heart_rate"}).json()
    assert [i["observation_id"] for i in page["items"]] == [i["observation_id"] for i in full["items"][2:4]]
    old = client.get(base, params={"until": iso(now - timedelta(days=3))}).json()
    assert old["items"] and all(i["origin"] == "baseline_history" for i in old["items"])
    assert client.get(base, params={"type": "mood"}).status_code == 422
    assert client.get(base, params={"limit": 0}).status_code == 422
    assert client.get(f"{API}/astronauts/NOBODY/observations").status_code == 404


def test_history_marks_procedure_readings(client, symptom_payload):
    from tests.test_d_procedures import _complete, _meas, _session

    case_id, s = _session(client, symptom_payload)
    _complete(client, s["session_id"])
    client.post(f"{API}/measurements", json=_meas(case_id, s["session_id"]))
    items = client.get(f"{API}/astronauts/DEMO-001/observations").json()["items"]
    proc = [i for i in items if i["origin"] == "procedure_measurement"]
    assert {i["type"] for i in proc} == {"blood_pressure_systolic", "blood_pressure_diastolic", "heart_rate"}
    assert all(i["measurement_id"] and i["detection"] is None for i in proc)


# --------------------------------------------------------------------------- scenarios (33.3)

def test_scenario_reassessment_due(client):
    r = client.post(f"{API}/demo/scenarios/SCN-REASSESSMENT-DUE")
    assert r.status_code == 200, r.text
    sc = r.json()
    assert sc["reset_first"] and sc["concern_id"] and len(sc["simulated_clock_changes"]) == 1
    c = client.get(f"{API}/monitoring-concerns/{sc['concern_id']}").json()
    assert c["status"] == "open" and c["reassessment"]["status"] == "due"
    case = client.get(f"{API}/cases/{sc['case_id']}").json()
    assert case["symptoms"] == [] and any(a["action"] == "demo.scenario_loaded" for a in case["audit"])
    done = obs(client, 66, 0)["detection"]
    assert done["outcome"] == "reassessment_completed"


def test_scenario_urgent_during_procedure(client):
    sc = client.post(f"{API}/demo/scenarios/SCN-URGENT-DURING-PROCEDURE").json()
    s = client.get(f"{API}/procedure-sessions/{sc['session_id']}").json()
    assert s["status"] == "in_progress" and s["completed_count"] == 2
    assert s["case_priority"] == "urgent" and s["attention"]["interrupt"] and s["urgent_events"] == []
    case = client.get(f"{API}/cases/{sc['case_id']}").json()
    assert case["priority_protection"]["automatic_downgrade_allowed"] is False


def test_scenario_emergency_during_procedure(client):
    sc = client.post(f"{API}/demo/scenarios/SCN-EMERGENCY-DURING-PROCEDURE").json()
    s = client.get(f"{API}/procedure-sessions/{sc['session_id']}").json()
    assert s["case_priority"] == "routine" and [e["case_id"] for e in s["urgent_events"]] == [sc["emergency_case_id"]]


def test_scenarios_are_isolated_from_each_other(client):
    first = client.post(f"{API}/demo/scenarios/SCN-REASSESSMENT-DUE").json()
    client.post(f"{API}/demo/scenarios/SCN-URGENT-DURING-PROCEDURE")
    assert client.get(f"{API}/monitoring-concerns/{first['concern_id']}").status_code == 404
    assert client.get(f"{API}/astronauts/DEMO-001/monitoring").json()["concerns"] == []
    nope = client.post(f"{API}/demo/scenarios/SCN-NOPE")
    assert nope.status_code == 404 and "SCN-REASSESSMENT-DUE" in nope.json()["error"]["details"]["available_scenarios"]


# --------------------------------------------------------------------------- roles (36.1)

def _ready_for_review(client):
    sc = client.post(f"{API}/demo/scenarios/SCN-REASSESSMENT-DUE").json()
    for i in range(3):
        obs(client, 66, 0.3 - 0.1 * i)
    assert client.get(f"{API}/monitoring-concerns/{sc['concern_id']}").json()["status"] == "awaiting_review"
    return sc


def test_only_the_medical_officer_can_close_a_concern(client):
    sc = _ready_for_review(client)
    url = f"{API}/monitoring-concerns/{sc['concern_id']}/review"
    denied = client.post(url, json={"actor_id": "DEMO-001", "decision": "close", "note": "I feel fine"})
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "ROLE_NOT_PERMITTED"
    assert denied.json()["error"]["details"]["role_code"] == "crew_member"
    audit = client.get(f"{API}/cases/{sc['case_id']}").json()["audit"]
    assert any(a["action"] == "access.denied" for a in audit)
    assert client.get(f"{API}/monitoring-concerns/{sc['concern_id']}").json()["status"] == "awaiting_review"
    ok = client.post(url, json={"actor_id": "DEMO-002", "decision": "close", "note": "Reviewed by CMO"})
    assert ok.status_code == 200 and ok.json()["status"] == "closed"


def test_any_crew_member_can_continue_monitoring(client):
    sc = client.post(f"{API}/demo/scenarios/SCN-REASSESSMENT-DUE").json()
    r = client.post(f"{API}/monitoring-concerns/{sc['concern_id']}/review",
                    json={"actor_id": "DEMO-001", "decision": "continue_monitoring", "note": "Still watching"})
    assert r.status_code == 200 and r.json()["status"] == "open"


def test_baseline_recompute_needs_the_medical_officer(client):
    r = client.post(f"{API}/astronauts/DEMO-001/baselines/spo2/recompute",
                    json={"actor_id": "DEMO-001", "reason": "self recompute"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "ROLE_NOT_PERMITTED"


def test_bootstrap_publishes_role_codes(client):
    boot = client.get(f"{API}/demo/bootstrap").json()
    assert boot["astronaut"]["role_code"] == "crew_member"
    assert boot["responder"]["role_code"] == "crew_medical_officer"

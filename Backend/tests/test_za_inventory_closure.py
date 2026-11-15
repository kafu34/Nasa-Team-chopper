"""Contract 2.11.0: equipment inventory updates (step 41) and controlled case closure (step 42)."""
from __future__ import annotations

from tests.conftest import now_iso
from tests.test_d_procedures import _complete, _meas, _session
from tests.test_u_health_intelligence import API, obs, open_concern


def upd(client, eq, actor="DEMO-002", **body):
    return client.post(f"{API}/equipment/{eq}/status", json={"actor_id": actor, "note": "Demo inventory check", **body})


def rec(client, case_id, zone="crew-quarters", cap="blood_pressure"):
    return client.post(f"{API}/equipment/recommend", json={"case_id": case_id, "capability": cap, "zone_id": zone})


def resolve(client, case_id, actor="DEMO-002", **kw):
    return client.post(f"{API}/cases/{case_id}/resolve", json={"actor_id": actor, "note": "Reviewed and resolved", **kw})


# --------------------------------------------------------------------------- step 41

def test_inventory_lists_usability(client):
    inv = {e["equipment_id"]: e for e in client.get(f"{API}/equipment").json()}
    assert inv["EQ-BP-01"]["usable"] and inv["EQ-BP-01"]["unusable_reasons"] == []
    assert inv["EQ-BP-02"]["unusable_reasons"] == ["readiness_unknown"]
    assert inv["EQ-BP-03"]["unusable_reasons"] == ["missing_supplies:cuff_adult_standard"]


def test_marking_a_device_out_of_service_invalidates_its_route_and_changes_the_pick(client, symptom_payload):
    case_id = client.post(f"{API}/symptoms", json=symptom_payload).json()["case_id"]
    first = rec(client, case_id).json()
    assert first["equipment_id"] == "EQ-BP-01"
    out = upd(client, "EQ-BP-01", readiness="needs_service").json()
    assert out["changed"] and not out["equipment"]["usable"]
    assert out["invalidated_recommendation_ids"] == [first["recommendation_id"]]
    stored = client.get(f"{API}/equipment/recommendations/{first['recommendation_id']}").json()
    assert stored["status"] == "invalidated" and "EQ-BP-01" in stored["invalidated_reason"]
    none = rec(client, case_id)
    assert none.status_code == 404 and none.json()["error"]["code"] == "NO_SUITABLE_EQUIPMENT"
    # restocking EQ-BP-03 (exercise) makes it the pick
    fixed = upd(client, "EQ-BP-03", supplies={"cuff_adult_standard": True}).json()
    assert fixed["equipment"]["usable"] and fixed["before"]["usable"] is False
    assert rec(client, case_id).json()["equipment_id"] == "EQ-BP-03"


def test_verified_ready_counts_as_a_fresh_check_and_moving_is_audited(client, symptom_payload):
    out = upd(client, "EQ-BP-02", readiness="verified_ready", zone_id="crew-quarters").json()
    assert out["equipment"]["usable"] and out["equipment"]["zone_id"] == "crew-quarters"
    case_id = client.post(f"{API}/symptoms", json=symptom_payload).json()["case_id"]
    pick = rec(client, case_id).json()
    assert pick["equipment_id"] == "EQ-BP-02" and pick["route_zone_ids"] == ["crew-quarters"]
    from app import models as m
    with client.app.state.session_factory() as db:
        ev = db.query(m.AuditEvent).filter(m.AuditEvent.action == "equipment.status_changed").one()
        assert ev.details["before"]["zone_id"] == "laboratory" and ev.details["after"]["zone_id"] == "crew-quarters"


def test_inventory_validation_and_roles(client):
    assert upd(client, "EQ-NOPE").status_code == 404
    assert upd(client, "EQ-BP-01", supplies={"coffee": True}).json()["error"]["code"] == "UNKNOWN_SUPPLY"
    assert upd(client, "EQ-BP-01", zone_id="moon").json()["error"]["code"] == "UNKNOWN_ZONE"
    assert upd(client, "EQ-BP-01", readiness="broken").status_code == 422
    assert upd(client, "EQ-BP-01", actor="GND-SUP-01", readiness="in_use").status_code == 403
    same = upd(client, "EQ-BP-02", readiness="unknown").json()
    assert same["changed"] is False and same["invalidated_recommendation_ids"] == []


def test_session_using_the_device_is_listed_not_cancelled(client, symptom_payload):
    case_id = client.post(f"{API}/symptoms", json=symptom_payload).json()["case_id"]
    s = client.post(f"{API}/procedure-sessions", json={"case_id": case_id, "procedure_id": "PROC-BP-01",
                                                       "actor_id": "DEMO-001", "mode": "self",
                                                       "equipment_id": "EQ-BP-01"}).json()
    out = upd(client, "EQ-BP-01", readiness="in_use").json()
    assert out["affected_session_ids"] == [s["session_id"]]
    assert client.get(f"{API}/procedure-sessions/{s['session_id']}").json()["status"] == "in_progress"


# --------------------------------------------------------------------------- step 42

def test_resolution_is_blocked_until_open_items_are_closed(client, symptom_payload):
    case_id, s = _session(client, symptom_payload)
    r = resolve(client, case_id)
    assert r.status_code == 409 and r.json()["error"]["code"] == "CASE_NOT_READY_TO_RESOLVE"
    kinds = {b["kind"] for b in r.json()["error"]["details"]["blockers"]}
    assert kinds == {"session_in_progress", "assessment_requested", "state_not_resolvable"}
    _complete(client, s["session_id"])
    client.post(f"{API}/measurements", json=_meas(case_id, s["session_id"]))
    r = resolve(client, case_id)
    assert {b["kind"] for b in r.json()["error"]["details"]["blockers"]} == {"follow_up_outstanding"}
    ok = resolve(client, case_id, close_outstanding_follow_ups=True)
    assert ok.status_code == 200, ok.text
    out = ok.json()
    case = out["case"]
    assert case["state"] == "resolved" and case["resolved_by"] == "DEMO-002" and case["resolution_note"]
    assert out["cancelled_follow_up_ids"] and case["follow_ups"][0]["status"] == "cancelled"
    assert any(a["action"] == "case.resolved" for a in case["audit"])
    again = resolve(client, case_id)
    assert again.status_code == 409 and again.json()["error"]["code"] == "CASE_RESOLVED"
    # a new symptom opens a new case
    sym = {**symptom_payload, "severity": 4, "onset": now_iso(60)}
    assert client.post(f"{API}/symptoms", json=sym).json()["case_id"] != case_id


def test_open_concern_blocks_resolution(client):
    d = open_concern(client)[-1]["detection"]
    r = resolve(client, d["case_id"])
    assert "open_monitoring_concern" in {b["kind"] for b in r.json()["error"]["details"]["blockers"]}


def test_only_clinical_roles_resolve(client, symptom_payload):
    case_id = client.post(f"{API}/symptoms", json=symptom_payload).json()["case_id"]
    for actor in ("DEMO-001", "GND-SUP-01"):
        assert resolve(client, case_id, actor=actor).status_code == 403
    assert resolve(client, case_id, actor="NOBODY").status_code == 404


def test_urgent_emergency_case_resolves_keeps_priority_and_stops_interrupting(client):
    emg = client.post(f"{API}/emergencies", json={"astronaut_id": "DEMO-001", "responder_id": "DEMO-002",
                                                  "trigger": "crew_collapse"}).json()
    r = resolve(client, emg["case_id"], actor="GND-FS-01")
    assert r.status_code == 200, r.text
    case = r.json()["case"]
    assert case["priority"] == "urgent" and case["attention"]["interrupt"] is False
    assert any("has not been acknowledged" in w for w in r.json()["warnings"])

"""Contract 2.5.0: hatch control, stored recommendations and their invalidation, routes from crew location."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tests.conftest import now_iso


def _case(client, symptom_payload):
    return client.post("/api/v1/symptoms", json=symptom_payload).json()["case_id"]


def _rec(client, case_id, **body):
    return client.post("/api/v1/equipment/recommend", json={"case_id": case_id, "capability": "blood_pressure",
                                                            **body})


def _hatch(client, hatch, state, actor="DEMO-002"):
    return client.post(f"/api/v1/habitats/HAB-01/hatches/{hatch}",
                       json={"state": state, "actor_id": actor, "reason": "Fictional maintenance test"})


def _locate(client, zone_rssi: dict, age=2):
    obs = [{"anchor_id": a, "rssi_dbm": r, "observed_at": now_iso(age)} for a, r in zone_rssi.items()]
    return client.post("/api/v1/location/estimate", json={"astronaut_id": "DEMO-001", "observations": obs}).json()


def test_recommendation_is_stored_and_readable(client, symptom_payload):
    rec = _rec(client, _case(client, symptom_payload), zone_id="crew-quarters").json()
    assert rec["recommendation_id"].startswith("REC-") and rec["status"] == "active"
    assert rec["habitat_state_version"] == 1 and rec["start_basis"] == "request_zone"
    again = client.get(f"/api/v1/equipment/recommendations/{rec['recommendation_id']}").json()
    assert again["route_geometry"] == rec["route_geometry"] and again["status"] == "active"
    assert client.get("/api/v1/equipment/recommendations/REC-NOPE").status_code == 404


def test_closing_a_route_hatch_invalidates_and_reroutes(client, symptom_payload):
    case_id = _case(client, symptom_payload)
    via_exercise = _rec(client, case_id, zone_id="crew-quarters").json()
    from_lab = _rec(client, case_id, zone_id="laboratory").json()  # lab -> CQ -> EX -> MED, also via H-EX-MED
    r = _hatch(client, "H-EX-MED", "closed")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["changed"] and out["state_version"] == 2 and out["state"] == "closed"
    assert set(out["invalidated_recommendation_ids"]) == {via_exercise["recommendation_id"],
                                                          from_lab["recommendation_id"]}
    stored = client.get(f"/api/v1/equipment/recommendations/{via_exercise['recommendation_id']}").json()
    assert stored["status"] == "invalidated" and "H-EX-MED" in stored["invalidated_reason"]
    mp = client.get("/api/v1/habitats/HAB-01/map").json()
    assert mp["state_version"] == 2
    assert next(p for p in mp["passages"] if p["hatch_id"] == "H-EX-MED")["hatch_state"] == "closed"
    blocked = _rec(client, case_id, zone_id="crew-quarters")
    assert blocked.status_code == 404 and blocked.json()["error"]["code"] == "NO_SUITABLE_EQUIPMENT"
    reopen = _hatch(client, "H-LAB-MED", "open").json()  # the other way into medical
    assert reopen["state_version"] == 3
    new = _rec(client, case_id, zone_id="crew-quarters").json()
    assert new["route_hatch_ids"] == ["H-CQ-LAB", "H-LAB-MED"] and new["habitat_state_version"] == 3
    audit = client.get(f"/api/v1/cases/{case_id}").json()["audit"]
    assert any(a["action"] == "equipment_recommendation.invalidated" for a in audit)


def test_closing_an_unrelated_hatch_keeps_the_recommendation(client, symptom_payload):
    rec = _rec(client, _case(client, symptom_payload), zone_id="crew-quarters").json()
    out = _hatch(client, "H-CQ-LAB", "closed").json()
    assert out["changed"] and out["invalidated_recommendation_ids"] == []
    stored = client.get(f"/api/v1/equipment/recommendations/{rec['recommendation_id']}").json()
    assert stored["status"] == "active"


def test_opening_a_hatch_invalidates_active_recommendations(client, symptom_payload):
    rec = _rec(client, _case(client, symptom_payload), zone_id="laboratory").json()
    out = _hatch(client, "H-LAB-MED", "open").json()
    assert rec["recommendation_id"] in out["invalidated_recommendation_ids"]


def test_no_change_and_validation(client):
    same = _hatch(client, "H-CQ-EX", "open").json()
    assert same["changed"] is False and same["state_version"] == 1
    assert _hatch(client, "H-NOPE", "closed").status_code == 404
    assert _hatch(client, "H-CQ-EX", "closed", actor="NOBODY").status_code == 403
    bad = client.post("/api/v1/habitats/HAB-01/hatches/H-CQ-EX", json={"state": "ajar", "actor_id": "DEMO-001",
                                                                      "reason": "x x x"})
    assert bad.status_code == 422
    assert client.post("/api/v1/habitats/HAB-99/hatches/H-CQ-EX",
                       json={"state": "closed", "actor_id": "DEMO-001", "reason": "test"}).status_code == 404


def test_hatch_state_survives_restart_and_reset_restores_it(harness):
    c = harness.start()
    _hatch(c, "H-CQ-EX", "closed")
    c = harness.restart()
    mp = c.get("/api/v1/habitats/HAB-01/map").json()
    assert mp["state_version"] == 2 and {p["hatch_id"]: p["hatch_state"] for p in mp["passages"]}["H-CQ-EX"] == "closed"
    c.post("/api/v1/demo/reset")
    mp = c.get("/api/v1/habitats/HAB-01/map").json()
    assert mp["state_version"] == 1 and {p["hatch_id"]: p["hatch_state"] for p in mp["passages"]}["H-CQ-EX"] == "open"


def test_route_from_latest_estimate_for_responder(client, symptom_payload):
    case_id = _case(client, symptom_payload)
    client.post("/api/v1/location/confirm", json={"astronaut_id": "DEMO-002", "zone_id": "exercise",
                                                  "confirmed_by": "DEMO-002"})
    rec = _rec(client, case_id, astronaut_id="DEMO-002", start_role="responder").json()
    assert rec["start_basis"] == "latest_estimate" and rec["start_role"] == "responder"
    assert rec["route_zone_ids"] == ["exercise", "medical"] and rec["start_astronaut_id"] == "DEMO-002"
    assert rec["start_confidence"] == 1.0 and rec["start_uncertainty"] is None


def test_start_requires_a_current_location(client, symptom_payload):
    case_id = _case(client, symptom_payload)
    none = _rec(client, case_id)
    assert none.status_code == 422 and none.json()["error"]["code"] == "START_REQUIRED"
    unknown = _rec(client, case_id, astronaut_id="DEMO-001")
    assert unknown.status_code == 409 and unknown.json()["error"]["code"] == "LOCATION_UNAVAILABLE"
    _locate(client, {"ANC-CQ-01": -50}, age=45)  # stale observations -> unavailable estimate
    assert _rec(client, case_id, astronaut_id="DEMO-001").status_code == 409


def test_uncertain_start_reports_candidates(client, symptom_payload):
    case_id = _case(client, symptom_payload)
    est = _locate(client, {"ANC-CQ-01": -60, "ANC-LAB-01": -62, "ANC-EX-01": -80, "ANC-MED-01": -90})
    assert est["zone_id"] == "crew-quarters" and est["confidence"] < 0.7
    rec = _rec(client, case_id, astronaut_id="DEMO-001").json()
    unc = rec["start_uncertainty"]
    cands = {c["zone_id"]: c["route_hops"] for c in unc["candidates"]}
    assert cands == {"crew-quarters": 2, "laboratory": 3} and unc["hop_spread"] == 1
    assert "may be in another candidate zone" in unc["note"]


def test_unobserved_neighbour_caps_confidence(client):
    est = _locate(client, {"ANC-CQ-01": -55, "ANC-EX-01": -80, "ANC-MED-01": -90})  # no lab anchor reports
    assert est["zone_id"] == "crew-quarters" and est["confidence"] == 0.5
    assert est["unobserved_zone_ids"] == ["laboratory"] and "could be there" in est["explanation"]
    latest = client.get("/api/v1/location/DEMO-001/latest").json()
    assert latest["estimate"]["unobserved_zone_ids"] == ["laboratory"]


def test_older_database_gets_state_version(harness):
    harness.start()
    harness.stop()
    db = Path(harness.db_url.removeprefix("sqlite:///"))
    with sqlite3.connect(db) as conn:
        conn.execute("ALTER TABLE habitats DROP COLUMN state_version")
    c = harness.start()
    assert c.get("/api/v1/habitats/HAB-01/map").json()["state_version"] == 1
    assert _hatch(c, "H-CQ-EX", "closed").json()["state_version"] == 2

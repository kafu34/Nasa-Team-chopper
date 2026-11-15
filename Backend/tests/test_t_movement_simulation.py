"""Contract 2.5.0: repeatable movement simulation through the real location engine (v3.1 §6 location simulation)."""
from __future__ import annotations

import json

import pytest


def run(client, scenario):
    r = client.post("/api/v1/simulation/movement", json={"scenario_id": scenario, "astronaut_id": "DEMO-001"})
    assert r.status_code == 200, r.text
    return r.json()


def test_walk_between_compartments_follows_the_person(client):
    out = run(client, "SIM-WALK-CQ-MED")
    ev = out["evaluation"]
    assert ev["tick_count"] == 9 and ev["zone_matches"] == 9
    zones = [t["estimate"]["zone_id"] for t in out["ticks"]]
    assert zones[0] == "crew-quarters" and zones[-1] == "medical" and "exercise" in zones
    latest = client.get("/api/v1/location/DEMO-001/latest").json()
    assert latest["estimate"]["estimate_id"] == out["ticks"][-1]["estimate"]["estimate_id"]
    assert latest["estimate"]["zone_id"] == "medical" and latest["display_mode"] == "zone_only"


def test_simulation_is_repeatable(client):
    a, b = run(client, "SIM-WALK-CQ-MED"), run(client, "SIM-WALK-CQ-MED")
    rssi = lambda o: [[x["rssi_dbm"] for x in t["generated_observations"]] for t in o["ticks"]]
    assert rssi(a) == rssi(b)


def test_conflicting_passage_signals_are_low_confidence_and_smoothed(client):
    out = run(client, "SIM-CONFLICT-PASSAGE")
    in_passage = [t for t, g in zip(out["ticks"], out["evaluation"]["ground_truth"]) if g["passage_id"]]
    assert in_passage and all(t["estimate"]["confidence"] <= 0.6 for t in in_passage)
    assert any(t["estimate"]["source"] == "ble_simulated_smoothed" for t in in_passage)
    assert out["evaluation"]["zone_matches"] == out["evaluation"]["tick_count"]


def test_missing_anchor_is_flagged_not_confident(client):
    out = run(client, "SIM-MISSING-ANCHOR")
    for t in out["ticks"]:
        e = t["estimate"]
        assert e["confidence"] <= 0.5  # capped: the laboratory has no reporting anchor
        assert any(r["anchor_id"] == "ANC-LAB-02" and r["reason"] == "disabled_anchor" for r in e["rejected"])
        assert all(o["anchor_id"] != "ANC-LAB-01" for o in t["generated_observations"])
    with client.app.state.session_factory() as db:
        from app import models as m
        row = db.get(m.LocationEstimate, out["ticks"][0]["estimate"]["estimate_id"])
        assert row.details["unobserved_zone_ids"] == ["laboratory"]


def test_stale_observations_give_unavailable_not_old_positions(client):
    out = run(client, "SIM-STALE")
    assert out["evaluation"]["unavailable_ticks"] == 2
    assert all(t["estimate"]["display_mode"] == "unavailable" for t in out["ticks"])
    for t in out["ticks"]:
        reasons = {r["anchor_id"]: r["reason"] for r in t["estimate"]["rejected"]}
        assert reasons.pop("ANC-LAB-02") == "disabled_anchor"  # checked before age
        assert set(reasons.values()) == {"stale_signal"} and len(reasons) == 4
    assert client.get("/api/v1/location/DEMO-001/latest").json()["display_mode"] == "unavailable"


def test_ground_truth_never_reaches_user_facing_endpoints(client, symptom_payload):
    out = run(client, "SIM-WALK-CQ-MED")
    truth_points = [g["point"] for g in out["evaluation"]["ground_truth"]]
    case_id = client.post("/api/v1/symptoms", json=symptom_payload).json()["case_id"]
    responses = [client.get("/api/v1/location/DEMO-001/latest").json(),
                 client.get("/api/v1/habitats/HAB-01/map").json(),
                 client.post("/api/v1/equipment/recommend", json={"case_id": case_id, "capability": "blood_pressure",
                                                                  "astronaut_id": "DEMO-001"}).json()]
    text = json.dumps(responses)
    assert "ground_truth" not in text and "true_zone_id" not in text
    latest = responses[0]
    assert latest["estimate"]["position"] is None
    mid = truth_points[3]  # an interior point, not a navigation reference or hatch point
    assert json.dumps(mid) not in text
    with client.app.state.session_factory() as db:
        from app import models as m
        assert all("ground_truth" not in json.dumps(r.details) for r in db.query(m.LocationEstimate))


def test_unknown_scenario_and_astronaut(client):
    assert client.post("/api/v1/simulation/movement",
                       json={"scenario_id": "SIM-NOPE", "astronaut_id": "DEMO-001"}).status_code == 404
    assert client.post("/api/v1/simulation/movement",
                       json={"scenario_id": "SIM-STALE", "astronaut_id": "NOBODY"}).status_code == 404

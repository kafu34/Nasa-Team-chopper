"""Part C: zone estimation and equipment recommendation."""
from datetime import timedelta

from app import models as m
from app.db import utcnow
from tests.conftest import now_iso


def _obs(anchor, rssi, age=1):
    return {"anchor_id": anchor, "rssi_dbm": rssi, "observed_at": now_iso(age)}


def _case(client, symptom_payload):
    return client.post("/api/v1/symptoms", json=symptom_payload).json()["case_id"]


def test_fixture_observations_estimate_crew_quarters(client, ble_payload):
    r = client.post("/api/v1/location/estimate", json=ble_payload)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["zone_id"] == "crew-quarters" and b["source"] == "ble_simulated"
    assert 0.5 < b["confidence"] <= 0.95
    assert {"anchor_id": "ANC-UNKNOWN-99", "reason": "unknown_anchor"} in b["rejected"]
    assert "ANC-UNKNOWN-99" not in b["used_anchor_ids"]
    assert b["observed_at"] is not None and "exact distance" in b["limitation"]


def test_unknown_anchor_strongest_signal_is_ignored(client):
    r = client.post("/api/v1/location/estimate", json={"astronaut_id": "DEMO-001", "observations": [
        _obs("ANC-FAKE", -30), _obs("ANC-MED-01", -70)]}).json()
    assert r["zone_id"] == "medical"


def test_stale_and_disabled_signals_rejected(client):
    r = client.post("/api/v1/location/estimate", json={"astronaut_id": "DEMO-001", "observations": [
        _obs("ANC-CQ-01", -50, age=120), _obs("ANC-LAB-02", -45)]}).json()
    reasons = {x["anchor_id"]: x["reason"] for x in r["rejected"]}
    assert reasons == {"ANC-CQ-01": "stale_signal", "ANC-LAB-02": "disabled_anchor"}
    assert r["zone_id"] is None and r["confidence"] == 0 and r["source"] == "unavailable"


def test_missing_signals_returns_unavailable(client):
    r = client.post("/api/v1/location/estimate", json={"astronaut_id": "DEMO-001", "observations": []})
    assert r.status_code == 200 and r.json()["source"] == "unavailable" and r.json()["zone_id"] is None


def test_conflicting_signals_low_confidence_and_hysteresis(client):
    first = client.post("/api/v1/location/estimate", json={"astronaut_id": "DEMO-001", "observations": [
        _obs("ANC-CQ-01", -50), _obs("ANC-LAB-01", -70)]}).json()
    assert first["zone_id"] == "crew-quarters"
    conflict = client.post("/api/v1/location/estimate", json={"astronaut_id": "DEMO-001", "observations": [
        _obs("ANC-CQ-01", -61), _obs("ANC-LAB-01", -60)]}).json()
    assert conflict["zone_id"] == "crew-quarters" and conflict["source"] == "ble_simulated_smoothed"
    assert conflict["confidence"] < 0.6


def test_rssi_validation(client):
    r = client.post("/api/v1/location/estimate", json={"astronaut_id": "DEMO-001",
                                                        "observations": [_obs("ANC-CQ-01", 20)]})
    assert r.status_code == 422


def test_manual_confirmation(client):
    r = client.post("/api/v1/location/confirm", json={"astronaut_id": "DEMO-001", "zone_id": "exercise",
                                                       "confirmed_by": "DEMO-002"}).json()
    assert r["source"] == "manual" and r["confidence"] == 1.0 and r["zone_id"] == "exercise"


def test_recommend_ready_bp_monitor_with_accessible_route(client, symptom_payload, fixture_data):
    case_id = _case(client, symptom_payload)
    r = client.post("/api/v1/equipment/recommend", json={"case_id": case_id, "zone_id": "crew-quarters",
                                                          "capability": "blood_pressure"})
    assert r.status_code == 200, r.text
    b = r.json()
    exp = fixture_data["expected_recommendation"]
    assert b["equipment_id"] == exp["equipment_id"] == "EQ-BP-01"
    assert b["route_zone_ids"] == exp["route_zone_ids"] == ["crew-quarters", "exercise", "medical"]
    assert b["readiness"] == "verified_ready" and b["procedure_id"] == "PROC-BP-01"
    excl = {e["equipment_id"]: e["reasons"] for e in b["excluded"]}
    assert excl["EQ-BP-02"] == ["readiness_unknown"]
    assert excl["EQ-BP-03"] == ["missing_supplies:cuff_adult_standard"]


def test_route_avoids_inaccessible_connection(client, symptom_payload):
    case_id = _case(client, symptom_payload)
    b = client.post("/api/v1/equipment/recommend", json={"case_id": case_id, "zone_id": "laboratory",
                                                          "capability": "blood_pressure"}).json()
    assert b["route_zone_ids"] == ["laboratory", "crew-quarters", "exercise", "medical"]


def test_stale_readiness_is_not_ready(client, symptom_payload):
    case_id = _case(client, symptom_payload)
    with client.app.state.session_factory() as db:
        db.get(m.Equipment, "EQ-BP-01").readiness_verified_at = utcnow() - timedelta(hours=30)
        db.commit()
    r = client.post("/api/v1/equipment/recommend", json={"case_id": case_id, "zone_id": "crew-quarters",
                                                          "capability": "blood_pressure"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "NO_SUITABLE_EQUIPMENT"
    reasons = {e["equipment_id"]: e["reasons"] for e in r.json()["error"]["details"]["excluded"]}
    assert reasons["EQ-BP-01"] == ["readiness_check_stale"]


def test_unreachable_zone_excluded(client, symptom_payload):
    case_id = _case(client, symptom_payload)
    with client.app.state.session_factory() as db:
        for c in db.query(m.ZoneConnection).filter(m.ZoneConnection.to_zone_id == "medical"):
            c.accessible = False
        db.commit()
    r = client.post("/api/v1/equipment/recommend", json={"case_id": case_id, "zone_id": "crew-quarters",
                                                          "capability": "blood_pressure"})
    assert r.status_code == 404
    reasons = {e["equipment_id"]: e["reasons"] for e in r.json()["error"]["details"]["excluded"]}
    assert "zone_not_accessible" in reasons["EQ-BP-01"]


def test_recommend_unknown_case_zone_capability(client, symptom_payload):
    case_id = _case(client, symptom_payload)
    assert client.post("/api/v1/equipment/recommend", json={"case_id": "X", "zone_id": "medical",
                                                             "capability": "blood_pressure"}).status_code == 404
    assert client.post("/api/v1/equipment/recommend", json={"case_id": case_id, "zone_id": "attic",
                                                             "capability": "blood_pressure"}).status_code == 404
    r = client.post("/api/v1/equipment/recommend", json={"case_id": case_id, "zone_id": "medical",
                                                          "capability": "mri"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "NO_SUITABLE_EQUIPMENT"

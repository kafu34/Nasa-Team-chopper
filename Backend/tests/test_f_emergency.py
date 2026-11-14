"""Part F: emergency activation without localisation."""
from app import models as m

EMERGENCY = {"astronaut_id": "DEMO-001", "responder_id": "DEMO-002", "trigger": "crew_collapse"}


def test_emergency_without_any_localisation(client):
    with client.app.state.session_factory() as db:
        assert db.query(m.LocationEstimate).count() == 0
        for a in db.query(m.WirelessAnchor):
            a.enabled = False  # localisation completely unavailable
        db.commit()
    r = client.post("/api/v1/emergencies", json=EMERGENCY)
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["priority"] == "urgent" and b["case_state"] == "escalated" and b["localisation_required"] is False
    assert b["attention"]["interrupt"] is True
    assert b["crew_alert"]["status"] == "simulated_alert_raised"
    assert b["flight_surgeon_escalation"]["status"] == "queued_for_transmission"
    assert b["emergency_information"]["reviewed_procedure_available"] is False
    assert "does not provide treatment" in b["emergency_information"]["limitation"]
    assert b["equipment_assistance"]["required_to_start_response"] is False
    case = client.get(f"/api/v1/cases/{b['case_id']}").json()
    assert case["kind"] == "emergency" and case["priority"] == "urgent"
    assert any(a["action"] == "emergency.activated" for a in case["audit"])


def test_emergency_crew_actions_contain_no_treatment(client):
    actions = " ".join(client.post("/api/v1/emergencies", json=EMERGENCY).json()["emergency_information"]["crew_actions"]).lower()
    for word in ("mg", "dose", "inject", "medication", "aspirin", "compress", "cpr"):
        assert word not in actions


def test_duplicate_activation(client):
    first = client.post("/api/v1/emergencies", json=EMERGENCY).json()
    r = client.post("/api/v1/emergencies", json={**EMERGENCY, "trigger": "manual_activation"})
    assert r.status_code == 200 and r.json()["duplicate"] is True and r.json()["case_id"] == first["case_id"]


def test_acknowledge_does_not_resolve_urgent_case(client):
    case_id = client.post("/api/v1/emergencies", json=EMERGENCY).json()["case_id"]
    r = client.post(f"/api/v1/cases/{case_id}/acknowledge", json={"actor_id": "DEMO-002"}).json()
    assert r["state"] == "escalated" and r["priority"] == "urgent" and r["acknowledged_by"] == "DEMO-002"


def test_emergency_validation(client):
    assert client.post("/api/v1/emergencies", json={**EMERGENCY, "trigger": "bored"}).status_code == 422
    assert client.post("/api/v1/emergencies", json={**EMERGENCY, "responder_id": "NOPE"}).status_code == 404


def test_equipment_assist_is_independent_secondary_step(client):
    case_id = client.post("/api/v1/emergencies", json=EMERGENCY).json()["case_id"]
    r = client.post("/api/v1/equipment/recommend", json={"case_id": case_id, "zone_id": "crew-quarters",
                                                          "capability": "aed"})
    assert r.status_code == 200 and r.json()["equipment_id"] == "EQ-AED-01"

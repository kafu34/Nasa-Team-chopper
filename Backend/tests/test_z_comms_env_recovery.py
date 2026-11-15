"""Contract 2.10.0: communications queue (step 37), environmental context (step 38), offline and recovery (39)."""
from __future__ import annotations

from datetime import timedelta

from app import models as m
from app.db import utcnow
from tests.test_u_health_intelligence import API, obs, open_concern

EMERGENCY = {"astronaut_id": "DEMO-001", "responder_id": "DEMO-002", "trigger": "crew_collapse"}


def send(client, sender="DEMO-002", direction="to_ground", priority="routine", subject="Daily report", **kw):
    r = client.post(f"{API}/comms/messages", json={"sender_id": sender, "direction": direction, "priority": priority,
                                                   "subject": subject, "body": "Fictional demonstration message.",
                                                   **kw})
    return r


def age_all(client, seconds):
    """Move every comms time back, as if `seconds` had passed (no sleeping in tests)."""
    with client.app.state.session_factory() as db:
        d = timedelta(seconds=seconds)
        for msg in db.query(m.CommsMessage):
            msg.created_at -= d
            msg.transmit_at = msg.transmit_at - d if msg.transmit_at else None
            msg.deliver_at = msg.deliver_at - d if msg.deliver_at else None
        lk = db.get(m.CommsLink, "LINK-HAB-01-GROUND")
        if lk:
            lk.changed_at -= d
        db.commit()


def msg(client, mid):
    return client.get(f"{API}/comms/messages/{mid}").json()


# --------------------------------------------------------------------------- step 37

def test_message_is_delayed_then_delivered_then_acknowledged_by_the_ground(client):
    r = send(client)
    assert r.status_code == 201, r.text
    m1 = r.json()
    assert m1["status"] == "in_transit" and m1["simulated"] and m1["recipient_role"] == "flight_surgeon"
    early = client.post(f"{API}/comms/messages/{m1['message_id']}/acknowledge", json={"actor_id": "GND-FS-01"})
    assert early.status_code == 409 and early.json()["error"]["code"] == "NOT_DELIVERED"
    age_all(client, 306)
    assert msg(client, m1["message_id"])["status"] == "delivered"
    wrong = client.post(f"{API}/comms/messages/{m1['message_id']}/acknowledge", json={"actor_id": "DEMO-001"})
    assert wrong.status_code == 403
    ok = client.post(f"{API}/comms/messages/{m1['message_id']}/acknowledge", json={"actor_id": "GND-FS-01"}).json()
    assert ok["status"] == "acknowledged" and ok["acknowledged_by"] == "GND-FS-01"
    again = client.post(f"{API}/comms/messages/{m1['message_id']}/acknowledge", json={"actor_id": "GND-FS-01"})
    assert again.status_code == 200 and again.json()["acknowledged_at"] == ok["acknowledged_at"]


def test_roles_for_sending(client):
    assert send(client, sender="GND-FS-01", direction="to_ground").status_code == 403
    assert send(client, sender="DEMO-001", direction="to_crew").status_code == 403
    assert send(client, sender="GND-SUP-01", direction="to_crew").status_code == 201
    assert send(client, sender="NOBODY").status_code == 404
    assert send(client, case_id="CASE-NOPE").status_code == 404


def test_resend_after_lost_response_is_idempotent(client):
    a = send(client, client_message_id="CLIENT-42")
    b = send(client, client_message_id="CLIENT-42")
    assert a.status_code == 201 and b.status_code == 200 and b.json()["duplicate"]
    assert a.json()["message_id"] == b.json()["message_id"]
    assert len(client.get(f"{API}/comms/messages").json()["messages"]) == 1


def test_outage_queues_messages_and_urgent_goes_first_on_restore(client):
    down = client.post(f"{API}/comms/link", json={"state": "down", "actor_id": "DEMO-002", "reason": "Simulated LOS"})
    assert down.status_code == 200 and down.json()["state"] == "down" and down.json()["outage_count"] == 1
    routine = send(client, subject="Routine report").json()
    urgent = send(client, priority="urgent", subject="Urgent question").json()
    assert routine["status"] == urgent["status"] == "queued"
    age_all(client, 400)  # time passes during the outage: still nothing sent
    assert msg(client, routine["message_id"])["status"] == "queued"
    client.post(f"{API}/comms/link", json={"state": "up", "actor_id": "DEMO-002", "reason": "Signal restored"})
    r, u = msg(client, routine["message_id"]), msg(client, urgent["message_id"])
    assert u["status"] == "in_transit" and r["status"] == "queued"  # one transmission at a time, urgent first
    age_all(client, 6)  # the 5-second transmission slot has passed
    r, u = msg(client, routine["message_id"]), msg(client, urgent["message_id"])
    assert r["status"] == "in_transit"
    assert u["transmit_at"] < r["transmit_at"] and u["deliver_at"] < r["deliver_at"]
    listing = client.get(f"{API}/comms/messages").json()
    assert [x["priority"] for x in listing["messages"]] == ["urgent", "routine"]


def test_message_already_sent_keeps_travelling_during_an_outage(client):
    sent = send(client).json()
    client.post(f"{API}/comms/link", json={"state": "down", "actor_id": "DEMO-002", "reason": "Simulated LOS"})
    age_all(client, 306)
    assert msg(client, sent["message_id"])["status"] == "delivered"


def test_only_the_flight_surgeon_acknowledges_medical_messages_to_the_ground(client):
    """2.11.1: the addressee acknowledges, not any ground role (found in Codex's live browser check)."""
    out = client.post(f"{API}/emergencies", json=EMERGENCY).json()
    mid = out["flight_surgeon_escalation"]["message_id"]
    routine = send(client).json()["message_id"]
    age_all(client, 320)
    for m_id in (mid, routine):
        assert msg(client, m_id)["status"] == "delivered"
        denied = client.post(f"{API}/comms/messages/{m_id}/acknowledge", json={"actor_id": "GND-SUP-01"})
        assert denied.status_code == 403 and denied.json()["error"]["code"] == "ROLE_NOT_PERMITTED"
        assert denied.json()["error"]["details"]["allowed_roles"] == ["flight_surgeon"]
        assert msg(client, m_id)["status"] == "delivered"  # still waiting for the flight surgeon
    ok = client.post(f"{API}/comms/messages/{mid}/acknowledge", json={"actor_id": "GND-FS-01"}).json()
    assert ok["status"] == "acknowledged" and ok["acknowledged_by"] == "GND-FS-01"
    matrix = {p["action"]: p["allowed_roles"] for p in client.get(f"{API}/access/roles").json()["permissions"]}
    assert matrix["comms.acknowledge_to_ground"] == ["flight_surgeon"]
    assert matrix["comms.acknowledge_to_crew"] == ["crew_medical_officer", "crew_member"]


def test_emergency_queues_an_urgent_message_to_the_flight_surgeon(client):
    out = client.post(f"{API}/emergencies", json=EMERGENCY).json()
    mid = out["flight_surgeon_escalation"]["message_id"]
    m1 = msg(client, mid)
    assert m1["priority"] == "urgent" and m1["direction"] == "to_ground" and m1["case_id"] == out["case_id"]
    dup = client.post(f"{API}/emergencies", json=EMERGENCY).json()
    assert dup["duplicate"] and dup["flight_surgeon_escalation"]["message_id"] == mid
    assert len(client.get(f"{API}/comms/messages", params={"case_id": out["case_id"]}).json()["messages"]) == 1
    assert out["crew_alert"]["status"] == "simulated_alert_raised"  # onboard response does not wait


def test_ground_reply_reaches_the_crew_and_crew_acknowledges(client):
    reply = send(client, sender="GND-FS-01", direction="to_crew", priority="urgent", subject="Advice").json()
    age_all(client, 306)
    assert client.post(f"{API}/comms/messages/{reply['message_id']}/acknowledge",
                       json={"actor_id": "GND-FS-01"}).status_code == 403
    ok = client.post(f"{API}/comms/messages/{reply['message_id']}/acknowledge", json={"actor_id": "DEMO-001"})
    assert ok.status_code == 200 and ok.json()["status"] == "acknowledged"


# --------------------------------------------------------------------------- step 38

def test_environment_context_is_attributed_and_cautious(client):
    out = client.get(f"{API}/environment/context", params={"astronaut_id": "DEMO-001"}).json()
    rad = out["radiation"]
    assert rad["dataset_id"] == "NASA-RADLAB" and rad["is_habitat_reading"] is False
    assert rad["is_personal_dose"] is False and out["health_relationship"] == "none_inferred"
    assert "not readings from the fictional HAB-01" in out["caution"]
    assert out["atmosphere"]["dataset_id"] == "NASA-EDA" and "BLOCKED" in out["atmosphere"]["note"]
    if rad["status"] == "IMPORTED":
        assert rad["latest_readings"] and all(r["unit"] for r in rad["latest_readings"])
    else:
        assert rad["latest_readings"] == []  # nothing invented when the snapshot is not imported


def test_environment_context_with_imported_radlab(harness):
    from pathlib import Path
    import shutil

    from app.config import REPO_DIR

    src = REPO_DIR / "data" / "nasa" / "raw" / "NASA-RADLAB"
    files = list(src.glob("radlab_ISS_2022-04-01.*"))
    if not files:
        import pytest
        pytest.skip("RadLab snapshot not present in this checkout")
    (harness.raw / "NASA-RADLAB").mkdir()
    for f in files:
        shutil.copyfile(f, harness.raw / "NASA-RADLAB" / f.name)
    c = harness.start(auto_import=True)
    rad = c.get(f"{API}/environment/context").json()["radiation"]
    assert rad["status"] == "IMPORTED" and rad["latest_readings"]
    first = rad["latest_readings"][0]
    assert first["spacecraft"] and first["source_file"].startswith("radlab_ISS") and first["source_row_number"] > 0


# --------------------------------------------------------------------------- step 39

def test_recovery_lists_what_a_client_must_restore(client, symptom_payload):
    case_id = client.post(f"{API}/symptoms", json=symptom_payload).json()["case_id"]
    s = client.post(f"{API}/procedure-sessions", json={"case_id": case_id, "procedure_id": "PROC-BP-01",
                                                       "actor_id": "DEMO-001", "mode": "self"}).json()
    client.post(f"{API}/comms/link", json={"state": "down", "actor_id": "DEMO-002", "reason": "Simulated LOS"})
    queued = send(client).json()
    rec = client.get(f"{API}/system/recovery").json()
    assert s["session_id"] in rec["open_session_ids"] and case_id in rec["open_case_ids"]
    assert queued["message_id"] in rec["undelivered_message_ids"] and rec["link_state"] == "down"
    assert "REM-SA-TEMP-001-overdue" in rec["open_reminder_ids"]
    assert any("GET /system/recovery" in line for line in rec["loss_of_server_behaviour"])


def test_restart_mid_session_mid_outage_and_mid_concern(harness, symptom_payload):
    c = harness.start()
    case_id = c.post(f"{API}/symptoms", json=symptom_payload).json()["case_id"]
    s = c.post(f"{API}/procedure-sessions", json={"case_id": case_id, "procedure_id": "PROC-BP-01",
                                                  "actor_id": "DEMO-001", "mode": "self"}).json()
    c.post(f"{API}/procedure-sessions/{s['session_id']}/steps", json={"step_id": "S1", "completion_source": "self_confirmed"})
    d = open_concern(c)[-1]["detection"]
    c.post(f"{API}/comms/link", json={"state": "down", "actor_id": "DEMO-002", "reason": "Simulated LOS"})
    queued = send(c).json()
    c = harness.restart()  # server lost and restarted
    sess = c.get(f"{API}/procedure-sessions/{s['session_id']}").json()
    assert sess["completed_count"] == 1 and sess["current_step_id"] == "S2"
    assert c.get(f"{API}/monitoring-concerns/{d['concern_id']}").json()["status"] == "open"
    assert msg(c, queued["message_id"])["status"] == "queued" and c.get(f"{API}/comms/link").json()["state"] == "down"
    c.post(f"{API}/comms/link", json={"state": "up", "actor_id": "DEMO-002", "reason": "Signal restored"})
    assert msg(c, queued["message_id"])["status"] == "in_transit"


def test_restart_mid_transmission_delivers_on_time(harness):
    c = harness.start()
    sent = send(c).json()
    c = harness.restart()
    assert msg(c, sent["message_id"])["status"] == "in_transit"
    age_all(c, 306)
    assert msg(c, sent["message_id"])["status"] == "delivered"


def test_lost_responses_can_be_resent_safely(client):
    o1 = obs(client, 70, 5)
    body = {k: o1[k] for k in ("astronaut_id", "type", "value", "unit", "source", "quality", "observed_at")}
    o2 = client.post(f"{API}/observations", json=body).json()
    assert o2["duplicate"] and o2["observation_id"] == o1["observation_id"]
    a = send(client, client_message_id="RETRY-1").json()
    b = send(client, client_message_id="RETRY-1").json()
    assert b["duplicate"] and a["message_id"] == b["message_id"]


def test_reset_clears_comms_and_restores_link(client):
    client.post(f"{API}/comms/link", json={"state": "down", "actor_id": "DEMO-002", "reason": "Simulated LOS"})
    send(client)
    client.post(f"{API}/demo/reset")
    assert client.get(f"{API}/comms/messages").json()["messages"] == []
    assert client.get(f"{API}/comms/link").json()["state"] == "up"

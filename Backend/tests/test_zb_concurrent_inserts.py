"""Regression: check-then-insert races on unique keys must not return 500 (found in a live browser check).

Each test lets a competing request commit the same row just before ours writes it, which is the losing
interleaving of two overlapping requests. The reminder case is in test_y_screening_access.py.
"""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import event

from app import models as m
from app.db import utcnow
from tests.conftest import now_iso
from tests.test_u_health_intelligence import API


@contextmanager
def competitor(client, table: str, write):
    engine, factory, fired = client.app.state.engine, client.app.state.session_factory, {"done": False}

    def before(conn, cursor, statement, params, context, executemany):
        if fired["done"] or f"INSERT INTO {table}" not in statement:
            return
        fired["done"] = True
        with factory() as other:
            write(other)
            other.commit()

    event.listen(engine, "before_cursor_execute", before)
    try:
        yield fired
    finally:
        event.remove(engine, "before_cursor_execute", before)


def test_first_link_creation_race(client):
    with client.app.state.session_factory() as db:
        db.query(m.CommsLink).delete()
        db.commit()
    with competitor(client, "comms_links", lambda s: s.add(m.CommsLink(
            link_id="LINK-HAB-01-GROUND", state="up", changed_at=utcnow(), changed_by="other-request",
            reason="created by the competing request", outage_count=0))) as fired:
        r = client.get(f"{API}/system/recovery")
    assert fired["done"] and r.status_code == 200, r.text
    assert client.get(f"{API}/comms/link").json()["changed_by"] == "other-request"  # one row, the winner's


def test_simultaneous_resend_returns_the_first_message(client):
    def first(s):
        s.add(m.CommsMessage(message_id="MSG-WINNER", client_message_id="CLIENT-RACE", direction="to_ground",
                             priority="routine", sender_id="DEMO-002", sender_role="crew_medical_officer",
                             recipient_role="flight_surgeon", case_id=None, subject="Report", body="Fictional.",
                             status="queued", created_at=utcnow()))
    client.get(f"{API}/comms/link")  # the link row exists, so the only insert left is the message
    with competitor(client, "comms_messages", first) as fired:
        r = client.post(f"{API}/comms/messages", json={"sender_id": "DEMO-002", "direction": "to_ground",
                                                       "subject": "Report", "body": "Fictional.",
                                                       "client_message_id": "CLIENT-RACE"})
    assert fired["done"] and r.status_code == 200, r.text
    assert r.json()["duplicate"] and r.json()["message_id"] == "MSG-WINNER"
    assert len(client.get(f"{API}/comms/messages").json()["messages"]) == 1


def test_simultaneous_step_event_returns_the_first_event(client, symptom_payload):
    case_id = client.post(f"{API}/symptoms", json=symptom_payload).json()["case_id"]
    sid = client.post(f"{API}/procedure-sessions", json={"case_id": case_id, "procedure_id": "PROC-BP-01",
                                                         "actor_id": "DEMO-001", "mode": "self"}).json()["session_id"]
    body = {"step_id": "S1", "event_type": "instruction_displayed", "visual_action_id": "VA-BP-01-PREPARE-EQUIPMENT",
            "actor_id": "DEMO-001", "client_event_id": f"{sid}:S1:instruction_displayed", "occurred_at": now_iso(1)}

    def first(s):
        s.add(m.ProcedureStepEvent(event_id="PSE-WINNER", session_id=sid, step_id="S1",
                                   event_type="instruction_displayed", visual_action_id="VA-BP-01-PREPARE-EQUIPMENT",
                                   client_event_id=body["client_event_id"], actor_id="DEMO-001",
                                   occurred_at=utcnow(), recorded_at=utcnow()))
    with competitor(client, "procedure_step_events", first) as fired:
        r = client.post(f"{API}/procedure-sessions/{sid}/events", json=body)
    assert fired["done"] and r.status_code == 200, r.text
    assert r.json()["duplicate"] and r.json()["event_id"] == "PSE-WINNER"
    states = client.get(f"{API}/procedure-sessions/{sid}").json()["step_states"]
    assert next(x for x in states if x["step_id"] == "S1")["displayed_at"] is not None

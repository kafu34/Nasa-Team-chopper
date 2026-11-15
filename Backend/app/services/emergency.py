"""Simulated emergency activation.

Runs synchronously with local SQLite only. It does not call localisation, equipment recommendation, AR,
NASA data loading, cloud AI or Earth communication.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import RULESET_VERSION
from ..db import utcnow
from ..errors import not_found
from ..schemas.emergency import (CrewAlert, EmergencyCreate, EmergencyInformation, EmergencyOut, EquipmentAssistance,
                                 FlightSurgeonEscalation)
from . import cases as case_svc
from .audit import audit

DUPLICATE_WINDOW = timedelta(minutes=10)

LIMITATION = ("No reviewed mission emergency medical procedure is loaded in this prototype. SENTINEL does not "
              "provide treatment instructions, medications or invasive procedures.")
CREW_ACTIONS = [
    "Make sure the area is safe for you and the crew member.",
    "Call other crew members to help immediately using the habitat alarm or voice loop.",
    "Follow your mission's approved emergency medical procedures and the Crew Medical Officer's direction.",
    "Contact the flight surgeon as soon as communication allows.",
    "If it is safe, note what happened and when.",
]
NEXT_ACTION = ("URGENT: crew response in progress. Follow approved mission emergency procedures and the Crew "
               "Medical Officer. Flight-surgeon escalation is queued.")


def _out(case: m.MedicalCase, ev: m.EmergencyEvent, duplicate: bool) -> EmergencyOut:
    return EmergencyOut(
        emergency_id=ev.emergency_id, case_id=case.case_id, case_state=case.state, priority="urgent",
        attention=case_svc.attention_for(case), astronaut_id=ev.astronaut_id, responder_id=ev.responder_id,
        trigger=ev.trigger, activated_at=ev.activated_at, duplicate=duplicate,
        crew_alert=CrewAlert(status="simulated_alert_raised",
                             message=f"Simulated crew alert: medical emergency for {ev.astronaut_id}."),
        flight_surgeon_escalation=FlightSurgeonEscalation(
            status="queued_for_transmission",
            note="Earth communication may be delayed or unavailable. Onboard crew response does not wait for it."),
        emergency_information=EmergencyInformation(reviewed_procedure_available=False, limitation=LIMITATION,
                                                   crew_actions=CREW_ACTIONS),
        equipment_assistance=EquipmentAssistance(
            available=True, endpoint="/api/v1/equipment/recommend", suggested_capabilities=["aed", "emergency_kit"],
            note="Optional secondary step. Not required to begin the crew response."),
        next_action=case.next_action)


def activate(db: Session, body: EmergencyCreate) -> tuple[EmergencyOut, bool]:
    for pid in (body.astronaut_id, body.responder_id):
        if db.get(m.Astronaut, pid) is None:
            raise not_found("Astronaut", pid)
    now = utcnow()
    case = case_svc.open_case(db, body.astronaut_id, "emergency")
    if case is not None and now - case.created_at < DUPLICATE_WINDOW:
        ev = db.scalars(select(m.EmergencyEvent).where(m.EmergencyEvent.case_id == case.case_id)
                        .order_by(m.EmergencyEvent.activated_at.desc())).first()
        audit(db, body.responder_id, "emergency.duplicate_activation", "emergency_event", ev.emergency_id,
              case.case_id, trigger=body.trigger)
        db.commit()
        return _out(case, ev, True), False

    case = m.MedicalCase(case_id=m.new_id("CASE"), astronaut_id=body.astronaut_id, kind="emergency", state="detected",
                         priority="urgent", evidence=[], next_action=NEXT_ACTION, follow_up_status="none",
                         ruleset_version=RULESET_VERSION, created_at=now, updated_at=now, urgent_since=now,
                         priority_reason=f"Emergency activated: {body.trigger}",
                         urgent_instruction="URGENT: crew response in progress.")
    db.add(case)
    db.flush()
    ev = m.EmergencyEvent(emergency_id=m.new_id("EMG"), case_id=case.case_id, astronaut_id=body.astronaut_id,
                          responder_id=body.responder_id, trigger=body.trigger, activated_at=now)
    db.add(ev)
    audit(db, body.responder_id, "emergency.activated", "emergency_event", ev.emergency_id, case.case_id,
          trigger=body.trigger, localisation_required=False)
    case_svc.add_evidence(case, "emergency", ev.emergency_id, f"Emergency activated: {body.trigger}")
    case_svc.transition(db, case, "escalated", "emergency-engine",
                        "Emergency activation: crew alert raised, flight-surgeon escalation queued")
    db.commit()
    return _out(case, ev, False), True

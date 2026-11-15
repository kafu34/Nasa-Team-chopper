"""Preventive screening (plan step 35, contract 2.9.0).

Rules
-----
S-1  due_state: `completed`; `upcoming` before due_at; `due` until due_at + grace_hours; `overdue` after that.
S-2  Durable reminders: one row per assessment and kind (`due`, `overdue`), created the first time the state is
     seen. Acknowledging a reminder never completes the assessment. Completion closes its open reminders.
S-3  A recorded measurement from the assessment's procedure completes every due or overdue assessment of that
     astronaut and procedure, and schedules the next one (due_at = completion + interval_hours).
S-4  Starting a screening opens (or joins) a routine case with no symptom needed. The schedule is fictional
     demonstration configuration, not a clinical recommendation.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .. import models as m
from ..config import RULESET_VERSION
from ..db import utcnow
from ..errors import ApiError, not_found
from ..schemas.demo import ScheduledAssessmentOut
from . import cases as case_svc
from .audit import audit

NEXT_ACTION_SCREENING = ("Complete the scheduled demonstration screening ({procedure_id}). This is a fictional "
                         "schedule, not a clinical recommendation.")


def due_state(a: m.ScheduledAssessment, now: datetime) -> str:
    if a.status == "completed":
        return "completed"
    if now < a.due_at:
        return "upcoming"
    if a.grace_hours is None or now < a.due_at + timedelta(hours=a.grace_hours):
        return "due"
    return "overdue"


def assessment_out(a: m.ScheduledAssessment, now: datetime | None = None) -> ScheduledAssessmentOut:
    now = now or utcnow()
    return ScheduledAssessmentOut(
        assessment_id=a.assessment_id, astronaut_id=a.astronaut_id, title=a.title, capability=a.capability,
        procedure_id=a.procedure_id, due_at=a.due_at, status=a.status,
        is_due=a.status == "scheduled" and a.due_at <= now, reason=a.reason, case_id=a.case_id,
        completed_at=a.completed_at, due_state=due_state(a, now),
        overdue_at=a.due_at + timedelta(hours=a.grace_hours) if a.grace_hours is not None else None,
        interval_hours=a.interval_hours, grace_hours=a.grace_hours, series_id=a.series_id or a.assessment_id,
        sequence=a.sequence or 1, symptom_linked=a.symptom_linked if a.symptom_linked is not None else True,
        completed_by_measurement_id=a.completed_by_measurement_id)


def get(db: Session, assessment_id: str) -> m.ScheduledAssessment:
    a = db.get(m.ScheduledAssessment, assessment_id)
    if a is None:
        raise not_found("Scheduled assessment", assessment_id)
    return a


def refresh(db: Session, astronaut_id: str, now: datetime | None = None) -> list[m.ScheduledAssessment]:
    """Creates any missing due/overdue reminders (rule S-2). Commits only when something changed."""
    now = now or utcnow()
    rows = db.scalars(select(m.ScheduledAssessment).where(m.ScheduledAssessment.astronaut_id == astronaut_id)
                      .order_by(m.ScheduledAssessment.assessment_id)).all()
    changed = False
    for a in rows:
        state = due_state(a, now)
        kinds = {"due": ["due"], "overdue": ["due", "overdue"]}.get(state, [])
        for kind in kinds:
            # One atomic statement: two overlapping requests (e.g. the screen loading assessments and reminders at
            # once) can no longer both insert the same reminder and fail on the unique key (500). Only the request
            # that actually created the row writes the audit entry.
            rid = f"REM-{a.assessment_id}-{kind}"
            created = db.execute(sqlite_insert(m.AssessmentReminder).values(
                reminder_id=rid, assessment_id=a.assessment_id, astronaut_id=astronaut_id, kind=kind, status="open",
                created_at=now).on_conflict_do_nothing()).rowcount
            if created:
                audit(db, "screening-manager", "reminder.created", "assessment_reminder", rid,
                      a.case_id, assessment_id=a.assessment_id, kind=kind)
                changed = True
    if changed:
        db.commit()
    return list(rows)


def reminders(db: Session, astronaut_id: str) -> list[m.AssessmentReminder]:
    refresh(db, astronaut_id)
    return list(db.scalars(select(m.AssessmentReminder).where(m.AssessmentReminder.astronaut_id == astronaut_id)
                           .order_by(m.AssessmentReminder.created_at, m.AssessmentReminder.reminder_id)))


def acknowledge_reminder(db: Session, reminder_id: str, actor_id: str) -> m.AssessmentReminder:
    r = db.get(m.AssessmentReminder, reminder_id)
    if r is None:
        raise not_found("Reminder", reminder_id)
    if db.get(m.Astronaut, actor_id) is None:
        raise not_found("Astronaut", actor_id)
    if r.status == "open":
        r.status, r.acknowledged_at, r.acknowledged_by = "acknowledged", utcnow(), actor_id
        audit(db, actor_id, "reminder.acknowledged", "assessment_reminder", r.reminder_id,
              note="Acknowledging a reminder does not complete the assessment.")
        db.commit()
    return r


def complete(db: Session, a: m.ScheduledAssessment, measurement_id: str, case_id: str | None,
             now: datetime) -> m.ScheduledAssessment | None:
    """Rule S-3 for one assessment. Returns the next occurrence, if one was scheduled."""
    a.status, a.completed_at, a.completed_by_measurement_id = "completed", now, measurement_id
    a.case_id = a.case_id or case_id
    for r in db.scalars(select(m.AssessmentReminder).where(m.AssessmentReminder.assessment_id == a.assessment_id,
                                                           m.AssessmentReminder.status != "closed_by_completion")):
        r.status, r.closed_at = "closed_by_completion", now
    audit(db, "screening-manager", "scheduled_assessment.completed", "scheduled_assessment", a.assessment_id,
          case_id, measurement_id=measurement_id)
    if not a.interval_hours:
        return None
    series = a.series_id or a.assessment_id
    seq = (a.sequence or 1) + 1
    nxt = m.ScheduledAssessment(
        assessment_id=f"{series}-{seq}", astronaut_id=a.astronaut_id, title=a.title, capability=a.capability,
        procedure_id=a.procedure_id, due_at=now + timedelta(hours=a.interval_hours), status="scheduled",
        reason=a.reason, interval_hours=a.interval_hours, grace_hours=a.grace_hours, series_id=series,
        sequence=seq, symptom_linked=a.symptom_linked)
    db.add(nxt)
    audit(db, "screening-manager", "scheduled_assessment.scheduled", "scheduled_assessment", nxt.assessment_id,
          None, due_at=nxt.due_at.isoformat(), previous_assessment_id=a.assessment_id)
    return nxt


def complete_matching(db: Session, astronaut_id: str, procedure_id: str, measurement_id: str, case_id: str,
                      now: datetime) -> list[str]:
    done = []
    for a in db.scalars(select(m.ScheduledAssessment).where(
            m.ScheduledAssessment.astronaut_id == astronaut_id, m.ScheduledAssessment.procedure_id == procedure_id,
            m.ScheduledAssessment.status == "scheduled", m.ScheduledAssessment.due_at <= now)).all():
        complete(db, a, measurement_id, case_id, now)
        done.append(a.assessment_id)
    return done


def start(db: Session, assessment_id: str, actor_id: str, mode: str, equipment_id: str | None):
    """Rule S-4. Returns (case, session, created)."""
    from ..schemas.procedures import SessionCreate
    from . import procedures

    a = get(db, assessment_id)
    if a.status == "completed":
        raise ApiError(409, "ASSESSMENT_COMPLETED", "This scheduled assessment is already completed.",
                       {"assessment_id": assessment_id, "completed_at": a.completed_at.isoformat()})
    if db.get(m.Astronaut, actor_id) is None:
        raise not_found("Astronaut", actor_id)
    now = utcnow()
    case = db.get(m.MedicalCase, a.case_id) if a.case_id else None
    if case is None or case.state not in case_svc.OPEN_STATES:
        case = case_svc.open_case(db, a.astronaut_id, "routine")
    if case is not None:
        req = case.requested_assessment
        if req and req.get("status") == "requested" and req.get("procedure_id") != a.procedure_id:
            raise ApiError(409, "CASE_HAS_PENDING_ASSESSMENT",
                           "The open case already requests a different assessment. Complete that one first.",
                           {"case_id": case.case_id, "requested_procedure_id": req.get("procedure_id")})
    else:
        case = m.MedicalCase(case_id=m.new_id("CASE"), astronaut_id=a.astronaut_id, kind="routine",
                             state="detected", priority="routine", evidence=[],
                             next_action=NEXT_ACTION_SCREENING.format(procedure_id=a.procedure_id),
                             follow_up_status="none", ruleset_version=RULESET_VERSION, created_at=now, updated_at=now)
        db.add(case)
        db.flush()
        audit(db, "screening-manager", "case.created", "medical_case", case.case_id, case.case_id, rule="R-SCR-01",
              assessment_id=a.assessment_id, note="Opened for a scheduled screening without a symptom report.")
    a.case_id = case.case_id
    if not any(e["type"] == "scheduled_assessment" and e["id"] == a.assessment_id for e in case.evidence):
        case_svc.add_evidence(case, "scheduled_assessment", a.assessment_id, a.title)
    if case.state == "detected":
        case_svc.transition(db, case, "investigating", "screening-manager", "R-SCR-01: scheduled screening started")
    if case_svc.can_transition(case.state, "awaiting_assessment") and not (
            case.requested_assessment and case.requested_assessment.get("status") == "requested"):
        case.requested_assessment = {"assessment_id": a.assessment_id, "capability": a.capability,
                                     "procedure_id": a.procedure_id, "status": "requested",
                                     "configured_reason": a.reason}
        case_svc.transition(db, case, "awaiting_assessment", "screening-manager",
                            f"R-SCR-01: scheduled screening {a.assessment_id} requested")
        case_svc.set_next_action(case, NEXT_ACTION_SCREENING.format(procedure_id=a.procedure_id))
    db.commit()
    session, created = procedures.create_session(db, SessionCreate(case_id=case.case_id, procedure_id=a.procedure_id,
                                                                   actor_id=actor_id, mode=mode,
                                                                   equipment_id=equipment_id))
    return case, session, created

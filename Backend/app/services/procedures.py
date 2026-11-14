"""Procedure sessions, step confirmation, measurement validation and follow-up (P0)."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import utcnow
from ..errors import ApiError, not_found
from ..schemas.cases import FollowUpOut, MeasurementOut
from ..schemas.procedures import (CompletedStep, MeasurementCreate, MeasurementResult, MeasurementValidation,
                                  ProcedureOut, ProcedureStep, SessionCreate, SessionOut)
from . import cases as case_svc
from .audit import audit

BP_LIMITS = {"systolic": (50, 260), "diastolic": (30, 160), "pulse": (20, 250)}
FUTURE_TOLERANCE = timedelta(minutes=5)

NEXT_ACTION_AFTER_READING = (
    "Simulated reading recorded. A repeat demonstration reading is scheduled. Technical checks passed; no clinical "
    "interpretation is made. Report any new or worsening symptoms, or contact the crew medical officer if concerned."
)


def get_procedure(db: Session, procedure_id: str) -> m.ProcedureDefinition:
    p = db.get(m.ProcedureDefinition, procedure_id)
    if p is None:
        raise not_found("Procedure", procedure_id)
    return p


def procedure_out(p: m.ProcedureDefinition) -> ProcedureOut:
    d = p.definition
    return ProcedureOut(**{k: d[k] for k in ProcedureOut.model_fields if k in d})


def _steps(p: m.ProcedureDefinition) -> list[dict]:
    return sorted(p.definition["steps"], key=lambda s: s["order"])


def get_session(db: Session, session_id: str) -> m.ProcedureSession:
    s = db.get(m.ProcedureSession, session_id)
    if s is None:
        raise not_found("Procedure session", session_id)
    return s


def session_out(db: Session, s: m.ProcedureSession) -> SessionOut:
    p = get_procedure(db, s.procedure_id)
    steps = {st["step_id"]: st for st in _steps(p)}
    case = db.get(m.MedicalCase, s.case_id)
    cur = steps.get(s.current_step_id) if s.current_step_id else None
    return SessionOut(session_id=s.session_id, case_id=s.case_id, procedure_id=s.procedure_id,
                      procedure_version=s.procedure_version, actor_id=s.actor_id, mode=s.mode, status=s.status,
                      current_step_id=s.current_step_id, current_step=ProcedureStep(**cur) if cur else None,
                      completed_steps=[CompletedStep(**c) for c in s.completed_steps], total_steps=len(steps),
                      completed_count=len(s.completed_steps), measurement_id=s.measurement_id,
                      created_at=s.created_at, updated_at=s.updated_at, completed_at=s.completed_at,
                      case_state=case.state)


def create_session(db: Session, body: SessionCreate) -> tuple[m.ProcedureSession, bool]:
    case = case_svc.get_case(db, body.case_id)
    p = get_procedure(db, body.procedure_id)
    if db.get(m.Astronaut, body.actor_id) is None:
        raise not_found("Astronaut", body.actor_id)
    if case.state == "resolved":
        raise ApiError(409, "CASE_RESOLVED", "Cannot start a procedure on a resolved case.", {"case_id": case.case_id})
    req = case.requested_assessment
    if req and req.get("procedure_id") not in (None, body.procedure_id):
        raise ApiError(409, "PROCEDURE_MISMATCH", "This case requests a different procedure.",
                       {"requested_procedure_id": req["procedure_id"], "received_procedure_id": body.procedure_id})
    existing = db.scalars(select(m.ProcedureSession).where(
        m.ProcedureSession.case_id == case.case_id, m.ProcedureSession.procedure_id == p.procedure_id,
        m.ProcedureSession.status == "in_progress")).first()
    if existing is not None:
        return existing, False
    now = utcnow()
    first = _steps(p)[0]["step_id"]
    s = m.ProcedureSession(session_id=m.new_id("SES"), case_id=case.case_id, procedure_id=p.procedure_id,
                           procedure_version=p.version, actor_id=body.actor_id, mode=body.mode, status="in_progress",
                           current_step_id=first, completed_steps=[], created_at=now, updated_at=now)
    db.add(s)
    audit(db, body.actor_id, "procedure_session.created", "procedure_session", s.session_id, case.case_id,
          procedure_id=p.procedure_id, procedure_version=p.version, mode=body.mode)
    if case.state == "awaiting_assessment":
        case_svc.transition(db, case, "awaiting_results", "procedure-engine",
                            f"Assessment session {s.session_id} started")
        case.next_action = f"Follow the {p.procedure_id} steps, then submit the reading."
    db.commit()
    return s, True


def confirm_step(db: Session, session_id: str, step_id: str, completion_source: str) -> m.ProcedureSession:
    s = get_session(db, session_id)
    p = get_procedure(db, s.procedure_id)
    order = [st["step_id"] for st in _steps(p)]
    if step_id not in order:
        raise ApiError(422, "UNKNOWN_STEP", f"Step '{step_id}' is not part of {p.procedure_id} {p.version}.",
                       {"allowed_step_ids": order})
    done = {c["step_id"] for c in s.completed_steps}
    if step_id in done:
        return s  # idempotent re-confirmation
    if s.status == "completed":
        raise ApiError(409, "SESSION_COMPLETED", "Session already completed.", {"session_id": s.session_id})
    if step_id != s.current_step_id:
        raise ApiError(409, "STEP_OUT_OF_ORDER", f"Expected step '{s.current_step_id}' next.",
                       {"expected_step_id": s.current_step_id, "received_step_id": step_id})
    now = utcnow()
    s.completed_steps = [*s.completed_steps, {"step_id": step_id, "completion_source": completion_source,
                                              "confirmed_at": now.isoformat()}]
    idx = order.index(step_id)
    s.current_step_id = order[idx + 1] if idx + 1 < len(order) else None
    s.updated_at = now
    if s.current_step_id is None:
        s.status = "completed"
        s.completed_at = now
    audit(db, s.actor_id, "procedure_step.confirmed", "procedure_session", s.session_id, s.case_id,
          step_id=step_id, completion_source=completion_source, note="Acknowledgement only")
    db.commit()
    return s


def _validate_measurement(body: MeasurementCreate, s: m.ProcedureSession, case: m.MedicalCase) -> list[str]:
    checks = []
    if s.case_id != case.case_id:
        raise ApiError(409, "SESSION_CASE_MISMATCH", "Session does not belong to this case.",
                       {"session_case_id": s.case_id, "case_id": case.case_id})
    if body.astronaut_id != case.astronaut_id:
        raise ApiError(409, "ASTRONAUT_MISMATCH", "Measurement astronaut does not match the case.",
                       {"case_astronaut_id": case.astronaut_id, "astronaut_id": body.astronaut_id})
    checks.append("session_and_case_association")
    if s.measurement_id is not None:
        raise ApiError(409, "MEASUREMENT_ALREADY_RECORDED", "This session already has a measurement.",
                       {"measurement_id": s.measurement_id})
    if s.status != "completed":
        raise ApiError(409, "SESSION_INCOMPLETE", "Confirm all procedure steps before submitting the reading.",
                       {"current_step_id": s.current_step_id})
    checks.append("procedure_steps_confirmed")
    v = body.value.model_dump()
    bad = {k: {"received": v[k], "min": lo, "max": hi} for k, (lo, hi) in BP_LIMITS.items()
           if v.get(k) is not None and not (lo <= v[k] <= hi)}
    if bad:
        raise ApiError(422, "MEASUREMENT_IMPLAUSIBLE",
                       "Value outside the technically plausible input range (input check, not a clinical judgement).",
                       bad)
    if v["systolic"] <= v["diastolic"]:
        raise ApiError(422, "MEASUREMENT_IMPLAUSIBLE", "Systolic must be greater than diastolic.", v)
    checks.append("plausible_numeric_input")
    now = utcnow()
    if body.observed_at > now + FUTURE_TOLERANCE:
        raise ApiError(422, "TIMESTAMP_IN_FUTURE", "observed_at is in the future.",
                       {"observed_at": body.observed_at.isoformat()})
    if body.observed_at < s.created_at - timedelta(minutes=1):
        raise ApiError(422, "TIMESTAMP_OUTSIDE_SESSION", "observed_at is before the procedure session started.",
                       {"session_created_at": s.created_at.isoformat()})
    checks.append("timestamp_within_session")
    checks.append("simulated_source_label")
    return checks


def record_measurement(db: Session, body: MeasurementCreate) -> MeasurementResult:
    case = case_svc.get_case(db, body.case_id)
    s = get_session(db, body.session_id)
    checks = _validate_measurement(body, s, case)
    now = utcnow()
    meas = m.AssessmentMeasurement(measurement_id=m.new_id("MEAS"), case_id=case.case_id, session_id=s.session_id,
                                   astronaut_id=body.astronaut_id, type=body.type, value=body.value.model_dump(),
                                   unit=body.unit, source=body.source, simulated=True, observed_at=body.observed_at,
                                   recorded_at=now)
    db.add(meas)
    db.flush()
    v = body.value
    for t, val, unit in (("blood_pressure_systolic", v.systolic, "mmHg"), ("blood_pressure_diastolic", v.diastolic, "mmHg"),
                         ("heart_rate", v.pulse, "bpm")):
        if val is not None:
            db.add(m.HealthObservation(observation_id=m.new_id("OBS"), astronaut_id=body.astronaut_id, type=t,
                                       value=val, unit=unit, observed_at=body.observed_at, recorded_at=now,
                                       source=body.source, quality="good", simulated=True,
                                       measurement_id=meas.measurement_id))
    s.measurement_id = meas.measurement_id
    s.updated_at = now
    case_svc.add_evidence(case, "measurement", meas.measurement_id,
                          f"Simulated blood pressure {v.systolic}/{v.diastolic} mmHg")
    audit(db, body.astronaut_id, "measurement.recorded", "assessment_measurement", meas.measurement_id,
          case.case_id, checks=checks, source=body.source)

    req = case.requested_assessment
    if req:
        case.requested_assessment = {**req, "status": "completed"}
        sa = db.get(m.ScheduledAssessment, req.get("assessment_id")) if req.get("assessment_id") else None
        if sa is not None and sa.status == "scheduled":
            sa.status = "completed"
            sa.completed_at = now
    if case.state == "awaiting_results":
        case_svc.transition(db, case, "monitoring", "procedure-engine",
                            "Simulated measurement recorded; follow-up scheduled")
        case.next_action = NEXT_ACTION_AFTER_READING

    fu_cfg = get_procedure(db, s.procedure_id).definition.get("follow_up")
    follow_up, created = None, False
    if fu_cfg:
        follow_up = db.scalars(select(m.FollowUpTask).where(
            m.FollowUpTask.case_id == case.case_id, m.FollowUpTask.task_type == fu_cfg["task_type"],
            m.FollowUpTask.status.in_(["scheduled", "due"]))).first()
        if follow_up is None:
            follow_up = m.FollowUpTask(follow_up_id=m.new_id("FU"), case_id=case.case_id,
                                       task_type=fu_cfg["task_type"], title=fu_cfg["title"],
                                       due_at=now + timedelta(hours=fu_cfg["due_in_hours"]), status="scheduled",
                                       interrupt=case.priority == "urgent", created_at=now)
            db.add(follow_up)
            created = True
            audit(db, "follow-up-manager", "follow_up.created", "follow_up_task", follow_up.follow_up_id,
                  case.case_id, task_type=fu_cfg["task_type"], due_at=follow_up.due_at.isoformat())
        case.follow_up_status = follow_up.status
    case.updated_at = now
    db.commit()
    return MeasurementResult(
        measurement=MeasurementOut.model_validate(meas), case_id=case.case_id, case_state=case.state,
        next_action=case.next_action, validation=MeasurementValidation(technical_checks_passed=True, checks=checks),
        follow_up=FollowUpOut.model_validate(follow_up) if follow_up else None, follow_up_created=created)


def refresh_follow_ups(db: Session, case: m.MedicalCase) -> None:
    """Marks scheduled follow-ups whose due time has passed as due (lazy, no background worker)."""
    now = utcnow()
    changed = False
    for fu in db.scalars(select(m.FollowUpTask).where(m.FollowUpTask.case_id == case.case_id,
                                                      m.FollowUpTask.status == "scheduled",
                                                      m.FollowUpTask.due_at <= now)):
        fu.status = "due"
        changed = True
        audit(db, "follow-up-manager", "follow_up.due", "follow_up_task", fu.follow_up_id, case.case_id)
    if changed:
        case.follow_up_status = "due"
        if case.state == "monitoring":
            case_svc.transition(db, case, "follow_up_due", "follow-up-manager", "Scheduled follow-up is due")
            case.next_action = "A scheduled follow-up assessment is due. Repeat the blood-pressure reading when convenient."
        db.commit()

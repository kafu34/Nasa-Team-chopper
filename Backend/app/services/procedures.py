"""Procedure sessions, step confirmation, measurement validation and follow-up (P0)."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models as m
from ..db import utcnow
from ..errors import ApiError, not_found
from ..schemas.cases import FollowUpOut, MeasurementOut
from ..schemas.procedures import (CompletedStep, MeasurementCreate, MeasurementResult, MeasurementValidation,
                                  ProcedureOut, ProcedureStep, SessionCreate, SessionOut, StepEventCreate,
                                  StepEventOut)
from . import cases as case_svc
from .audit import audit

BP_LIMITS = {"systolic": (50, 260), "diastolic": (30, 160), "pulse": (20, 250)}
# Technical input ranges per measurement type (not clinical limits). 2.8.0 adds pulse oximetry and temperature.
LIMITS = {"blood_pressure": BP_LIMITS, "pulse_oximetry": {"spo2": (50, 100), "pulse": (20, 250)},
          "body_temperature": {"temperature": (30, 43)}}
CAPABILITY_TYPE = {"blood_pressure": "blood_pressure", "pulse_oximetry": "pulse_oximetry",
                   "body_temperature": "body_temperature"}
# Observations stored from a recorded measurement: (observation type, value key, unit).
DERIVED = {"blood_pressure": [("blood_pressure_systolic", "systolic", "mmHg"),
                              ("blood_pressure_diastolic", "diastolic", "mmHg"), ("heart_rate", "pulse", "bpm")],
           "pulse_oximetry": [("spo2", "spo2", "%"), ("heart_rate", "pulse", "bpm")],
           "body_temperature": [("body_temperature", "temperature", "degC")]}


def _summary(type_: str, v: dict) -> str:
    if type_ == "pulse_oximetry":
        return f"Simulated SpO2 {v['spo2']} %" + (f", pulse {v['pulse']} bpm" if v.get("pulse") is not None else "")
    if type_ == "body_temperature":
        return f"Simulated temperature {v['temperature']:g} degC"
    return f"Simulated blood pressure {v['systolic']}/{v['diastolic']} mmHg"
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
    reqs = [{"step_id": s["step_id"], "action_id": s["visual"]["action_id"],
             "asset_ids": [s["visual"]["asset_id"], *s["visual"]["additional_asset_ids"]]}
            for s in sorted(d["steps"], key=lambda s: s["order"])]
    return ProcedureOut(**{k: d[k] for k in ProcedureOut.model_fields if k in d}, visual_requirements=reqs)


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
                      case_state=case.state, equipment=s.equipment_snapshot,
                      case_priority=case.priority, attention=case_svc.attention_for(case),
                      urgent_events=case_svc.urgent_events(db, case.astronaut_id, exclude_case_id=case.case_id),
                      **_visual_state(db, s, case, _steps(p)))


def _visual_state(db: Session, s: m.ProcedureSession, case: m.MedicalCase, steps: list[dict]) -> dict:
    events = db.scalars(select(m.ProcedureStepEvent).where(m.ProcedureStepEvent.session_id == s.session_id)
                        .order_by(m.ProcedureStepEvent.occurred_at, m.ProcedureStepEvent.recorded_at)).all()
    acks = {c["step_id"]: c for c in s.completed_steps}
    states = []
    for st in steps:
        ev = [e for e in events if e.step_id == st["step_id"]]
        shown = [e.occurred_at for e in ev if e.event_type == "instruction_displayed"]
        views = [e.occurred_at for e in ev if e.event_type in ("animation_viewed", "animation_replayed")]
        ack = acks.get(st["step_id"])
        states.append({"step_id": st["step_id"], "visual_action_id": st["visual"]["action_id"],
                       "displayed_at": min(shown) if shown else None,
                       "view_count": sum(e.event_type == "animation_viewed" for e in ev),
                       "replay_count": sum(e.event_type == "animation_replayed" for e in ev),
                       "last_viewed_at": max(views) if views else None,
                       "visual_unavailable": any(e.event_type == "visual_unavailable" for e in ev),
                       "acknowledged_at": ack["confirmed_at"] if ack else None,
                       "completion_source": ack["completion_source"] if ack else None})
    n = len(states)

    def count_stage(name, key, label):
        done = [x for x in states if x[key]]
        at = max((x[key] for x in done), default=None) if done else None
        status = "done" if len(done) == n else "partial" if done else "pending"
        return {"stage": name, "status": status, "at": at if status == "done" else None,
                "detail": f"{len(done)} of {n} steps {label}."}

    stages = [count_stage("instruction_displayed", "displayed_at", "displayed")]
    unavailable = [x["step_id"] for x in states if x["visual_unavailable"]]
    viewed = count_stage("animation_viewed", "last_viewed_at", "with a viewed demonstration")
    if unavailable:
        viewed["detail"] += f" Visual demonstration unavailable for {', '.join(unavailable)}."
        if viewed["status"] != "done":
            viewed["status"] = "unavailable"
    stages.append(viewed)
    ack = count_stage("steps_acknowledged", "acknowledged_at", "acknowledged (acknowledgement only)")
    stages.append(ack)
    meas = db.get(m.AssessmentMeasurement, s.measurement_id) if s.measurement_id else None
    checks = []
    if meas is not None:
        rec = db.scalars(select(m.AuditEvent).where(m.AuditEvent.action == "measurement.recorded",
                                                    m.AuditEvent.entity_id == meas.measurement_id)).first()
        checks = (rec.details or {}).get("checks", []) if rec is not None else []
    stages.append({"stage": "device_reading_received", "status": "done" if meas else "pending",
                   "at": meas.recorded_at if meas else None,
                   "detail": (f"Simulated reading {meas.measurement_id} from {meas.source}." if meas
                              else "No reading submitted for this session.")})
    stages.append({"stage": "technical_validation", "status": "done" if meas else "pending",
                   "at": meas.recorded_at if meas else None,
                   "detail": ("Technical checks passed: " + ", ".join(checks) + ". Not a clinical judgement."
                              if meas else "Runs when a reading is submitted.")})
    req = case.requested_assessment or {}
    assessed = meas is not None and req.get("status") == "completed"
    stages.append({"stage": "assessment_completed", "status": "done" if assessed else "pending",
                   "at": meas.recorded_at if assessed else None,
                   "detail": (f"Configured assessment {req.get('assessment_id') or req.get('procedure_id')} completed "
                              "by this session." if assessed else "Completes when this session's reading is "
                              "recorded.")})
    fu = None
    if meas is not None:
        fu = db.scalars(select(m.FollowUpTask).where(m.FollowUpTask.case_id == s.case_id)
                        .order_by(m.FollowUpTask.created_at.desc())).first()
    stages.append({"stage": "follow_up_created", "status": "done" if fu else "pending",
                   "at": fu.created_at if fu else None,
                   "detail": (f"Follow-up {fu.follow_up_id} ({fu.status}) due {fu.due_at.isoformat()}." if fu
                              else "Created after a recorded reading.")})
    return {"step_states": states, "stages": stages}


def _bind_equipment(db: Session, p: m.ProcedureDefinition, equipment_id: str) -> dict:
    from .spatial import READINESS_MAX_AGE

    e = db.get(m.Equipment, equipment_id)
    if e is None:
        raise not_found("Equipment", equipment_id)
    d = p.definition
    problems = []
    if e.capability != d["required_capability"]:
        problems.append(f"capability {e.capability} is not {d['required_capability']}")
    if e.device_model not in d["compatible_device_models"]:
        problems.append(f"model '{e.device_model}' is not listed for {p.procedure_id}")
    if p.procedure_id not in (e.compatible_procedure_ids or []):
        problems.append(f"the inventory record does not list {p.procedure_id}")
    if problems:
        raise ApiError(422, "EQUIPMENT_INCOMPATIBLE", f"{equipment_id} cannot be used for {p.procedure_id}: "
                       + "; ".join(problems) + ".", {"equipment_id": equipment_id, "problems": problems})
    now = utcnow()
    reasons = []
    if e.readiness != "verified_ready":
        reasons.append(f"readiness_{e.readiness}")
    elif e.readiness_verified_at is None or now - e.readiness_verified_at > READINESS_MAX_AGE:
        reasons.append("readiness_check_stale")
    missing = [x for x in e.required_supplies if not e.supplies.get(x, False)]
    if missing:
        reasons.append("missing_supplies:" + ",".join(missing))
    if reasons:
        raise ApiError(409, "EQUIPMENT_NOT_READY", f"{equipment_id} is not verified ready.",
                       {"equipment_id": equipment_id, "reasons": reasons})
    return {"equipment_id": e.equipment_id, "device_model": e.device_model, "zone_id_at_start": e.zone_id,
            "readiness_at_start": e.readiness,
            "readiness_verified_at": e.readiness_verified_at.isoformat() if e.readiness_verified_at else None}


def record_step_event(db: Session, session_id: str, body: StepEventCreate) -> StepEventOut:
    s = get_session(db, session_id)
    p = get_procedure(db, s.procedure_id)
    steps = {st["step_id"]: st for st in _steps(p)}
    step = steps.get(body.step_id)
    if step is None:
        raise ApiError(422, "UNKNOWN_STEP", f"Step '{body.step_id}' is not part of {p.procedure_id} {p.version}.",
                       {"allowed_step_ids": list(steps)})
    expected = step["visual"]["action_id"]
    if body.visual_action_id != expected:
        raise ApiError(422, "VISUAL_ACTION_MISMATCH", f"Step {body.step_id} uses visual action {expected}.",
                       {"expected_visual_action_id": expected, "received_visual_action_id": body.visual_action_id})
    if db.get(m.Astronaut, body.actor_id) is None:
        raise not_found("Astronaut", body.actor_id)
    if body.client_event_id is not None:
        prev = db.scalars(select(m.ProcedureStepEvent).where(
            m.ProcedureStepEvent.session_id == s.session_id,
            m.ProcedureStepEvent.client_event_id == body.client_event_id)).first()
        if prev is not None:
            return StepEventOut(**_event_dict(prev), duplicate=True)
    now = utcnow()
    at = body.occurred_at or now
    if at > now + FUTURE_TOLERANCE:
        raise ApiError(422, "TIMESTAMP_IN_FUTURE", "occurred_at is in the future.", {"occurred_at": at.isoformat()})
    if at < s.created_at - timedelta(minutes=1):
        raise ApiError(422, "TIMESTAMP_OUTSIDE_SESSION", "occurred_at is before the procedure session started.",
                       {"session_created_at": s.created_at.isoformat()})
    ev = m.ProcedureStepEvent(event_id=m.new_id("PSE"), session_id=s.session_id, step_id=body.step_id,
                              event_type=body.event_type, visual_action_id=expected,
                              client_event_id=body.client_event_id, actor_id=body.actor_id, note=body.note,
                              occurred_at=at, recorded_at=now)
    db.add(ev)
    try:
        db.flush()
    except IntegrityError:
        # The same client_event_id arrived twice at once: return the first event, as a sequential repeat would.
        db.rollback()
        prev = db.scalars(select(m.ProcedureStepEvent).where(
            m.ProcedureStepEvent.session_id == s.session_id,
            m.ProcedureStepEvent.client_event_id == body.client_event_id)).first()
        if prev is None:
            raise
        return StepEventOut(**_event_dict(prev), duplicate=True)
    audit(db, body.actor_id, f"procedure_visual.{body.event_type}", "procedure_session", s.session_id, s.case_id,
          step_id=body.step_id, visual_action_id=expected, note="Visual record only; not clinical execution")
    db.commit()
    return StepEventOut(**_event_dict(ev))


def _event_dict(e: m.ProcedureStepEvent) -> dict:
    return {k: getattr(e, k) for k in ("event_id", "session_id", "step_id", "event_type", "visual_action_id",
                                       "actor_id", "client_event_id", "occurred_at", "recorded_at")}


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
        if body.equipment_id is not None and existing.equipment_id not in (None, body.equipment_id):
            raise ApiError(409, "SESSION_EQUIPMENT_MISMATCH", "The open session for this case uses another device.",
                           {"session_id": existing.session_id, "session_equipment_id": existing.equipment_id,
                            "received_equipment_id": body.equipment_id})
        if body.equipment_id is not None and existing.equipment_id is None:
            existing.equipment_snapshot = _bind_equipment(db, p, body.equipment_id)
            existing.equipment_id = body.equipment_id
            audit(db, body.actor_id, "procedure_session.equipment_bound", "procedure_session",
                  existing.session_id, case.case_id, equipment_id=body.equipment_id)
            db.commit()
        return existing, False
    snapshot = _bind_equipment(db, p, body.equipment_id) if body.equipment_id is not None else None
    now = utcnow()
    first = _steps(p)[0]["step_id"]
    s = m.ProcedureSession(session_id=m.new_id("SES"), case_id=case.case_id, procedure_id=p.procedure_id,
                           procedure_version=p.version, actor_id=body.actor_id, mode=body.mode, status="in_progress",
                           current_step_id=first, completed_steps=[], created_at=now, updated_at=now,
                           equipment_id=body.equipment_id, equipment_snapshot=snapshot)
    db.add(s)
    audit(db, body.actor_id, "procedure_session.created", "procedure_session", s.session_id, case.case_id,
          procedure_id=p.procedure_id, procedure_version=p.version, mode=body.mode, equipment_id=body.equipment_id)
    if case.state == "awaiting_assessment":
        case_svc.transition(db, case, "awaiting_results", "procedure-engine",
                            f"Assessment session {s.session_id} started")
        case_svc.set_next_action(case, f"Follow the {p.procedure_id} steps, then submit the reading.")
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


def _validate_measurement(body: MeasurementCreate, s: m.ProcedureSession, case: m.MedicalCase,
                          proc_capability: str) -> list[str]:
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
    if body.equipment_id is not None and s.equipment_id is not None and body.equipment_id != s.equipment_id:
        raise ApiError(422, "EQUIPMENT_MISMATCH", "The reading names a different device from the session's.",
                       {"session_equipment_id": s.equipment_id, "received_equipment_id": body.equipment_id})
    if s.equipment_id is not None:
        checks.append("device_matches_session")
    capability = proc_capability
    expected = CAPABILITY_TYPE.get(capability)
    if body.type != expected:
        raise ApiError(422, "MEASUREMENT_TYPE_MISMATCH",
                       f"Procedure {s.procedure_id} records '{expected}' measurements, not '{body.type}'.",
                       {"procedure_id": s.procedure_id, "expected_type": expected, "received_type": body.type})
    checks.append("measurement_type_matches_procedure")
    v = body.value.model_dump()
    bad = {k: {"received": v[k], "min": lo, "max": hi} for k, (lo, hi) in LIMITS[body.type].items()
           if v.get(k) is not None and not (lo <= v[k] <= hi)}
    if bad:
        raise ApiError(422, "MEASUREMENT_IMPLAUSIBLE",
                       "Value outside the technically plausible input range (input check, not a clinical judgement).",
                       bad)
    if body.type == "blood_pressure" and v["systolic"] <= v["diastolic"]:
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
    checks = _validate_measurement(body, s, case, get_procedure(db, s.procedure_id).required_capability)
    now = utcnow()
    meas = m.AssessmentMeasurement(measurement_id=m.new_id("MEAS"), case_id=case.case_id, session_id=s.session_id,
                                   astronaut_id=body.astronaut_id, type=body.type, value=body.value.model_dump(),
                                   unit=body.unit, source=body.source, simulated=True, observed_at=body.observed_at,
                                   recorded_at=now)
    db.add(meas)
    db.flush()
    v = body.value.model_dump()
    for t, key, unit in DERIVED[body.type]:
        val = v.get(key)
        if val is not None:
            db.add(m.HealthObservation(observation_id=m.new_id("OBS"), astronaut_id=body.astronaut_id, type=t,
                                       value=val, unit=unit, observed_at=body.observed_at, recorded_at=now,
                                       source=body.source, quality="good", simulated=True,
                                       measurement_id=meas.measurement_id))
    s.measurement_id = meas.measurement_id
    s.updated_at = now
    case_svc.add_evidence(case, "measurement", meas.measurement_id, _summary(body.type, v))
    audit(db, body.astronaut_id, "measurement.recorded", "assessment_measurement", meas.measurement_id,
          case.case_id, checks=checks, source=body.source)

    req = case.requested_assessment
    if req:
        case.requested_assessment = {**req, "status": "completed"}
        sa = db.get(m.ScheduledAssessment, req.get("assessment_id")) if req.get("assessment_id") else None
        if sa is not None and sa.status == "scheduled":
            from . import screening

            screening.complete(db, sa, meas.measurement_id, case.case_id, now)
    if case.state == "awaiting_results":
        case_svc.transition(db, case, "monitoring", "procedure-engine",
                            "Simulated measurement recorded; follow-up scheduled")
        case_svc.set_next_action(case, NEXT_ACTION_AFTER_READING)

    from . import screening

    screening.complete_matching(db, body.astronaut_id, s.procedure_id, meas.measurement_id, case.case_id, now)
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
            case_svc.set_next_action(case, "A scheduled follow-up assessment is due. Repeat the reading when "
                                           "convenient.")
        db.commit()

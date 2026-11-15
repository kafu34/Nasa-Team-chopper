"""Persistent medical-case state machine (deterministic, versioned)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import RULESET_VERSION
from ..db import utcnow
from ..errors import ApiError, not_found
from ..schemas.cases import (AuditOut, CaseOut, CaseSummary, EvidenceRef, FollowUpOut, MeasurementOut,
                             RequestedAssessment, SymptomOut)
from ..schemas.common import Attention
from ..schemas.monitoring import PriorityProtection, UrgentEvent
from .audit import audit

OPEN_STATES = {"detected", "investigating", "awaiting_assessment", "awaiting_results", "action_required",
               "monitoring", "follow_up_due", "escalated"}

# Allowed transitions. "resolved" is reachable only through an explicit resolution step, never via acknowledge.
TRANSITIONS: dict[str, set[str]] = {
    "detected": {"investigating", "escalated"},
    "investigating": {"awaiting_assessment", "action_required", "monitoring", "escalated"},
    "awaiting_assessment": {"awaiting_results", "escalated", "action_required"},
    "awaiting_results": {"monitoring", "action_required", "awaiting_assessment", "escalated"},
    "action_required": {"awaiting_assessment", "monitoring", "escalated"},
    "monitoring": {"follow_up_due", "awaiting_assessment", "escalated", "resolved"},
    "follow_up_due": {"awaiting_assessment", "monitoring", "escalated"},
    "escalated": {"monitoring", "resolved"},
    "resolved": set(),
}


def can_transition(src: str, dst: str) -> bool:
    return dst in TRANSITIONS.get(src, set())


def transition(db: Session, case: m.MedicalCase, dst: str, actor: str, reason: str) -> None:
    if case.state == dst:
        return
    if not can_transition(case.state, dst):
        raise ApiError(409, "INVALID_CASE_TRANSITION", f"Case cannot move from '{case.state}' to '{dst}'.",
                       {"case_id": case.case_id, "from": case.state, "to": dst})
    audit(db, actor, "case.state_changed", "medical_case", case.case_id, case.case_id,
          from_state=case.state, to_state=dst, reason=reason, ruleset_version=RULESET_VERSION)
    case.state = dst
    case.updated_at = utcnow()


def add_evidence(case: m.MedicalCase, ref_type: str, ref_id: str, summary_text: str) -> None:
    case.evidence = [*case.evidence, {"type": ref_type, "id": ref_id, "summary": summary_text,
                                      "recorded_at": utcnow().isoformat()}]


def set_next_action(case: m.MedicalCase, text: str) -> None:
    """The only writer of next_action. While the case is urgent its urgent instruction always stays first, so a
    routine step finishing (reading recorded, follow-up due) can never hide it (2.6.0)."""
    lead = case.urgent_instruction if case.priority == "urgent" else None
    if lead and not text.startswith(lead):
        text = f"{lead} {text}"
    case.next_action = text


def raise_priority(db: Session, case: m.MedicalCase, actor: str, rule: str, reason: str, instruction: str,
                   **details) -> bool:
    """The only priority writer. It can only raise: there is no automatic path back to routine (2.6.0).

    Returns True when the priority changed. Open follow-ups start interrupting.
    """
    if case.priority == "urgent":
        audit(db, actor, "case.urgent_event_recorded", "medical_case", case.case_id, case.case_id, rule=rule,
              reason=reason, note="Case already urgent; priority kept.", **details)
        return False
    now = utcnow()
    case.priority = "urgent"
    case.urgent_since = now
    case.priority_reason = reason
    case.urgent_instruction = instruction
    for fu in db.scalars(select(m.FollowUpTask).where(m.FollowUpTask.case_id == case.case_id,
                                                      m.FollowUpTask.status.in_(["scheduled", "due"]))):
        fu.interrupt = True
    set_next_action(case, case.next_action)
    case.updated_at = now
    audit(db, actor, "case.priority_raised", "medical_case", case.case_id, case.case_id, rule=rule, reason=reason,
          **details)
    return True


def get_case(db: Session, case_id: str) -> m.MedicalCase:
    case = db.get(m.MedicalCase, case_id)
    if case is None:
        raise not_found("Case", case_id)
    return case


def open_case(db: Session, astronaut_id: str, kind: str) -> m.MedicalCase | None:
    return db.scalars(
        select(m.MedicalCase)
        .where(m.MedicalCase.astronaut_id == astronaut_id, m.MedicalCase.kind == kind,
               m.MedicalCase.state.in_(OPEN_STATES))
        .order_by(m.MedicalCase.created_at.desc())
    ).first()


def attention_for(case: m.MedicalCase) -> Attention:
    if case.priority == "urgent":
        return Attention(priority="urgent", interrupt=True, reason="Urgent case: immediate crew attention.")
    return Attention(priority="routine", interrupt=False,
                     reason="Routine item: shown in the task list without interrupting current work.")


def summary(case: m.MedicalCase) -> CaseSummary:
    return CaseSummary(case_id=case.case_id, astronaut_id=case.astronaut_id, kind=case.kind, state=case.state,
                       priority=case.priority, next_action=case.next_action, updated_at=case.updated_at)


def case_out(db: Session, case: m.MedicalCase) -> CaseOut:
    cid = case.case_id
    follow_ups = db.scalars(select(m.FollowUpTask).where(m.FollowUpTask.case_id == cid)
                            .order_by(m.FollowUpTask.created_at)).all()
    symptoms = db.scalars(select(m.SymptomReport).where(m.SymptomReport.case_id == cid)
                          .order_by(m.SymptomReport.reported_at)).all()
    sessions = db.scalars(select(m.ProcedureSession.session_id).where(m.ProcedureSession.case_id == cid)
                          .order_by(m.ProcedureSession.created_at)).all()
    measurements = db.scalars(select(m.AssessmentMeasurement).where(m.AssessmentMeasurement.case_id == cid)
                              .order_by(m.AssessmentMeasurement.recorded_at)).all()
    events = db.scalars(select(m.AuditEvent).where(m.AuditEvent.case_id == cid).order_by(m.AuditEvent.id)).all()
    req = case.requested_assessment
    return CaseOut(
        case_id=cid,
        astronaut_id=case.astronaut_id,
        kind=case.kind,
        state=case.state,
        priority=case.priority,
        attention=attention_for(case),
        evidence=[EvidenceRef(**e) for e in case.evidence],
        requested_assessment=RequestedAssessment(**req) if req else None,
        next_action=case.next_action,
        follow_up_status=case.follow_up_status,
        follow_ups=[FollowUpOut.model_validate(f) for f in follow_ups],
        symptoms=[SymptomOut.model_validate(s) for s in symptoms],
        session_ids=list(sessions),
        measurements=[MeasurementOut.model_validate(x) for x in measurements],
        ruleset_version=case.ruleset_version,
        acknowledged_at=case.acknowledged_at,
        acknowledged_by=case.acknowledged_by,
        created_at=case.created_at,
        updated_at=case.updated_at,
        audit=[AuditOut.model_validate(e) for e in events],
        monitoring_concern_ids=list(db.scalars(select(m.MonitoringConcern.concern_id)
                                               .where(m.MonitoringConcern.case_id == cid)
                                               .order_by(m.MonitoringConcern.opened_at))),
        priority_protection=priority_protection(case),
    )


def priority_protection(case: m.MedicalCase) -> PriorityProtection | None:
    if case.priority != "urgent":
        return None
    return PriorityProtection(urgent_since=case.urgent_since or case.created_at, reason=case.priority_reason,
                              urgent_instruction=case.urgent_instruction)


def urgent_events(db: Session, astronaut_id: str, exclude_case_id: str | None = None) -> list[UrgentEvent]:
    rows = db.scalars(select(m.MedicalCase).where(m.MedicalCase.astronaut_id == astronaut_id,
                                                  m.MedicalCase.priority == "urgent",
                                                  m.MedicalCase.state.in_(OPEN_STATES))
                      .order_by(m.MedicalCase.created_at)).all()
    return [UrgentEvent(case_id=c.case_id, kind=c.kind, state=c.state, priority=c.priority,
                        attention=attention_for(c), urgent_since=c.urgent_since or c.created_at,
                        reason=c.priority_reason, next_action=c.next_action)
            for c in rows if c.case_id != exclude_case_id]


def acknowledge(db: Session, case: m.MedicalCase, actor_id: str) -> None:
    """Records acknowledgement only. Never changes state and never resolves a case."""
    case.acknowledged_at = utcnow()
    case.acknowledged_by = actor_id
    audit(db, actor_id, "case.acknowledged", "medical_case", case.case_id, case.case_id,
          note="Acknowledgement recorded. Case state unchanged.", state=case.state)

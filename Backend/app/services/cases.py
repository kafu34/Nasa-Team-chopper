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
    )


def acknowledge(db: Session, case: m.MedicalCase, actor_id: str) -> None:
    """Records acknowledgement only. Never changes state and never resolves a case."""
    case.acknowledged_at = utcnow()
    case.acknowledged_by = actor_id
    audit(db, actor_id, "case.acknowledged", "medical_case", case.case_id, case.case_id,
          note="Acknowledgement recorded. Case state unchanged.", state=case.state)

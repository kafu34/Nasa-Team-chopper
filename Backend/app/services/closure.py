"""Controlled case closure (plan step 42, contract 2.11.0).

Rules
-----
R-RES-1  Only the crew medical officer or the flight surgeon may resolve a case (`case.resolve`).
R-RES-2  Blockers (409 CASE_NOT_READY_TO_RESOLVE, all listed together):
         - an open monitoring concern;
         - an in-progress procedure session;
         - a requested assessment not yet done;
         - a scheduled or due follow-up, unless `close_outstanding_follow_ups` is true. Each cancellation is audited.
R-RES-3  The case moves to `resolved` only through the state machine (monitoring or escalated -> resolved). A
         follow_up_due case returns to monitoring first, once its follow-ups are closed.
R-RES-4  The priority value is kept (never downgraded); a resolved case no longer interrupts. Unacknowledged urgent
         messages for the case are returned as warnings, not blockers.
Nothing is ever resolved automatically.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import utcnow
from ..errors import ApiError
from . import access
from . import cases as case_svc
from .audit import audit


def blockers(db: Session, case: m.MedicalCase, close_follow_ups: bool) -> list[dict]:
    out = []
    for c in db.scalars(select(m.MonitoringConcern).where(m.MonitoringConcern.case_id == case.case_id,
                                                          m.MonitoringConcern.status != "closed")):
        out.append({"kind": "open_monitoring_concern", "id": c.concern_id,
                    "detail": f"Concern {c.concern_id} is {c.status}; review and close it first."})
    for s in db.scalars(select(m.ProcedureSession).where(m.ProcedureSession.case_id == case.case_id,
                                                         m.ProcedureSession.status == "in_progress")):
        out.append({"kind": "session_in_progress", "id": s.session_id,
                    "detail": f"Procedure session {s.session_id} is still in progress."})
    req = case.requested_assessment
    if req and req.get("status") == "requested":
        out.append({"kind": "assessment_requested", "id": req.get("assessment_id") or req.get("procedure_id"),
                    "detail": f"The requested assessment {req.get('procedure_id')} has not been recorded."})
    if not close_follow_ups:
        for fu in db.scalars(select(m.FollowUpTask).where(m.FollowUpTask.case_id == case.case_id,
                                                          m.FollowUpTask.status.in_(["scheduled", "due"]))):
            out.append({"kind": "follow_up_outstanding", "id": fu.follow_up_id,
                        "detail": f"Follow-up {fu.follow_up_id} is {fu.status}. Complete it, or resolve with "
                                  "close_outstanding_follow_ups=true and a reason."})
    if case.state not in ("monitoring", "escalated", "follow_up_due"):
        out.append({"kind": "state_not_resolvable", "id": case.state,
                    "detail": f"A case in state '{case.state}' cannot be resolved yet."})
    return out


def resolve(db: Session, fx: dict, case: m.MedicalCase, actor_id: str, note: str,
            close_follow_ups: bool) -> dict:
    access.require(db, fx, actor_id, "case.resolve", "medical_case", case.case_id, case.case_id)
    if case.state == "resolved":
        raise ApiError(409, "CASE_RESOLVED", "The case is already resolved.", {"case_id": case.case_id})
    found = blockers(db, case, close_follow_ups)
    if found:
        raise ApiError(409, "CASE_NOT_READY_TO_RESOLVE", "The case still has open items.",
                       {"case_id": case.case_id, "blockers": found})
    now = utcnow()
    cancelled = []
    for fu in db.scalars(select(m.FollowUpTask).where(m.FollowUpTask.case_id == case.case_id,
                                                      m.FollowUpTask.status.in_(["scheduled", "due"]))):
        fu.status, fu.completed_at = "cancelled", now
        cancelled.append(fu.follow_up_id)
        audit(db, actor_id, "follow_up.cancelled", "follow_up_task", fu.follow_up_id, case.case_id,
              reason=f"Cancelled at case resolution: {note}")
    if cancelled:
        case.follow_up_status = "completed"
    if case.state == "follow_up_due":
        case_svc.transition(db, case, "monitoring", actor_id, "Follow-ups closed before resolution")
    case_svc.transition(db, case, "resolved", actor_id, f"Resolved by {actor_id}: {note}")
    case.resolved_at, case.resolved_by, case.resolution_note = now, actor_id, note
    case_svc.set_next_action(case, "Case resolved by the crew medical team. Report any new symptoms.")
    warnings = [f"Urgent message {x.message_id} for this case has not been acknowledged ({x.status})."
                for x in db.scalars(select(m.CommsMessage).where(m.CommsMessage.case_id == case.case_id,
                                                                 m.CommsMessage.priority == "urgent",
                                                                 m.CommsMessage.status != "acknowledged"))]
    audit(db, actor_id, "case.resolved", "medical_case", case.case_id, case.case_id, note=note,
          cancelled_follow_up_ids=cancelled, priority_kept=case.priority, warnings=warnings)
    case.updated_at = now
    db.commit()
    return {"cancelled_follow_up_ids": cancelled, "warnings": warnings}

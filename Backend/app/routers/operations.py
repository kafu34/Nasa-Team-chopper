"""Operational endpoints: preventive screening and access (2.9.0)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db, utcnow
from ..errors import not_found
from ..schemas.common import error_responses
from ..schemas.operations import (AccessMatrixOut, AssessmentList, AssessmentStart, AssessmentStartOut, ReminderAck,
                                  ReminderList, ReminderOut)
from ..services import access, screening
from ..services import procedures as proc_svc

router = APIRouter(prefix="/api/v1")


@router.get("/access/roles", response_model=AccessMatrixOut, tags=["access"],
            summary="Role codes, permission matrix and fictional personnel (2.9.0)")
def get_roles(request: Request) -> AccessMatrixOut:
    return AccessMatrixOut(**access.matrix(request.app.state.fixture))


@router.get("/astronauts/{astronaut_id}/assessments", response_model=AssessmentList, responses=error_responses(404),
            tags=["screening"], summary="Scheduled screening assessments with due/overdue state (2.9.0)")
def list_assessments(astronaut_id: str, db: Session = Depends(get_db)) -> AssessmentList:
    if db.get(m.Astronaut, astronaut_id) is None:
        raise not_found("Astronaut", astronaut_id)
    now = utcnow()
    return AssessmentList(astronaut_id=astronaut_id,
                          assessments=[screening.assessment_out(a, now) for a in screening.refresh(db, astronaut_id, now)])


@router.get("/astronauts/{astronaut_id}/reminders", response_model=ReminderList, responses=error_responses(404),
            tags=["screening"], summary="Durable due and overdue reminders (2.9.0)")
def list_reminders(astronaut_id: str, db: Session = Depends(get_db)) -> ReminderList:
    if db.get(m.Astronaut, astronaut_id) is None:
        raise not_found("Astronaut", astronaut_id)
    return ReminderList(astronaut_id=astronaut_id,
                        reminders=[ReminderOut.model_validate(r) for r in screening.reminders(db, astronaut_id)])


@router.post("/reminders/{reminder_id}/acknowledge", response_model=ReminderOut, responses=error_responses(404),
             tags=["screening"], summary="Acknowledge a reminder (never completes the assessment)")
def acknowledge_reminder(reminder_id: str, body: ReminderAck, db: Session = Depends(get_db)) -> ReminderOut:
    return ReminderOut.model_validate(screening.acknowledge_reminder(db, reminder_id, body.actor_id))


@router.post("/assessments/{assessment_id}/start", response_model=AssessmentStartOut, status_code=201,
             responses=error_responses(404, 409, 422), tags=["screening"],
             summary="Start a scheduled screening: opens or joins a routine case and its procedure session",
             description="No symptom is needed. 409 ASSESSMENT_COMPLETED, 409 CASE_HAS_PENDING_ASSESSMENT. The "
                         "measurement from the session completes the assessment and schedules the next one.")
def start_assessment(assessment_id: str, body: AssessmentStart, response: Response,
                     db: Session = Depends(get_db)) -> AssessmentStartOut:
    case, session, created = screening.start(db, assessment_id, body.actor_id, body.mode, body.equipment_id)
    if not created:
        response.status_code = 200
    return AssessmentStartOut(assessment=screening.assessment_out(screening.get(db, assessment_id)),
                              case_id=case.case_id, case_state=case.state, session=proc_svc.session_out(db, session),
                              session_created=created)

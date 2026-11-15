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
from typing import Optional

from fastapi import Query
from sqlalchemy import select

from ..config import CONTRACT_VERSION
from ..schemas.operations import (CommsAck, CommsList, CommsMessageOut, CommsSend, EnvironmentContext, LinkChange,
                                  LinkOut, RecoveryOut)
from ..services import access, comms, environment, screening
from ..services import procedures as proc_svc

router = APIRouter(prefix="/api/v1")


LOSS_OF_SERVER = [
    "Every record is written to the local SQLite database before a response is sent, so a server restart loses "
    "nothing that was acknowledged with a 2xx response.",
    "If a response is lost, resend with the same client ID (client_event_id, client_message_id) or the same "
    "observation; duplicates are returned, not stored twice.",
    "While the server is unreachable the client must say so and must not show cached data as current. Emergency "
    "crew actions (call crew, follow approved procedures) never depend on the server.",
    "After reconnecting, call GET /system/recovery and restore the listed sessions, concerns, reminders and "
    "messages.",
]


def _comms_out(msg, duplicate: bool = False) -> CommsMessageOut:
    return CommsMessageOut.model_validate(msg).model_copy(update={"duplicate": duplicate})


@router.post("/comms/messages", response_model=CommsMessageOut, status_code=201,
             responses=error_responses(403, 404, 422), tags=["communications"],
             summary="Queue a medical message (simulated delayed link, 2.10.0)",
             description="to_ground needs a crew role; to_crew needs a ground role. 200 with duplicate=true for a "
                         "repeated client_message_id.")
def send_message(body: CommsSend, request: Request, response: Response,
                 db: Session = Depends(get_db)) -> CommsMessageOut:
    fx = request.app.state.fixture
    msg, dup = comms.send(db, fx, body.sender_id, body.direction, body.priority, body.subject, body.body,
                          body.case_id, body.client_message_id)
    if dup:
        response.status_code = 200
    return _comms_out(msg, dup)


@router.get("/comms/messages", response_model=CommsList, tags=["communications"],
            summary="The communications queue, urgent first (delivery is computed from the clock)")
def list_messages(request: Request, direction: Optional[str] = Query(default=None),
                  status: Optional[str] = Query(default=None), case_id: Optional[str] = Query(default=None),
                  db: Session = Depends(get_db)) -> CommsList:
    fx = request.app.state.fixture
    rows = comms.listing(db, fx, direction, status, case_id)
    return CommsList(messages=[_comms_out(r) for r in rows], link_state=comms.link(db).state,
                     one_way_delay_seconds=fx["comms"]["one_way_delay_seconds"], note=fx["comms"]["note"])


@router.get("/comms/messages/{message_id}", response_model=CommsMessageOut, responses=error_responses(404),
            tags=["communications"], summary="One message with its transmission state")
def get_message(message_id: str, request: Request, db: Session = Depends(get_db)) -> CommsMessageOut:
    return _comms_out(comms.get(db, request.app.state.fixture, message_id))


@router.post("/comms/messages/{message_id}/acknowledge", response_model=CommsMessageOut,
             responses=error_responses(403, 404, 409), tags=["communications"],
             summary="Acknowledge a delivered message (receiving side only; 409 NOT_DELIVERED)")
def acknowledge_message(message_id: str, body: CommsAck, request: Request,
                        db: Session = Depends(get_db)) -> CommsMessageOut:
    return _comms_out(comms.acknowledge(db, request.app.state.fixture, message_id, body.actor_id))


def _link_out(fx: dict, lk) -> LinkOut:
    return LinkOut(link_id=lk.link_id, state=lk.state, changed_at=lk.changed_at, changed_by=lk.changed_by,
                   reason=lk.reason, outage_count=lk.outage_count or 0,
                   one_way_delay_seconds=fx["comms"]["one_way_delay_seconds"],
                   transmit_seconds=fx["comms"]["transmit_seconds"])


@router.get("/comms/link", response_model=LinkOut, tags=["communications"], summary="Simulated link state")
def get_link(request: Request, db: Session = Depends(get_db)) -> LinkOut:
    fx = request.app.state.fixture
    comms.advance(db, fx)
    lk = comms.link(db)
    db.commit()
    return _link_out(fx, lk)


@router.post("/comms/link", response_model=LinkOut, responses=error_responses(403, 404, 422),
             tags=["communications"], summary="Simulate loss or restoration of the ground link")
def change_link(body: LinkChange, request: Request, db: Session = Depends(get_db)) -> LinkOut:
    fx = request.app.state.fixture
    return _link_out(fx, comms.set_link(db, fx, body.state, body.actor_id, body.reason))


@router.get("/environment/context", response_model=EnvironmentContext, tags=["environment"],
            summary="Attributed environmental context (RadLab ISS snapshot); no health relationship inferred")
def environment_context(request: Request, astronaut_id: Optional[str] = Query(default=None),
                        db: Session = Depends(get_db)) -> EnvironmentContext:
    return EnvironmentContext(**environment.context(db, request.app.state.settings, astronaut_id))


@router.get("/system/recovery", response_model=RecoveryOut, responses=error_responses(404), tags=["system"],
            summary="What a client must restore after reconnecting (2.10.0)")
def recovery(request: Request, astronaut_id: str = Query(default="DEMO-001"),
             db: Session = Depends(get_db)) -> RecoveryOut:
    from ..services import cases as case_svc

    fx = request.app.state.fixture
    if db.get(m.Astronaut, astronaut_id) is None:
        raise not_found("Astronaut", astronaut_id)
    screening.refresh(db, astronaut_id)
    case_ids = list(db.scalars(select(m.MedicalCase.case_id).where(
        m.MedicalCase.astronaut_id == astronaut_id, m.MedicalCase.state.in_(case_svc.OPEN_STATES))))
    msgs = comms.listing(db, fx)
    out = RecoveryOut(
        server_time=utcnow(), contract_version=CONTRACT_VERSION, astronaut_id=astronaut_id,
        open_session_ids=list(db.scalars(select(m.ProcedureSession.session_id).where(
            m.ProcedureSession.case_id.in_(case_ids), m.ProcedureSession.status == "in_progress"))),
        open_concern_ids=list(db.scalars(select(m.MonitoringConcern.concern_id).where(
            m.MonitoringConcern.astronaut_id == astronaut_id, m.MonitoringConcern.status != "closed"))),
        open_case_ids=case_ids,
        open_reminder_ids=list(db.scalars(select(m.AssessmentReminder.reminder_id).where(
            m.AssessmentReminder.astronaut_id == astronaut_id, m.AssessmentReminder.status == "open"))),
        undelivered_message_ids=[x.message_id for x in msgs if x.status in ("queued", "in_transit")],
        unacknowledged_message_ids=[x.message_id for x in msgs if x.status == "delivered"],
        link_state=comms.link(db).state, loss_of_server_behaviour=LOSS_OF_SERVER)
    db.commit()
    return out


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

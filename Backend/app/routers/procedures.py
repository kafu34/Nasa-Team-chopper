from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas.common import error_responses
from ..schemas.demo import ProcedureSummary
from ..schemas.procedures import (MeasurementCreate, MeasurementResult, ProcedureOut, SessionCreate, SessionOut,
                                  StepConfirm, StepEventCreate, StepEventOut)
from ..services import procedures as svc

router = APIRouter(prefix="/api/v1")


@router.get("/procedures", response_model=list[ProcedureSummary], tags=["procedures"],
            summary="List every educational procedure (2.8.0)")
def list_procedures(db: Session = Depends(get_db)) -> list[ProcedureSummary]:
    from sqlalchemy import select

    from .. import models as m

    return [ProcedureSummary.model_validate(p)
            for p in db.scalars(select(m.ProcedureDefinition).order_by(m.ProcedureDefinition.procedure_id))]


@router.get("/procedures/{procedure_id}", response_model=ProcedureOut, responses=error_responses(404),
            tags=["procedures"], summary="Get a versioned educational procedure definition")
def get_procedure(procedure_id: str, db: Session = Depends(get_db)) -> ProcedureOut:
    return svc.procedure_out(svc.get_procedure(db, procedure_id))


@router.post("/procedure-sessions", response_model=SessionOut, status_code=201,
             responses=error_responses(404, 409, 422), tags=["procedures"],
             summary="Start a procedure session for a case (self or responder mode)",
             description="201 for a new session; 200 returns the existing in-progress session for the same case "
                         "and procedure.")
def create_session(body: SessionCreate, response: Response, db: Session = Depends(get_db)) -> SessionOut:
    s, created = svc.create_session(db, body)
    if not created:
        response.status_code = 200
    return svc.session_out(db, s)


@router.get("/procedure-sessions/{session_id}", response_model=SessionOut, responses=error_responses(404),
            tags=["procedures"], summary="Get a procedure session (optional endpoint)")
def get_session(session_id: str, db: Session = Depends(get_db)) -> SessionOut:
    return svc.session_out(db, svc.get_session(db, session_id))


@router.post("/procedure-sessions/{session_id}/steps", response_model=SessionOut,
             responses=error_responses(404, 409, 422), tags=["procedures"],
             summary="Confirm the next procedure step (acknowledgement only)",
             description="Steps must be confirmed in order. Re-confirming a completed step is idempotent.")
def confirm_step(session_id: str, body: StepConfirm, db: Session = Depends(get_db)) -> SessionOut:
    return svc.session_out(db, svc.confirm_step(db, session_id, body.step_id, body.completion_source))


@router.post("/procedure-sessions/{session_id}/events", response_model=StepEventOut, status_code=201,
             responses=error_responses(404, 422), tags=["procedures"],
             summary="Record that a step's instruction or visual demonstration was shown (contract 2.4.0)",
             description="Events record what the crew member saw. They never change step order, session status or "
                         "case state, and they are not evidence of correct clinical execution. A repeated "
                         "client_event_id returns the first event with duplicate=true (status 200).")
def record_step_event(session_id: str, body: StepEventCreate, response: Response,
                      db: Session = Depends(get_db)) -> StepEventOut:
    out = svc.record_step_event(db, session_id, body)
    if out.duplicate:
        response.status_code = 200
    return out


@router.post("/measurements", response_model=MeasurementResult, status_code=201,
             responses=error_responses(404, 409, 422), tags=["measurements"],
             summary="Submit a simulated blood-pressure reading for a completed session",
             description="Technical validation only. Updates the case and creates a follow-up without duplicates.")
def create_measurement(body: MeasurementCreate, db: Session = Depends(get_db)) -> MeasurementResult:
    return svc.record_measurement(db, body)

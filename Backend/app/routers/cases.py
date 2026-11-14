from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db, utcnow
from ..errors import not_found
from ..schemas.cases import (CaseAcknowledge, CaseOut, ObservationCreate, ObservationCreated, SymptomCreate,
                             SymptomCreated)
from ..schemas.common import error_responses
from ..services import cases as case_svc
from ..services import observations as obs_svc
from ..services import rules
from ..services.audit import audit

router = APIRouter(prefix="/api/v1", tags=["cases"])


@router.post("/symptoms", response_model=SymptomCreated, status_code=201, responses=error_responses(404, 422),
             summary="Report a symptom from the Anatomical Twin; creates or updates a fictional case",
             description="201 when a new report is stored. 200 with duplicate=true when an identical report "
                         "(same region, laterality and severity) was already received within 10 minutes.")
def create_symptom(body: SymptomCreate, request: Request, response: Response,
                   db: Session = Depends(get_db)) -> SymptomCreated:
    sym, case, duplicate = rules.report_symptom(db, request.app.state.fixture, body)
    if duplicate:
        response.status_code = 200
    return SymptomCreated(symptom_id=sym.symptom_id, case_id=case.case_id, case_state=case.state,
                          next_action=case.next_action, duplicate=duplicate)


@router.get("/cases/{case_id}", response_model=CaseOut, responses=error_responses(404),
            summary="Get a case with evidence, follow-ups, measurements and audit history")
def get_case(case_id: str, db: Session = Depends(get_db)) -> CaseOut:
    from ..services.procedures import refresh_follow_ups

    case = case_svc.get_case(db, case_id)
    refresh_follow_ups(db, case)
    return case_svc.case_out(db, case)


@router.post("/cases/{case_id}/acknowledge", response_model=CaseOut, responses=error_responses(404),
             summary="Acknowledge a case alert (optional). Never changes state and never resolves the case.")
def acknowledge_case(case_id: str, body: CaseAcknowledge, db: Session = Depends(get_db)) -> CaseOut:
    case = case_svc.get_case(db, case_id)
    if db.get(m.Astronaut, body.actor_id) is None:
        raise not_found("Astronaut", body.actor_id)
    case_svc.acknowledge(db, case, body.actor_id)
    db.commit()
    return case_svc.case_out(db, case)


@router.post("/observations", response_model=ObservationCreated, status_code=201,
             responses=error_responses(404, 422), tags=["observations"],
             summary="Submit a simulated health observation (optional endpoint)",
             description="Technical validation only (catalogue type, unit, plausible input range, time). "
                         "Passing validation is not a clinical judgement. 200 with duplicate=true for an "
                         "identical resubmission.")
def create_observation(body: ObservationCreate, request: Request, response: Response,
                       db: Session = Depends(get_db)) -> ObservationCreated:
    if db.get(m.Astronaut, body.astronaut_id) is None:
        raise not_found("Astronaut", body.astronaut_id)
    obs_svc.validate(request.app.state.fixture, body)
    existing = db.scalars(select(m.HealthObservation).where(
        m.HealthObservation.astronaut_id == body.astronaut_id, m.HealthObservation.type == body.type,
        m.HealthObservation.observed_at == body.observed_at, m.HealthObservation.value == body.value,
        m.HealthObservation.source == body.source)).first()
    if existing is not None:
        response.status_code = 200
        return ObservationCreated(duplicate=True, **_obs_dict(existing))
    obs = m.HealthObservation(observation_id=m.new_id("OBS"), astronaut_id=body.astronaut_id, type=body.type,
                              value=body.value, unit=body.unit, observed_at=body.observed_at, recorded_at=utcnow(),
                              source=body.source, quality=body.quality, simulated=True)
    db.add(obs)
    audit(db, body.astronaut_id, "observation.recorded", "health_observation", obs.observation_id,
          type=body.type, source=body.source)
    db.commit()
    return ObservationCreated(duplicate=False, **_obs_dict(obs))


def _obs_dict(obs: m.HealthObservation) -> dict:
    return {k: getattr(obs, k) for k in ("observation_id", "astronaut_id", "type", "value", "unit", "observed_at",
                                         "recorded_at", "source", "quality", "simulated")}

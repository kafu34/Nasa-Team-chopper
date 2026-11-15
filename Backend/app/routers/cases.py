from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db, utcnow
from ..errors import not_found
from ..errors import ApiError
from ..schemas.cases import (CaseAcknowledge, CaseOut, CaseResolve, CaseResolveOut, ObservationBatch, ObservationBatchOut, ObservationCreate,
                             ObservationCreated, SymptomCreate, SymptomCreated)
from ..services import access, detection
from ..schemas.common import error_responses
from ..services import cases as case_svc
from ..services import observations as obs_svc
from ..services import rules
from ..services.audit import audit

router = APIRouter(prefix="/api/v1", tags=["cases"])


@router.post("/symptoms", response_model=SymptomCreated, status_code=201, responses=error_responses(404, 422),
             summary="Report a symptom from the Anatomical Twin; creates or updates a fictional case",
             description="201 when a new report is stored. 200 with duplicate=true when an identical report "
                         "(same region, laterality, severity and surface site) was already received within 10 minutes. "
                         "surface_point is optional; when sent, its site_id must belong to region_id/laterality.")
def create_symptom(body: SymptomCreate, request: Request, response: Response,
                   db: Session = Depends(get_db)) -> SymptomCreated:
    sym, case, duplicate = rules.report_symptom(db, request.app.state.fixture, body)
    if duplicate:
        response.status_code = 200
    return SymptomCreated(symptom_id=sym.symptom_id, case_id=case.case_id, case_state=case.state,
                          next_action=case.next_action, duplicate=duplicate, surface_point=sym.surface_point)


@router.get("/cases/{case_id}", response_model=CaseOut, responses=error_responses(403, 404),
            summary="Get a case with evidence, follow-ups, measurements and audit history",
            description="Optional viewer_id (2.9.0): when sent, the viewer's role is checked (crew medical officer, "
                        "flight surgeon, or the crew member whose case it is) and the read is audited. Without it "
                        "the demonstration behaviour is unchanged.")
def get_case(case_id: str, request: Request, viewer_id: Optional[str] = Query(default=None),
             db: Session = Depends(get_db)) -> CaseOut:
    from ..services.procedures import refresh_follow_ups

    case = case_svc.get_case(db, case_id)
    access.check_viewer(db, request.app.state.fixture, viewer_id, "case.read_sensitive", "medical_case",
                        case.case_id, case.astronaut_id)
    refresh_follow_ups(db, case)
    return case_svc.case_out(db, case)


@router.post("/cases/{case_id}/resolve", response_model=CaseResolveOut, responses=error_responses(403, 404, 409, 422),
             summary="Resolve a case (crew medical officer or flight surgeon) once its open items are closed",
             description="409 CASE_NOT_READY_TO_RESOLVE lists every blocker: open concern, session in progress, "
                         "requested assessment, outstanding follow-up (unless close_outstanding_follow_ups), state. "
                         "The priority value is kept; a resolved case stops interrupting (2.11.0).")
def resolve_case(case_id: str, body: CaseResolve, request: Request, db: Session = Depends(get_db)) -> CaseResolveOut:
    from ..services import closure

    case = case_svc.get_case(db, case_id)
    out = closure.resolve(db, request.app.state.fixture, case, body.actor_id, body.note,
                          body.close_outstanding_follow_ups)
    return CaseResolveOut(case=case_svc.case_out(db, case), **out)


@router.post("/cases/{case_id}/acknowledge", response_model=CaseOut, responses=error_responses(403, 404),
             summary="Acknowledge a case alert (optional). Never changes state and never resolves the case.",
             description="Crew members and the flight surgeon may acknowledge; ground support gets 403 (2.9.0).")
def acknowledge_case(case_id: str, body: CaseAcknowledge, request: Request,
                     db: Session = Depends(get_db)) -> CaseOut:
    case = case_svc.get_case(db, case_id)
    access.require(db, request.app.state.fixture, body.actor_id, "case.acknowledge", "medical_case", case.case_id,
                   case.case_id)
    case_svc.acknowledge(db, case, body.actor_id)
    db.commit()
    return case_svc.case_out(db, case)


@router.post("/observations", response_model=ObservationCreated, status_code=201,
             responses=error_responses(404, 422), tags=["observations"],
             summary="Submit a simulated health observation; it is checked by the DET-1.0 detection rules",
             description="Technical validation (catalogue type, unit, plausible input range, time), then the "
                         "data-quality gate and the configured detection rules (2.6.0). Passing validation is not a "
                         "clinical judgement and a detection is not a diagnosis. 200 with duplicate=true for an "
                         "identical resubmission, which is not evaluated again.")
def create_observation(body: ObservationCreate, request: Request, response: Response,
                       db: Session = Depends(get_db)) -> ObservationCreated:
    obs, duplicate = detection.ingest(db, request.app.state.fixture, body)
    if duplicate:
        response.status_code = 200
    return _created(obs, duplicate)


@router.post("/observations/batch", response_model=ObservationBatchOut, responses=error_responses(404, 422),
             tags=["observations"], summary="Automatic ingestion of a simulated wearable sync (2.6.0)",
             description="Every item is validated first; if any fails, nothing is stored and the error names the "
                         "item index. Items are then stored and evaluated in observed_at order.")
def create_observation_batch(body: ObservationBatch, request: Request,
                             db: Session = Depends(get_db)) -> ObservationBatchOut:
    fx = request.app.state.fixture
    for i, item in enumerate(body.observations):
        try:
            if db.get(m.Astronaut, item.astronaut_id) is None:
                raise not_found("Astronaut", item.astronaut_id)
            obs_svc.validate(fx, item)
        except ApiError as e:
            raise ApiError(e.status_code, e.code, f"Item {i}: {e.message}", {**(e.details if isinstance(e.details, dict) else {"details": e.details}), "index": i})
    results, opened = [], []
    for item in sorted(body.observations, key=lambda o: o.observed_at):
        obs, duplicate = detection.ingest(db, fx, item)
        out = _created(obs, duplicate)
        if not duplicate and out.detection and out.detection.outcome == "concern_opened":
            opened.append(out.detection.concern_id)
        results.append(out)
    return ObservationBatchOut(results=results, stored=sum(not r.duplicate for r in results),
                               duplicates=sum(r.duplicate for r in results), concern_ids_opened=opened)


def _created(obs: m.HealthObservation, duplicate: bool) -> ObservationCreated:
    return ObservationCreated(duplicate=duplicate, detection=obs.detection if obs.detection else None,
                              **_obs_dict(obs))


def _obs_dict(obs: m.HealthObservation) -> dict:
    return {k: getattr(obs, k) for k in ("observation_id", "astronaut_id", "type", "value", "unit", "observed_at",
                                         "recorded_at", "source", "quality", "simulated")}

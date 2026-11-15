"""Proactive health intelligence endpoints (contract 2.6.0; history and role check 2.7.0)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas.common import error_responses
from ..schemas.monitoring import (BaselineList, BaselineOut, BaselineRecompute, ConcernOut, ConcernReview,
                                  DetectionRulesetOut, MonitoringOut, ObservationHistory)
from ..services import baselines as bl_svc
from ..services import detection
from ..services import monitoring as mon

router = APIRouter(prefix="/api/v1", tags=["monitoring"])


@router.get("/monitoring/ruleset", response_model=DetectionRulesetOut,
            summary="The configured DET-1.0 demonstration detection rules")
def get_ruleset(request: Request) -> DetectionRulesetOut:
    return mon.detection_ruleset_out(request.app.state.fixture)


@router.get("/astronauts/{astronaut_id}/monitoring", response_model=MonitoringOut, responses=error_responses(404),
            summary="Per-measurement freshness, baseline, latest reading, trend, concerns and data-quality items",
            description="Data-quality items (missing, stale, poor quality, insufficient baseline) never open a case. "
                        "Trends are descriptive only.")
def get_monitoring(astronaut_id: str, request: Request, db: Session = Depends(get_db)) -> MonitoringOut:
    return mon.summary(db, request.app.state.fixture, astronaut_id)


@router.get("/astronauts/{astronaut_id}/observations", response_model=ObservationHistory,
            responses=error_responses(404, 422), summary="Full observation history, newest first (2.7.0)",
            description="Filters: type, since, until (ISO 8601 with offset). Paging: limit (1-1000, default 200) and "
                        "offset. Each item carries its stored detection result and origin.")
def get_observations(astronaut_id: str, request: Request, type: Optional[str] = Query(default=None),
                     since: Optional[datetime] = Query(default=None), until: Optional[datetime] = Query(default=None),
                     limit: int = Query(default=200, ge=1, le=1000), offset: int = Query(default=0, ge=0),
                     db: Session = Depends(get_db)) -> ObservationHistory:
    return mon.history(db, request.app.state.fixture, astronaut_id, type, since, until, limit, offset)


@router.get("/astronauts/{astronaut_id}/baselines", response_model=BaselineList, responses=error_responses(404),
            summary="Every individual baseline version (active and superseded)")
def get_baselines(astronaut_id: str, request: Request, type: Optional[str] = Query(default=None),
                  db: Session = Depends(get_db)) -> BaselineList:
    return mon.baseline_list(db, request.app.state.fixture, astronaut_id, type)


@router.post("/astronauts/{astronaut_id}/baselines/{type}/recompute", response_model=BaselineOut, status_code=201,
             responses=error_responses(403, 404, 409, 422),
             summary="Create a new baseline version (explicit and audited; never automatic)",
             description="409 BASELINE_FROZEN while a monitoring concern for this type is not closed. 422 "
                         "INSUFFICIENT_BASELINE_DATA when too few valid readings remain. Readings observed while a "
                         "concern was open are always excluded. Needs role crew_medical_officer or flight_surgeon "
                         "(403 ROLE_NOT_PERMITTED, 2.7.0).")
def recompute_baseline(astronaut_id: str, type: str, body: BaselineRecompute, request: Request,
                       db: Session = Depends(get_db)) -> BaselineOut:
    row = bl_svc.recompute(db, request.app.state.fixture, astronaut_id, type, body.actor_id, body.reason)
    return mon.baseline_out(db, row)


@router.get("/monitoring-concerns/{concern_id}", response_model=ConcernOut, responses=error_responses(404),
            summary="A monitoring concern with its evidence, reassessment and review state")
def get_concern(concern_id: str, request: Request, db: Session = Depends(get_db)) -> ConcernOut:
    return mon.concern_out(db, request.app.state.fixture, detection.get_concern(db, concern_id))


@router.post("/monitoring-concerns/{concern_id}/review", response_model=ConcernOut,
             responses=error_responses(403, 404, 409, 422),
             summary="Human review: continue monitoring, or close a concern that is awaiting review",
             description="Closing needs status awaiting_review (409 CONCERN_NOT_READY_FOR_REVIEW otherwise). Closing a "
                         "concern unfreezes its baseline and never resolves the case. Closing needs role crew_medical_officer "
                         "or flight_surgeon (403 ROLE_NOT_PERMITTED, 2.7.0); continue_monitoring is open to any crew "
                         "member.")
def review_concern(concern_id: str, body: ConcernReview, request: Request,
                   db: Session = Depends(get_db)) -> ConcernOut:
    fx = request.app.state.fixture
    c = detection.review(db, fx, concern_id, body.actor_id, body.decision, body.note)
    return mon.concern_out(db, fx, c)

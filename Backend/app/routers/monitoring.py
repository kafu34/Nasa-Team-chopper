"""Proactive health intelligence endpoints (contract 2.6.0)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas.common import error_responses
from ..schemas.monitoring import (BaselineList, BaselineOut, BaselineRecompute, ConcernOut, ConcernReview,
                                  DetectionRulesetOut, MonitoringOut)
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


@router.get("/astronauts/{astronaut_id}/baselines", response_model=BaselineList, responses=error_responses(404),
            summary="Every individual baseline version (active and superseded)")
def get_baselines(astronaut_id: str, request: Request, type: Optional[str] = Query(default=None),
                  db: Session = Depends(get_db)) -> BaselineList:
    return mon.baseline_list(db, request.app.state.fixture, astronaut_id, type)


@router.post("/astronauts/{astronaut_id}/baselines/{type}/recompute", response_model=BaselineOut, status_code=201,
             responses=error_responses(404, 409, 422),
             summary="Create a new baseline version (explicit and audited; never automatic)",
             description="409 BASELINE_FROZEN while a monitoring concern for this type is not closed. 422 "
                         "INSUFFICIENT_BASELINE_DATA when too few valid readings remain. Readings observed while a "
                         "concern was open are always excluded.")
def recompute_baseline(astronaut_id: str, type: str, body: BaselineRecompute, request: Request,
                       db: Session = Depends(get_db)) -> BaselineOut:
    row = bl_svc.recompute(db, request.app.state.fixture, astronaut_id, type, body.actor_id, body.reason)
    return mon.baseline_out(db, row)


@router.get("/monitoring-concerns/{concern_id}", response_model=ConcernOut, responses=error_responses(404),
            summary="A monitoring concern with its evidence, reassessment and review state")
def get_concern(concern_id: str, request: Request, db: Session = Depends(get_db)) -> ConcernOut:
    return mon.concern_out(db, request.app.state.fixture, detection.get_concern(db, concern_id))


@router.post("/monitoring-concerns/{concern_id}/review", response_model=ConcernOut,
             responses=error_responses(404, 409, 422),
             summary="Human review: continue monitoring, or close a concern that is awaiting review",
             description="Closing needs status awaiting_review (409 CONCERN_NOT_READY_FOR_REVIEW otherwise). Closing a "
                         "concern unfreezes its baseline and never resolves the case. Any registered crew member may "
                         "review until role-based access is built (PARTIAL).")
def review_concern(concern_id: str, body: ConcernReview, request: Request,
                   db: Session = Depends(get_db)) -> ConcernOut:
    fx = request.app.state.fixture
    c = detection.review(db, fx, concern_id, body.actor_id, body.decision, body.note)
    return mon.concern_out(db, fx, c)

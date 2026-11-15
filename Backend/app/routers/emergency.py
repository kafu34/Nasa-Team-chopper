from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas.common import error_responses
from ..schemas.emergency import EmergencyCreate, EmergencyOut
from ..services import emergency

router = APIRouter(prefix="/api/v1", tags=["emergency"])


@router.post("/emergencies", response_model=EmergencyOut, status_code=201, responses=error_responses(404, 422),
             summary="Activate the simulated emergency workflow (no localisation or equipment step required)",
             description="201 for a new activation; 200 with duplicate=true if an emergency for the same astronaut "
                         "was activated within the last 10 minutes.")
def activate_emergency(body: EmergencyCreate, response: Response, request: Request,
                       db: Session = Depends(get_db)) -> EmergencyOut:
    out, created = emergency.activate(db, body, request.app.state.fixture)
    if not created:
        response.status_code = 200
    return out

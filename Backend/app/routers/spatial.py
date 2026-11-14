from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas.common import error_responses
from ..schemas.spatial import (EquipmentRecommendation, EquipmentRecommendRequest, LocationConfirmRequest,
                               LocationEstimateOut, LocationEstimateRequest)
from ..services import spatial

router = APIRouter(prefix="/api/v1")


@router.post("/location/estimate", response_model=LocationEstimateOut, responses=error_responses(404, 422),
             tags=["spatial"], summary="Estimate the astronaut's zone from simulated BLE observations",
             description="Always 200 for a known astronaut. When no valid signal remains, zone_id is null, "
                         "confidence is 0 and source is 'unavailable'.")
def estimate_location(body: LocationEstimateRequest, db: Session = Depends(get_db)) -> LocationEstimateOut:
    return spatial.estimate(db, body)


@router.post("/location/confirm", response_model=LocationEstimateOut, responses=error_responses(404, 422),
             tags=["spatial"], summary="Manually confirm the astronaut's zone (optional endpoint)")
def confirm_location(body: LocationConfirmRequest, db: Session = Depends(get_db)) -> LocationEstimateOut:
    return spatial.confirm(db, body.astronaut_id, body.zone_id, body.confirmed_by)


@router.post("/equipment/recommend", response_model=EquipmentRecommendation, responses=error_responses(404, 422),
             tags=["equipment"], summary="Recommend ready, supplied, accessible equipment and a zone route",
             description="404 NO_SUITABLE_EQUIPMENT (details.excluded lists reasons) when nothing qualifies.")
def recommend_equipment(body: EquipmentRecommendRequest, db: Session = Depends(get_db)) -> EquipmentRecommendation:
    return spatial.recommend(db, body.case_id, body.zone_id, body.capability)

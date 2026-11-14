from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas.common import error_responses
from ..schemas.habitat import HabitatMapOut
from ..schemas.spatial import (EquipmentRecommendation, EquipmentRecommendRequest, LocationConfirmRequest,
                               LocationEstimateOut, LocationEstimateRequest, LocationLatestOut)
from ..services import habitat, spatial

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
def recommend_equipment(body: EquipmentRecommendRequest, request: Request,
                        db: Session = Depends(get_db)) -> EquipmentRecommendation:
    return spatial.recommend(db, request.app.state.fixture, body.case_id, body.zone_id, body.capability)


@router.get("/location/{astronaut_id}/latest", response_model=LocationLatestOut, responses=error_responses(404),
            tags=["spatial"], summary="Newest location estimate with a freshness label (contract 2.2.0)",
            description="display_mode is 'stale' once the newest observation is older than 30 s (BLE) or 15 min "
                        "(manual confirmation). Stale estimates are last-known zones, never current positions.")
def latest_location(astronaut_id: str, db: Session = Depends(get_db)) -> LocationLatestOut:
    return spatial.latest(db, astronaut_id)


@router.get("/habitats/{habitat_id}/map", response_model=HabitatMapOut, responses=error_responses(404),
            tags=["habitat"], summary="Habitat floor plan, hatches, anchors, equipment and route network "
                                      "(contract 2.2.0)",
            description="Static geometry from the fixture merged with live hatch, anchor and equipment state. All "
                        "coordinates use coordinate_frame (metres) and map_version, the same as equipment routes.")
def habitat_map(habitat_id: str, request: Request, db: Session = Depends(get_db)) -> HabitatMapOut:
    return HabitatMapOut(**habitat.build_map(db, request.app.state.fixture, habitat_id))

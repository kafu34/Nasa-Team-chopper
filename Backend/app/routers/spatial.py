from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas.common import error_responses
from ..schemas.habitat import HabitatMapOut, HatchChange, HatchChangeOut
from ..schemas.spatial import (EquipmentRecommendation, EquipmentRecommendRequest, LocationConfirmRequest,
                               LocationEstimateOut, LocationEstimateRequest, LocationLatestOut)
from ..schemas.simulation import MovementRunOut, MovementRunRequest
from ..services import habitat, simulation, spatial

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


@router.post("/equipment/recommend", response_model=EquipmentRecommendation,
             responses=error_responses(404, 409, 422),
             tags=["equipment"], summary="Recommend ready, supplied, accessible equipment and a zone route",
             description="404 NO_SUITABLE_EQUIPMENT (details.excluded lists reasons) when nothing qualifies.")
def recommend_equipment(body: EquipmentRecommendRequest, request: Request,
                        db: Session = Depends(get_db)) -> EquipmentRecommendation:
    return spatial.recommend(db, request.app.state.fixture, body)


@router.get("/equipment/recommendations/{recommendation_id}", response_model=EquipmentRecommendation,
            responses=error_responses(404), tags=["equipment"],
            summary="Read a stored recommendation and whether it is still valid (contract 2.5.0)",
            description="status becomes 'invalidated' when a hatch on its route closes, or any hatch opens. "
                        "Request a new recommendation then.")
def get_recommendation(recommendation_id: str, db: Session = Depends(get_db)) -> EquipmentRecommendation:
    return spatial.get_recommendation(db, recommendation_id)


@router.post("/habitats/{habitat_id}/hatches/{hatch_id}", response_model=HatchChangeOut,
             responses=error_responses(403, 404, 422), tags=["habitat"],
             summary="Open or close a hatch (contract 2.5.0)",
             description="Changes the live hatch state used by routing, increases the habitat state_version, and "
                         "invalidates affected stored recommendations. Audited. Any registered crew member of the "
                         "habitat may do this in the prototype; role-based authorisation is not implemented.")
def change_hatch(habitat_id: str, hatch_id: str, body: HatchChange, db: Session = Depends(get_db)) -> HatchChangeOut:
    return HatchChangeOut(**habitat.change_hatch(db, habitat_id, hatch_id, body.state, body.actor_id, body.reason))


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


@router.post("/simulation/movement", response_model=MovementRunOut, responses=error_responses(404, 422),
             tags=["simulation"], summary="Run a repeatable movement scenario through the location engine (2.5.0)",
             description="Test harness. Generates simulated BLE observations along a fixture path, sends each tick "
                         "through the normal estimator (stored as ordinary estimates) and returns ground truth "
                         "only in the evaluation block. Scenarios: shared/fixtures/demo_scenario.json "
                         "movement_scenarios.")
def run_movement(body: MovementRunRequest, request: Request, db: Session = Depends(get_db)) -> MovementRunOut:
    return MovementRunOut(**simulation.run(db, request.app.state.fixture, body.scenario_id, body.astronaut_id))

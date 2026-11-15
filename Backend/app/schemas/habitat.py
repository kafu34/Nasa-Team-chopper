"""Habitat geometry contract (2.2.0): one coordinate frame and map version for the map, positions and routes."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .common import DataCategory

Point = list[float]


class CoordinateFrame(BaseModel):
    frame_id: str
    origin: str
    x_axis: str
    y_axis: str
    units: Literal["metres"]
    dimensions: Literal[2]


class DeckOut(BaseModel):
    deck_id: str
    name: str
    bounds: list[Point] = Field(description="[[min_x, min_y], [max_x, max_y]] in the frame.")


class CompartmentOut(BaseModel):
    zone_id: str
    name: str
    deck_id: str
    polygon: list[Point] = Field(description="Outline, counter-clockwise, metres.")
    walkable: bool = True
    navigation_reference: Point = Field(description="Route start/end point for the zone. Not anyone's position.")
    navigation_node_id: str


class PassageOut(BaseModel):
    passage_id: str
    hatch_id: str
    deck_id: str
    from_zone_id: str
    to_zone_id: str
    polygon: list[Point]
    hatch_point: Point
    accessible: bool = Field(description="Live state from the connection registry.")
    hatch_state: Literal["open", "closed"]
    note: str


class AnchorPositionOut(BaseModel):
    anchor_id: str
    zone_id: str
    enabled: bool
    point: Point


class EquipmentPositionOut(BaseModel):
    equipment_id: str
    device_model: str
    capability: str
    zone_id: str
    readiness: str
    point: Optional[Point] = Field(description="Null when no registered position lies in the device's current zone.")
    position_status: Literal["registered", "not_registered_for_current_zone"]


class RouteNodeOut(BaseModel):
    node_id: str
    kind: Literal["zone_reference", "hatch"]
    point: Point
    zone_id: Optional[str] = None
    hatch_id: Optional[str] = None


class RouteEdgeOut(BaseModel):
    from_node_id: str
    to_node_id: str
    passage_id: str
    length_m: float
    accessible: bool


class RouteNetworkOut(BaseModel):
    nodes: list[RouteNodeOut]
    edges: list[RouteEdgeOut]


class HabitatMapOut(BaseModel):
    habitat_id: str
    name: str
    map_version: str
    state_version: int = Field(description="Increases on every hatch change. Geometry is fixed per map_version; "
                                           "live state (hatches) per state_version.")
    description: str
    coordinate_frame: CoordinateFrame
    decks: list[DeckOut]
    compartments: list[CompartmentOut]
    passages: list[PassageOut]
    anchors: list[AnchorPositionOut]
    equipment: list[EquipmentPositionOut]
    route_network: RouteNetworkOut
    note: str = ("Fictional habitat. Equipment and anchor points are registry positions, not live tracking. "
                 "Crew locations are zone-level estimates and are never drawn as precise points.")
    data_category: DataCategory = "SIMULATED_ENVIRONMENT_OR_DEVICE"


class HatchChange(BaseModel):
    state: Literal["open", "closed"]
    actor_id: str = Field(examples=["DEMO-002"])
    reason: str = Field(min_length=3, max_length=300, examples=["Fictional maintenance finished"])


class HatchChangeOut(BaseModel):
    habitat_id: str
    hatch_id: str
    from_zone_id: str
    to_zone_id: str
    state: Literal["open", "closed"]
    changed: bool = Field(description="False when the hatch was already in the requested state.")
    state_version: int
    invalidated_recommendation_ids: list[str]
    access_note: str = ("Any registered crew member of this habitat may change a hatch in this prototype. "
                        "Role-based authorisation is not implemented yet.")
    data_category: Literal["SIMULATED_ENVIRONMENT_OR_DEVICE"] = "SIMULATED_ENVIRONMENT_OR_DEVICE"


class StartReference(BaseModel):
    kind: Literal["zone_navigation_reference"]
    zone_id: str
    node_id: str
    point: Point
    note: str = ("Routes start at the zone's navigation reference because only a zone is known. It is not the "
                 "person's precise position.")


class RouteGeometry(BaseModel):
    frame_id: str
    map_version: str
    points: list[Point] = Field(description="Polyline: zone reference -> hatch -> zone reference ... -> device.")
    node_ids: list[str]
    length_m: float
    end_equipment_point: Optional[Point]

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from .common import DataCategory, TzModel
from .demo import Readiness
from .habitat import RouteGeometry, StartReference


class BleObservation(TzModel):
    anchor_id: str = Field(examples=["ANC-CQ-01"])
    rssi_dbm: int = Field(ge=-120, le=0, examples=[-52], description="Received signal strength in dBm.")
    observed_at: datetime


class LocationEstimateRequest(TzModel):
    astronaut_id: str = Field(examples=["DEMO-001"])
    observations: list[BleObservation] = Field(max_length=100,
                                               description="Simulated BLE observations. May be empty.")


class RejectedObservation(BaseModel):
    anchor_id: str
    reason: Literal["unknown_anchor", "disabled_anchor", "stale_signal", "future_timestamp"]


class ZoneScore(BaseModel):
    zone_id: str
    best_rssi_dbm: int
    anchor_count: int


DisplayMode = Literal["zone_only", "estimated_xy", "unavailable", "stale"]
LocationSource = Literal["ble_simulated", "ble_simulated_smoothed", "manual", "unavailable"]


class LocationEstimateOut(BaseModel):
    estimate_id: str
    astronaut_id: str
    zone_id: Optional[str] = Field(description="Null when no valid signal is available.")
    confidence: float = Field(ge=0, le=1)
    source: LocationSource
    observed_at: Optional[datetime] = Field(description="Timestamp of the newest observation used.")
    estimated_at: datetime
    method: str
    used_anchor_ids: list[str]
    rejected: list[RejectedObservation]
    zone_scores: list[ZoneScore]
    explanation: str
    limitation: str = "Zone-level estimate from simulated signals. RSSI does not give exact distance."
    display_mode: DisplayMode = Field(
        default="zone_only", description="zone_only: highlight the zone, no point. estimated_xy: draw `position` "
        "with its uncertainty (never produced by LOC-P0-1.1). unavailable: no estimate. stale: last-known only "
        "(GET /location/{astronaut_id}/latest).")
    position: Optional[list[float]] = Field(default=None, description="x/y in the map frame. Always null for the "
                                                                      "zone-only engine.")
    position_uncertainty_m: Optional[float] = None
    unobserved_zone_ids: list[str] = Field(default_factory=list, description="Neighbouring zones with no "
                                           "reporting anchor; the person could be there (LOC-P0-1.1, 2.5.0).")
    map_version: Optional[str] = None
    data_category: DataCategory = "SIMULATED_ENVIRONMENT_OR_DEVICE"

    @model_validator(mode="after")
    def _mode(self):
        if self.zone_id is None:
            self.display_mode = "unavailable"
        elif self.position is None and self.display_mode == "estimated_xy":
            self.display_mode = "zone_only"
        return self


class LocationLatestOut(BaseModel):
    astronaut_id: str
    display_mode: DisplayMode
    estimate: Optional[LocationEstimateOut] = Field(description="Newest stored estimate, or null if none exists.")
    age_seconds: Optional[float] = Field(description="Seconds since the newest observation (or confirmation).")
    stale_after_seconds: Optional[int]
    label: str


class LocationConfirmRequest(TzModel):
    astronaut_id: str = Field(examples=["DEMO-001"])
    zone_id: str = Field(examples=["crew-quarters"])
    confirmed_by: str = Field(examples=["DEMO-001"])


class EquipmentRecommendRequest(TzModel):
    case_id: str
    zone_id: Optional[str] = Field(default=None, examples=["crew-quarters"],
                                   description="Start zone. Optional since 2.5.0: when omitted, the start is the "
                                               "latest location estimate of astronaut_id.")
    capability: str = Field(examples=["blood_pressure"])
    astronaut_id: Optional[str] = Field(default=None, examples=["DEMO-002"],
                                        description="Optional (2.5.0). Whose location the route starts from.")
    start_role: Literal["patient", "responder"] = Field(
        default="patient", description="Optional (2.5.0). Whether the route is for the patient or a responder "
                                       "fetching the device.")


class StartCandidate(BaseModel):
    zone_id: str
    best_rssi_dbm: Optional[int] = Field(description="Null for a zone with no reporting anchor.")
    route_hops: Optional[int] = Field(description="Hops from this zone to the chosen device; null if unreachable.")


class StartUncertainty(BaseModel):
    confidence: float
    candidates: list[StartCandidate]
    hop_spread: Optional[int] = Field(description="Max minus min hops over reachable candidates.")
    note: str = ("The start zone is uncertain. The route is drawn from the most likely zone; the person may be in "
                 "another candidate zone.")


class ExcludedEquipment(BaseModel):
    equipment_id: str
    zone_id: str
    reasons: list[str]


class EquipmentRecommendation(BaseModel):
    recommendation_id: Optional[str] = Field(default=None, description="Stored recommendation (2.5.0); read it "
                                             "back with GET /equipment/recommendations/{id}.")
    status: Literal["active", "invalidated"] = "active"
    invalidated_reason: Optional[str] = None
    habitat_state_version: Optional[int] = None
    equipment_id: str
    device_model: str
    zone_id: str
    readiness: Readiness
    readiness_verified_at: Optional[datetime]
    route_zone_ids: list[str] = Field(description="Accessible route from the request zone to the device zone, inclusive.")
    route_hops: int
    procedure_id: Optional[str]
    capability: str
    supplies: dict[str, bool]
    excluded: list[ExcludedEquipment]
    explanation: str
    map_version: str
    coordinate_frame_id: str
    start_reference: StartReference
    route_hatch_ids: list[str] = Field(description="Hatches on the route, in order. All are open.")
    route_geometry: RouteGeometry = Field(description="Route polyline in the map frame (metres).")
    start_basis: Literal["request_zone", "latest_estimate"] = "request_zone"
    start_role: Literal["patient", "responder"] = "patient"
    start_astronaut_id: Optional[str] = None
    start_estimate_id: Optional[str] = None
    start_confidence: Optional[float] = None
    start_uncertainty: Optional[StartUncertainty] = Field(
        default=None, description="Present when the start comes from an estimate with confidence below 0.7.")
    readiness_note: str = ("Readiness comes from the equipment registry check, not from wireless detection. "
                           "A detected advertisement does not mean a device is medically ready.")
    data_category: DataCategory = "SIMULATED_ENVIRONMENT_OR_DEVICE"

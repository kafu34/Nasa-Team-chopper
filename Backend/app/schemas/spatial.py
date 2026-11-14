from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .common import DataCategory, TzModel
from .demo import Readiness


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
    data_category: DataCategory = "SIMULATED_ENVIRONMENT_OR_DEVICE"


class LocationConfirmRequest(TzModel):
    astronaut_id: str = Field(examples=["DEMO-001"])
    zone_id: str = Field(examples=["crew-quarters"])
    confirmed_by: str = Field(examples=["DEMO-001"])


class EquipmentRecommendRequest(TzModel):
    case_id: str
    zone_id: str = Field(examples=["crew-quarters"], description="Current (estimated or confirmed) zone.")
    capability: str = Field(examples=["blood_pressure"])


class ExcludedEquipment(BaseModel):
    equipment_id: str
    zone_id: str
    reasons: list[str]


class EquipmentRecommendation(BaseModel):
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
    readiness_note: str = ("Readiness comes from the equipment registry check, not from wireless detection. "
                           "A detected advertisement does not mean a device is medically ready.")
    data_category: DataCategory = "SIMULATED_ENVIRONMENT_OR_DEVICE"

"""Movement simulation harness (contract 2.5.0). A test tool, not a source for user-facing location displays."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from .common import DataCategory, TzModel


class MovementRunRequest(TzModel):
    scenario_id: str = Field(examples=["SIM-WALK-CQ-MED"])
    astronaut_id: str = Field(examples=["DEMO-001"])


class GeneratedObservation(BaseModel):
    anchor_id: str
    rssi_dbm: int
    observed_at: datetime


class TickEstimate(BaseModel):
    estimate_id: str
    zone_id: Optional[str]
    confidence: float
    source: str
    display_mode: str
    rejected: list[dict[str, Any]]


class MovementTick(BaseModel):
    tick: int
    generated_observations: list[GeneratedObservation]
    estimate: TickEstimate


class MovementRunOut(BaseModel):
    scenario_id: str
    description: str
    astronaut_id: str
    model: dict[str, Any]
    ticks: list[MovementTick]
    evaluation: dict[str, Any] = Field(description="Ground truth and per-tick comparison. For testing only; never "
                                                   "use it as the crew member's location.")
    note: str = ("Each tick's observations were sent through the normal location engine and stored as an estimate. "
                 "User-facing displays read those estimates (GET /location/{id}/latest), never the ground truth.")
    data_category: DataCategory = "SIMULATED_ENVIRONMENT_OR_DEVICE"

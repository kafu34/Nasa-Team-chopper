from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, StrictInt

from .cases import FollowUpOut, MeasurementOut
from .common import CaseState, TzModel

CONFIRMATION_NOTE = "A confirmed step records an acknowledgement only. It does not prove correct clinical execution."


class ProcedureStep(BaseModel):
    step_id: str
    order: int
    title: str
    instruction: str
    anatomical_region_ids: list[str]
    requires_confirmation: bool
    responder_note: str


class FollowUpConfig(BaseModel):
    task_type: str
    title: str
    due_in_hours: int


class ProcedureOut(BaseModel):
    procedure_id: str
    version: str
    title: str
    purpose: str
    required_capability: str
    compatible_device_models: list[str]
    anatomical_region_ids: list[str]
    content_status: Literal["EDUCATIONAL_DEMO_ONLY"]
    source_basis: str
    safety_limitations: list[str]
    steps: list[ProcedureStep]
    follow_up: FollowUpConfig
    confirmation_note: str = CONFIRMATION_NOTE


class SessionCreate(TzModel):
    case_id: str
    procedure_id: str = Field(examples=["PROC-BP-01"])
    actor_id: str = Field(examples=["DEMO-001"])
    mode: Literal["self", "responder"]


class StepConfirm(TzModel):
    step_id: str = Field(examples=["S1"])
    completion_source: Literal["self_confirmed", "responder_confirmed", "demo_auto"]


class CompletedStep(BaseModel):
    step_id: str
    completion_source: str
    confirmed_at: datetime


class SessionOut(BaseModel):
    session_id: str
    case_id: str
    procedure_id: str
    procedure_version: str
    actor_id: str
    mode: Literal["self", "responder"]
    status: Literal["in_progress", "completed"]
    current_step_id: Optional[str] = Field(description="Next step to confirm; null when all steps are confirmed.")
    current_step: Optional[ProcedureStep]
    completed_steps: list[CompletedStep]
    total_steps: int
    completed_count: int
    measurement_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    case_state: CaseState
    confirmation_note: str = CONFIRMATION_NOTE


class BloodPressureValue(BaseModel):
    systolic: StrictInt = Field(examples=[118])
    diastolic: StrictInt = Field(examples=[76])
    pulse: Optional[StrictInt] = Field(default=None, examples=[70])


class MeasurementCreate(TzModel):
    case_id: str
    session_id: str
    astronaut_id: str = Field(examples=["DEMO-001"])
    type: Literal["blood_pressure"]
    value: BloodPressureValue
    unit: Literal["mmHg"]
    source: Literal["SIMULATED_DEVICE", "SIMULATED_MANUAL_ENTRY"] = Field(
        description="Only simulated sources are accepted in this prototype.")
    observed_at: datetime


class MeasurementValidation(BaseModel):
    technical_checks_passed: bool
    checks: list[str]
    clinical_interpretation: None = None
    note: str = "Technical validity is not clinical normality. No clinical interpretation is made."


class MeasurementResult(BaseModel):
    measurement: MeasurementOut
    case_id: str
    case_state: CaseState
    next_action: str
    validation: MeasurementValidation
    follow_up: Optional[FollowUpOut]
    follow_up_created: bool = Field(description="False when an equivalent open follow-up already existed.")

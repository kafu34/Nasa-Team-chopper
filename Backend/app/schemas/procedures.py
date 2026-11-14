from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, StrictInt

from .cases import FollowUpOut, MeasurementOut
from .common import CaseState, TzModel

CONFIRMATION_NOTE = "A confirmed step records an acknowledgement only. It does not prove correct clinical execution."


ValidationLevel = Literal["EDUCATIONAL_DEMONSTRATION", "SIMULATED_EQUIPMENT_WORKFLOW", "HARDWARE_TESTED_WORKFLOW",
                          "MISSION_APPROVED_PROCEDURE"]
CameraView = Literal["front", "back", "left_side", "right_side", "equipment_closeup"]


class StepEquipment(BaseModel):
    required_capability: str
    compatible_device_models: list[str]
    components: list[str] = Field(description="Parts of the device shown in this step, e.g. monitor, cuff.")


class CameraTarget(BaseModel):
    view: CameraView
    target_region_id: str
    target_laterality: str
    framing: str = Field(description="patient_and_equipment, region_closeup, patient_posture, device_controls or "
                                     "device_display.")


class StepVisual(BaseModel):
    """Visual contract (2.2.0). Codex maps action_id and asset IDs to implemented scenes and animations."""

    action_id: str = Field(description="Unique per step. Codex's visual-action registry must implement it.")
    asset_id: str = Field(description="Primary 3D asset of the scene.")
    additional_asset_ids: list[str]
    camera: CameraTarget
    expected_visible_action: str = Field(description="What the animation must visibly show.")
    replay_allowed: bool
    pause_allowed: bool


class ProcedureStep(BaseModel):
    step_id: str
    order: int
    title: str
    instruction: str
    anatomical_region_ids: list[str]
    requires_confirmation: bool
    responder_note: str
    target_region_id: str
    target_laterality: str
    target_site_id: Optional[str] = Field(description="Detailed surface site on the default anatomy model, if any.")
    patient_role: Literal["crew_member_being_assessed"]
    equipment: StepEquipment
    instruction_source_ids: list[str]
    visual: StepVisual
    warnings: list[str]


class InstructionSource(BaseModel):
    source_id: str
    description: str
    reviewed_by_flight_surgeon: bool


class VisualRequirement(BaseModel):
    step_id: str
    action_id: str
    asset_ids: list[str]


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
    validation_level: ValidationLevel = Field(
        description="EDUCATIONAL_DEMONSTRATION: content for teaching only. Completing it does not establish that "
                    "the technique is safe or approved for spacecraft use.")
    intended_patient: str
    source_basis: str
    instruction_sources: list[InstructionSource]
    safety_limitations: list[str]
    steps: list[ProcedureStep]
    follow_up: FollowUpConfig
    visual_requirements: list[VisualRequirement] = Field(
        description="Every visual action and asset the frontend must implement for this procedure.")
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

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from typing import Union

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from .cases import FollowUpOut, MeasurementOut
from .common import Attention, CaseState, Priority, TzModel
from .monitoring import UrgentEvent

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
    equipment_id: Optional[str] = Field(
        default=None, examples=["EQ-BP-01"], description="Optional (2.4.0). The inventory device used, normally "
        "the one from POST /equipment/recommend. Must be compatible with the procedure and verified ready.")


StepEventType = Literal["instruction_displayed", "animation_viewed", "animation_replayed", "visual_unavailable"]
VISUAL_NOTE = ("Displayed instructions, viewed animations and acknowledged steps show what the crew member saw and "
               "confirmed. They do not prove that the real-world step was performed correctly.")


class StepEventCreate(TzModel):
    step_id: str = Field(examples=["S3"])
    event_type: StepEventType = Field(description="instruction_displayed: the step's instruction was shown. "
                                      "animation_viewed: its demonstration played to the end. animation_replayed: it "
                                      "was played again. visual_unavailable: the frontend has no implemented scene "
                                      "for this action and showed the unavailable state.")
    visual_action_id: str = Field(examples=["VA-BP-03-WRAP-CUFF"], description="Must equal the step's visual.action_id.")
    actor_id: str = Field(examples=["DEMO-001"])
    client_event_id: Optional[str] = Field(default=None, max_length=64, description="Idempotency key. A repeat "
                                           "returns the first event with duplicate=true.")
    occurred_at: Optional[datetime] = Field(default=None, description="Client time of the event; defaults to the "
                                            "server time. Must not be in the future or before the session started.")
    note: Optional[str] = Field(default=None, max_length=300)


class StepEventOut(BaseModel):
    event_id: str
    session_id: str
    step_id: str
    event_type: StepEventType
    visual_action_id: str
    actor_id: str
    client_event_id: Optional[str]
    occurred_at: datetime
    recorded_at: datetime
    duplicate: bool = False


class SessionEquipment(BaseModel):
    equipment_id: str
    device_model: str
    zone_id_at_start: str
    readiness_at_start: str
    readiness_verified_at: Optional[datetime]


class StepState(BaseModel):
    step_id: str
    visual_action_id: str
    displayed_at: Optional[datetime]
    view_count: int
    replay_count: int
    last_viewed_at: Optional[datetime]
    visual_unavailable: bool
    acknowledged_at: Optional[datetime]
    completion_source: Optional[str]


SessionStageName = Literal["instruction_displayed", "animation_viewed", "steps_acknowledged",
                           "device_reading_received", "technical_validation", "assessment_completed",
                           "follow_up_created"]


class SessionStage(BaseModel):
    stage: SessionStageName
    status: Literal["done", "partial", "pending", "unavailable"]
    at: Optional[datetime] = Field(description="When the stage was completed (latest contributing record).")
    detail: str


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
    equipment: Optional[SessionEquipment] = Field(default=None, description="Device bound at session start (2.4.0).")
    step_states: list[StepState] = Field(default_factory=list, description="Per-step visual and acknowledgement "
                                         "state, for restoring the coach after reopening (2.4.0).")
    stages: list[SessionStage] = Field(default_factory=list, description="Separate records of display, viewing, "
                                       "acknowledgement, reading, validation, assessment and follow-up (2.4.0).")
    case_priority: Optional[Priority] = Field(default=None, description="Priority of this session's case (2.6.0).")
    attention: Optional[Attention] = Field(default=None, description="Interrupt the coach when urgent (2.6.0).")
    urgent_events: list[UrgentEvent] = Field(default_factory=list, description="Other open urgent cases for the "
                                             "same astronaut, e.g. an emergency activated during this routine "
                                             "procedure (2.6.0). The routine session is not cancelled.")
    confirmation_note: str = CONFIRMATION_NOTE
    visual_note: str = VISUAL_NOTE


class BloodPressureValue(BaseModel):
    systolic: StrictInt = Field(examples=[118])
    diastolic: StrictInt = Field(examples=[76])
    pulse: Optional[StrictInt] = Field(default=None, examples=[70])


class PulseOximetryValue(BaseModel):
    """2.8.0. SpO2 in %, pulse in beats per minute."""
    model_config = ConfigDict(extra="forbid")
    spo2: StrictInt = Field(examples=[98])
    pulse: Optional[StrictInt] = Field(default=None, examples=[68])


class TemperatureValue(BaseModel):
    """2.8.0. Degrees Celsius."""
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    temperature: float = Field(examples=[36.7])


MEASUREMENT_SHAPES = {"blood_pressure": (BloodPressureValue, "mmHg"), "pulse_oximetry": (PulseOximetryValue, "%"),
                      "body_temperature": (TemperatureValue, "degC")}


class MeasurementCreate(TzModel):
    case_id: str
    session_id: str
    astronaut_id: str = Field(examples=["DEMO-001"])
    type: Literal["blood_pressure", "pulse_oximetry", "body_temperature"] = Field(
        description="Must match the procedure: PROC-BP-01 blood_pressure, PROC-PO-01 pulse_oximetry, PROC-TEMP-01 "
                    "body_temperature (2.8.0).")
    value: Union[BloodPressureValue, PulseOximetryValue, TemperatureValue] = Field(
        description="blood_pressure {systolic, diastolic, pulse?}; pulse_oximetry {spo2, pulse?}; body_temperature "
                    "{temperature}.")
    unit: Literal["mmHg", "%", "degC"]
    source: Literal["SIMULATED_DEVICE", "SIMULATED_MANUAL_ENTRY"] = Field(
        description="Only simulated sources are accepted in this prototype.")
    observed_at: datetime
    equipment_id: Optional[str] = Field(default=None, description="Optional (2.4.0). Must equal the session's "
                                        "device when the session has one.")

    @model_validator(mode="after")
    def _shape_matches_type(self):
        model, unit = MEASUREMENT_SHAPES[self.type]
        if not isinstance(self.value, model):
            raise ValueError(f"value for type '{self.type}' must have the fields of {model.__name__}")
        if self.unit != unit:
            raise ValueError(f"unit for type '{self.type}' must be '{unit}'")
        return self


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

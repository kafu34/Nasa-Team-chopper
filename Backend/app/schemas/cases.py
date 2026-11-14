from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .common import Attention, CaseState, DataCategory, Laterality, Out, Priority, Strict, TzModel

_COORD = dict(ge=-5.0, le=5.0, description="Model units (not centimetres); finite, within +/-5.")


class SurfaceAttachment(Strict):
    """Mesh-relative marker attachment: a triangle of `mesh_id` and a barycentric position inside it."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    triangle_index: int = Field(ge=0, le=10_000_000, examples=[1204])
    barycentric: list[float] = Field(min_length=3, max_length=3, examples=[[0.2, 0.3, 0.5]],
                                     description="Three weights, each 0-1, summing to 1 (+/-0.001).")

    @field_validator("barycentric")
    @classmethod
    def _weights(cls, v: list[float]) -> list[float]:
        if any(w < 0 or w > 1 for w in v) or abs(sum(v) - 1) > 1e-3:
            raise ValueError("barycentric weights must each be within 0-1 and sum to 1")
        return v


class SurfacePoint(Strict):
    """A tapped point on a registered 3D Anatomical Twin model. A diagram location, not a measurement."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    model_id: str = Field(max_length=64, examples=["sentinel-body-v1"],
                          description="Registered model (GET /api/v1/demo/bootstrap -> surface_models).")
    model_version: Optional[str] = Field(default=None, max_length=32, examples=["1.0.0"],
                                         description="Optional (2.2.0). Must equal the model's current version; "
                                                     "when omitted the server records the current version.")
    site_id: str = Field(examples=["right_shoulder"],
                         description="Detailed surface site; must map to the request's region_id and laterality.")
    x: float = Field(examples=[-0.468], **_COORD)
    y: float = Field(examples=[0.704], **_COORD)
    z: float = Field(examples=[0.131], **_COORD)
    mesh_id: Optional[str] = Field(default=None, max_length=128, pattern=r"^[A-Za-z0-9_.:\-]+$",
                                   description="Optional (2.2.0). Mesh the point lies on. Validated when the "
                                               "model manifest declares its meshes.")
    attachment: Optional[SurfaceAttachment] = Field(
        default=None, description="Optional (2.2.0). Triangle + barycentric position on mesh_id, for markers "
        "that stay attached when the model is posed or re-rendered.")


MarkerStatus = Literal["current", "model_version_changed", "model_version_incompatible", "model_retired",
                       "model_unknown"]


class SurfacePointOut(BaseModel):
    model_id: str
    model_version: str = Field(description="Version the point was reported on (1.0.0 for points stored before "
                                           "contract 2.2.0).")
    site_id: str
    site_label: str
    x: float
    y: float
    z: float
    mesh_id: Optional[str] = None
    mesh_validation: Literal["not_supplied", "not_declared_by_model", "validated"] = "not_supplied"
    attachment: Optional[dict[str, Any]] = None
    marker_status: MarkerStatus = Field(description="Marker migration status against the registered model.")
    render_hint: Literal["exact_point", "site_only", "not_renderable"] = Field(
        description="exact_point: draw at the stored coordinates. site_only: highlight the named site, do not "
        "place the old coordinates. not_renderable: show the record without a marker.")

    @model_validator(mode="before")
    @classmethod
    def _migrate(cls, data: Any) -> Any:
        if isinstance(data, dict) and "marker_status" not in data:
            from ..services.surface_sites import describe
            return describe(data)
        return data


class SymptomCreate(TzModel):
    astronaut_id: str = Field(examples=["DEMO-001"])
    region_id: str = Field(examples=["head"], description="Anatomical region ID from the demo fixture.")
    laterality: Laterality = Field(examples=["midline"])
    severity: int = Field(ge=0, le=10, examples=[3], description="Self-reported severity 0-10.")
    onset: datetime = Field(description="ISO 8601 time the symptom started.", examples=["2026-11-14T08:45:00Z"])
    note: Optional[str] = Field(default=None, max_length=1000)
    surface_point: Optional[SurfacePoint] = Field(
        default=None, description="Optional (v2.2). Exact point on the 3D Anatomical Twin. Stored and returned "
        "as reported; the rules engine still uses only region_id and laterality.")


class SymptomCreated(BaseModel):
    symptom_id: str
    case_id: str
    case_state: CaseState
    next_action: str
    duplicate: bool = Field(description="True when the report repeated an identical recent report and was deduplicated.")
    surface_point: Optional[SurfacePointOut] = None
    record_kind: Literal["patient_reported_symptom"] = "patient_reported_symptom"
    data_category: DataCategory = "SIMULATED_ASTRONAUT"


class EvidenceRef(BaseModel):
    type: Literal["symptom", "observation", "measurement", "scheduled_assessment", "emergency"]
    id: str
    summary: str
    recorded_at: datetime


class RequestedAssessment(BaseModel):
    assessment_id: Optional[str]
    capability: str
    procedure_id: str
    status: str
    configured_reason: str


class FollowUpOut(Out):
    follow_up_id: str
    task_type: str
    title: str
    due_at: datetime
    status: str
    interrupt: bool
    created_at: datetime


class SymptomOut(Out):
    symptom_id: str
    region_id: str
    laterality: str
    severity: int
    onset: datetime
    note: Optional[str]
    surface_point: Optional[SurfacePointOut] = None
    reported_at: datetime
    record_kind: Literal["patient_reported_symptom"] = Field(
        default="patient_reported_symptom", description="Self-report. Not a monitoring concern or a verified finding.")


class MeasurementOut(Out):
    measurement_id: str
    case_id: str
    session_id: str
    astronaut_id: str
    type: str
    value: dict[str, Any]
    unit: str
    source: str
    simulated: bool
    observed_at: datetime
    recorded_at: datetime
    data_category: DataCategory = "SIMULATED_ASTRONAUT"


class AuditOut(Out):
    timestamp: datetime
    actor: str
    action: str
    entity_type: str
    entity_id: str
    details: dict[str, Any]


class CaseSummary(BaseModel):
    case_id: str
    astronaut_id: str
    kind: Literal["routine", "emergency"]
    state: CaseState
    priority: Priority
    next_action: str
    updated_at: datetime


class CaseOut(BaseModel):
    case_id: str
    astronaut_id: str
    kind: Literal["routine", "emergency"]
    state: CaseState
    priority: Priority
    attention: Attention
    evidence: list[EvidenceRef]
    requested_assessment: Optional[RequestedAssessment]
    next_action: str
    follow_up_status: Literal["none", "scheduled", "due", "completed"]
    follow_ups: list[FollowUpOut]
    symptoms: list[SymptomOut]
    session_ids: list[str]
    measurements: list[MeasurementOut]
    ruleset_version: str
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    audit: list[AuditOut]
    data_category: DataCategory = "SIMULATED_ASTRONAUT"
    disclaimer: str = "Fictional demonstration case. Not a diagnosis."


class CaseAcknowledge(TzModel):
    actor_id: str = Field(examples=["DEMO-001"])


class ObservationCreate(TzModel):
    astronaut_id: str = Field(examples=["DEMO-001"])
    type: str = Field(examples=["heart_rate"])
    value: float = Field(examples=[71])
    unit: str = Field(examples=["bpm"])
    source: Literal["SIMULATED_WEARABLE", "SIMULATED_MANUAL_ENTRY", "SIMULATED_DEVICE"]
    observed_at: datetime
    quality: Literal["good", "fair", "poor"] = "good"


class ObservationOut(Out):
    observation_id: str
    astronaut_id: str
    type: str
    value: float
    unit: str
    observed_at: datetime
    recorded_at: datetime
    source: str
    quality: str
    simulated: bool
    data_category: DataCategory = "SIMULATED_ASTRONAUT"


class ObservationCreated(ObservationOut):
    duplicate: bool


class ObservationStatus(BaseModel):
    type: str
    unit: str
    status: Literal["current", "stale", "missing"]
    stale_after_minutes: int
    latest_value: Optional[float]
    latest_observed_at: Optional[datetime]

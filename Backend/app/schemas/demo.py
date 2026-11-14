from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from .cases import CaseSummary, ObservationOut, ObservationStatus
from .common import DataCategory, Laterality, Out
from .research import DatasetSummary


class Mission(BaseModel):
    mission_id: str
    mission_name: str
    habitat_id: str
    mission_day: int


class AstronautOut(BaseModel):
    astronaut_id: str
    display_name: str
    role: str
    fictional: bool
    mission: Mission
    data_category: DataCategory = "SIMULATED_ASTRONAUT"


class ZoneOut(Out):
    zone_id: str
    name: str


class ConnectionOut(Out):
    from_zone_id: str
    to_zone_id: str
    accessible: bool
    note: str
    hatch_id: Optional[str] = None


class HabitatOut(BaseModel):
    habitat_id: str
    name: str
    map_version: str
    zones: list[ZoneOut]
    connections: list[ConnectionOut]
    data_category: DataCategory = "SIMULATED_ENVIRONMENT_OR_DEVICE"


class AnchorOut(Out):
    anchor_id: str
    zone_id: str
    enabled: bool
    verified_at: Optional[datetime]
    verified_by: Optional[str]
    data_category: DataCategory = "SIMULATED_ENVIRONMENT_OR_DEVICE"


Readiness = Literal["verified_ready", "unknown", "needs_service", "in_use"]


class EquipmentOut(Out):
    equipment_id: str
    device_model: str
    capability: str
    zone_id: str
    readiness: Readiness
    readiness_verified_at: Optional[datetime]
    supplies: dict[str, bool]
    required_supplies: list[str]
    compatible_procedure_ids: list[str]
    status_updated_at: datetime
    data_category: DataCategory = "SIMULATED_ENVIRONMENT_OR_DEVICE"


class ProcedureSummary(Out):
    procedure_id: str
    version: str
    title: str
    required_capability: str


class ScheduledAssessmentOut(Out):
    assessment_id: str
    astronaut_id: str
    title: str
    capability: str
    procedure_id: str
    due_at: datetime
    status: Literal["scheduled", "completed"]
    is_due: bool
    reason: str
    case_id: Optional[str]
    completed_at: Optional[datetime]


class RegionOut(BaseModel):
    region_id: str
    label: str
    lateral: bool


class SitePlausibility(BaseModel):
    y_min_m: float
    y_max_m: float
    surface: Literal["front", "back", "any"]


class SurfaceSiteOut(BaseModel):
    site_id: str
    label: str
    region_id: str
    laterality: Laterality
    plausibility: Optional[SitePlausibility] = Field(default=None, description="Coarse height/face band checked "
                                                     "on report, for models that declare it.")


class SurfaceModelOut(BaseModel):
    model_id: str
    coordinate_limit: float
    coordinate_note: str
    sites: list[SurfaceSiteOut]


class SurfaceMeshOut(BaseModel):
    mesh_id: str
    triangle_count: int
    description: Optional[str] = None
    layer: Optional[str] = None
    selectable: bool = True
    node_transform: Optional[dict[str, list[float]]] = Field(default=None, description="translation and scale "
                                                             "from mesh-local to model coordinates.")
    local_bounds: Optional[dict[str, list[float]]] = None


class SurfaceModelVersionOut(BaseModel):
    model_version: str
    coordinates_compatible: bool
    note: str


class RegisteredSurfaceModelOut(BaseModel):
    """A 3D Anatomical Twin model from shared/anatomy/<model_id>.json (contract 2.2.0)."""

    model_id: str
    model_version: str
    status: Literal["active", "retired"]
    kind: str
    description: str
    asset: Optional[dict[str, Any]] = Field(default=None, description="Frontend asset file, hash, licence and "
                                            "attribution.")
    coordinate_frame: dict[str, Any]
    side_tolerance: float
    meshes: Optional[list[SurfaceMeshOut]] = Field(description="Null when the model does not declare its meshes; "
                                                               "mesh_id is then stored but not validated.")
    previous_versions: list[SurfaceModelVersionOut]
    sites: list[SurfaceSiteOut]


class AnnotationKindOut(BaseModel):
    kind: Literal["surface_selection", "region_classification", "patient_reported_symptom", "monitoring_concern",
                  "verified_finding"]
    description: str


class BleObservationTemplate(BaseModel):
    anchor_id: str
    rssi_dbm: int
    age_seconds: int = Field(description="Client sets observed_at = now - age_seconds.")


class DemoInputs(BaseModel):
    """Canonical demo inputs from shared/fixtures/demo_scenario.json, for the frontend to submit."""

    ble_observations: list[BleObservationTemplate]
    expected_zone_id: str
    symptom: dict[str, Any]
    measurement: dict[str, Any]
    emergency: dict[str, Any]
    expected_recommendation: dict[str, Any]


class BootstrapOut(BaseModel):
    contract_version: str
    fixture_version: str
    ruleset_version: str
    server_time: datetime
    disclaimer: str
    astronaut: AstronautOut
    responder: AstronautOut
    habitat: HabitatOut
    anchors: list[AnchorOut]
    equipment: list[EquipmentOut]
    procedures: list[ProcedureSummary]
    scheduled_assessments: list[ScheduledAssessmentOut]
    observations: list[ObservationOut]
    observation_status: list[ObservationStatus]
    open_cases: list[CaseSummary]
    anatomical_regions: list[RegionOut]
    laterality_values: list[Laterality]
    surface_model: SurfaceModelOut = Field(description="Default model in the v2.2 shape. See surface_models.")
    surface_models: list[RegisteredSurfaceModelOut]
    anatomical_annotation_kinds: list[AnnotationKindOut]
    demo_inputs: DemoInputs
    research_datasets: list[DatasetSummary]


class ResetOut(BaseModel):
    reset: bool
    fixture_version: str
    reset_at: datetime
    research_records_before: int
    research_records_after: int
    message: str


class HealthOut(BaseModel):
    status: Literal["ok"]
    service: str
    contract_version: str
    database: Literal["ok", "error"]
    offline_capable: bool
    server_time: datetime

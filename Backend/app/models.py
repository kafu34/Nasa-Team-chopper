"""SQLite persistence models for SENTINEL AI (P0)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, UTCDateTime, utcnow


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


# --------------------------------------------------------------------------- synthetic demo world


class Astronaut(Base):
    __tablename__ = "astronauts"
    astronaut_id: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    fictional: Mapped[bool] = mapped_column(Boolean, default=True)
    mission_id: Mapped[str] = mapped_column(String)
    mission_name: Mapped[str] = mapped_column(String)
    habitat_id: Mapped[str] = mapped_column(ForeignKey("habitats.habitat_id"))
    mission_day: Mapped[int] = mapped_column(Integer)


class Habitat(Base):
    __tablename__ = "habitats"
    habitat_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    map_version: Mapped[str] = mapped_column(String)


class Zone(Base):
    __tablename__ = "zones"
    zone_id: Mapped[str] = mapped_column(String, primary_key=True)
    habitat_id: Mapped[str] = mapped_column(ForeignKey("habitats.habitat_id"), index=True)
    name: Mapped[str] = mapped_column(String)


class ZoneConnection(Base):
    __tablename__ = "zone_connections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    habitat_id: Mapped[str] = mapped_column(ForeignKey("habitats.habitat_id"), index=True)
    from_zone_id: Mapped[str] = mapped_column(ForeignKey("zones.zone_id"))
    to_zone_id: Mapped[str] = mapped_column(ForeignKey("zones.zone_id"))
    accessible: Mapped[bool] = mapped_column(Boolean)
    note: Mapped[str] = mapped_column(String, default="")
    hatch_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class WirelessAnchor(Base):
    __tablename__ = "wireless_anchors"
    anchor_id: Mapped[str] = mapped_column(String, primary_key=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.zone_id"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean)
    verified_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    verified_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class Equipment(Base):
    __tablename__ = "equipment"
    equipment_id: Mapped[str] = mapped_column(String, primary_key=True)
    device_model: Mapped[str] = mapped_column(String)
    capability: Mapped[str] = mapped_column(String, index=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.zone_id"), index=True)
    readiness: Mapped[str] = mapped_column(String)
    readiness_verified_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    supplies: Mapped[dict] = mapped_column(JSON, default=dict)
    required_supplies: Mapped[list] = mapped_column(JSON, default=list)
    compatible_procedure_ids: Mapped[list] = mapped_column(JSON, default=list)
    status_updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ProcedureDefinition(Base):
    __tablename__ = "procedure_definitions"
    procedure_id: Mapped[str] = mapped_column(String, primary_key=True)
    version: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    required_capability: Mapped[str] = mapped_column(String)
    definition: Mapped[dict] = mapped_column(JSON)


class HealthObservation(Base):
    __tablename__ = "health_observations"
    observation_id: Mapped[str] = mapped_column(String, primary_key=True)
    astronaut_id: Mapped[str] = mapped_column(ForeignKey("astronauts.astronaut_id"), index=True)
    type: Mapped[str] = mapped_column(String, index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    source: Mapped[str] = mapped_column(String)
    quality: Mapped[str] = mapped_column(String)
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    measurement_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class ScheduledAssessment(Base):
    __tablename__ = "scheduled_assessments"
    assessment_id: Mapped[str] = mapped_column(String, primary_key=True)
    astronaut_id: Mapped[str] = mapped_column(ForeignKey("astronauts.astronaut_id"), index=True)
    title: Mapped[str] = mapped_column(String)
    capability: Mapped[str] = mapped_column(String)
    procedure_id: Mapped[str] = mapped_column(ForeignKey("procedure_definitions.procedure_id"))
    due_at: Mapped[datetime] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String, default="scheduled")
    reason: Mapped[str] = mapped_column(Text)
    case_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)


class MedicalCase(Base):
    __tablename__ = "medical_cases"
    case_id: Mapped[str] = mapped_column(String, primary_key=True)
    astronaut_id: Mapped[str] = mapped_column(ForeignKey("astronauts.astronaut_id"), index=True)
    kind: Mapped[str] = mapped_column(String)  # routine | emergency
    state: Mapped[str] = mapped_column(String, index=True)
    priority: Mapped[str] = mapped_column(String)  # routine | urgent
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    requested_assessment: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    next_action: Mapped[str] = mapped_column(Text)
    follow_up_status: Mapped[str] = mapped_column(String, default="none")
    ruleset_version: Mapped[str] = mapped_column(String)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class SymptomReport(Base):
    __tablename__ = "symptom_reports"
    symptom_id: Mapped[str] = mapped_column(String, primary_key=True)
    astronaut_id: Mapped[str] = mapped_column(ForeignKey("astronauts.astronaut_id"), index=True)
    region_id: Mapped[str] = mapped_column(String)
    laterality: Mapped[str] = mapped_column(String)
    severity: Mapped[int] = mapped_column(Integer)
    onset: Mapped[datetime] = mapped_column(UTCDateTime)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    surface_point: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    reported_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    case_id: Mapped[str] = mapped_column(ForeignKey("medical_cases.case_id"), index=True)


class FollowUpTask(Base):
    __tablename__ = "follow_up_tasks"
    follow_up_id: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("medical_cases.case_id"), index=True)
    task_type: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    due_at: Mapped[datetime] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String, default="scheduled")
    interrupt: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ProcedureSession(Base):
    __tablename__ = "procedure_sessions"
    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("medical_cases.case_id"), index=True)
    procedure_id: Mapped[str] = mapped_column(ForeignKey("procedure_definitions.procedure_id"))
    procedure_version: Mapped[str] = mapped_column(String)
    actor_id: Mapped[str] = mapped_column(ForeignKey("astronauts.astronaut_id"))
    mode: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="in_progress")
    current_step_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    completed_steps: Mapped[list] = mapped_column(JSON, default=list)
    measurement_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)


class AssessmentMeasurement(Base):
    __tablename__ = "assessment_measurements"
    measurement_id: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("medical_cases.case_id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("procedure_sessions.session_id"), unique=True)
    astronaut_id: Mapped[str] = mapped_column(ForeignKey("astronauts.astronaut_id"), index=True)
    type: Mapped[str] = mapped_column(String)
    value: Mapped[dict] = mapped_column(JSON)
    unit: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class LocationEstimate(Base):
    __tablename__ = "location_estimates"
    estimate_id: Mapped[str] = mapped_column(String, primary_key=True)
    astronaut_id: Mapped[str] = mapped_column(ForeignKey("astronauts.astronaut_id"), index=True)
    zone_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    confidence: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String)
    observed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    estimated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class EmergencyEvent(Base):
    __tablename__ = "emergency_events"
    emergency_id: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("medical_cases.case_id"), index=True)
    astronaut_id: Mapped[str] = mapped_column(ForeignKey("astronauts.astronaut_id"))
    responder_id: Mapped[str] = mapped_column(ForeignKey("astronauts.astronaut_id"))
    trigger: Mapped[str] = mapped_column(String)
    activated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    entity_type: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str] = mapped_column(String, index=True)
    case_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


SYNTHETIC_TABLES = [
    # Deleted in this order on demo reset (children first). Research tables are never listed here.
    AuditEvent,
    EmergencyEvent,
    LocationEstimate,
    HealthObservation,
    AssessmentMeasurement,
    FollowUpTask,
    ProcedureSession,
    SymptomReport,
    ScheduledAssessment,
    MedicalCase,
    Equipment,
    WirelessAnchor,
    ProcedureDefinition,
    Astronaut,
    ZoneConnection,
    Zone,
    Habitat,
]


# --------------------------------------------------------------------------- genuine NASA research data


class DatasetImport(Base):
    __tablename__ = "dataset_imports"
    import_id: Mapped[str] = mapped_column(String, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String, index=True)
    source_file: Mapped[str] = mapped_column(String)
    sha256: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)  # IMPORTED | IMPORT_FAILED
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    rows_read: Mapped[int] = mapped_column(Integer, default=0)
    rows_imported: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    message: Mapped[str] = mapped_column(Text, default="")


class ResearchMeasurement(Base):
    __tablename__ = "research_measurements"
    __table_args__ = (
        UniqueConstraint("dataset_id", "source_file", "source_row_number", name="uq_research_row"),
        Index("ix_research_subject_analyte", "dataset_id", "subject_id", "analyte"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(String, index=True)
    import_id: Mapped[str] = mapped_column(ForeignKey("dataset_imports.import_id"))
    source_file: Mapped[str] = mapped_column(String)
    source_row_number: Mapped[int] = mapped_column(Integer)
    subject_id: Mapped[str] = mapped_column(String)
    sex: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    analyte: Mapped[str] = mapped_column(String)
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    value_raw: Mapped[str] = mapped_column(String)
    unit: Mapped[str] = mapped_column(String)
    range_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    range_min_raw: Mapped[str] = mapped_column(String)
    range_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    range_max_raw: Mapped[str] = mapped_column(String)
    test_type: Mapped[str] = mapped_column(String)
    timepoint: Mapped[str] = mapped_column(String)
    timepoint_phase: Mapped[str] = mapped_column(String)
    timepoint_day_offset: Mapped[int] = mapped_column(Integer)
    timepoint_order: Mapped[int] = mapped_column(Integer)


class GeneExpressionValue(Base):
    """One processed (normalised) expression value: one probe/probeset in one NASA research sample.

    Research data only (NASA_RESEARCH). Never linked to a SENTINEL astronaut, case or measurement.
    """

    __tablename__ = "gene_expression_values"
    __table_args__ = (
        UniqueConstraint("dataset_id", "source_file", "source_row_number", "sample_id", name="uq_expression_cell"),
        Index("ix_expression_sample_probe", "dataset_id", "sample_id", "probe_id"),
        Index("ix_expression_gene", "dataset_id", "gene_symbol"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(String, index=True)
    import_id: Mapped[str] = mapped_column(ForeignKey("dataset_imports.import_id"))
    source_file: Mapped[str] = mapped_column(String)
    source_row_number: Mapped[int] = mapped_column(Integer)
    source_column: Mapped[str] = mapped_column(String)
    sample_id: Mapped[str] = mapped_column(String)
    probe_id: Mapped[str] = mapped_column(String)
    gene_symbol: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    value_raw: Mapped[str] = mapped_column(String)


class AssayMeasurement(Base):
    """One value from a wide NASA bio-assay table (BIO_ASSAY_TABLE), e.g. OSD-656 urine NULISA panel.

    One record per (sample row, measurement column). Research data only (NASA_RESEARCH).
    """

    __tablename__ = "assay_measurements"
    __table_args__ = (
        UniqueConstraint("dataset_id", "source_file", "source_row_number", "source_column", name="uq_assay_cell"),
        Index("ix_assay_subject_analyte", "dataset_id", "subject_id", "analyte"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(String, index=True)
    import_id: Mapped[str] = mapped_column(ForeignKey("dataset_imports.import_id"))
    source_file: Mapped[str] = mapped_column(String)
    source_row_number: Mapped[int] = mapped_column(Integer)
    source_column: Mapped[str] = mapped_column(String)
    sample_name: Mapped[str] = mapped_column(String)
    subject_id: Mapped[str] = mapped_column(String)
    specimen: Mapped[str] = mapped_column(String)
    analyte: Mapped[str] = mapped_column(String)
    measure: Mapped[str] = mapped_column(String)
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    value_raw: Mapped[str] = mapped_column(String)
    unit: Mapped[str] = mapped_column(String)
    timepoint: Mapped[str] = mapped_column(String)
    timepoint_phase: Mapped[str] = mapped_column(String)
    timepoint_day_offset: Mapped[int] = mapped_column(Integer)
    timepoint_order: Mapped[int] = mapped_column(Integer)
    target_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    gene_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    uniprot_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    protein_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class TimeseriesValue(Base):
    """One reading of one metric from a NASA telemetry snapshot (e.g. RadLab radiation dosimetry).

    Research/context data only (NASA_RESEARCH). Never a SENTINEL habitat (HAB-01) or astronaut reading.
    """

    __tablename__ = "timeseries_values"
    __table_args__ = (
        UniqueConstraint("dataset_id", "source_file", "source_row_number", "metric", name="uq_timeseries_cell"),
        Index("ix_timeseries_metric_time", "dataset_id", "metric", "timestamp"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(String, index=True)
    import_id: Mapped[str] = mapped_column(ForeignKey("dataset_imports.import_id"))
    source_file: Mapped[str] = mapped_column(String)
    source_row_number: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime)
    timestamp_raw: Mapped[str] = mapped_column(String)
    instrument_id: Mapped[str] = mapped_column(String)
    instrument_family: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    spacecraft: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    module: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    metric: Mapped[str] = mapped_column(String)
    value: Mapped[float] = mapped_column(Float)
    value_raw: Mapped[str] = mapped_column(String)
    unit: Mapped[str] = mapped_column(String)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    altitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class HistologyCount(Base):
    """One count from a NASA histology/immunostaining table (HISTOLOGY_COUNTS_V1), e.g. OSD-817 TUNEL / CTB.

    Ex vivo human donor tissue; research data only (NASA_RESEARCH).
    """

    __tablename__ = "histology_counts"
    __table_args__ = (
        UniqueConstraint("dataset_id", "source_file", "source_row_number", "measure", name="uq_histology_cell"),
        Index("ix_histology_assay", "dataset_id", "assay", "donor_id"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(String, index=True)
    import_id: Mapped[str] = mapped_column(ForeignKey("dataset_imports.import_id"))
    source_file: Mapped[str] = mapped_column(String)
    source_row_number: Mapped[int] = mapped_column(Integer)
    sample_name: Mapped[str] = mapped_column(String)
    donor_id: Mapped[str] = mapped_column(String)
    eye: Mapped[str] = mapped_column(String)
    fixation: Mapped[str] = mapped_column(String)
    assay: Mapped[str] = mapped_column(String)
    measure: Mapped[str] = mapped_column(String)
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    value_raw: Mapped[str] = mapped_column(String)
    group_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    days_on_system: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    donor_sex: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    donor_age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    annotation_file: Mapped[Optional[str]] = mapped_column(String, nullable=True)

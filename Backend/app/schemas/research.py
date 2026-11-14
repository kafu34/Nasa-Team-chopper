from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .common import DataCategory, DatasetStatus

DatasetId = Literal["OSD-575", "OSD-656", "NASA-EDA", "NASA-RADLAB", "OSD-654", "OSD-684", "OSD-573", "OSD-817"]
RecordSchema = Literal[
    "CMP_ANALYTE_V1", "BIO_ASSAY_TABLE", "ENVIRONMENT_TIMESERIES_V1", "RADIATION_TIMESERIES_V1",
    "OMICS_OR_IMAGING",
]


class ImportInfo(BaseModel):
    import_id: str
    source_file: str
    sha256: str
    status: Literal["IMPORTED", "IMPORT_FAILED"]
    started_at: datetime
    finished_at: Optional[datetime]
    rows_read: int
    rows_imported: int
    missing_values: dict[str, int] = Field(description="Count of missing (null) values per column.")
    message: str


class DatasetSummary(BaseModel):
    dataset_id: DatasetId
    title: str
    title_verified: bool = Field(description="False when the exact title has not been confirmed from the source.")
    description: str
    source_url: Optional[str]
    source_url_verified: bool
    organization: str
    data_category: DataCategory = "NASA_RESEARCH"
    record_schema: RecordSchema
    priority: Literal["P0", "P1", "P2"]
    status: DatasetStatus
    status_reason: str
    expected_files: list[str]
    records_available: int
    records_endpoint: Optional[str] = Field(description="Endpoint returning numerical records, when IMPORTED.")


class DatasetDetail(DatasetSummary):
    experimental_context: str
    limitations: list[str]
    latest_import: Optional[ImportInfo]
    raw_dir: str = Field(description="Repository-relative folder the importer reads.")


class DatasetList(BaseModel):
    datasets: list[DatasetSummary]
    status_values: list[DatasetStatus]
    data_categories: list[DataCategory]


class Provenance(BaseModel):
    dataset_id: DatasetId
    title: str
    organization: str
    source_url: str
    source_file: str
    sha256: str
    import_id: str
    imported_at: datetime
    transformation: str


class CmpRecord(BaseModel):
    """One analyte value from LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv."""

    record_id: int
    dataset_id: DatasetId
    subject_id: str = Field(description="Anonymised research subject ID as published (e.g. C001).")
    sex: Optional[str]
    analyte: str = Field(description="ANALYTE column, verbatim.")
    value: Optional[float] = Field(description="Numeric VALUE; null when the source says NA.")
    value_raw: str = Field(description="VALUE column exactly as in the source file.")
    unit: str = Field(description="UNITS column, verbatim.")
    range_min: Optional[float]
    range_min_raw: str
    range_max: Optional[float] = Field(description="Null when the source says N/A (no upper bound).")
    range_max_raw: str
    test_type: str
    timepoint: str = Field(description="Original label, e.g. L-92 (92 days before launch) or R+1 (1 day after return).")
    timepoint_phase: Literal["PREFLIGHT", "POSTFLIGHT"]
    timepoint_day_offset: int = Field(description="Signed days relative to launch (L) or return (R).")
    timepoint_order: int = Field(description="Chronological sort key across all timepoints.")
    source_file: str
    source_row_number: int = Field(description="1-based data row number in the source CSV (header excluded).")
    data_category: DataCategory = "NASA_RESEARCH"


class ResearchRecordsPage(BaseModel):
    dataset_id: DatasetId
    title: str
    source_url: str
    source_file: str
    record_schema: RecordSchema
    data_category: DataCategory = "NASA_RESEARCH"
    provenance: Provenance
    total: int = Field(description="Total records matching the filters.")
    limit: int
    offset: int
    filters_applied: dict[str, Optional[str]]
    available_subjects: list[str]
    available_analytes: list[str]
    available_timepoints: list[str] = Field(description="Chronologically ordered.")
    limitations: list[str]
    records: list[CmpRecord]


class TimeseriesPoint(BaseModel):
    timestamp: datetime
    value: Optional[float]
    unit: str


class TimeseriesPage(BaseModel):
    dataset_id: DatasetId
    metric: str
    unit: str
    data_category: DataCategory = "NASA_RESEARCH"
    provenance: Provenance
    total: int
    limit: int
    offset: int
    points: list[TimeseriesPoint]

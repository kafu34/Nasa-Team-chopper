from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .common import DataCategory, DatasetStatus, HumanHealthAnalysis, StudyType

DatasetId = Literal["OSD-575", "OSD-656", "NASA-EDA", "NASA-RADLAB", "OSD-654", "OSD-684", "OSD-573", "OSD-817",
                    "OSD-195", "OSD-546"]
RecordSchema = Literal[
    "CMP_ANALYTE_V1", "BIO_ASSAY_TABLE", "ENVIRONMENT_TIMESERIES_V1", "RADIATION_TIMESERIES_V1",
    "OMICS_OR_IMAGING", "GENE_EXPRESSION_V1",
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
    # v2.2 classification (additive fields)
    study_type: StudyType
    organism: str = Field(description="Organism studied, e.g. 'Homo sapiens', 'Mus musculus', or 'not applicable'.")
    human_health_analysis: HumanHealthAnalysis = Field(
        description="PRIMARY_HUMAN_RESEARCH for human studies; animal and environment sources are kept separate.")
    astronaut_specific_findings_allowed: Literal[False] = Field(
        False, description="Always false: no NASA research dataset generates findings about a SENTINEL astronaut.")
    body_systems: list[str] = Field(description="Anatomical Twin research panels this dataset informs, "
                                                "e.g. skeletal_muscle, bone, blood_chemistry.")
    measured: str = Field(description="Plain statement of what the experiment actually measured.")
    not_a_measurement_of: list[str] = Field(description="Things this dataset must never be displayed as.")


class DatasetDetail(DatasetSummary):
    experimental_context: str
    limitations: list[str]
    latest_import: Optional[ImportInfo]
    raw_dir: str = Field(description="Repository-relative folder the importer reads.")


class StudyTypeInfo(BaseModel):
    study_type: StudyType
    label: str
    description: str


class DatasetList(BaseModel):
    datasets: list[DatasetSummary]
    status_values: list[DatasetStatus]
    data_categories: list[DataCategory]
    study_types: list[StudyTypeInfo] = Field(default_factory=list, description="v2.2 classification legend.")


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


class ResearchSample(BaseModel):
    """Verified sample metadata for an expression dataset (from the NASA OSDR study metadata)."""

    sample_id: str = Field(description="GEO sample accession used by NASA OSDR, e.g. GSM2813750.")
    subject_id: Optional[str] = Field(description="Anonymised research subject number as published; null for cells.")
    study_type: StudyType
    factors: dict[str, str] = Field(description="Experimental factor values, verbatim from OSDR metadata.")
    factors_verified: dict[str, bool] = Field(description="Per factor: true when read verbatim from the OSDR "
                                                          "sample table; false when derived (e.g. from file names).")
    condition_label: str
    source_file_name: Optional[str] = Field(description="Name of the NASA file this sample's values came from.")
    imported: bool


class ComparisonReadiness(BaseModel):
    ready: bool = Field(description="True only when matched samples and verified normalisation are both present.")
    reasons: list[str]


class GeneExpressionRecord(BaseModel):
    """One processed expression value: one probe/probeset in one research sample (GENE_EXPRESSION_V1)."""

    record_id: int
    dataset_id: DatasetId
    sample_id: str
    subject_id: Optional[str]
    condition_label: str
    probe_id: str = Field(description="Probe/probeset/transcript-cluster ID, verbatim.")
    gene_symbol: Optional[str] = Field(description="Gene symbol when present in the NASA file; never inferred.")
    value: Optional[float] = Field(description="Processed expression value; null when the source cell is missing.")
    value_raw: str
    value_unit: str = Field(description="Scale of the value as published by NASA (e.g. RMA, log2 scale).")
    normalization: str
    normalization_verified: bool
    source_file: str
    source_row_number: int
    source_column: str
    data_category: DataCategory = "NASA_RESEARCH"


class AssayRecord(BaseModel):
    """One value from a wide bio-assay table (BIO_ASSAY_TABLE), e.g. OSD-656 urine inflammation panel."""

    record_id: int
    dataset_id: DatasetId
    sample_name: str = Field(description="'Sample Name' exactly as in the source, e.g. C001_urine_L-92.")
    subject_id: str = Field(description="Anonymised research subject ID as published (e.g. C001).")
    specimen: str = Field(description="Specimen type parsed from the sample name, e.g. urine.")
    analyte: str = Field(description="Target name as in the column header, e.g. il6.")
    measure: Literal["concentration_npq", "percent_normalized_value"]
    value: Optional[float] = Field(description="Numeric value; null when the source says NA.")
    value_raw: str
    unit: str
    timepoint: str
    timepoint_phase: Literal["PREFLIGHT", "POSTFLIGHT"]
    timepoint_day_offset: int
    timepoint_order: int
    target_name: Optional[str] = Field(description="From the NASA target information file; null if no exact match.")
    gene_name: Optional[str]
    uniprot_id: Optional[str]
    protein_name: Optional[str]
    source_file: str
    source_row_number: int
    source_column: str = Field(description="Exact column header in the source file.")
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
    records: list[CmpRecord] = Field(description="CMP_ANALYTE_V1 records (OSD-575). Empty for other schemas.")
    # v2.2 additive fields for GENE_EXPRESSION_V1 datasets (OSD-195, OSD-546)
    study_type: Optional[StudyType] = None
    expression_records: list[GeneExpressionRecord] = Field(
        default_factory=list, description="GENE_EXPRESSION_V1 records. Empty for other schemas.")
    samples: list[ResearchSample] = Field(default_factory=list, description="Sample metadata (expression datasets).")
    assay_records: list[AssayRecord] = Field(
        default_factory=list, description="BIO_ASSAY_TABLE records (OSD-656). Empty for other schemas.")
    available_measures: list[str] = Field(default_factory=list,
                                          description="BIO_ASSAY_TABLE measure names present in the dataset.")
    comparison_readiness: Optional[ComparisonReadiness] = None
    source_files: list[Provenance] = Field(default_factory=list,
                                           description="Provenance of every imported file (multi-file datasets).")


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

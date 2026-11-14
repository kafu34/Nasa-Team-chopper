"""Registry of the eight canonical NASA dataset identifiers and their availability status.

Metadata marked *_verified=False has not been confirmed verbatim from the NASA source and must be
checked before it is quoted in the submission.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import REPO_DIR, Settings
from ..schemas.research import DatasetDetail, DatasetSummary, ImportInfo

OSDR = "NASA Open Science Data Repository (OSDR)"
OSD575_FILE = "LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv"

REGISTRY: dict[str, dict] = {
    "OSD-575": dict(
        title="SpaceX Inspiration4 Blood Serum Metabolic Panel and Immune/Cardiac Cytokine Arrays",
        title_verified=False,
        description="Serum from the four Inspiration4 crew members (C001-C004) collected before launch and after "
                    "return: comprehensive metabolic panel (CMP) plus immune and cardiovascular multiplex arrays.",
        source_url="https://osdr.nasa.gov/bio/repo/data/studies/OSD-575",
        source_url_verified=True,
        record_schema="CMP_ANALYTE_V1",
        priority="P0",
        expected_files=[OSD575_FILE],
        importer=True,
        experimental_context="SpaceX Inspiration4 (September 2021, about 3 days in low Earth orbit). Samples were "
                             "collected on the ground at L-92, L-44 and L-3 (days before launch) and R+1, R+45, "
                             "R+82 and R+194 (days after return). No sample in this file was collected in flight.",
        limitations=[
            "Four civilian crew members; far too small for clinical conclusions.",
            "Preflight and postflight ground samples only; not in-flight measurements.",
            "Reference ranges are the laboratory's general ranges, not personal astronaut thresholds.",
            "Laboratory assays; SENTINEL does not claim any onboard device can replicate them.",
            "Shown as research context only. Never substituted for fictional DEMO-001 measurements.",
        ],
    ),
    "OSD-656": dict(
        title="OSD-656: Inspiration4 urine inflammation panel (title pending verification)",
        title_verified=False,
        description="Urine from the four Inspiration4 crew members, pre- and post-flight, NULISA-seq 200-plex "
                    "inflammation panel (Alamar Biosciences).",
        source_url="https://osdr.nasa.gov/bio/repo/data/studies/OSD-656",
        source_url_verified=False,
        record_schema="BIO_ASSAY_TABLE",
        priority="P1",
        expected_files=["LSDS-64_Multiplex_urine.immune.AlamarPanel_TRANSFORMED.csv"],
        importer=False,
        experimental_context="SpaceX Inspiration4; ground samples before launch and after return.",
        limitations=["No importer in P0.", "Small cohort; research context only."],
    ),
    "NASA-EDA": dict(
        title="Environmental Data App (EDA)",
        title_verified=True,
        description="NASA OSDR portal for ISS cabin and hardware environmental telemetry (temperature, relative "
                    "humidity, CO2) and radiation summaries for selected missions.",
        source_url="https://visualization.osdr.nasa.gov/eda/",
        source_url_verified=True,
        record_schema="ENVIRONMENT_TIMESERIES_V1",
        priority="P1",
        expected_files=["(EDA telemetry table export, CSV)"],
        importer=False,
        experimental_context="ISS environmental telemetry for specific research missions; not SENTINEL habitat data.",
        limitations=["No importer in P0.", "ISS telemetry must not be shown as live HAB-01 readings."],
    ),
    "NASA-RADLAB": dict(
        title="NASA RadLab radiation data (title and URL pending verification)",
        title_verified=False,
        description="Space radiation dosimetry data. Exact portal name and URL not yet confirmed.",
        source_url="https://visualization.osdr.nasa.gov/radlab/",
        source_url_verified=False,
        record_schema="RADIATION_TIMESERIES_V1",
        priority="P1",
        expected_files=["(RadLab export, CSV)"],
        importer=False,
        experimental_context="Not yet confirmed.",
        limitations=["No importer in P0.", "Source not yet verified.",
                     "Must not be shown as live HAB-01 dosimeter readings."],
    ),
    "OSD-654": dict(
        title="OSD-654: mouse tibia bone DXA and micro-CT (title pending verification)",
        title_verified=False,
        description="Mouse (C57BL/6J) tibia bone measurements by DXA and micro-CT, including hindlimb-unloading "
                    "ground-analogue groups.",
        source_url="https://osdr.nasa.gov/bio/repo/data/studies/OSD-654",
        source_url_verified=False,
        record_schema="BIO_ASSAY_TABLE",
        priority="P2",
        expected_files=["LSDS-66_microCT_uCT_TRANSFORMED.csv", "LSDS-66_Bone_Biomechanical_DXA_tibia_TRANSFORMED.csv"],
        importer=False,
        experimental_context="Animal ground-analogue study; not human data.",
        limitations=["No importer in P0.", "Mouse data; not transferable to astronaut thresholds."],
    ),
    "OSD-684": dict(
        title="Human skeletal muscle tissue chip autonomous payload reveals changes in fiber type and metabolic "
              "gene expression due to spaceflight",
        title_verified=True,
        description="Bulk RNA-seq of human skeletal muscle tissue chips, spaceflight versus ground control.",
        source_url="https://osdr.nasa.gov/bio/repo/data/studies/OSD-684",
        source_url_verified=False,
        record_schema="OMICS_OR_IMAGING",
        priority="P2",
        expected_files=["GLDS-615_rna_seq_Normalized_Counts_GLbulkRNAseq.csv"],
        importer=False,
        experimental_context="Tissue-chip payload; cells, not astronauts.",
        limitations=["No importer in P0.", "Large omics processing deferred (P2)."],
    ),
    "OSD-573": dict(
        title="OSD-573: Inspiration4 capsule metagenomics (title pending verification)",
        title_verified=False,
        description="Shotgun metagenomic sequencing of environmental swabs from the Inspiration4 Dragon capsule.",
        source_url="https://osdr.nasa.gov/bio/repo/data/studies/OSD-573",
        source_url_verified=False,
        record_schema="OMICS_OR_IMAGING",
        priority="P2",
        expected_files=["GLDS-565_GMetagenomics_README.txt"],
        importer=False,
        experimental_context="Spacecraft environment microbiology.",
        limitations=["No importer in P0.", "Large sequence files; processing deferred (P2)."],
    ),
    "OSD-817": dict(
        title="OSD-817: human optic nerve tissue study (title pending verification)",
        title_verified=False,
        description="Histology and immunostaining of human donor optic nerve tissue (organotypic culture).",
        source_url="https://osdr.nasa.gov/bio/repo/data/studies/OSD-817",
        source_url_verified=False,
        record_schema="OMICS_OR_IMAGING",
        priority="P2",
        expected_files=["LSDS-135_microscopy_PPD_TRANSFORMED.csv"],
        importer=False,
        experimental_context="Donor tissue study; relevance to spaceflight eye changes not yet verified here.",
        limitations=["No importer in P0.", "Imaging processing deferred (P2)."],
    ),
}

CANONICAL_IDS = list(REGISTRY)


def raw_dir_for(settings: Settings, dataset_id: str) -> Path:
    # OSD-575's file lives directly in data/nasa/raw/ (owner instruction); others in data/nasa/raw/<ID>/.
    return settings.nasa_raw_dir if dataset_id == "OSD-575" else settings.nasa_raw_dir / dataset_id


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_DIR).as_posix()
    except ValueError:
        return path.as_posix()


def latest_import(db: Session, dataset_id: str) -> m.DatasetImport | None:
    return db.scalars(select(m.DatasetImport).where(m.DatasetImport.dataset_id == dataset_id)
                      .order_by(m.DatasetImport.started_at.desc())).first()


def record_count(db: Session, dataset_id: str) -> int:
    return db.scalar(select(func.count()).select_from(m.ResearchMeasurement)
                     .where(m.ResearchMeasurement.dataset_id == dataset_id)) or 0


def compute_status(db: Session, settings: Settings, dataset_id: str) -> tuple[str, str]:
    meta = REGISTRY[dataset_id]
    n = record_count(db, dataset_id)
    last = latest_import(db, dataset_id)
    if n > 0:
        return "IMPORTED", f"{n} records imported."
    if last is not None and last.status == "IMPORT_FAILED":
        return "IMPORT_FAILED", last.message
    folder = raw_dir_for(settings, dataset_id)
    if meta["importer"]:
        if (folder / meta["expected_files"][0]).is_file():
            return "READY_TO_IMPORT", "Source file present; run the importer."
        return "NOT_DOWNLOADED", f"Place {meta['expected_files'][0]} in {_rel(folder)}/."
    if folder.is_dir() and any(folder.iterdir()):
        return "UNSUPPORTED_FORMAT", "Files present but no importer is implemented yet (deferred feature)."
    return "NOT_DOWNLOADED", "Not downloaded. No importer implemented yet (deferred feature)."


def _base(db: Session, settings: Settings, dataset_id: str) -> dict:
    meta = REGISTRY[dataset_id]
    status, reason = compute_status(db, settings, dataset_id)
    return dict(
        dataset_id=dataset_id,
        title=meta["title"],
        title_verified=meta["title_verified"],
        description=meta["description"],
        source_url=meta["source_url"],
        source_url_verified=meta["source_url_verified"],
        organization=OSDR,
        record_schema=meta["record_schema"],
        priority=meta["priority"],
        status=status,
        status_reason=reason,
        expected_files=meta["expected_files"],
        records_available=record_count(db, dataset_id),
        records_endpoint=f"/api/v1/research/datasets/{dataset_id}/records" if status == "IMPORTED" else None,
    )


def summary(db: Session, settings: Settings, dataset_id: str) -> DatasetSummary:
    return DatasetSummary(**_base(db, settings, dataset_id))


def detail(db: Session, settings: Settings, dataset_id: str) -> DatasetDetail:
    meta = REGISTRY[dataset_id]
    last = latest_import(db, dataset_id)
    info = None
    if last is not None:
        info = ImportInfo(import_id=last.import_id, source_file=last.source_file, sha256=last.sha256,
                          status=last.status, started_at=last.started_at, finished_at=last.finished_at,
                          rows_read=last.rows_read, rows_imported=last.rows_imported,
                          missing_values=last.summary.get("missing_values", {}), message=last.message)
    return DatasetDetail(**_base(db, settings, dataset_id), experimental_context=meta["experimental_context"],
                         limitations=meta["limitations"], latest_import=info,
                         raw_dir=_rel(raw_dir_for(settings, dataset_id)))

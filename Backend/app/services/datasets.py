"""Registry of the canonical NASA dataset identifiers (eight from v2.1, OSD-195 and OSD-546 from v2.2),
their scientific classification and availability status.

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
        title="SpaceX Inspiration4 Blood Serum Metabolic Panel and Immune/Cardiac Cytokine Arrays (Comprehensive "
              "Metabolic Panel and Multiplex)",
        title_verified=True,
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
        title="SpaceX Inspiration4 Urine Inflammation Panel (Multiplex, NULISAseq)",
        title_verified=True,
        description="Urine from the four Inspiration4 crew members, pre- and post-flight, NULISA-seq 200-plex "
                    "inflammation panel (Alamar Biosciences).",
        source_url="https://osdr.nasa.gov/bio/repo/data/studies/OSD-656",
        source_url_verified=True,
        record_schema="BIO_ASSAY_TABLE",
        priority="P1",
        expected_files=["LSDS-64_Multiplex_urine.immune.AlamarPanel_TRANSFORMED.csv",
                        "LSDS-64_Multiplex_200plex v1-Target Information.csv"],
        importer=True,
        experimental_context="SpaceX Inspiration4 (about 3 days in low Earth orbit). Urine collected on the ground "
                             "before launch (L-92, L-44, L-3) and after return (R+1, R+45, R+82). Not in-flight "
                             "samples. 22 samples from crew members C001-C004 (not every member at every "
                             "timepoint).",
        limitations=[
            "Four civilian crew members; far too small for clinical conclusions.",
            "Preflight and postflight ground samples only; not in-flight measurements.",
            "NPQ and percent-normalized values are relative assay units as published, not clinical "
            "concentrations; no reference ranges exist in the file.",
            "Two columns with an empty header in the NASA file are not imported (meaning cannot be verified).",
            "Research context only. Never used to diagnose or assess a SENTINEL astronaut.",
        ],
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
        title="RadLab",
        title_verified=True,
        description="NASA OSDR visualization portal giving a single point of access to radiation telemetry "
                    "(dosimetry) data from databases maintained by multiple space agencies.",
        source_url="https://visualization.osdr.nasa.gov/radlab/",
        source_url_verified=True,
        record_schema="RADIATION_TIMESERIES_V1",
        priority="P1",
        expected_files=["(RadLab export, CSV)"],
        importer=False,
        experimental_context="Radiation dosimetry from space missions, aggregated across agencies; not SENTINEL "
                             "habitat data.",
        limitations=["No importer in P0.",
                     "Must not be shown as live HAB-01 dosimeter readings."],
    ),
    "OSD-654": dict(
        title="Toward countering muscle and bone loss with spaceflight: GSK3 as a potential target (Tibia, RR9 and "
              "HLU, MicroCT and DXA Scanning)",
        title_verified=True,
        description="Mouse (Mus musculus) tibia bone measurements by DXA and micro-CT from the Rodent Research-9 "
                    "spaceflight mission (SpaceX-12, ISS, Aug-Sep 2017) and a hindlimb-unloading (HLU) ground "
                    "analogue.",
        source_url="https://osdr.nasa.gov/bio/repo/data/studies/OSD-654",
        source_url_verified=True,
        record_schema="BIO_ASSAY_TABLE",
        priority="P2",
        expected_files=["LSDS-66_microCT_uCT_TRANSFORMED.csv", "LSDS-66_Bone_Biomechanical_DXA_tibia_TRANSFORMED.csv"],
        importer=False,
        experimental_context="Animal study (mice): spaceflight on the ISS (Rodent Research-9) plus a hindlimb-unloading "
                             "ground analogue. Not human data. Kept separately identified as animal research and "
                             "excluded from SENTINEL's primary human-health analysis (v2.2).",
        limitations=["No importer in P0.", "Mouse data; not transferable to astronaut thresholds.",
                     "Animal research: never used to generate astronaut-specific medical findings."],
    ),
    "OSD-684": dict(
        title="Human skeletal muscle tissue chip autonomous payload reveals changes in fiber type and metabolic "
              "gene expression due to spaceflight",
        title_verified=True,
        description="Bulk RNA-seq of human skeletal muscle tissue chips, spaceflight versus ground control.",
        source_url="https://osdr.nasa.gov/bio/repo/data/studies/OSD-684",
        source_url_verified=True,
        record_schema="OMICS_OR_IMAGING",
        priority="P2",
        expected_files=["GLDS-615_rna_seq_Normalized_Counts_GLbulkRNAseq.csv"],
        importer=False,
        experimental_context="Tissue-chip payload; cells, not astronauts.",
        limitations=["No importer in P0.", "Large omics processing deferred (P2)."],
    ),
    "OSD-573": dict(
        title="SpaceX Inspiration4 Dragon Capsule Metagenomic and Metatranscriptomic Microbial Swabs",
        title_verified=True,
        description="Metagenomic and metatranscriptomic sequencing of swabs from nine surfaces inside the SpaceX "
                    "Inspiration4 Dragon capsule, plus an open-air control.",
        source_url="https://osdr.nasa.gov/bio/repo/data/studies/OSD-573",
        source_url_verified=True,
        record_schema="OMICS_OR_IMAGING",
        priority="P2",
        expected_files=["GLDS-565_GMetagenomics_README.txt"],
        importer=False,
        experimental_context="Spacecraft environment microbiology.",
        limitations=["No importer in P0.", "Large sequence files; processing deferred (P2)."],
    ),
    "OSD-817": dict(
        title="The ex vivo human translaminar autonomous system to study spaceflight associated neuro-ocular "
              "syndrome pathogenesis (Optic Nerve, Histology and Microscopy)",
        title_verified=True,
        description="Histology and light microscopy of human donor optic-nerve tissue in organotypic culture, "
                    "used as a ground model of spaceflight-associated neuro-ocular syndrome (SANS).",
        source_url="https://osdr.nasa.gov/bio/repo/data/studies/OSD-817",
        source_url_verified=True,
        record_schema="OMICS_OR_IMAGING",
        priority="P2",
        expected_files=["LSDS-135_microscopy_PPD_TRANSFORMED.csv"],
        importer=False,
        experimental_context="Ground study on donated human tissue (no spaceflight); a laboratory model for "
                             "studying spaceflight-associated neuro-ocular syndrome.",
        limitations=["No importer in P0.", "Imaging processing deferred (P2)."],
    ),
    "OSD-195": dict(
        title="Effects of 21 days of bedrest on human skeletal muscle gene expression",
        title_verified=True,
        description="Skeletal-muscle (vastus lateralis) gene expression in 12 healthy male volunteers before and "
                    "after 21 days of bed rest, Affymetrix microarrays. One processed (normalised) expression file "
                    "per sample (24 samples).",
        source_url="https://osdr.nasa.gov/bio/repo/data/studies/OSD-195",
        source_url_verified=True,
        record_schema="GENE_EXPRESSION_V1",
        priority="P1",
        expected_files=["GLDS-195_microarray_GSM2813749_processed.txt",
                        "GLDS-195_microarray_GSM2813750_processed.txt",
                        "(any other GLDS-195_microarray_GSM<id>_processed.txt from OSDR)"],
        importer=True,
        experimental_context="Human ground analogue: bed rest on Earth. Nobody in this study flew in space. "
                             "Sample pairs are matched per subject (Before Bed Rest / After Bed Rest), verified "
                             "from the NASA OSDR sample metadata.",
        limitations=[
            "Ground-analogue (bed rest) study, not an astronaut or spaceflight dataset.",
            "Gene expression (mRNA abundance) only; it is not a measurement of muscle mass, strength or function.",
            "12 healthy male volunteers; not representative of all crew members.",
            "Normalisation method stated in the OSDR summary (RMA) is not yet verified verbatim; no cross-sample "
            "comparison is computed by SENTINEL.",
            "Raw .CEL microarray files are not processed by SENTINEL (P2).",
            "Research context only. Never used to diagnose or assess a SENTINEL astronaut.",
        ],
    ),
    "OSD-546": dict(
        title="SCD – Stem Cell Differentiation Toward Osteoblast Onboard the International Space Station",
        title_verified=True,
        description="Human bone-marrow mesenchymal stem cells cultured about 2 weeks aboard the ISS (Soyuz "
                    "TMA-15M/TMA-16M) in osteogenic or standard medium, versus ground controls; Affymetrix Human "
                    "Gene 1.0 ST microarrays processed by the NASA GeneLab pipeline.",
        source_url="https://osdr.nasa.gov/bio/repo/data/studies/OSD-546",
        source_url_verified=True,
        record_schema="GENE_EXPRESSION_V1",
        priority="P1",
        expected_files=["GLDS-546_array_normalized_expression_probeset.csv", "GLDS-546_array_SampleTable.csv"],
        importer=True,
        experimental_context="Spaceflight experiment on human-derived cells in culture (13 samples: 7 flight, "
                             "6 ground control). No astronaut was measured. Spaceflight (Space Flight / Ground "
                             "Control) and Treatment (osteogenic / standard medium) verified from NASA GeneLab's "
                             "GLDS-546_array_SampleTable.csv and runsheet.",
        limitations=[
            "Human-derived cells in culture, not a measurement of any person's bone density or bone health.",
            "Gene expression only; not bone mineral density, fracture risk or osteoporosis status.",
            "Small groups: 3-4 cell-culture replicates per flight/medium group.",
            "No differential-expression result is recomputed or reinterpreted by SENTINEL.",
            "Research context only. Never used to diagnose or assess a SENTINEL astronaut.",
        ],
    ),
}

# v2.2 scientific classification. human_health_analysis keeps animal and environment sources out of the
# primary human-health analysis. No dataset may generate astronaut-specific findings.
CLASSIFICATION: dict[str, dict] = {
    "OSD-575": dict(study_type="HUMAN_SPACEFLIGHT", organism="Homo sapiens",
                    human_health_analysis="PRIMARY_HUMAN_RESEARCH", body_systems=["blood_chemistry"],
                    measured="Blood serum chemistry (comprehensive metabolic panel) of the four Inspiration4 crew "
                             "members, sampled on the ground before launch and after return.",
                    not_a_measurement_of=["SENTINEL astronaut DEMO-001 or DEMO-002", "in-flight blood chemistry"]),
    "OSD-656": dict(study_type="HUMAN_SPACEFLIGHT", organism="Homo sapiens",
                    human_health_analysis="PRIMARY_HUMAN_RESEARCH", body_systems=["immune_inflammation"],
                    measured="Urine inflammation protein panel of the Inspiration4 crew, pre- and post-flight.",
                    not_a_measurement_of=["SENTINEL astronaut DEMO-001 or DEMO-002"]),
    "NASA-EDA": dict(study_type="SPACEFLIGHT_ENVIRONMENT", organism="not applicable",
                     human_health_analysis="ENVIRONMENT_CONTEXT", body_systems=[],
                     measured="ISS cabin environmental telemetry for specific research missions.",
                     not_a_measurement_of=["live HAB-01 habitat readings", "any person's physiology"]),
    "NASA-RADLAB": dict(study_type="SPACEFLIGHT_ENVIRONMENT", organism="not applicable",
                        human_health_analysis="ENVIRONMENT_CONTEXT", body_systems=[],
                        measured="Space radiation dosimetry telemetry from multiple space agencies.",
                        not_a_measurement_of=["live HAB-01 dosimeter readings", "an astronaut's personal dose"]),
    "OSD-654": dict(study_type="ANIMAL_RESEARCH", organism="Mus musculus",
                    human_health_analysis="SEPARATE_ANIMAL_RESEARCH", body_systems=["bone"],
                    measured="Mouse tibia bone measurements (DXA, micro-CT) after ISS spaceflight (Rodent "
                             "Research-9) or hindlimb unloading on the ground.",
                    not_a_measurement_of=["human or astronaut bone density"]),
    "OSD-684": dict(study_type="HUMAN_DERIVED_CELLS", organism="Homo sapiens",
                    human_health_analysis="PRIMARY_HUMAN_RESEARCH", body_systems=["skeletal_muscle"],
                    measured="Gene expression of human skeletal-muscle tissue chips, spaceflight vs ground.",
                    not_a_measurement_of=["astronaut muscle mass or strength"]),
    "OSD-573": dict(study_type="SPACEFLIGHT_ENVIRONMENT", organism="microbial communities (metagenomics)",
                    human_health_analysis="ENVIRONMENT_CONTEXT", body_systems=[],
                    measured="Microbial DNA from Inspiration4 capsule surface swabs.",
                    not_a_measurement_of=["an astronaut infection or microbiome diagnosis"]),
    "OSD-817": dict(study_type="HUMAN_DERIVED_CELLS", organism="Homo sapiens",
                    human_health_analysis="PRIMARY_HUMAN_RESEARCH", body_systems=["eye_optic_nerve"],
                    measured="Histology and microscopy of human donor optic-nerve tissue in culture (ground model "
                             "of spaceflight-associated neuro-ocular syndrome).",
                    not_a_measurement_of=["astronaut eye health or vision"]),
    "OSD-195": dict(study_type="HUMAN_GROUND_ANALOGUE", organism="Homo sapiens",
                    human_health_analysis="PRIMARY_HUMAN_RESEARCH", body_systems=["skeletal_muscle"],
                    measured="mRNA expression in thigh-muscle biopsies of volunteers before and after 21 days of "
                             "bed rest on Earth.",
                    not_a_measurement_of=["astronaut muscle mass", "muscle strength",
                                          "muscle deterioration of any SENTINEL astronaut", "spaceflight data"]),
    "OSD-546": dict(study_type="HUMAN_DERIVED_CELLS", organism="Homo sapiens",
                    human_health_analysis="PRIMARY_HUMAN_RESEARCH", body_systems=["bone"],
                    measured="mRNA expression of human bone-marrow stem cells cultured aboard the ISS versus on "
                             "the ground, in osteogenic or standard medium.",
                    not_a_measurement_of=["astronaut bone density", "bone mineral density", "fracture risk",
                                          "any person's bone health"]),
}

STUDY_TYPES = [
    ("HUMAN_SPACEFLIGHT", "Human spaceflight measurements",
     "Measurements from people who flew in space (samples may be collected before launch or after return)."),
    ("HUMAN_GROUND_ANALOGUE", "Human ground-analogue experiment",
     "Human volunteers in an Earth-based analogue of spaceflight, such as bed rest. Nobody flew."),
    ("HUMAN_DERIVED_CELLS", "Human-derived cells or tissue",
     "Experiments on human cells or tissue in culture (in flight or on the ground), not on a person."),
    ("ANIMAL_RESEARCH", "Animal research",
     "Non-human organisms. Kept separate and never used for astronaut-specific findings."),
    ("SPACEFLIGHT_ENVIRONMENT", "Spacecraft environment",
     "Cabin telemetry, radiation or spacecraft microbiology. Not a body measurement."),
    ("FICTIONAL_DEMONSTRATION", "Fictional demonstration data",
     "SENTINEL's fictional astronauts, habitat and devices (data categories SIMULATED_ASTRONAUT and "
     "SIMULATED_ENVIRONMENT_OR_DEVICE). Not real measurements."),
]

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
    table = {"GENE_EXPRESSION_V1": m.GeneExpressionValue, "BIO_ASSAY_TABLE": m.AssayMeasurement}.get(
        REGISTRY[dataset_id]["record_schema"], m.ResearchMeasurement)
    return db.scalar(select(func.count()).select_from(table).where(table.dataset_id == dataset_id)) or 0


def compute_status(db: Session, settings: Settings, dataset_id: str) -> tuple[str, str]:
    meta = REGISTRY[dataset_id]
    n = record_count(db, dataset_id)
    last = latest_import(db, dataset_id)
    if n > 0:
        return "IMPORTED", f"{n} records imported."
    if last is not None and last.status == "IMPORT_FAILED":
        return "IMPORT_FAILED", last.message
    folder = raw_dir_for(settings, dataset_id)
    if meta["record_schema"] == "GENE_EXPRESSION_V1":
        from ..importers import expression

        return expression.file_status(settings, dataset_id, folder)
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
        **CLASSIFICATION[dataset_id],
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

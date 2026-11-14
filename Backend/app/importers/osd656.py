"""Importer for NASA OSDR OSD-656: Inspiration4 crew urine, NULISA-seq inflammation panel (BIO_ASSAY_TABLE).

Source files (data/nasa/raw/OSD-656/)
- LSDS-64_Multiplex_urine.immune.AlamarPanel_TRANSFORMED.csv   (required)
    One row per urine sample ('Sample Name' = <subject>_urine_<timepoint>, e.g. C001_urine_L-92).
    One column per measurement: <target>_concentration_npq and <target>_percent_normalized_value.
- LSDS-64_Multiplex_200plex v1-Target Information.csv           (optional annotation)
    Target, AlamarTargetID, UniProtID, ProteinName, GeneName.

Rules
- One record per (sample row, measurement column); values kept as published (value_raw); NA/empty -> null.
- Columns whose header is empty in the NASA file are NOT imported (their meaning cannot be verified); their
  positions are recorded in the import summary.
- Sample names must match <C###>_urine_<L-n|R+n>; timepoints parsed exactly as for OSD-575.
- Target annotation is joined only on an exact normalised name match; otherwise left null (never guessed).
- Atomic, SHA-256 deduplicated, JSON import log. No reference ranges, thresholds or interpretation.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Optional

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import Settings
from ..db import utcnow
from .expression import ExpressionImportResult as ImportResult
from .osd575 import ImportFormatError, parse_timepoint

DATASET_ID = "OSD-656"
SOURCE_FILE = "LSDS-64_Multiplex_urine.immune.AlamarPanel_TRANSFORMED.csv"
TARGET_FILE = "LSDS-64_Multiplex_200plex v1-Target Information.csv"
SAMPLE_RE = re.compile(r"^(C\d{3})_(urine)_([LR][+-]\d+)$")
MEASURES = {
    "concentration_npq": ("concentration_npq", "NPQ (NULISA Protein Quantification units, as published)"),
    "percent_normalized_value": ("percent_normalized_value", "percent (normalized value, as published)"),
}
MEASURE_RE = re.compile(r"^(.+)_(concentration_npq|percent_normalized_value)$")
MISSING_TOKENS = {"", "NA", "N/A", "NAN", "NULL"}
TRANSFORMATION = (
    "Wide table unpivoted: one record per sample row and measurement column. Values parsed to numbers; NA stored "
    "as null with the original text in value_raw. Sample names split into subject, specimen and timepoint "
    "(L-n PREFLIGHT, R+n POSTFLIGHT). Target, measure and units kept as named in the column header. Columns with "
    "an empty header in the NASA file are not imported. Target annotation joined from the NASA target information "
    "file on exact normalised name only. No ranges, thresholds or statistics added."
)


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower().replace(", human", "")).strip("_")


def parse_targets(text: str) -> dict[str, dict]:
    out = {}
    for r in csv.DictReader(io.StringIO(text)):
        key = _norm(r.get("Target") or "")
        if key:
            out[key] = dict(target_name=r.get("Target") or None, gene_name=r.get("GeneName") or None,
                            uniprot_id=r.get("UniProtID") or None, protein_name=r.get("ProteinName") or None)
    return out


def _num(raw: str) -> Optional[float]:
    s = (raw or "").strip()
    if s.upper() in MISSING_TOKENS:
        return None
    try:
        return float(s)
    except ValueError as exc:
        raise ImportFormatError(f"non-numeric value '{raw}'") from exc


def parse_table(text: str, targets: dict[str, dict]) -> tuple[list[dict], dict]:
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise ImportFormatError("file contains no data rows")
    header = rows[0]
    if header[0].strip() != "Sample Name":
        raise ImportFormatError(f"first column must be 'Sample Name', found '{header[0]}'")
    columns, skipped = [], []
    for i, h in enumerate(header[1:], start=1):
        if not h.strip():
            skipped.append({"position": i + 1, "previous_header": header[i - 1], "reason": "empty header"})
            continue
        mt = MEASURE_RE.match(h.strip())
        if not mt:
            raise ImportFormatError(f"unrecognised measurement column '{h}'")
        columns.append((i, h.strip(), mt.group(1), mt.group(2)))
    seen_samples, out, missing = set(), [], {}
    annotated, unannotated = set(), set()
    for n, r in enumerate(rows[1:], start=1):
        if len(r) != len(header):
            raise ImportFormatError(f"row {n}: expected {len(header)} columns, found {len(r)}")
        sample = r[0].strip()
        ms = SAMPLE_RE.match(sample)
        if not ms:
            raise ImportFormatError(f"row {n}: unrecognised sample name '{sample}'")
        if sample in seen_samples:
            raise ImportFormatError(f"row {n}: duplicate sample '{sample}'")
        seen_samples.add(sample)
        subject, specimen, tp = ms.groups()
        phase, offset, order = parse_timepoint(tp)
        for i, col, analyte, measure in columns:
            try:
                value = _num(r[i])
            except ImportFormatError as exc:
                raise ImportFormatError(f"row {n}, column {col}: {exc}") from exc
            if value is None:
                missing[col] = missing.get(col, 0) + 1
            ann = targets.get(_norm(analyte), {})
            (annotated if ann else unannotated).add(analyte)
            out.append(dict(source_row_number=n, source_column=col, sample_name=sample, subject_id=subject,
                            specimen=specimen, analyte=analyte, measure=MEASURES[measure][0],
                            unit=MEASURES[measure][1], value=value, value_raw=r[i], timepoint=tp,
                            timepoint_phase=phase, timepoint_day_offset=offset, timepoint_order=order,
                            target_name=ann.get("target_name"), gene_name=ann.get("gene_name"),
                            uniprot_id=ann.get("uniprot_id"), protein_name=ann.get("protein_name")))
    info = {"samples": sorted(seen_samples), "measurement_columns": len(columns), "skipped_columns": skipped,
            "missing_values": missing, "analytes": len({c[2] for c in columns}),
            "annotated_analytes": len(annotated), "unannotated_analytes": sorted(unannotated)}
    return out, info


def _write_log(settings: Settings, result: ImportResult, info: dict) -> str:
    settings.import_log_dir.mkdir(parents=True, exist_ok=True)
    path = settings.import_log_dir / f"{DATASET_ID}_{result.import_id}.json"
    path.write_text(json.dumps({**result.__dict__, "log_path": None, "transformation": TRANSFORMATION,
                                "skipped_columns": info.get("skipped_columns", []),
                                "written_at": utcnow().isoformat()}, indent=2), encoding="utf-8")
    return path.as_posix()


def import_folder(db: Session, settings: Settings, folder: Path) -> ImportResult:
    A = m.AssayMeasurement
    path = folder / SOURCE_FILE
    if not path.is_file():
        return ImportResult(outcome="not_found", dataset_id=DATASET_ID,
                            message=f"{SOURCE_FILE} not found in {folder.as_posix()}.")
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    tpath = folder / TARGET_FILE
    tdata = tpath.read_bytes() if tpath.is_file() else b""
    companions = {TARGET_FILE: hashlib.sha256(tdata).hexdigest()} if tdata else {}
    result = ImportResult(outcome="failed", dataset_id=DATASET_ID, source_file=SOURCE_FILE, sha256=sha)
    already = db.scalars(select(m.DatasetImport).where(m.DatasetImport.dataset_id == DATASET_ID,
                                                       m.DatasetImport.sha256 == sha,
                                                       m.DatasetImport.status == "IMPORTED")
                         .order_by(m.DatasetImport.started_at.desc())).first()
    existing = db.scalar(select(func.count()).select_from(A).where(A.dataset_id == DATASET_ID)) or 0
    if already is not None and existing == already.rows_imported \
            and already.summary.get("companion_files_sha256", {}) == companions:
        result.outcome, result.import_id, result.rows_read = "skipped_duplicate", already.import_id, already.rows_read
        result.samples = already.summary.get("samples", [])
        result.message = f"{SOURCE_FILE} already imported as {already.import_id}; no rows added."
        return result
    imp = m.DatasetImport(import_id=m.new_id("IMP"), dataset_id=DATASET_ID, source_file=SOURCE_FILE, sha256=sha,
                          status="IMPORT_FAILED", started_at=utcnow())
    result.import_id, info = imp.import_id, {}
    try:
        targets = parse_targets(tdata.decode("utf-8-sig")) if tdata else {}
        rows, info = parse_table(data.decode("utf-8-sig"), targets)
        result.rows_read, result.samples = len(rows), info["samples"]
        result.missing_values = info["missing_values"]
        db.execute(delete(A).where(A.dataset_id == DATASET_ID))
        db.add(imp)
        db.flush()
        for r in rows:
            r.update(dataset_id=DATASET_ID, import_id=imp.import_id, source_file=SOURCE_FILE)
        db.execute(insert(A), rows)
        imp.status, imp.rows_read, imp.rows_imported = "IMPORTED", len(rows), len(rows)
        imp.summary = {**info, "companion_files_sha256": companions}
        skipped = len(info["skipped_columns"])
        imp.message = (f"Imported {len(rows)} values ({info['analytes']} targets x {len(info['samples'])} samples); "
                       f"{skipped} column(s) with an empty header in the NASA file not imported.")
        imp.finished_at = utcnow()
        db.commit()
        result.outcome, result.rows_imported, result.message = "imported", len(rows), imp.message
    except (ImportFormatError, UnicodeDecodeError) as exc:
        db.rollback()
        db.add(m.DatasetImport(import_id=result.import_id, dataset_id=DATASET_ID, source_file=SOURCE_FILE,
                               sha256=sha, status="IMPORT_FAILED", started_at=imp.started_at, finished_at=utcnow(),
                               rows_read=result.rows_read, rows_imported=0, summary={}, message=str(exc)))
        db.commit()
        result.message = str(exc)
    result.log_path = _write_log(settings, result, info)
    return result


def import_if_available(db: Session, settings: Settings) -> ImportResult:
    from ..services.datasets import raw_dir_for

    return import_folder(db, settings, raw_dir_for(settings, DATASET_ID))

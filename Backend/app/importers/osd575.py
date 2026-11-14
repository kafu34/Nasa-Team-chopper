"""Importer for NASA OSDR OSD-575 comprehensive metabolic panel (CMP) CSV.

Source file: LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv
Columns:     ANALYTE, VALUE, RANGE_MIN, RANGE_MAX, UNITS, TEST_TYPE, SUBJECT_ID, SEX, timepoint

Rules
- Values are stored exactly as published (value_raw) and parsed to float when numeric.
- 'NA', 'N/A', 'NaN' and empty cells are missing values and become NULL, never 0.
- Timepoints keep their original label; L-n = n days before launch (PREFLIGHT), R+n = n days after
  return (POSTFLIGHT). No row is labelled as in-flight.
- The import is atomic: any malformed row fails the whole import (status IMPORT_FAILED).
- Re-importing a file with the same SHA-256 is skipped (duplicate ingestion prevention). The unique
  constraint (dataset_id, source_file, source_row_number) is a second guard.
- Every run writes a DatasetImport record and a JSON log in <var_dir>/import_logs/.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import Settings
from ..db import utcnow

DATASET_ID = "OSD-575"
SOURCE_FILE = "LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv"
REQUIRED_COLUMNS = ["ANALYTE", "VALUE", "RANGE_MIN", "RANGE_MAX", "UNITS", "TEST_TYPE", "SUBJECT_ID", "SEX", "timepoint"]
MISSING_TOKENS = {"", "NA", "N/A", "NAN", "NULL"}
TIMEPOINT_RE = re.compile(r"^([LR])([+-])(\d+)$")
TRANSFORMATION = (
    "Rows copied one-to-one from the source CSV. VALUE/RANGE_MIN/RANGE_MAX parsed to numbers when numeric; "
    "NA, N/A and empty cells stored as null with the original text kept in *_raw fields. Units, analyte names, "
    "subject IDs and timepoint labels kept verbatim. Timepoints additionally parsed into phase "
    "(PREFLIGHT for L-n, POSTFLIGHT for R+n) and signed day offset for ordering."
)


class ImportFormatError(ValueError):
    pass


@dataclass
class ImportResult:
    outcome: str  # imported | skipped_duplicate | failed | not_found
    dataset_id: str = DATASET_ID
    source_file: str = SOURCE_FILE
    import_id: Optional[str] = None
    sha256: Optional[str] = None
    rows_read: int = 0
    rows_imported: int = 0
    missing_values: dict = field(default_factory=dict)
    message: str = ""
    log_path: Optional[str] = None


def parse_number(raw: str) -> Optional[float]:
    s = (raw or "").strip()
    if s.upper() in MISSING_TOKENS:
        return None
    try:
        return float(s)
    except ValueError as exc:
        raise ImportFormatError(f"non-numeric value '{raw}'") from exc


def parse_timepoint(label: str) -> tuple[str, int, int]:
    """Returns (phase, day_offset, order). Raises ImportFormatError for unknown formats."""
    mt = TIMEPOINT_RE.match((label or "").strip())
    if not mt:
        raise ImportFormatError(f"unrecognised timepoint '{label}'")
    anchor, sign, days = mt.groups()
    offset = int(days) * (-1 if sign == "-" else 1)
    if anchor == "L":
        return "PREFLIGHT", offset, offset - 100_000  # all launch-relative points sort before return-relative
    return "POSTFLIGHT", offset, offset + 100_000


def parse_rows(text: str) -> tuple[list[dict], dict[str, int]]:
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing_cols:
        raise ImportFormatError(f"missing required columns: {missing_cols}; found {header}")
    rows, missing = [], {c: 0 for c in REQUIRED_COLUMNS}
    for i, r in enumerate(reader, start=1):
        try:
            for c in REQUIRED_COLUMNS:
                if (r.get(c) or "").strip().upper() in MISSING_TOKENS:
                    missing[c] += 1
            for c in ("ANALYTE", "UNITS", "SUBJECT_ID", "timepoint"):
                if not (r.get(c) or "").strip():
                    raise ImportFormatError(f"empty required identifier column {c}")
            phase, offset, order = parse_timepoint(r["timepoint"])
            sex = (r["SEX"] or "").strip()
            rows.append(dict(
                source_row_number=i, analyte=r["ANALYTE"], value=parse_number(r["VALUE"]), value_raw=r["VALUE"],
                unit=r["UNITS"], range_min=parse_number(r["RANGE_MIN"]), range_min_raw=r["RANGE_MIN"],
                range_max=parse_number(r["RANGE_MAX"]), range_max_raw=r["RANGE_MAX"], test_type=r["TEST_TYPE"],
                subject_id=r["SUBJECT_ID"], sex=None if sex.upper() in MISSING_TOKENS else sex,
                timepoint=r["timepoint"], timepoint_phase=phase, timepoint_day_offset=offset, timepoint_order=order))
        except ImportFormatError as exc:
            raise ImportFormatError(f"row {i}: {exc}") from exc
    if not rows:
        raise ImportFormatError("file contains no data rows")
    return rows, missing


def _write_log(settings: Settings, result: ImportResult) -> str:
    settings.import_log_dir.mkdir(parents=True, exist_ok=True)
    path = settings.import_log_dir / f"{result.dataset_id}_{result.import_id}.json"
    path.write_text(json.dumps({**asdict(result), "log_path": None, "transformation": TRANSFORMATION,
                                "written_at": utcnow().isoformat()}, indent=2), encoding="utf-8")
    return path.as_posix()


def import_csv(db: Session, settings: Settings, path: Path) -> ImportResult:
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    already = db.scalars(select(m.DatasetImport).where(m.DatasetImport.dataset_id == DATASET_ID,
                                                       m.DatasetImport.sha256 == sha,
                                                       m.DatasetImport.status == "IMPORTED")).first()
    existing_rows = db.query(m.ResearchMeasurement).filter(m.ResearchMeasurement.dataset_id == DATASET_ID).count()
    if already is not None and existing_rows == already.rows_imported:
        return ImportResult(outcome="skipped_duplicate", import_id=already.import_id, sha256=sha,
                            rows_read=already.rows_read, rows_imported=0,
                            missing_values=already.summary.get("missing_values", {}),
                            message=f"File already imported as {already.import_id}; no rows added.")

    imp = m.DatasetImport(import_id=m.new_id("IMP"), dataset_id=DATASET_ID, source_file=path.name, sha256=sha,
                          status="IMPORT_FAILED", started_at=utcnow())
    result = ImportResult(outcome="failed", import_id=imp.import_id, sha256=sha, source_file=path.name)
    try:
        rows, missing = parse_rows(data.decode("utf-8-sig"))
        result.rows_read, result.missing_values = len(rows), missing
        # A new version of the file replaces earlier OSD-575 rows atomically.
        db.execute(delete(m.ResearchMeasurement).where(m.ResearchMeasurement.dataset_id == DATASET_ID))
        db.add(imp)
        db.flush()
        db.add_all(m.ResearchMeasurement(dataset_id=DATASET_ID, import_id=imp.import_id, source_file=path.name, **r)
                   for r in rows)
        imp.status, imp.rows_read, imp.rows_imported = "IMPORTED", len(rows), len(rows)
        imp.summary = {"missing_values": missing, "columns": REQUIRED_COLUMNS}
        imp.message = f"Imported {len(rows)} rows."
        imp.finished_at = utcnow()
        db.commit()
        result.outcome, result.rows_imported, result.message = "imported", len(rows), imp.message
    except (ImportFormatError, UnicodeDecodeError) as exc:
        db.rollback()
        imp = m.DatasetImport(import_id=result.import_id, dataset_id=DATASET_ID, source_file=path.name, sha256=sha,
                              status="IMPORT_FAILED", started_at=imp.started_at, finished_at=utcnow(),
                              rows_read=result.rows_read, rows_imported=0, summary={}, message=str(exc))
        db.add(imp)
        db.commit()
        result.message = str(exc)
    result.log_path = _write_log(settings, result)
    return result


def import_if_available(db: Session, settings: Settings) -> ImportResult:
    path = settings.nasa_raw_dir / SOURCE_FILE
    if not path.is_file():
        return ImportResult(outcome="not_found", message=f"{path.as_posix()} not found. Place the OSD-575 CSV there.")
    return import_csv(db, settings, path)

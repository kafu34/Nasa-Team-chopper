"""Importer for a saved NASA RadLab API snapshot (NASA-RADLAB, RADIATION_TIMESERIES_V1).

Source (data/nasa/raw/NASA-RADLAB/)
- radlab_ISS_2022-04-01.csv         CSV returned unchanged by the public RadLab data API
- radlab_ISS_2022-04-01.query.json  the exact query URL, retrieval time and SHA-256 of the CSV

API documentation: https://visualization.osdr.nasa.gov/radlab/gui/data-api/
Columns: timestamp, instrument_id, absorbed_dose_rate (uGy/hour), dose_equivalent_rate (uSv/hour), altitude (km),
instrument_family, latitude (deg), longitude (deg), module, spacecraft.

Rules
- Long format: one record per (row, metric) for each metric cell that holds a number. Empty metric cells are not
  readings; they are counted per metric in the import summary (missing_values) and not stored.
- RadLab timestamps carry no timezone. SENTINEL treats them as UTC (ISS operations run on UTC); this is an
  assumption, stated in the dataset limitations. The original text is kept in timestamp_raw.
- The query.json SHA-256 must match the CSV, otherwise the import fails (the snapshot was altered).
- The RadLab output can contain the same instrument and timestamp twice with different values (3 cases in the
  2022-04-01 snapshot, all DosTel1). Both are kept as published and listed in summary.repeated_readings.
- Atomic, SHA-256 deduplicated, JSON import log. No thresholds, alerts or personal-dose interpretation.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import Settings
from ..db import utcnow
from .expression import ExpressionImportResult as ImportResult
from .osd575 import ImportFormatError

DATASET_ID = "NASA-RADLAB"
SOURCE_FILE = "radlab_ISS_2022-04-01.csv"
QUERY_FILE = "radlab_ISS_2022-04-01.query.json"
METRICS = {"absorbed_dose_rate": "μGy/hour", "dose_equivalent_rate": "μSv/hour"}  # units per RadLab API docs
REQUIRED = ["timestamp", "instrument_id"]
MISSING_TOKENS = {"", "NA", "N/A", "NAN", "NULL"}
TRANSFORMATION = (
    "RadLab API CSV saved unchanged, then reshaped to one record per reading and metric (absorbed_dose_rate in "
    "uGy/hour, dose_equivalent_rate in uSv/hour, units from the RadLab API documentation). Empty metric cells are "
    "counted, not stored. Timestamps have no timezone in the source and are treated as UTC (original text kept). "
    "Instrument, module, spacecraft and ISS position copied verbatim. No thresholds or interpretation added."
)


def _num(raw: Optional[str], what: str) -> Optional[float]:
    s = (raw or "").strip()
    if s.upper() in MISSING_TOKENS:
        return None
    try:
        return float(s)
    except ValueError as exc:
        raise ImportFormatError(f"non-numeric {what} '{raw}'") from exc


def _ts(raw: str) -> datetime:
    try:
        dt = datetime.fromisoformat(raw.strip())
    except ValueError as exc:
        raise ImportFormatError(f"unrecognised timestamp '{raw}'") from exc
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _opt(raw: Optional[str]) -> Optional[str]:
    s = (raw or "").strip()
    return None if s.upper() in MISSING_TOKENS else s


def parse_csv(text: str) -> tuple[list[dict], dict]:
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    missing_cols = [c for c in REQUIRED if c not in header]
    metrics = [k for k in METRICS if k in header]
    if missing_cols or not metrics:
        raise ImportFormatError(f"missing required columns {missing_cols or list(METRICS)}; found {header}")
    out, empty, rows_read, seen, repeated = [], {k: 0 for k in metrics}, 0, {}, {}
    for n, r in enumerate(reader, start=1):
        rows_read += 1
        try:
            if not (r.get("instrument_id") or "").strip():
                raise ImportFormatError("empty instrument_id")
            # The RadLab API can return the same instrument and timestamp more than once with different values.
            # Both rows are kept as published (never picked or averaged) and listed in the import summary.
            key = f"{r['timestamp']} {r['instrument_id'].strip()}"
            if key in seen:
                repeated.setdefault(key, [seen[key]]).append(n)
            else:
                seen[key] = n
            ts = _ts(r["timestamp"])
            pos = {k: _num(r.get(k), k) for k in ("latitude", "longitude", "altitude")}
            for metric in metrics:
                value = _num(r.get(metric), metric)
                if value is None:
                    empty[metric] += 1
                    continue
                out.append(dict(source_row_number=n, timestamp=ts, timestamp_raw=r["timestamp"],
                                instrument_id=r["instrument_id"].strip(),
                                instrument_family=_opt(r.get("instrument_family")),
                                spacecraft=_opt(r.get("spacecraft")), module=_opt(r.get("module")),
                                metric=metric, value=value, value_raw=r[metric], unit=METRICS[metric], **pos))
        except ImportFormatError as exc:
            raise ImportFormatError(f"row {n}: {exc}") from exc
    if not rows_read:
        raise ImportFormatError("file contains no data rows")
    stored = sorted({r["metric"] for r in out})
    return out, {"rows_read": rows_read, "columns": header, "metrics_stored": stored, "missing_values": empty,
                 "instruments": sorted({r["instrument_id"] for r in out}),
                 "repeated_readings": repeated}  # "timestamp instrument" -> source row numbers


def _write_log(settings: Settings, result: ImportResult, query: dict) -> str:
    settings.import_log_dir.mkdir(parents=True, exist_ok=True)
    path = settings.import_log_dir / f"{DATASET_ID}_{result.import_id}.json"
    path.write_text(json.dumps({**result.__dict__, "log_path": None, "transformation": TRANSFORMATION,
                                "query": query, "written_at": utcnow().isoformat()}, indent=2), encoding="utf-8")
    return path.as_posix()


def read_query(folder: Path) -> dict:
    p = folder / QUERY_FILE
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def import_folder(db: Session, settings: Settings, folder: Path) -> ImportResult:
    T = m.TimeseriesValue
    path = folder / SOURCE_FILE
    if not path.is_file():
        return ImportResult(outcome="not_found", dataset_id=DATASET_ID,
                            message=f"{SOURCE_FILE} not found in {folder.as_posix()}.")
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    result = ImportResult(outcome="failed", dataset_id=DATASET_ID, source_file=SOURCE_FILE, sha256=sha)
    already = db.scalars(select(m.DatasetImport).where(m.DatasetImport.dataset_id == DATASET_ID,
                                                       m.DatasetImport.sha256 == sha,
                                                       m.DatasetImport.status == "IMPORTED")
                         .order_by(m.DatasetImport.started_at.desc())).first()
    existing = db.scalar(select(func.count()).select_from(T).where(T.dataset_id == DATASET_ID)) or 0
    if already is not None and existing == already.rows_imported:
        result.outcome, result.import_id, result.rows_read = "skipped_duplicate", already.import_id, already.rows_read
        result.message = f"{SOURCE_FILE} already imported as {already.import_id}; no rows added."
        return result
    imp = m.DatasetImport(import_id=m.new_id("IMP"), dataset_id=DATASET_ID, source_file=SOURCE_FILE, sha256=sha,
                          status="IMPORT_FAILED", started_at=utcnow())
    result.import_id, query = imp.import_id, {}
    try:
        query = read_query(folder)
        if not query.get("query_url"):
            raise ImportFormatError(f"{QUERY_FILE} with the RadLab query_url is required for provenance")
        if query.get("sha256") and query["sha256"] != sha:
            raise ImportFormatError(f"SHA-256 of {SOURCE_FILE} does not match {QUERY_FILE}; snapshot was altered")
        rows, info = parse_csv(data.decode("utf-8-sig"))
        result.rows_read, result.missing_values = info["rows_read"], info["missing_values"]
        db.execute(delete(T).where(T.dataset_id == DATASET_ID))
        db.add(imp)
        db.flush()
        for r in rows:
            r.update(dataset_id=DATASET_ID, import_id=imp.import_id, source_file=SOURCE_FILE)
        if rows:
            db.execute(insert(T), rows)
        imp.status, imp.rows_read, imp.rows_imported = "IMPORTED", info["rows_read"], len(rows)
        imp.summary = {**info, "query_url": query["query_url"], "retrieved_at": query.get("retrieved_at")}
        imp.message = (f"Imported {len(rows)} readings from {info['rows_read']} rows "
                       f"({', '.join(info['instruments'])}); metrics stored: {', '.join(info['metrics_stored'])}; "
                       f"{len(info['repeated_readings'])} instrument/timestamp pair(s) appear more than once in the "
                       f"source and are kept as published.")
        imp.finished_at = utcnow()
        db.commit()
        result.outcome, result.rows_imported, result.message = "imported", len(rows), imp.message
    except (ImportFormatError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        db.rollback()
        db.add(m.DatasetImport(import_id=result.import_id, dataset_id=DATASET_ID, source_file=SOURCE_FILE,
                               sha256=sha, status="IMPORT_FAILED", started_at=imp.started_at, finished_at=utcnow(),
                               rows_read=result.rows_read, rows_imported=0, summary={}, message=str(exc)))
        db.commit()
        result.message = str(exc)
    result.log_path = _write_log(settings, result, query)
    return result


def import_if_available(db: Session, settings: Settings) -> ImportResult:
    from ..services.datasets import raw_dir_for

    return import_folder(db, settings, raw_dir_for(settings, DATASET_ID))

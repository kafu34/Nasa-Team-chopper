"""Importer for NASA OSDR OSD-817 (LSDS-135): TUNEL and CTB counts in ex vivo human optic-nerve tissue.

Study: "The ex vivo human translaminar autonomous system to study spaceflight associated neuro-ocular syndrome
pathogenesis (Optic Nerve, Histology and Microscopy)". Ground study on de-identified human donor eyes.

Source files (data/nasa/raw/OSD-817/)
- LSDS-135_immunostaining_TUNEL_TRANSFORMED.csv     Sample Name, Counts, Normalized Counts   (required)
- LSDS-135_immunostaining_CTB_TRANSFORMED.csv       Sample Name, Counts, Normalized Counts   (required)
- LSDS-135_immunostaining_Tunel Analysis_SUBMITTED.xlsx   per-eye annotation (optional)
- LSDS-135_immunostaining_CTB Analysis_SUBMITTED.xlsx     per-eye annotation (optional)
  Subject #, Eye, Gender, Age, Race, Group, Days on System, Counts, notes, Counts/Normalized to Control.

Rules
- Values come from the TRANSFORMED CSVs, verbatim (value_raw) and parsed; NA/empty -> null.
- The SUBMITTED workbooks add the group number, days on system, donor sex and age, and image-quality notes. Their
  counts must equal the TRANSFORMED counts and their normalized values must round to the TRANSFORMED values,
  otherwise the import fails. Donor race is not imported (not needed).
- Group numbers are kept exactly as published. They are NOT mapped to pressure/tilt conditions: the workbook's
  normalisation reference ("Normalized to Control" = 1.0) is Group 6, which the OSDR study description defines as
  15:16 mmHg with a 10-degree tilt, so the group numbering cannot be verified against the description.
- Atomic, SHA-256 deduplicated (all four files), JSON import log. No interpretation or statistics.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import Settings
from ..db import utcnow
from .expression import ExpressionImportResult as ImportResult
from .osd575 import ImportFormatError

DATASET_ID = "OSD-817"
ASSAYS = {
    "TUNEL": ("LSDS-135_immunostaining_TUNEL_TRANSFORMED.csv", "LSDS-135_immunostaining_Tunel Analysis_SUBMITTED.xlsx"),
    "CTB": ("LSDS-135_immunostaining_CTB_TRANSFORMED.csv", "LSDS-135_immunostaining_CTB Analysis_SUBMITTED.xlsx"),
}
SAMPLE_RE = re.compile(r"^(\d+)_(OD|OS)_(FN|PFA)$")
MISSING_TOKENS = {"", "NA", "N/A", "NAN", "NULL"}
MEASURES = {"Counts": "counts", "Normalized Counts": "normalized_counts"}
UNITS = {"counts": "count (per field, as published)", "normalized_counts": "ratio to the published reference eye"}
TRANSFORMATION = (
    "TRANSFORMED CSV rows copied one-to-one: one record per sample and measure (counts, normalized counts), "
    "values parsed to numbers with the original text in value_raw. Sample names split into donor ID, eye (OD right, "
    "OS left) and fixation (FN formalin). Group number, days on system, donor sex/age and image-quality notes "
    "joined from the NASA SUBMITTED workbook after checking its counts match. Group numbers are not mapped to "
    "experimental conditions. No statistics or interpretation added."
)
_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _num(raw: Optional[str], what: str) -> Optional[float]:
    s = (raw or "").strip()
    if s.upper() in MISSING_TOKENS:
        return None
    try:
        return float(s)
    except ValueError as exc:
        raise ImportFormatError(f"non-numeric {what} '{raw}'") from exc


def read_xlsx_rows(data: bytes) -> list[list[str]]:
    """Minimal reader for the first worksheet of an .xlsx (no external dependency). Returns rows of cell text."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(f"{_NS}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{_NS}t")))
        sheet = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet"))[0]
        rows = []
        for row in ET.fromstring(z.read(sheet)).iter(f"{_NS}row"):
            cells: dict[int, str] = {}
            for c in row.findall(f"{_NS}c"):
                col = re.match(r"[A-Z]+", c.get("r", "A")).group(0)
                idx = 0
                for ch in col:
                    idx = idx * 26 + ord(ch) - 64
                v = c.find(f"{_NS}v")
                if v is not None:
                    text = shared[int(v.text)] if c.get("t") == "s" else (v.text or "")
                else:
                    is_ = c.find(f"{_NS}is")
                    text = "".join(t.text or "" for t in is_.iter(f"{_NS}t")) if is_ is not None else ""
                cells[idx - 1] = text
            rows.append([cells.get(i, "") for i in range(max(cells) + 1)] if cells else [])
        return rows
    except (zipfile.BadZipFile, ET.ParseError, IndexError, KeyError, ValueError) as exc:
        raise ImportFormatError(f"unreadable workbook: {exc}") from exc


def parse_annotation(data: bytes) -> dict[tuple[str, str], dict]:
    rows = [r for r in read_xlsx_rows(data) if any(c.strip() for c in r)]
    header = [h.strip() for h in rows[0]]
    need = ["Subject #", "Eye", "Group", "Counts"]
    if any(h not in header for h in need):
        raise ImportFormatError(f"workbook missing columns {[h for h in need if h not in header]}")
    ix = {h: header.index(h) for h in header if h}
    norm_col = next((i for i, h in enumerate(header) if h.startswith("Counts/Normalized")), None)
    days_col = next((i for i, h in enumerate(header) if h.startswith("Days on System")), None)
    note_cols = [i for i, h in enumerate(header) if i > ix["Counts"] and i != norm_col]
    out = {}
    for r in rows[1:]:
        r = r + [""] * (len(header) - len(r))
        donor, eye = r[ix["Subject #"]].strip(), r[ix["Eye"]].strip()
        if not donor:
            continue
        num = lambda i: int(float(r[i])) if i is not None and r[i].strip() else None  # noqa: E731
        notes = "; ".join(r[i].strip() for i in note_cols if r[i].strip())
        out[(donor, eye)] = dict(group_number=r[ix["Group"]].strip() or None, days_on_system=num(days_col),
                                 donor_sex=(r[ix["Gender"]].strip() or None) if "Gender" in ix else None,
                                 donor_age=num(ix.get("Age")), notes=notes or None,
                                 counts=_num(r[ix["Counts"]], "workbook Counts"),
                                 normalized=_num(r[norm_col], "workbook normalized") if norm_col is not None else None)
    return out


def parse_assay(assay: str, text: str, annotation: dict, annotation_file: Optional[str]) -> tuple[list[dict], dict]:
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    header = [h.strip() for h in rows[0]]
    if header[:1] != ["Sample Name"] or any(h not in header for h in MEASURES):
        raise ImportFormatError(f"{assay}: expected columns Sample Name, Counts, Normalized Counts; found {header}")
    out, missing, seen = [], {v: 0 for v in MEASURES.values()}, set()
    for n, r in enumerate(rows[1:], start=1):
        sample = r[0].strip()
        ms = SAMPLE_RE.match(sample)
        if not ms:
            raise ImportFormatError(f"{assay} row {n}: unrecognised sample name '{sample}'")
        if sample in seen:
            raise ImportFormatError(f"{assay} row {n}: duplicate sample '{sample}'")
        seen.add(sample)
        donor, eye, fixation = ms.groups()
        ann = annotation.get((donor, eye), {}) if annotation else {}
        if annotation and not ann:
            raise ImportFormatError(f"{assay}: sample {sample} not found in {annotation_file}")
        for col, measure in MEASURES.items():
            raw = r[header.index(col)]
            value = _num(raw, f"{assay} {col}")
            if value is None:
                missing[measure] += 1
            ref = ann.get("counts" if measure == "counts" else "normalized")
            if ann and value is not None and ref is not None:
                # TRANSFORMED normalized values are the workbook values rounded to 2 decimals (half-up, e.g.
                # 2.4449999 -> 2.45), so they may differ by at most 0.005.
                ok = value == ref if measure == "counts" else abs(ref - value) <= 0.0051
                if not ok:
                    raise ImportFormatError(f"{assay} {sample} {col}: TRANSFORMED {raw} disagrees with "
                                            f"{annotation_file} value {ref}")
            out.append(dict(source_row_number=n, sample_name=sample, donor_id=donor, eye=eye, fixation=fixation,
                            assay=assay, measure=measure, value=value, value_raw=raw,
                            group_number=ann.get("group_number"), days_on_system=ann.get("days_on_system"),
                            donor_sex=ann.get("donor_sex"), donor_age=ann.get("donor_age"),
                            notes=ann.get("notes"), annotation_file=annotation_file if ann else None))
    return out, {"samples": len(seen), "missing_values": missing}


def _write_log(settings: Settings, result: ImportResult, info: dict) -> str:
    settings.import_log_dir.mkdir(parents=True, exist_ok=True)
    path = settings.import_log_dir / f"{DATASET_ID}_{result.import_id}.json"
    path.write_text(json.dumps({**result.__dict__, "log_path": None, "transformation": TRANSFORMATION, **info,
                                "written_at": utcnow().isoformat()}, indent=2, default=str), encoding="utf-8")
    return path.as_posix()


def import_folder(db: Session, settings: Settings, folder: Path) -> ImportResult:
    H = m.HistologyCount
    first = folder / ASSAYS["TUNEL"][0]
    missing = [ASSAYS[a][0] for a in ASSAYS if not (folder / ASSAYS[a][0]).is_file()]
    if missing:
        return ImportResult(outcome="not_found", dataset_id=DATASET_ID, message=f"{missing} not found.")
    blobs = {name: (folder / name).read_bytes() for pair in ASSAYS.values() for name in pair
             if (folder / name).is_file()}
    hashes = {name: hashlib.sha256(b).hexdigest() for name, b in blobs.items()}
    sha = hashes[first.name]
    result = ImportResult(outcome="failed", dataset_id=DATASET_ID, source_file=first.name, sha256=sha)
    already = db.scalars(select(m.DatasetImport).where(m.DatasetImport.dataset_id == DATASET_ID,
                                                       m.DatasetImport.status == "IMPORTED")
                         .order_by(m.DatasetImport.started_at.desc())).first()
    existing = db.scalar(select(func.count()).select_from(H).where(H.dataset_id == DATASET_ID)) or 0
    if already is not None and existing == already.rows_imported and already.summary.get("files_sha256") == hashes:
        result.outcome, result.import_id, result.rows_read = "skipped_duplicate", already.import_id, already.rows_read
        result.message = f"OSD-817 files already imported as {already.import_id}; no rows added."
        return result
    imp = m.DatasetImport(import_id=m.new_id("IMP"), dataset_id=DATASET_ID, source_file=first.name, sha256=sha,
                          status="IMPORT_FAILED", started_at=utcnow())
    result.import_id, info = imp.import_id, {}
    try:
        rows, per_assay = [], {}
        for assay, (csv_name, xlsx_name) in ASSAYS.items():
            ann = parse_annotation(blobs[xlsx_name]) if xlsx_name in blobs else {}
            assay_rows, assay_info = parse_assay(assay, blobs[csv_name].decode("utf-8-sig"), ann,
                                                 xlsx_name if ann else None)
            for r in assay_rows:
                r["source_file"] = csv_name
            rows += assay_rows
            per_assay[assay] = {**assay_info, "annotated": bool(ann)}
        info = {"assays": per_assay, "files_sha256": hashes,
                "missing_values": {f"{a}.{k}": v for a, i in per_assay.items() for k, v in i["missing_values"].items()}}
        result.rows_read, result.missing_values = len(rows), info["missing_values"]
        db.execute(delete(H).where(H.dataset_id == DATASET_ID))
        db.add(imp)
        db.flush()
        for r in rows:
            r.update(dataset_id=DATASET_ID, import_id=imp.import_id)
        db.execute(insert(H), rows)
        imp.status, imp.rows_read, imp.rows_imported = "IMPORTED", len(rows), len(rows)
        imp.summary = info
        imp.message = (f"Imported {len(rows)} values: " + ", ".join(
            f"{a} {i['samples']} samples{' (annotated)' if i['annotated'] else ''}" for a, i in per_assay.items())
            + ". Group numbers kept as published; not mapped to pressure/tilt conditions.")
        imp.finished_at = utcnow()
        db.commit()
        result.outcome, result.rows_imported, result.message = "imported", len(rows), imp.message
    except (ImportFormatError, UnicodeDecodeError) as exc:
        db.rollback()
        db.add(m.DatasetImport(import_id=result.import_id, dataset_id=DATASET_ID, source_file=first.name,
                               sha256=sha, status="IMPORT_FAILED", started_at=imp.started_at, finished_at=utcnow(),
                               rows_read=result.rows_read, rows_imported=0, summary={}, message=str(exc)))
        db.commit()
        result.message = str(exc)
    result.log_path = _write_log(settings, result, info)
    return result


def import_if_available(db: Session, settings: Settings) -> ImportResult:
    from ..services.datasets import raw_dir_for

    return import_folder(db, settings, raw_dir_for(settings, DATASET_ID))

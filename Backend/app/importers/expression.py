"""Importer for NASA GeneLab *processed* gene-expression files (record schema GENE_EXPRESSION_V1).

Supported sources (P1, v2.2)
- OSD-195 (human bed-rest ground analogue): one file per sample,
  data/nasa/raw/OSD-195/GLDS-195_microarray_<GSM>_processed.txt
  Tab- or comma-separated; a probe-ID column and exactly one value column (header 'VALUE' preferred).
  Comment lines starting with '#' or '!' are ignored. A header row is optional for two-column files.
- OSD-546 (human bone-marrow stem cells, ISS vs ground): GeneLab pipeline tables,
  data/nasa/raw/OSD-546/GLDS-546_array_normalized_expression_probeset.csv  (probesets x samples)
  data/nasa/raw/OSD-546/GLDS-546_array_SampleTable.csv                      (sample -> group)

Rules
- Raw Affymetrix .CEL(.gz) files are never processed here (P2). Their presence alone gives UNSUPPORTED_FORMAT.
- Values are stored as published (value_raw) and parsed to float; NA/NaN/empty -> null, never 0.
- Every sample must match the verified OSDR sample metadata (expression_metadata.py). For OSD-546 the
  NASA SampleTable must agree with the verified Spaceflight factor, otherwise the import fails.
- Each file import is atomic and deduplicated by SHA-256. A changed file replaces only its own rows.
- No fold change, statistics or interpretation is computed. Research data is never linked to an astronaut.
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

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import REPO_DIR, Settings
from ..db import utcnow
from .expression_metadata import SAMPLES

MISSING_TOKENS = {"", "NA", "N/A", "NAN", "NULL"}
PROBE_HEADERS = {"ID_REF", "ID", "PROBE_ID", "PROBEID", "PROBESET_ID", "PROBESETID", "TRANSCRIPT_CLUSTER_ID",
                 "PROBESET"}
SYMBOL_HEADERS = {"SYMBOL", "GENE_SYMBOL", "GENESYMBOL"}
OSD195_PATTERN = re.compile(r"^GLDS-195_microarray_(GSM\d+)_processed\.txt$")
OSD546_EXPRESSION = "GLDS-546_array_normalized_expression_probeset.csv"
OSD546_SAMPLE_TABLE = "GLDS-546_array_SampleTable.csv"
CHUNK = 20_000

NORMALIZATION: dict[str, dict] = {
    "OSD-195": dict(
        text="NASA GeneLab per-sample processed (normalised) microarray data as published. The OSDR study summary "
             "indicates RMA normalisation in Affymetrix Expression Console 1.4.1; not yet verified verbatim.",
        verified=False,
        value_unit="Processed expression value as published by NASA (scale not verified by SENTINEL)",
    ),
    "OSD-546": dict(
        text="NASA GeneLab NF_MAAffymetrix v1.0.0 (R 4.1.3, oligo 1.58.0): background correction, quantile "
             "normalisation and RMA summarisation per probeset.",
        verified=True,
        value_unit="RMA-normalised expression (log2 scale, oligo RMA output)",
    ),
}

TRANSFORMATION = (
    "Processed NASA GeneLab expression values copied one-to-one: one record per probe/probeset per sample. "
    "Values parsed to numbers; NA/NaN/empty stored as null with the original text in value_raw. Probe IDs, gene "
    "symbols (only when present in the file), sample IDs and units kept verbatim. Sample conditions joined from "
    "verified NASA OSDR metadata. No re-normalisation, fold change or statistics computed."
)


class ExpressionFormatError(ValueError):
    pass


@dataclass
class ExpressionImportResult:
    outcome: str  # imported | skipped_duplicate | failed | not_found | unsupported_format
    dataset_id: str
    source_file: Optional[str] = None
    import_id: Optional[str] = None
    sha256: Optional[str] = None
    samples: list[str] = field(default_factory=list)
    rows_read: int = 0
    rows_imported: int = 0
    missing_values: dict = field(default_factory=dict)
    message: str = ""
    log_path: Optional[str] = None


# --------------------------------------------------------------------------- file discovery / status


def _is_raw_cel(p: Path) -> bool:
    name = p.name.lower()
    return name.endswith(".cel") or name.endswith(".cel.gz")


def osd195_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and OSD195_PATTERN.match(p.name))


def file_status(settings: Settings, dataset_id: str, folder: Path) -> tuple[str, str]:
    """Availability status when no records are imported and the last import did not fail."""
    present = sorted(p.name for p in folder.iterdir() if p.is_file()) if folder.is_dir() else []
    if dataset_id == "OSD-195":
        usable = [p.name for p in osd195_files(folder)]
        if usable:
            return "READY_TO_IMPORT", f"{len(usable)} processed sample file(s) present; run the importer."
        needed = "GLDS-195_microarray_GSM2813749_processed.txt and GLDS-195_microarray_GSM2813750_processed.txt"
    else:
        missing = [f for f in (OSD546_EXPRESSION, OSD546_SAMPLE_TABLE) if f not in present]
        if not missing:
            return "READY_TO_IMPORT", "Processed probeset table and sample table present; run the importer."
        needed = " and ".join(missing)
    try:
        rel = folder.resolve().relative_to(REPO_DIR).as_posix()
    except ValueError:
        rel = folder.as_posix()
    if any(_is_raw_cel(folder / n) for n in present):
        return "UNSUPPORTED_FORMAT", (f"Only raw Affymetrix .CEL files found; raw microarray processing is not "
                                      f"implemented (P2). Place NASA processed file(s) {needed} in {rel}/.")
    if present:
        return "UNSUPPORTED_FORMAT", f"Files present but not the expected processed file(s): {needed}."
    return "NOT_DOWNLOADED", f"Not downloaded. Place NASA processed file(s) {needed} in {rel}/."


# --------------------------------------------------------------------------- parsing


def _num(raw: str) -> Optional[float]:
    s = (raw or "").strip()
    if s.upper() in MISSING_TOKENS:
        return None
    try:
        return float(s)
    except ValueError as exc:
        raise ExpressionFormatError(f"non-numeric value '{raw}'") from exc


def _is_number(raw: str) -> bool:
    try:
        float((raw or "").strip())
        return True
    except ValueError:
        return False


def _rows(text: str) -> list[list[str]]:
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith(("#", "!"))]
    if not lines:
        raise ExpressionFormatError("file contains no data rows")
    delim = "\t" if "\t" in lines[0] else ","
    return [[c.strip().strip('"') for c in r] for r in csv.reader(lines, delimiter=delim)]


def parse_osd195(text: str) -> tuple[list[dict], dict]:
    rows = _rows(text)
    first = rows[0]
    has_header = len(first) >= 2 and not _is_number(first[1])
    if has_header:
        upper = [h.upper() for h in first]
        probe_col = next((i for i, h in enumerate(upper) if h in PROBE_HEADERS), 0)
        symbol_col = next((i for i, h in enumerate(upper) if h in SYMBOL_HEADERS), None)
        if "VALUE" in upper:
            value_col = upper.index("VALUE")
        else:
            candidates = [i for i in range(len(first)) if i not in (probe_col, symbol_col)]
            if len(candidates) != 1:
                raise ExpressionFormatError(f"cannot identify a single value column in header {first}")
            value_col = candidates[0]
        header, data = first, rows[1:]
    else:
        if len(first) != 2:
            raise ExpressionFormatError("headerless file must have exactly two columns (probe ID, value)")
        probe_col, value_col, symbol_col, header, data = 0, 1, None, ["(probe)", "(value)"], rows
    if not data:
        raise ExpressionFormatError("file contains no data rows")
    width, seen, out, missing = len(header), set(), [], 0
    for i, r in enumerate(data, start=1):
        if len(r) != width:
            raise ExpressionFormatError(f"row {i}: expected {width} columns, found {len(r)}")
        probe = r[probe_col]
        if not probe:
            raise ExpressionFormatError(f"row {i}: empty probe ID")
        if probe in seen:
            raise ExpressionFormatError(f"row {i}: duplicate probe ID '{probe}'")
        seen.add(probe)
        try:
            value = _num(r[value_col])
        except ExpressionFormatError as exc:
            raise ExpressionFormatError(f"row {i}: {exc}") from exc
        missing += value is None
        out.append(dict(source_row_number=i, probe_id=probe, value=value, value_raw=r[value_col],
                        gene_symbol=(r[symbol_col] or None) if symbol_col is not None else None,
                        source_column=header[value_col]))
    return out, {"columns": header, "value_column": header[value_col], "missing_values": {"value": missing}}


def _sample_table_groups(text: str) -> dict[str, str]:
    """Map each verified OSD-546 sample (GSM) to the text of the *other* cells of its SampleTable row
    (the group/condition cells; the cell naming the sample itself is excluded)."""
    rows = _rows(text)
    found = {}
    for gsm, meta in SAMPLES["OSD-546"].items():
        for r in rows:
            if any(gsm in c or meta["code"] in c for c in r):
                found[gsm] = " | ".join(c for c in r if c and gsm not in c and meta["code"] not in c)
                break
    return found


def _group_agrees(group_text: str, factors: dict[str, str]) -> bool:
    """SampleTable group text, e.g. '(Space Flight & osteogenic)', must state both verified factors."""
    t = group_text.lower()
    flight_ok = ("flight" in t and "ground" not in t) if factors["Spaceflight"] == "Space Flight" else "ground" in t
    other = {"osteogenic": "standard", "standard": "osteogenic"}[factors["Treatment"]]
    return flight_ok and factors["Treatment"] in t and other not in t


def parse_osd546(expr_text: str, sample_table_text: str) -> tuple[list[dict], dict]:
    rows = _rows(expr_text)
    header, data = rows[0], rows[1:]
    if not data:
        raise ExpressionFormatError("probeset table contains no data rows")
    upper = [h.upper() for h in header]
    sample_cols: dict[int, str] = {}
    for gsm, meta in SAMPLES["OSD-546"].items():
        hits = [i for i, h in enumerate(header) if gsm in h or meta["code"] in h]
        if len(hits) > 1:
            raise ExpressionFormatError(f"sample {gsm} matches several columns: {[header[i] for i in hits]}")
        if hits:
            sample_cols[hits[0]] = gsm
    if not sample_cols:
        raise ExpressionFormatError(f"no column matches a verified OSD-546 sample; header {header[:8]}...")
    groups = _sample_table_groups(sample_table_text)
    for gsm in sample_cols.values():
        expected = SAMPLES["OSD-546"][gsm]["factors"]
        if gsm not in groups:
            raise ExpressionFormatError(f"sample {gsm} is not listed in {OSD546_SAMPLE_TABLE}")
        if not _group_agrees(groups[gsm], expected):
            raise ExpressionFormatError(f"sample {gsm}: SampleTable row '{groups[gsm]}' disagrees with the verified "
                                        f"OSDR factors {expected}")
    probe_col = next((i for i, h in enumerate(upper) if h in PROBE_HEADERS), 0)
    if probe_col in sample_cols:
        raise ExpressionFormatError("probe ID column could not be identified")
    symbol_col = next((i for i, h in enumerate(upper) if h in SYMBOL_HEADERS), None)
    out, missing, seen = [], {gsm: 0 for gsm in sample_cols.values()}, set()
    for i, r in enumerate(data, start=1):
        if len(r) != len(header):
            raise ExpressionFormatError(f"row {i}: expected {len(header)} columns, found {len(r)}")
        probe = r[probe_col]
        if not probe or probe in seen:
            raise ExpressionFormatError(f"row {i}: empty or duplicate probeset ID '{probe}'")
        seen.add(probe)
        symbol = (r[symbol_col] or None) if symbol_col is not None else None
        if symbol is not None and symbol.upper() in MISSING_TOKENS:
            symbol = None
        for col, gsm in sample_cols.items():
            try:
                value = _num(r[col])
            except ExpressionFormatError as exc:
                raise ExpressionFormatError(f"row {i}, column {header[col]}: {exc}") from exc
            missing[gsm] += value is None
            out.append(dict(source_row_number=i, probe_id=probe, gene_symbol=symbol, value=value, value_raw=r[col],
                            source_column=header[col], sample_id=gsm))
    info = {"columns": header, "sample_columns": {header[c]: g for c, g in sample_cols.items()},
            "annotation_columns": [h for i, h in enumerate(header) if i not in sample_cols],
            "missing_values": missing, "sample_table_rows": {g: groups[g] for g in sample_cols.values()}}
    return out, info


# --------------------------------------------------------------------------- import


def _write_log(settings: Settings, result: ExpressionImportResult) -> str:
    settings.import_log_dir.mkdir(parents=True, exist_ok=True)
    path = settings.import_log_dir / f"{result.dataset_id}_{result.import_id}.json"
    path.write_text(json.dumps({**asdict(result), "log_path": None, "transformation": TRANSFORMATION,
                                "normalization": NORMALIZATION[result.dataset_id],
                                "written_at": utcnow().isoformat()}, indent=2), encoding="utf-8")
    return path.as_posix()


def _import_file(db: Session, settings: Settings, dataset_id: str, path: Path, sha: str, parse,
                 companions: Optional[dict[str, str]] = None) -> ExpressionImportResult:
    """sha is the SHA-256 of `path` itself. companions maps companion file name -> SHA-256 (e.g. the OSD-546
    SampleTable); a changed companion also triggers re-import."""
    G = m.GeneExpressionValue
    companions = companions or {}
    result = ExpressionImportResult(outcome="failed", dataset_id=dataset_id, source_file=path.name, sha256=sha)
    already = db.scalars(select(m.DatasetImport).where(m.DatasetImport.dataset_id == dataset_id,
                                                       m.DatasetImport.source_file == path.name,
                                                       m.DatasetImport.sha256 == sha,
                                                       m.DatasetImport.status == "IMPORTED")
                         .order_by(m.DatasetImport.started_at.desc())).first()
    existing = db.scalar(select(func.count()).select_from(G).where(G.dataset_id == dataset_id,
                                                                   G.source_file == path.name)) or 0
    if already is not None and existing == already.rows_imported \
            and already.summary.get("companion_files_sha256", {}) == companions:
        result.outcome, result.import_id = "skipped_duplicate", already.import_id
        result.rows_read, result.samples = already.rows_read, already.summary.get("samples", [])
        result.message = f"{path.name} already imported as {already.import_id}; no rows added."
        return result
    imp = m.DatasetImport(import_id=m.new_id("IMP"), dataset_id=dataset_id, source_file=path.name, sha256=sha,
                          status="IMPORT_FAILED", started_at=utcnow())
    result.import_id = imp.import_id
    try:
        rows, info = parse()
        samples = sorted({r["sample_id"] for r in rows})
        result.rows_read, result.samples, result.missing_values = len(rows), samples, info["missing_values"]
        db.execute(delete(G).where(G.dataset_id == dataset_id, G.source_file == path.name))
        db.add(imp)
        db.flush()
        for r in rows:
            r.update(dataset_id=dataset_id, import_id=imp.import_id, source_file=path.name)
        for start in range(0, len(rows), CHUNK):
            db.execute(insert(G), rows[start:start + CHUNK])
        imp.status, imp.rows_read, imp.rows_imported = "IMPORTED", len(rows), len(rows)
        imp.summary = {**info, "samples": samples, "normalization": NORMALIZATION[dataset_id],
                       "companion_files_sha256": companions}
        imp.message = f"Imported {len(rows)} expression values for {len(samples)} sample(s)."
        imp.finished_at = utcnow()
        db.commit()
        result.outcome, result.rows_imported, result.message = "imported", len(rows), imp.message
    except (ExpressionFormatError, UnicodeDecodeError) as exc:
        db.rollback()
        db.add(m.DatasetImport(import_id=result.import_id, dataset_id=dataset_id, source_file=path.name, sha256=sha,
                               status="IMPORT_FAILED", started_at=imp.started_at, finished_at=utcnow(),
                               rows_read=result.rows_read, rows_imported=0, summary={}, message=str(exc)))
        db.commit()
        result.message = str(exc)
    result.log_path = _write_log(settings, result)
    return result


def import_osd195_file(db: Session, settings: Settings, path: Path) -> ExpressionImportResult:
    mt = OSD195_PATTERN.match(path.name)
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()

    def parse():
        if not mt:
            raise ExpressionFormatError(f"file name '{path.name}' is not GLDS-195_microarray_<GSM>_processed.txt")
        gsm = mt.group(1)
        if gsm not in SAMPLES["OSD-195"]:
            raise ExpressionFormatError(f"sample {gsm} is not in the verified OSD-195 sample metadata")
        rows, info = parse_osd195(data.decode("utf-8-sig"))
        for r in rows:
            r["sample_id"] = gsm
        return rows, info

    return _import_file(db, settings, "OSD-195", path, sha, parse)


def import_osd546(db: Session, settings: Settings, folder: Path) -> ExpressionImportResult:
    expr, table = folder / OSD546_EXPRESSION, folder / OSD546_SAMPLE_TABLE
    data = expr.read_bytes()
    sample_table = table.read_bytes()
    return _import_file(db, settings, "OSD-546", expr, hashlib.sha256(data).hexdigest(),
                        lambda: parse_osd546(data.decode("utf-8-sig"), sample_table.decode("utf-8-sig")),
                        companions={OSD546_SAMPLE_TABLE: hashlib.sha256(sample_table).hexdigest()})


def import_dataset(db: Session, settings: Settings, dataset_id: str) -> list[ExpressionImportResult]:
    from ..services.datasets import raw_dir_for

    folder = raw_dir_for(settings, dataset_id)
    if dataset_id == "OSD-195":
        files = osd195_files(folder)
        if files:
            return [import_osd195_file(db, settings, p) for p in files]
    elif dataset_id == "OSD-546":
        if (folder / OSD546_EXPRESSION).is_file() and (folder / OSD546_SAMPLE_TABLE).is_file():
            return [import_osd546(db, settings, folder)]
    else:
        raise ValueError(f"{dataset_id} has no expression importer")
    status, reason = file_status(settings, dataset_id, folder)
    return [ExpressionImportResult(outcome="unsupported_format" if status == "UNSUPPORTED_FORMAT" else "not_found",
                                   dataset_id=dataset_id, message=reason)]


def import_all_available(db: Session, settings: Settings) -> dict[str, list[ExpressionImportResult]]:
    return {d: import_dataset(db, settings, d) for d in ("OSD-195", "OSD-546")}

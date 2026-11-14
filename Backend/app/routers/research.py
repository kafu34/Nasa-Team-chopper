from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import as_utc, get_db
from ..errors import ApiError
from ..schemas.common import error_responses
from ..importers import osd656, osd817, radlab
from ..schemas.research import (AssayRecord, CmpRecord, HistologyRecord, ComparisonReadiness, DatasetDetail, DatasetList, GeneExpressionRecord,
                                Provenance, ResearchRecordsPage, ResearchSample, StudyTypeInfo, TimeseriesPage,
                                TimeseriesPoint)
from ..services import datasets as ds
from ..importers import expression as ex
from ..importers.expression_metadata import SAMPLES
from ..importers.osd575 import TRANSFORMATION

router = APIRouter(prefix="/api/v1", tags=["research"])

STATUS_VALUES = ["NOT_DOWNLOADED", "READY_TO_IMPORT", "IMPORTED", "IMPORT_FAILED", "UNSUPPORTED_FORMAT"]


def _unknown_dataset(dataset_id: str) -> ApiError:
    return ApiError(404, "UNKNOWN_DATASET", f"Dataset '{dataset_id}' is not a canonical identifier (case-sensitive).",
                    {"dataset_id": dataset_id, "allowed_dataset_ids": ds.CANONICAL_IDS})


def _unavailable(db: Session, settings, dataset_id: str) -> ApiError:
    status, reason = ds.compute_status(db, settings, dataset_id)
    return ApiError(503, "DATASET_UNAVAILABLE", f"Dataset '{dataset_id}' has no imported records ({status}).",
                    {"dataset_id": dataset_id, "status": status, "status_reason": reason,
                     "source_url": ds.REGISTRY[dataset_id]["source_url"]})


@router.get("/research/datasets", response_model=DatasetList,
            summary="Catalogue of the canonical NASA datasets with scientific classification")
def list_datasets(request: Request, db: Session = Depends(get_db)) -> DatasetList:
    st = request.app.state.settings
    return DatasetList(datasets=[ds.summary(db, st, d) for d in ds.CANONICAL_IDS], status_values=STATUS_VALUES,
                       data_categories=["NASA_RESEARCH", "SIMULATED_ASTRONAUT", "SIMULATED_ENVIRONMENT_OR_DEVICE"],
                       study_types=[StudyTypeInfo(study_type=t, label=lbl, description=d)
                                    for t, lbl, d in ds.STUDY_TYPES])


@router.get("/research/datasets/{dataset_id}", response_model=DatasetDetail, responses=error_responses(404),
            summary="Dataset metadata, provenance, availability status and latest import log")
def get_dataset(dataset_id: str, request: Request, db: Session = Depends(get_db)) -> DatasetDetail:
    if dataset_id not in ds.REGISTRY:
        raise _unknown_dataset(dataset_id)
    return ds.detail(db, request.app.state.settings, dataset_id)


def _wrong_filter(dataset_id: str, given: dict[str, Optional[str]]) -> None:
    bad = sorted(k for k, v in given.items() if v is not None)
    if bad:
        raise ApiError(422, "INVALID_FILTER_FOR_DATASET",
                       f"Filter(s) {bad} do not apply to {dataset_id} ({ds.REGISTRY[dataset_id]['record_schema']}).",
                       {"parameters": bad, "record_schema": ds.REGISTRY[dataset_id]["record_schema"]})


def _provenance(dataset_id: str, imp: m.DatasetImport, transformation: str) -> Provenance:
    meta = ds.REGISTRY[dataset_id]
    return Provenance(dataset_id=dataset_id, title=meta["title"], organization=ds.OSDR, source_url=meta["source_url"],
                      source_file=imp.source_file, sha256=imp.sha256, import_id=imp.import_id,
                      imported_at=imp.finished_at or imp.started_at, transformation=transformation)


def _readiness(dataset_id: str, imported: set[str]) -> ComparisonReadiness:
    norm = ex.NORMALIZATION[dataset_id]
    reasons = ["SENTINEL does not compute fold changes or statistics; any comparison is research context only."]
    if dataset_id == "OSD-195":
        by_subject: dict[str, set[str]] = {}
        for gsm in imported:
            meta = SAMPLES[dataset_id][gsm]
            by_subject.setdefault(meta["subject_id"], set()).add(meta["factors"]["Bed Rest"])
        pairs = sorted(s for s, phases in by_subject.items() if len(phases) == 2)
        matched = bool(pairs)
        reasons.append(f"Matched before/after bed-rest pairs imported for subject(s): {pairs}." if matched else
                       "No subject has both its Before and After Bed Rest samples imported.")
        if matched and len(pairs) == 1:
            reasons.append("Only one subject: a single pair cannot show a general effect of bed rest.")
    else:
        f = [SAMPLES[dataset_id][g]["factors"] for g in imported]
        media = [t for t in ("osteogenic", "standard")
                 if {x["Spaceflight"] for x in f if x["Treatment"] == t} == {"Space Flight", "Ground Control"}]
        matched = bool(media)
        reasons.append(f"Space Flight and Ground Control samples imported in the same medium: {media}." if matched
                       else "No medium has both Space Flight and Ground Control samples imported.")
        reasons.append("Spaceflight and Treatment factors checked against NASA GLDS-546_array_SampleTable.csv.")
        reasons.append("Cells in culture: results describe cell gene expression, not any person's bone health.")
    reasons.append("Normalisation verified from NASA processing metadata." if norm["verified"] else
                   "Normalisation not yet verified verbatim from NASA metadata.")
    return ComparisonReadiness(ready=matched and norm["verified"], reasons=reasons)


def _expression_page(db: Session, settings, dataset_id: str, subject_id: Optional[str], sample_id: Optional[str],
                     probe_id: Optional[str], gene_symbol: Optional[str], limit: int, offset: int) -> ResearchRecordsPage:
    G = m.GeneExpressionValue
    imports = db.scalars(select(m.DatasetImport).where(m.DatasetImport.dataset_id == dataset_id,
                                                       m.DatasetImport.status == "IMPORTED")
                         .order_by(m.DatasetImport.started_at.desc())).all()
    live = {s for s in db.scalars(select(G.source_file).where(G.dataset_id == dataset_id).distinct())}
    current = {}
    for imp in imports:  # newest first: keep the latest successful import of each file still holding rows
        if imp.source_file in live and imp.source_file not in current:
            current[imp.source_file] = imp
    if not current:
        raise _unavailable(db, settings, dataset_id)
    meta, norm, samples_meta = ds.REGISTRY[dataset_id], ex.NORMALIZATION[dataset_id], SAMPLES[dataset_id]
    imported = set(db.scalars(select(G.sample_id).where(G.dataset_id == dataset_id).distinct()))
    subjects = sorted({samples_meta[g]["subject_id"] for g in imported if samples_meta[g]["subject_id"]}, key=int)
    for name, val, allowed in (("subject_id", subject_id, subjects), ("sample_id", sample_id, sorted(imported))):
        if val is not None and val not in allowed:
            raise ApiError(422, "UNKNOWN_FILTER_VALUE", f"{name} '{val}' is not present in {dataset_id}.",
                           {"parameter": name, "allowed_values": allowed})
    base = select(G).where(G.dataset_id == dataset_id)
    if subject_id:
        base = base.where(G.sample_id.in_([g for g in imported if samples_meta[g]["subject_id"] == subject_id]))
    if sample_id:
        base = base.where(G.sample_id == sample_id)
    if probe_id:
        base = base.where(G.probe_id == probe_id)
    if gene_symbol:
        base = base.where(G.gene_symbol == gene_symbol)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(base.order_by(G.source_file, G.source_row_number, G.sample_id).limit(limit).offset(offset)).all()
    latest = next(iter(current.values()))
    file_of = {g: (samples_meta[g]["processed_file"] or ex.OSD546_EXPRESSION) for g in samples_meta}
    return ResearchRecordsPage(
        dataset_id=dataset_id, title=meta["title"], source_url=meta["source_url"], source_file=latest.source_file,
        record_schema=meta["record_schema"], provenance=_provenance(dataset_id, latest, ex.TRANSFORMATION),
        total=total, limit=limit, offset=offset,
        filters_applied={"subject_id": subject_id, "sample_id": sample_id, "probe_id": probe_id,
                         "gene_symbol": gene_symbol},
        available_subjects=subjects, available_analytes=[], available_timepoints=[],
        limitations=meta["limitations"], records=[],
        study_type=ds.CLASSIFICATION[dataset_id]["study_type"],
        expression_records=[GeneExpressionRecord(
            record_id=r.id, dataset_id=dataset_id, sample_id=r.sample_id,
            subject_id=samples_meta[r.sample_id]["subject_id"],
            condition_label=samples_meta[r.sample_id]["condition_label"], probe_id=r.probe_id,
            gene_symbol=r.gene_symbol, value=r.value, value_raw=r.value_raw, value_unit=norm["value_unit"],
            normalization=norm["text"], normalization_verified=norm["verified"], source_file=r.source_file,
            source_row_number=r.source_row_number, source_column=r.source_column) for r in rows],
        samples=[ResearchSample(sample_id=g, subject_id=s["subject_id"],
                                study_type=ds.CLASSIFICATION[dataset_id]["study_type"], factors=s["factors"],
                                factors_verified=s["factors_verified"], condition_label=s["condition_label"],
                                source_file_name=file_of[g], imported=g in imported)
                 for g, s in samples_meta.items()],
        comparison_readiness=_readiness(dataset_id, imported),
        source_files=[_provenance(dataset_id, imp, ex.TRANSFORMATION) for imp in current.values()])


def _assay_page(db: Session, settings, dataset_id: str, subject_id: Optional[str], analyte: Optional[str],
                timepoint: Optional[str], measure: Optional[str], limit: int, offset: int) -> ResearchRecordsPage:
    A = m.AssayMeasurement
    imp = db.scalars(select(m.DatasetImport).where(m.DatasetImport.dataset_id == dataset_id,
                                                   m.DatasetImport.status == "IMPORTED")
                     .order_by(m.DatasetImport.started_at.desc())).first()
    if imp is None or ds.record_count(db, dataset_id) == 0:
        raise _unavailable(db, settings, dataset_id)
    where = A.dataset_id == dataset_id
    subjects = sorted(db.scalars(select(A.subject_id).where(where).distinct()))
    analytes = sorted(db.scalars(select(A.analyte).where(where).distinct()))
    measures = sorted(db.scalars(select(A.measure).where(where).distinct()))
    tps = [t for t, _ in db.execute(select(A.timepoint, func.min(A.timepoint_order)).where(where)
                                   .group_by(A.timepoint).order_by(func.min(A.timepoint_order)))]
    for name, val, allowed in (("subject_id", subject_id, subjects), ("analyte", analyte, analytes),
                               ("timepoint", timepoint, tps), ("measure", measure, measures)):
        if val is not None and val not in allowed:
            raise ApiError(422, "UNKNOWN_FILTER_VALUE", f"{name} '{val}' is not present in {dataset_id}.",
                           {"parameter": name, "allowed_values": allowed})
    base = select(A).where(where)
    for col, val in ((A.subject_id, subject_id), (A.analyte, analyte), (A.timepoint, timepoint), (A.measure, measure)):
        if val:
            base = base.where(col == val)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(base.order_by(A.analyte, A.measure, A.subject_id, A.timepoint_order)
                      .limit(limit).offset(offset)).all()
    meta = ds.REGISTRY[dataset_id]
    prov = _provenance(dataset_id, imp, osd656.TRANSFORMATION)
    return ResearchRecordsPage(
        dataset_id=dataset_id, title=meta["title"], source_url=meta["source_url"], source_file=imp.source_file,
        record_schema=meta["record_schema"], provenance=prov, total=total, limit=limit, offset=offset,
        filters_applied={"subject_id": subject_id, "analyte": analyte, "timepoint": timepoint, "measure": measure},
        available_subjects=subjects, available_analytes=analytes, available_timepoints=tps,
        available_measures=measures, limitations=meta["limitations"], records=[],
        study_type=ds.CLASSIFICATION[dataset_id]["study_type"], source_files=[prov],
        assay_records=[AssayRecord(record_id=r.id, dataset_id=dataset_id,
                                   **{k: getattr(r, k) for k in AssayRecord.model_fields
                                      if k not in ("record_id", "dataset_id", "data_category")}) for r in rows])


def _histology_page(db: Session, settings, dataset_id: str, subject_id: Optional[str], analyte: Optional[str],
                    measure: Optional[str], limit: int, offset: int) -> ResearchRecordsPage:
    H = m.HistologyCount
    imp = db.scalars(select(m.DatasetImport).where(m.DatasetImport.dataset_id == dataset_id,
                                                   m.DatasetImport.status == "IMPORTED")
                     .order_by(m.DatasetImport.started_at.desc())).first()
    if imp is None or ds.record_count(db, dataset_id) == 0:
        raise _unavailable(db, settings, dataset_id)
    where = H.dataset_id == dataset_id
    donors = sorted(db.scalars(select(H.donor_id).where(where).distinct()), key=int)
    assays = sorted(db.scalars(select(H.assay).where(where).distinct()))
    measures = sorted(db.scalars(select(H.measure).where(where).distinct()))
    for name, val, allowed in (("subject_id", subject_id, donors), ("analyte", analyte, assays),
                               ("measure", measure, measures)):
        if val is not None and val not in allowed:
            raise ApiError(422, "UNKNOWN_FILTER_VALUE", f"{name} '{val}' is not present in {dataset_id}.",
                           {"parameter": name, "allowed_values": allowed})
    base = select(H).where(where)
    for col, val in ((H.donor_id, subject_id), (H.assay, analyte), (H.measure, measure)):
        if val:
            base = base.where(col == val)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(base.order_by(H.assay, H.source_row_number, H.measure).limit(limit).offset(offset)).all()
    meta = ds.REGISTRY[dataset_id]
    files = imp.summary.get("files_sha256", {})
    provs = []
    for name, sha in files.items():
        p = _provenance(dataset_id, imp, osd817.TRANSFORMATION)
        p.source_file, p.sha256 = name, sha
        provs.append(p)
    return ResearchRecordsPage(
        dataset_id=dataset_id, title=meta["title"], source_url=meta["source_url"], source_file=imp.source_file,
        record_schema=meta["record_schema"], provenance=_provenance(dataset_id, imp, osd817.TRANSFORMATION),
        total=total, limit=limit, offset=offset,
        filters_applied={"subject_id": subject_id, "analyte": analyte, "measure": measure},
        available_subjects=donors, available_analytes=assays, available_timepoints=[], available_measures=measures,
        limitations=meta["limitations"], records=[], study_type=ds.CLASSIFICATION[dataset_id]["study_type"],
        source_files=provs,
        histology_records=[HistologyRecord(record_id=r.id, dataset_id=dataset_id, unit=osd817.UNITS[r.measure],
                                           **{k: getattr(r, k) for k in HistologyRecord.model_fields
                                              if k not in ("record_id", "dataset_id", "data_category", "unit")})
                           for r in rows])


def _records_page(db: Session, settings, dataset_id: str, subject_id: Optional[str], analyte: Optional[str],
                  timepoint: Optional[str], limit: int, offset: int, sample_id: Optional[str] = None,
                  probe_id: Optional[str] = None, gene_symbol: Optional[str] = None,
                  measure: Optional[str] = None) -> ResearchRecordsPage:
    if dataset_id not in ds.REGISTRY:
        raise _unknown_dataset(dataset_id)
    schema = ds.REGISTRY[dataset_id]["record_schema"]
    if schema in ("RADIATION_TIMESERIES_V1", "ENVIRONMENT_TIMESERIES_V1"):
        endpoint = "/api/v1/radiation/timeseries" if schema == "RADIATION_TIMESERIES_V1" \
            else "/api/v1/environment/timeseries"
        raise ApiError(422, "INVALID_DATASET_FOR_ENDPOINT",
                       f"{dataset_id} is a timeseries dataset; use {endpoint}?dataset_id={dataset_id}.",
                       {"dataset_id": dataset_id, "use_endpoint": endpoint})
    if schema == "GENE_EXPRESSION_V1":
        _wrong_filter(dataset_id, {"analyte": analyte, "timepoint": timepoint, "measure": measure})
        return _expression_page(db, settings, dataset_id, subject_id, sample_id, probe_id, gene_symbol, limit, offset)
    _wrong_filter(dataset_id, {"sample_id": sample_id, "probe_id": probe_id, "gene_symbol": gene_symbol})
    if schema == "BIO_ASSAY_TABLE":
        return _assay_page(db, settings, dataset_id, subject_id, analyte, timepoint, measure, limit, offset)
    if schema == "HISTOLOGY_COUNTS_V1":
        _wrong_filter(dataset_id, {"timepoint": timepoint})
        return _histology_page(db, settings, dataset_id, subject_id, analyte, measure, limit, offset)
    _wrong_filter(dataset_id, {"measure": measure})
    imp = db.scalars(select(m.DatasetImport).where(m.DatasetImport.dataset_id == dataset_id,
                                                   m.DatasetImport.status == "IMPORTED")
                     .order_by(m.DatasetImport.started_at.desc())).first()
    if imp is None or ds.record_count(db, dataset_id) == 0:
        raise _unavailable(db, settings, dataset_id)
    R = m.ResearchMeasurement
    base = select(R).where(R.dataset_id == dataset_id)
    subjects = sorted(db.scalars(select(R.subject_id).where(R.dataset_id == dataset_id).distinct()))
    analytes = sorted(db.scalars(select(R.analyte).where(R.dataset_id == dataset_id).distinct()))
    tps = [t for t, _ in db.execute(select(R.timepoint, func.min(R.timepoint_order)).where(R.dataset_id == dataset_id)
                                   .group_by(R.timepoint).order_by(func.min(R.timepoint_order)))]
    for name, val, allowed in (("subject_id", subject_id, subjects), ("analyte", analyte, analytes),
                               ("timepoint", timepoint, tps)):
        if val is not None and val not in allowed:
            raise ApiError(422, "UNKNOWN_FILTER_VALUE", f"{name} '{val}' is not present in {dataset_id}.",
                           {"parameter": name, "allowed_values": allowed})
    if subject_id:
        base = base.where(R.subject_id == subject_id)
    if analyte:
        base = base.where(R.analyte == analyte)
    if timepoint:
        base = base.where(R.timepoint == timepoint)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(base.order_by(R.subject_id, R.timepoint_order, R.source_row_number)
                      .limit(limit).offset(offset)).all()
    meta = ds.REGISTRY[dataset_id]
    return ResearchRecordsPage(
        dataset_id=dataset_id, title=meta["title"], source_url=meta["source_url"], source_file=imp.source_file,
        record_schema=meta["record_schema"],
        provenance=_provenance(dataset_id, imp, TRANSFORMATION),
        study_type=ds.CLASSIFICATION[dataset_id]["study_type"],
        source_files=[_provenance(dataset_id, imp, TRANSFORMATION)],
        total=total, limit=limit, offset=offset,
        filters_applied={"subject_id": subject_id, "analyte": analyte, "timepoint": timepoint},
        available_subjects=subjects, available_analytes=analytes, available_timepoints=tps,
        limitations=meta["limitations"],
        records=[CmpRecord(record_id=r.id, **{k: getattr(r, k) for k in CmpRecord.model_fields
                                              if k not in ("record_id", "data_category")}) for r in rows])


@router.get("/research/datasets/{dataset_id}/records", response_model=ResearchRecordsPage,
            responses=error_responses(404, 422, 503),
            summary="Numerical records of an imported dataset (paginated, filterable)",
            description="503 DATASET_UNAVAILABLE (details.status, details.source_url) when not imported. "
                        "CMP_ANALYTE_V1 datasets fill `records` (filters subject_id, analyte, timepoint). "
                        "GENE_EXPRESSION_V1 datasets (OSD-195, OSD-546) fill `expression_records`, `samples` and "
                        "`comparison_readiness` (filters subject_id, sample_id, probe_id, gene_symbol). A filter "
                        "that does not apply to the dataset's schema returns 422 INVALID_FILTER_FOR_DATASET.")
def dataset_records(dataset_id: str, request: Request, db: Session = Depends(get_db),
                    subject_id: Optional[str] = Query(None, examples=["C001"]),
                    analyte: Optional[str] = Query(None, examples=["GLUCOSE"]),
                    timepoint: Optional[str] = Query(None, examples=["L-92"]),
                    sample_id: Optional[str] = Query(None, examples=["GSM2813750"]),
                    probe_id: Optional[str] = Query(None),
                    gene_symbol: Optional[str] = Query(None, examples=["MSTN"]),
                    measure: Optional[str] = Query(None, examples=["concentration_npq"]),
                    limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)) -> ResearchRecordsPage:
    return _records_page(db, request.app.state.settings, dataset_id, subject_id, analyte, timepoint, limit, offset,
                         sample_id, probe_id, gene_symbol, measure)


@router.get("/research/osd-575", response_model=ResearchRecordsPage, responses=error_responses(422, 503),
            summary="Actual OSD-575 CMP records (compatibility endpoint; default returns all 531 rows)",
            description="503 DATASET_UNAVAILABLE when the CSV has not been imported. Never returns invented values.")
def osd575(request: Request, db: Session = Depends(get_db),
           subject_id: Optional[str] = Query(None, examples=["C001"]),
           analyte: Optional[str] = Query(None, examples=["GLUCOSE"]),
           timepoint: Optional[str] = Query(None, examples=["R+1"]),
           limit: int = Query(1000, ge=1, le=1000), offset: int = Query(0, ge=0)) -> ResearchRecordsPage:
    return _records_page(db, request.app.state.settings, "OSD-575", subject_id, analyte, timepoint, limit, offset)


def _timeseries(db: Session, settings, dataset_id: str, allowed: list[str], metric: Optional[str] = None,
                start: Optional[datetime] = None, end: Optional[datetime] = None, instrument_id: Optional[str] = None,
                limit: int = 500, offset: int = 0) -> TimeseriesPage:
    if dataset_id not in allowed:
        raise ApiError(422, "INVALID_DATASET_FOR_ENDPOINT", f"'{dataset_id}' is not a timeseries dataset here.",
                       {"allowed_dataset_ids": allowed})
    T = m.TimeseriesValue
    imp = db.scalars(select(m.DatasetImport).where(m.DatasetImport.dataset_id == dataset_id,
                                                   m.DatasetImport.status == "IMPORTED")
                     .order_by(m.DatasetImport.started_at.desc())).first()
    if imp is None or ds.record_count(db, dataset_id) == 0:
        raise _unavailable(db, settings, dataset_id)  # nothing is ever fabricated
    where = T.dataset_id == dataset_id
    metrics = sorted(db.scalars(select(T.metric).where(where).distinct()))
    instruments = sorted(db.scalars(select(T.instrument_id).where(where).distinct()))
    metric = metric or ("absorbed_dose_rate" if "absorbed_dose_rate" in metrics else metrics[0])
    for name, val, ok in (("metric", metric, metrics), ("instrument_id", instrument_id, instruments)):
        if val is not None and val not in ok:
            raise ApiError(422, "UNKNOWN_FILTER_VALUE", f"{name} '{val}' is not present in {dataset_id}.",
                           {"parameter": name, "allowed_values": ok})
    first, last = db.execute(select(func.min(T.timestamp), func.max(T.timestamp)).where(where)).one()
    q = select(T).where(where, T.metric == metric)
    if instrument_id:
        q = q.where(T.instrument_id == instrument_id)
    if start:
        q = q.where(T.timestamp >= as_utc(start))
    if end:
        q = q.where(T.timestamp < as_utc(end))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(T.timestamp, T.instrument_id).limit(limit).offset(offset)).all()
    meta = ds.REGISTRY[dataset_id]
    prov = _provenance(dataset_id, imp, radlab.TRANSFORMATION)
    prov.source_url = imp.summary.get("query_url") or prov.source_url
    return TimeseriesPage(
        dataset_id=dataset_id, metric=metric, unit=radlab.METRICS.get(metric, rows[0].unit if rows else ""),
        provenance=prov, total=total, limit=limit, offset=offset,
        points=[TimeseriesPoint(timestamp=r.timestamp, value=r.value, unit=r.unit, timestamp_raw=r.timestamp_raw,
                                instrument_id=r.instrument_id, instrument_family=r.instrument_family,
                                spacecraft=r.spacecraft, module=r.module, latitude=r.latitude,
                                longitude=r.longitude, altitude=r.altitude, source_row_number=r.source_row_number)
                for r in rows],
        study_type=ds.CLASSIFICATION[dataset_id]["study_type"],
        filters_applied={"metric": metric, "instrument_id": instrument_id,
                         "start": start.isoformat() if start else None, "end": end.isoformat() if end else None},
        available_metrics=metrics, available_instruments=instruments, first_timestamp=first, last_timestamp=last,
        limitations=meta["limitations"])


@router.get("/environment/timeseries", response_model=TimeseriesPage, responses=error_responses(422, 503),
            summary="NASA environmental telemetry timeseries (P1; returns 503 until imported)")
def environment_timeseries(request: Request, db: Session = Depends(get_db),
                           dataset_id: str = Query("NASA-EDA"), metric: Optional[str] = Query(None, examples=["co2"]),
                           start: Optional[datetime] = None, end: Optional[datetime] = None,
                           limit: int = Query(500, ge=1, le=5000), offset: int = Query(0, ge=0)) -> TimeseriesPage:
    return _timeseries(db, request.app.state.settings, dataset_id, ["NASA-EDA"])


@router.get("/radiation/timeseries", response_model=TimeseriesPage, responses=error_responses(422, 503),
            summary="NASA radiation dosimetry timeseries (RadLab ISS snapshot; 503 until imported)",
            description="Readings from a saved NASA RadLab API snapshot (ISS, 2022-04-01 UTC). metric defaults to "
                        "absorbed_dose_rate (μGy/hour). Filters: instrument_id, start (inclusive), end (exclusive). "
                        "Points are ordered by timestamp then instrument. Research context only: never live HAB-01 "
                        "readings or an astronaut's personal dose.")
def radiation_timeseries(request: Request, db: Session = Depends(get_db),
                         dataset_id: str = Query("NASA-RADLAB"),
                         metric: Optional[str] = Query(None, examples=["absorbed_dose_rate"]),
                         instrument_id: Optional[str] = Query(None, examples=["DosTel1"]),
                         start: Optional[datetime] = None, end: Optional[datetime] = None,
                         limit: int = Query(500, ge=1, le=5000), offset: int = Query(0, ge=0)) -> TimeseriesPage:
    return _timeseries(db, request.app.state.settings, dataset_id, ["NASA-RADLAB", "NASA-EDA"], metric, start, end,
                       instrument_id, limit, offset)

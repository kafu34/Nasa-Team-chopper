from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..errors import ApiError
from ..schemas.common import error_responses
from ..schemas.research import (CmpRecord, DatasetDetail, DatasetList, Provenance, ResearchRecordsPage,
                                TimeseriesPage)
from ..services import datasets as ds
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


@router.get("/research/datasets", response_model=DatasetList, summary="Catalogue of the eight canonical NASA datasets")
def list_datasets(request: Request, db: Session = Depends(get_db)) -> DatasetList:
    st = request.app.state.settings
    return DatasetList(datasets=[ds.summary(db, st, d) for d in ds.CANONICAL_IDS], status_values=STATUS_VALUES,
                       data_categories=["NASA_RESEARCH", "SIMULATED_ASTRONAUT", "SIMULATED_ENVIRONMENT_OR_DEVICE"])


@router.get("/research/datasets/{dataset_id}", response_model=DatasetDetail, responses=error_responses(404),
            summary="Dataset metadata, provenance, availability status and latest import log")
def get_dataset(dataset_id: str, request: Request, db: Session = Depends(get_db)) -> DatasetDetail:
    if dataset_id not in ds.REGISTRY:
        raise _unknown_dataset(dataset_id)
    return ds.detail(db, request.app.state.settings, dataset_id)


def _records_page(db: Session, settings, dataset_id: str, subject_id: Optional[str], analyte: Optional[str],
                  timepoint: Optional[str], limit: int, offset: int) -> ResearchRecordsPage:
    if dataset_id not in ds.REGISTRY:
        raise _unknown_dataset(dataset_id)
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
        provenance=Provenance(dataset_id=dataset_id, title=meta["title"], organization=ds.OSDR,
                              source_url=meta["source_url"], source_file=imp.source_file, sha256=imp.sha256,
                              import_id=imp.import_id, imported_at=imp.finished_at or imp.started_at,
                              transformation=TRANSFORMATION),
        total=total, limit=limit, offset=offset,
        filters_applied={"subject_id": subject_id, "analyte": analyte, "timepoint": timepoint},
        available_subjects=subjects, available_analytes=analytes, available_timepoints=tps,
        limitations=meta["limitations"],
        records=[CmpRecord(record_id=r.id, **{k: getattr(r, k) for k in CmpRecord.model_fields
                                              if k not in ("record_id", "data_category")}) for r in rows])


@router.get("/research/datasets/{dataset_id}/records", response_model=ResearchRecordsPage,
            responses=error_responses(404, 422, 503),
            summary="Numerical records of an imported dataset (paginated, filterable)",
            description="503 DATASET_UNAVAILABLE (details.status, details.source_url) when not imported.")
def dataset_records(dataset_id: str, request: Request, db: Session = Depends(get_db),
                    subject_id: Optional[str] = Query(None, examples=["C001"]),
                    analyte: Optional[str] = Query(None, examples=["GLUCOSE"]),
                    timepoint: Optional[str] = Query(None, examples=["L-92"]),
                    limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)) -> ResearchRecordsPage:
    return _records_page(db, request.app.state.settings, dataset_id, subject_id, analyte, timepoint, limit, offset)


@router.get("/research/osd-575", response_model=ResearchRecordsPage, responses=error_responses(422, 503),
            summary="Actual OSD-575 CMP records (compatibility endpoint; default returns all 531 rows)",
            description="503 DATASET_UNAVAILABLE when the CSV has not been imported. Never returns invented values.")
def osd575(request: Request, db: Session = Depends(get_db),
           subject_id: Optional[str] = Query(None, examples=["C001"]),
           analyte: Optional[str] = Query(None, examples=["GLUCOSE"]),
           timepoint: Optional[str] = Query(None, examples=["R+1"]),
           limit: int = Query(1000, ge=1, le=1000), offset: int = Query(0, ge=0)) -> ResearchRecordsPage:
    return _records_page(db, request.app.state.settings, "OSD-575", subject_id, analyte, timepoint, limit, offset)


def _timeseries(db: Session, settings, dataset_id: str, allowed: list[str]) -> TimeseriesPage:
    if dataset_id not in allowed:
        raise ApiError(422, "INVALID_DATASET_FOR_ENDPOINT", f"'{dataset_id}' is not a timeseries dataset here.",
                       {"allowed_dataset_ids": allowed})
    # No timeseries importer exists in P0, so nothing is ever fabricated here.
    raise _unavailable(db, settings, dataset_id)


@router.get("/environment/timeseries", response_model=TimeseriesPage, responses=error_responses(422, 503),
            summary="NASA environmental telemetry timeseries (P1; returns 503 until imported)")
def environment_timeseries(request: Request, db: Session = Depends(get_db),
                           dataset_id: str = Query("NASA-EDA"), metric: Optional[str] = Query(None, examples=["co2"]),
                           start: Optional[datetime] = None, end: Optional[datetime] = None,
                           limit: int = Query(500, ge=1, le=5000), offset: int = Query(0, ge=0)) -> TimeseriesPage:
    return _timeseries(db, request.app.state.settings, dataset_id, ["NASA-EDA"])


@router.get("/radiation/timeseries", response_model=TimeseriesPage, responses=error_responses(422, 503),
            summary="NASA radiation dosimetry timeseries (P1; returns 503 until imported)")
def radiation_timeseries(request: Request, db: Session = Depends(get_db),
                         dataset_id: str = Query("NASA-RADLAB"), metric: Optional[str] = Query(None, examples=["dose_rate"]),
                         start: Optional[datetime] = None, end: Optional[datetime] = None,
                         limit: int = Query(500, ge=1, le=5000), offset: int = Query(0, ge=0)) -> TimeseriesPage:
    return _timeseries(db, request.app.state.settings, dataset_id, ["NASA-RADLAB", "NASA-EDA"])

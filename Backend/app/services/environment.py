"""Environmental context (plan step 38, contract 2.10.0).

Shows the latest imported RadLab reading per instrument, with attribution. These are historical ISS area-dosimeter
readings: they are not the fictional HAB-01 habitat and not any crew member's dose. No relationship to the crew
member's health is inferred. NASA-EDA stays BLOCKED until a source file and importer exist.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import Settings
from . import datasets as ds

CAUTION = ("Historical ISS area-dosimeter readings from NASA RadLab. They are not readings from the fictional HAB-01 "
           "habitat and not any crew member's personal dose. SENTINEL infers no relationship between these values "
           "and the crew member's health.")


def context(db: Session, settings: Settings, astronaut_id: str | None = None) -> dict:
    rad = ds.summary(db, settings, "NASA-RADLAB")
    eda = ds.summary(db, settings, "NASA-EDA")
    readings = []
    if rad.status == "IMPORTED":
        latest = (select(m.TimeseriesValue.instrument_id, m.TimeseriesValue.metric,
                         func.max(m.TimeseriesValue.timestamp).label("ts"))
                  .where(m.TimeseriesValue.dataset_id == "NASA-RADLAB")
                  .group_by(m.TimeseriesValue.instrument_id, m.TimeseriesValue.metric).subquery())
        rows = db.execute(select(m.TimeseriesValue).join(
            latest, (m.TimeseriesValue.instrument_id == latest.c.instrument_id)
            & (m.TimeseriesValue.metric == latest.c.metric) & (m.TimeseriesValue.timestamp == latest.c.ts))
            .where(m.TimeseriesValue.dataset_id == "NASA-RADLAB")
            .order_by(m.TimeseriesValue.instrument_id, m.TimeseriesValue.metric)).scalars().all()
        seen = set()
        for r in rows:
            if (r.instrument_id, r.metric) in seen:
                continue
            seen.add((r.instrument_id, r.metric))
            readings.append({"instrument_id": r.instrument_id, "instrument_family": r.instrument_family,
                             "spacecraft": r.spacecraft, "module": r.module, "metric": r.metric, "value": r.value,
                             "value_raw": r.value_raw, "unit": r.unit, "timestamp": r.timestamp,
                             "source_file": r.source_file, "source_row_number": r.source_row_number})
    return {
        "astronaut_id": astronaut_id,
        "radiation": {"dataset_id": "NASA-RADLAB", "status": rad.status, "title": rad.title,
                      "source_url": getattr(rad, "source_url", None), "location": "ISS (historical snapshot)",
                      "is_habitat_reading": False, "is_personal_dose": False, "latest_readings": readings,
                      "limitations": list(getattr(rad, "limitations", []) or [])},
        "atmosphere": {"dataset_id": "NASA-EDA", "status": eda.status,
                       "note": "BLOCKED: no NASA-EDA source file or importer exists, so no atmosphere data is shown."},
        "health_relationship": "none_inferred",
        "caution": CAUTION,
        "data_category": "NASA_RESEARCH",
    }

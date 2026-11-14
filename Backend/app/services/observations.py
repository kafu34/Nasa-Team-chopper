"""Observation validation and freshness (current / stale / missing)."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import utcnow
from ..errors import ApiError
from ..schemas.cases import ObservationCreate, ObservationStatus

FUTURE_TOLERANCE = timedelta(minutes=5)


def catalogue(fx: dict) -> dict[str, dict]:
    return {c["type"]: c for c in fx["observation_catalogue"]}


def validate(fx: dict, body: ObservationCreate) -> None:
    cat = catalogue(fx)
    spec = cat.get(body.type)
    if spec is None:
        raise ApiError(422, "UNKNOWN_OBSERVATION_TYPE", f"Observation type '{body.type}' is not in the catalogue.",
                       {"allowed_types": sorted(cat)})
    if body.unit != spec["unit"]:
        raise ApiError(422, "UNIT_MISMATCH", f"Unit for '{body.type}' must be '{spec['unit']}'.",
                       {"expected_unit": spec["unit"], "received_unit": body.unit})
    if not (spec["min"] <= body.value <= spec["max"]):
        raise ApiError(422, "VALUE_OUT_OF_TECHNICAL_RANGE",
                       "Value is outside the technically plausible input range. This is not a clinical judgement.",
                       {"min": spec["min"], "max": spec["max"], "received": body.value})
    if body.observed_at > utcnow() + FUTURE_TOLERANCE:
        raise ApiError(422, "TIMESTAMP_IN_FUTURE", "observed_at is in the future.",
                       {"observed_at": body.observed_at.isoformat()})


def statuses(db: Session, fx: dict, astronaut_id: str) -> list[ObservationStatus]:
    now = utcnow()
    out = []
    for spec in fx["observation_catalogue"]:
        latest = db.scalars(select(m.HealthObservation)
                            .where(m.HealthObservation.astronaut_id == astronaut_id,
                                   m.HealthObservation.type == spec["type"])
                            .order_by(m.HealthObservation.observed_at.desc())).first()
        if latest is None:
            status = "missing"
        elif now - latest.observed_at > timedelta(minutes=spec["stale_after_minutes"]):
            status = "stale"
        else:
            status = "current"
        out.append(ObservationStatus(type=spec["type"], unit=spec["unit"], status=status,
                                     stale_after_minutes=spec["stale_after_minutes"],
                                     latest_value=latest.value if latest else None,
                                     latest_observed_at=latest.observed_at if latest else None))
    return out

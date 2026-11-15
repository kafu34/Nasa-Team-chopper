"""Individual baselines (BASELINE-1.0, contract 2.6.0).

Rules
-----
B-1  A baseline is the median of the astronaut's technically valid readings of one type (quality `good` or `fair`)
     inside the configured window; spread = 1.4826 x median absolute deviation, never below the type's floor.
B-2  Each computation is a new version. The previous version is kept as `superseded`; nothing is overwritten.
B-3  Baselines never update automatically. Only the seed (version 1) and an explicit, audited recompute create one.
B-4  While a monitoring concern for that astronaut and type is not closed, recompute is refused (BASELINE_FROZEN).
B-5  Readings observed while a concern was open (from its first evidence to its closure) are always excluded, so a
     prolonged deterioration can never become the new baseline.
B-6  Fewer than `min_samples` valid readings: no baseline (INSUFFICIENT_BASELINE_DATA). Nothing is inferred.

This is fictional demonstration configuration, not a clinically reviewed method.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import utcnow
from ..errors import ApiError, not_found
from .audit import audit

OPEN_CONCERN_STATES = ("open", "awaiting_review")


def method(fx: dict) -> dict:
    return fx["baseline_method"]


def type_config(fx: dict, type_: str) -> dict:
    cfg = method(fx)["types"].get(type_)
    if cfg is None:
        raise ApiError(422, "UNKNOWN_OBSERVATION_TYPE", f"Observation type '{type_}' has no baseline configuration.",
                       {"allowed_types": sorted(method(fx)["types"])})
    return cfg


def active(db: Session, astronaut_id: str, type_: str) -> m.HealthBaseline | None:
    return db.scalars(select(m.HealthBaseline).where(m.HealthBaseline.astronaut_id == astronaut_id,
                                                     m.HealthBaseline.type == type_,
                                                     m.HealthBaseline.status == "active")).first()


def versions(db: Session, astronaut_id: str, type_: str | None = None) -> list[m.HealthBaseline]:
    q = select(m.HealthBaseline).where(m.HealthBaseline.astronaut_id == astronaut_id)
    if type_ is not None:
        q = q.where(m.HealthBaseline.type == type_)
    return list(db.scalars(q.order_by(m.HealthBaseline.type, m.HealthBaseline.version)))


def freezing_concern(db: Session, astronaut_id: str, type_: str) -> m.MonitoringConcern | None:
    return db.scalars(select(m.MonitoringConcern).where(m.MonitoringConcern.astronaut_id == astronaut_id,
                                                        m.MonitoringConcern.type == type_,
                                                        m.MonitoringConcern.status.in_(OPEN_CONCERN_STATES))
                      .order_by(m.MonitoringConcern.opened_at)).first()


def _excluded_periods(db: Session, astronaut_id: str, type_: str) -> list[tuple[datetime, datetime | None]]:
    rows = db.scalars(select(m.MonitoringConcern).where(m.MonitoringConcern.astronaut_id == astronaut_id,
                                                        m.MonitoringConcern.type == type_))
    return [(c.first_evidence_at, c.closed_at) for c in rows]


def compute(db: Session, fx: dict, astronaut_id: str, type_: str, now: datetime | None = None) -> dict:
    """Pure calculation (rules B-1, B-5, B-6). Stores nothing."""
    now = now or utcnow()
    cfg = type_config(fx, type_)
    meth = method(fx)
    start = now - timedelta(days=cfg["window_days"])
    rows = db.scalars(select(m.HealthObservation).where(
        m.HealthObservation.astronaut_id == astronaut_id, m.HealthObservation.type == type_,
        m.HealthObservation.observed_at >= start, m.HealthObservation.observed_at <= now,
        m.HealthObservation.quality.in_(meth["allowed_qualities"])).order_by(m.HealthObservation.observed_at)).all()
    periods = _excluded_periods(db, astronaut_id, type_)
    used, excluded = [], 0
    for o in rows:
        if any(a <= o.observed_at <= (b or now) for a, b in periods):
            excluded += 1
            continue
        used.append(o)
    out = {"type": type_, "sample_count": len(used), "min_samples": cfg["min_samples"], "excluded_count": excluded,
           "window_start": start, "window_end": now, "sufficient": len(used) >= cfg["min_samples"]}
    if out["sufficient"]:
        values = [o.value for o in used]
        centre = median(values)
        mad = median(abs(v - centre) for v in values)
        out.update(centre=round(centre, 3), spread=round(max(mad * meth["mad_scale"], cfg["min_spread"]), 3),
                   source_observation_ids=[o.observation_id for o in used], unit=used[0].unit)
    return out


def create_version(db: Session, fx: dict, astronaut_id: str, type_: str, actor: str, reason: str,
                   now: datetime | None = None) -> m.HealthBaseline:
    now = now or utcnow()
    calc = compute(db, fx, astronaut_id, type_, now)
    if not calc["sufficient"]:
        raise ApiError(422, "INSUFFICIENT_BASELINE_DATA",
                       f"Only {calc['sample_count']} valid '{type_}' readings in the window; "
                       f"{calc['min_samples']} are needed. No baseline is inferred.",
                       {"sample_count": calc["sample_count"], "min_samples": calc["min_samples"],
                        "excluded_count": calc["excluded_count"]})
    prev = active(db, astronaut_id, type_)
    if prev is not None:
        prev.status = "superseded"
        prev.superseded_at = now
    version = (db.scalar(select(func.max(m.HealthBaseline.version)).where(
        m.HealthBaseline.astronaut_id == astronaut_id, m.HealthBaseline.type == type_)) or 0) + 1
    row = m.HealthBaseline(baseline_id=f"BL-{astronaut_id}-{type_}-v{version}", astronaut_id=astronaut_id,
                           type=type_, unit=calc["unit"], version=version, status="active",
                           method_id=method(fx)["method_id"], centre=calc["centre"], spread=calc["spread"],
                           sample_count=calc["sample_count"], excluded_count=calc["excluded_count"],
                           window_start=calc["window_start"], window_end=calc["window_end"],
                           source_observation_ids=calc["source_observation_ids"], created_at=now, created_by=actor,
                           reason=reason)
    db.add(row)
    db.flush()
    audit(db, actor, "baseline.created", "health_baseline", row.baseline_id, type=type_, version=version,
          centre=row.centre, spread=row.spread, sample_count=row.sample_count, excluded_count=row.excluded_count,
          superseded_baseline_id=prev.baseline_id if prev else None, method_id=row.method_id, reason=reason)
    return row


def recompute(db: Session, fx: dict, astronaut_id: str, type_: str, actor_id: str, reason: str) -> m.HealthBaseline:
    if db.get(m.Astronaut, astronaut_id) is None:
        raise not_found("Astronaut", astronaut_id)
    if db.get(m.Astronaut, actor_id) is None:
        raise not_found("Astronaut", actor_id)
    type_config(fx, type_)
    concern = freezing_concern(db, astronaut_id, type_)
    if concern is not None:
        raise ApiError(409, "BASELINE_FROZEN",
                       "A monitoring concern for this measurement is not closed, so the baseline is frozen. "
                       "This stops a sustained change from becoming the new baseline.",
                       {"concern_id": concern.concern_id, "concern_status": concern.status})
    row = create_version(db, fx, astronaut_id, type_, actor_id, reason)
    db.commit()
    return row


def ensure_initial(db: Session, fx: dict, now: datetime | None = None) -> list[str]:
    """Seeds the fictional baseline history and version-1 baselines when the database has no baseline yet."""
    hist = fx.get("baseline_history")
    if not hist or db.scalar(select(m.HealthBaseline.baseline_id).limit(1)) is not None:
        return []
    astro = hist["astronaut_id"]
    if db.get(m.Astronaut, astro) is None:
        return []
    now = now or utcnow()
    for type_, s in hist["series"].items():
        for i, v in enumerate(s["values"]):
            oid = f"OBS-HIST-{type_.upper()}-{i + 1:02d}"
            if db.get(m.HealthObservation, oid) is not None:
                continue
            at = now - timedelta(days=s["first_days_ago"] - i)
            db.add(m.HealthObservation(observation_id=oid, astronaut_id=astro, type=type_, value=v, unit=s["unit"],
                                       observed_at=at, recorded_at=at, source=hist["source"],
                                       quality=hist["quality"], simulated=True))
    db.flush()
    made = []
    for type_ in method(fx)["types"]:
        if compute(db, fx, astro, type_, now)["sufficient"]:
            row = create_version(db, fx, astro, type_, "baseline-engine",
                                 "Initial baseline from the fictional demonstration history.", now)
            made.append(f"baseline {row.baseline_id}")
    db.commit()
    return made

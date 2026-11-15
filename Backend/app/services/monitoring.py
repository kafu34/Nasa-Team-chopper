"""Read models for proactive health intelligence (contract 2.6.0): baselines, concerns and the monitoring summary."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import utcnow
from ..errors import not_found
from ..schemas.monitoring import (BaselineList, BaselineOut, ConcernOut, DataQualityItem, DetectionRuleOut,
                                  DetectionRulesetOut, MonitoringOut, ReassessmentOut, TrendOut, TypeMonitoring)
from . import baselines as bl_svc
from . import detection
from . import observations as obs_svc

TREND_DEFAULT_MINUTES = 1440


def detection_ruleset_out(fx: dict) -> DetectionRulesetOut:
    rs = fx["detection_ruleset"]
    return DetectionRulesetOut(
        ruleset_version=rs["ruleset_version"], baseline_method_id=fx["baseline_method"]["method_id"],
        disclaimer=rs["disclaimer"],
        rules=[DetectionRuleOut(**{k: r[k] for k in DetectionRuleOut.model_fields if k in r},
                                assessment_procedure_id=(r.get("assessment") or {}).get("procedure_id"))
               for r in rs["rules"]])


def baseline_out(db: Session, b: m.HealthBaseline) -> BaselineOut:
    concern = bl_svc.freezing_concern(db, b.astronaut_id, b.type) if b.status == "active" else None
    return BaselineOut(**{k: getattr(b, k) for k in ("baseline_id", "astronaut_id", "type", "unit", "version",
                                                     "status", "method_id", "centre", "spread", "sample_count",
                                                     "excluded_count", "window_start", "window_end",
                                                     "source_observation_ids", "created_at", "created_by", "reason",
                                                     "superseded_at")},
                       frozen=concern is not None, frozen_by_concern_id=concern.concern_id if concern else None)


def baseline_list(db: Session, fx: dict, astronaut_id: str, type_: str | None = None) -> BaselineList:
    if db.get(m.Astronaut, astronaut_id) is None:
        raise not_found("Astronaut", astronaut_id)
    meth = fx["baseline_method"]
    return BaselineList(astronaut_id=astronaut_id, method_id=meth["method_id"], method_description=meth["description"],
                        baselines=[baseline_out(db, b) for b in bl_svc.versions(db, astronaut_id, type_)])


def concern_out(db: Session, fx: dict, c: m.MonitoringConcern) -> ConcernOut:
    rule = detection.rule_for(fx, c.type)
    fu = detection.latest_reassessment(db, c.concern_id)
    if fu is not None and fu.status == "scheduled" and fu.due_at <= utcnow():
        status = "due"  # shown as due; stored lazily on the next ingestion or case read
    else:
        status = fu.status if fu else None
    return ConcernOut(
        concern_id=c.concern_id, astronaut_id=c.astronaut_id, type=c.type, unit=c.unit, rule_id=c.rule_id,
        rule_title=rule["title"] if rule else None, ruleset_version=c.ruleset_version, baseline_id=c.baseline_id,
        baseline_version=c.baseline_version, baseline_frozen=c.status != "closed", direction=c.direction,
        status=c.status, case_id=c.case_id, opened_at=c.opened_at, first_evidence_at=c.first_evidence_at,
        last_triggered_at=c.last_triggered_at, trigger_count=c.trigger_count, suppressed_count=c.suppressed_count,
        evidence_observation_ids=c.evidence_observation_ids, consecutive_within_baseline=c.consecutive_within,
        recovery_count=rule["recovery_count"] if rule else None, reassessment_passed=c.reassessment_passed,
        reassessment=ReassessmentOut(follow_up_id=fu.follow_up_id, status=status, due_at=fu.due_at,
                                     completed_at=fu.completed_at, completion_evidence_id=fu.completion_evidence_id)
        if fu else None,
        closed_at=c.closed_at, closed_by=c.closed_by, review_note=c.review_note,
        disclaimer=fx["detection_ruleset"]["disclaimer"])


def _trend(rows: list[m.HealthObservation], spread: float | None, minutes: int) -> TrendOut:
    pts = [(o.observed_at, o.value) for o in rows if o.quality != "poor"]
    if len(pts) < 3:
        return TrendOut(readings=len(pts), window_minutes=minutes, slope_per_hour=None,
                        description="insufficient_readings")
    t0 = pts[0][0]
    xs = [(t - t0).total_seconds() / 3600 for t, _ in pts]
    ys = [v for _, v in pts]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return TrendOut(readings=len(pts), window_minutes=minutes, slope_per_hour=None,
                        description="insufficient_readings")
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
    change = slope * (xs[-1] - xs[0])
    desc = "stable" if spread is None or abs(change) < spread else ("rising" if slope > 0 else "falling")
    return TrendOut(readings=len(pts), window_minutes=minutes, slope_per_hour=round(slope, 4), description=desc)


def summary(db: Session, fx: dict, astronaut_id: str, now: datetime | None = None) -> MonitoringOut:
    if db.get(m.Astronaut, astronaut_id) is None:
        raise not_found("Astronaut", astronaut_id)
    now = now or utcnow()
    meth = fx["baseline_method"]
    fresh = {s.type: s for s in obs_svc.statuses(db, fx, astronaut_id)}
    types, quality = [], []
    for spec in fx["observation_catalogue"]:
        t = spec["type"]
        rule = detection.rule_for(fx, t)
        bl = bl_svc.active(db, astronaut_id, t)
        minutes = rule["window_minutes"] if rule else TREND_DEFAULT_MINUTES
        rows = db.scalars(select(m.HealthObservation).where(
            m.HealthObservation.astronaut_id == astronaut_id, m.HealthObservation.type == t,
            m.HealthObservation.observed_at >= now - timedelta(minutes=minutes))
            .order_by(m.HealthObservation.observed_at)).all()
        latest = db.scalars(select(m.HealthObservation).where(
            m.HealthObservation.astronaut_id == astronaut_id, m.HealthObservation.type == t)
            .order_by(m.HealthObservation.observed_at.desc(), m.HealthObservation.recorded_at.desc())).first()
        concern = detection.open_concern(db, astronaut_id, t)
        f = fresh[t].status
        if f == "missing":
            quality.append(DataQualityItem(type=t, issue="missing", note="No reading received. Nothing is concluded "
                                                                         "from missing data."))
        elif f == "stale":
            quality.append(DataQualityItem(type=t, issue="stale", note=f"Latest reading is older than "
                                           f"{spec['stale_after_minutes']} minutes. Take a new reading; the old one "
                                           "is not used for detection."))
        if any(o.quality == "poor" for o in rows):
            quality.append(DataQualityItem(type=t, issue="recent_poor_quality", note="A recent reading was marked "
                                           "poor quality and was excluded. Check the sensor fit or device."))
        if rule and bl is None:
            calc = bl_svc.compute(db, fx, astronaut_id, t, now)
            if calc["sufficient"]:
                quality.append(DataQualityItem(type=t, issue="baseline_not_created",
                                               note="Enough valid readings exist but no baseline version has been "
                                                    "created. No comparison is made until one is recomputed."))
            else:
                quality.append(DataQualityItem(type=t, issue="baseline_insufficient",
                                               note=f"{calc['sample_count']} of {calc['min_samples']} valid "
                                                    "readings for an individual baseline. No comparison is made."))
        det = latest.detection if latest is not None and latest.detection and "outcome" in latest.detection else None
        types.append(TypeMonitoring(
            type=t, unit=spec["unit"], freshness=f, rule_id=rule["rule_id"] if rule else None,
            baseline=baseline_out(db, bl) if bl else None, latest_value=latest.value if latest else None,
            latest_observed_at=latest.observed_at if latest else None,
            latest_quality=latest.quality if latest else None,
            difference_from_baseline=round(latest.value - bl.centre, 3) if latest is not None and bl else None,
            latest_detection=det, trend=_trend(rows, bl.spread if bl else None, minutes),
            open_concern_id=concern.concern_id if concern else None))
    concerns = db.scalars(select(m.MonitoringConcern).where(m.MonitoringConcern.astronaut_id == astronaut_id)
                          .order_by(m.MonitoringConcern.opened_at)).all()
    return MonitoringOut(astronaut_id=astronaut_id, ruleset_version=fx["detection_ruleset"]["ruleset_version"],
                         baseline_method_id=meth["method_id"], generated_at=now, types=types,
                         concerns=[concern_out(db, fx, c) for c in concerns], data_quality=quality,
                         disclaimer=fx["detection_ruleset"]["disclaimer"])

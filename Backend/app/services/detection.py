"""Proactive health detection (DET-1.0, contract 2.6.0).

Every ingested observation passes a data-quality gate before any rule runs:
  G-1  quality `poor`                                   -> `excluded_poor_quality`
  G-2  older than the type's stale limit at ingestion    -> `excluded_stale`
  G-3  no configured rule for the type                   -> `not_monitored`
  G-4  no active individual baseline                     -> `no_baseline`
Excluded readings never count towards a sustained change and never reset one.

For a reading that passes, rule DET-<type>-01 compares it with the active baseline: it deviates when the
difference reaches max(k x spread, minimum absolute change) in the configured direction.
  D-1  No concern open: `required_consecutive` passing readings in a row inside the window, all deviating in the
       same direction from the same baseline version, open a `monitoring_concern` (`concern_opened`). Fewer give
       `deviation_not_sustained`. A non-deviating reading gives `within_baseline`.
  D-2  Concern open, deviating reading: the same concern is updated (`concern_updated`). No second concern or case.
       Case evidence and an alert at most once per suppression window; the rest are counted as suppressed.
  D-3  Concern open, reading within baseline: counted (`within_baseline_concern_open`). A good-quality reading
       observed after the reassessment follow-up is due completes it (`reassessment_completed`). After a completed
       reassessment and `recovery_count` consecutive in-baseline readings the concern waits for human review
       (`concern_ready_for_review`). Nothing is ever closed or resolved automatically.
  D-4  Opening a concern joins the astronaut's open routine case or opens one (detected -> investigating), requests
       the configured assessment when the case has none pending, and schedules a reassessment follow-up.
These are configured demonstration rules. A deviation from a synthetic baseline is not a diagnosis.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import RULESET_VERSION
from ..db import utcnow
from ..errors import ApiError, not_found
from ..schemas.cases import ObservationCreate
from . import baselines as bl_svc
from . import cases as case_svc
from . import observations as obs_svc
from .audit import audit

EPS = 1e-9
OPEN = bl_svc.OPEN_CONCERN_STATES
NEXT_ACTION_CONCERN_ASSESS = ("A configured monitoring rule found a sustained change from your individual baseline. "
                              "Complete the requested demonstration assessment ({procedure_id}). This is not a "
                              "diagnosis.")
NEXT_ACTION_CONCERN_MONITOR = ("A configured monitoring rule found a sustained change from your individual baseline. "
                               "Keep wearing the sensor; a reassessment is scheduled. Contact the crew medical "
                               "officer if you are concerned. This is not a diagnosis.")
NEXT_ACTION_REVIEW = ("Readings are back within the individual baseline after the reassessment. A crew member must "
                      "review the monitoring concern; it is not closed automatically.")


def ruleset(fx: dict) -> dict:
    return fx["detection_ruleset"]


def rule_for(fx: dict, type_: str) -> dict | None:
    return next((r for r in ruleset(fx)["rules"] if r["type"] == type_), None)


def _direction(rule: dict, bl: m.HealthBaseline, value: float) -> tuple[str | None, float, float]:
    diff = value - bl.centre
    threshold = max(rule["k_spread"] * bl.spread, rule["min_abs_change"])
    if diff >= threshold - EPS and rule["direction"] in ("above", "either"):
        return "above", diff, threshold
    if -diff >= threshold - EPS and rule["direction"] in ("below", "either"):
        return "below", diff, threshold
    return None, diff, threshold


def open_concern(db: Session, astronaut_id: str, type_: str) -> m.MonitoringConcern | None:
    return bl_svc.freezing_concern(db, astronaut_id, type_)


def _outstanding_reassessment(db: Session, concern_id: str) -> m.FollowUpTask | None:
    return db.scalars(select(m.FollowUpTask).where(m.FollowUpTask.concern_id == concern_id,
                                                   m.FollowUpTask.status.in_(["scheduled", "due"]))
                      .order_by(m.FollowUpTask.created_at.desc())).first()


def latest_reassessment(db: Session, concern_id: str) -> m.FollowUpTask | None:
    return db.scalars(select(m.FollowUpTask).where(m.FollowUpTask.concern_id == concern_id)
                      .order_by(m.FollowUpTask.created_at.desc())).first()


def _schedule_reassessment(db: Session, case: m.MedicalCase, c: m.MonitoringConcern, rule: dict,
                           now: datetime) -> m.FollowUpTask:
    fu = m.FollowUpTask(follow_up_id=m.new_id("FU"), case_id=case.case_id, task_type="monitoring_reassessment",
                        title=f"Reassess {c.type} for monitoring concern {c.concern_id}",
                        due_at=now + timedelta(minutes=rule["reassessment_minutes"]), status="scheduled",
                        interrupt=case.priority == "urgent", created_at=now, concern_id=c.concern_id)
    db.add(fu)
    if case.follow_up_status in ("none", "completed"):
        case.follow_up_status = "scheduled"
    audit(db, "follow-up-manager", "follow_up.created", "follow_up_task", fu.follow_up_id, case.case_id,
          task_type=fu.task_type, due_at=fu.due_at.isoformat(), concern_id=c.concern_id, rule=rule["rule_id"])
    return fu


def _complete_follow_up(db: Session, case: m.MedicalCase, fu: m.FollowUpTask, obs: m.HealthObservation,
                        outcome: str, now: datetime) -> None:
    fu.status = "completed"
    fu.completed_at = now
    fu.completion_evidence_id = obs.observation_id
    audit(db, "follow-up-manager", "follow_up.completed", "follow_up_task", fu.follow_up_id, case.case_id,
          evidence_observation_id=obs.observation_id, outcome=outcome)
    others = db.scalars(select(m.FollowUpTask).where(m.FollowUpTask.case_id == case.case_id,
                                                     m.FollowUpTask.follow_up_id != fu.follow_up_id,
                                                     m.FollowUpTask.status.in_(["scheduled", "due"]))).all()
    case.follow_up_status = ("due" if any(o.status == "due" for o in others) else
                             "scheduled" if others else "completed")
    if case.state == "follow_up_due" and case.follow_up_status != "due":
        case_svc.transition(db, case, "monitoring", "follow-up-manager",
                            f"Reassessment {fu.follow_up_id} completed by observation {obs.observation_id}")


def _mark_due(db: Session, case: m.MedicalCase, fu: m.FollowUpTask | None, now: datetime) -> None:
    if fu is not None and fu.status == "scheduled" and fu.due_at <= now:
        fu.status = "due"
        case.follow_up_status = "due"
        audit(db, "follow-up-manager", "follow_up.due", "follow_up_task", fu.follow_up_id, case.case_id)


def _open_case(db: Session, astronaut_id: str, rule: dict, rs: str, now: datetime) -> m.MedicalCase:
    case = case_svc.open_case(db, astronaut_id, "routine")
    if case is not None:
        return case
    case = m.MedicalCase(case_id=m.new_id("CASE"), astronaut_id=astronaut_id, kind="routine", state="detected",
                         priority="routine", evidence=[], next_action=NEXT_ACTION_CONCERN_MONITOR,
                         follow_up_status="none", ruleset_version=RULESET_VERSION, created_at=now, updated_at=now)
    db.add(case)
    db.flush()
    audit(db, "detection-engine", "case.created", "medical_case", case.case_id, case.case_id, rule=rule["rule_id"],
          ruleset_version=rs, state="detected",
          note="Opened by a configured monitoring rule without a symptom report.")
    return case


def _open_concern(db: Session, fx: dict, obs: m.HealthObservation, rule: dict, bl: m.HealthBaseline,
                  evidence: list[m.HealthObservation], direction: str, now: datetime) -> m.MonitoringConcern:
    rs = ruleset(fx)["ruleset_version"]
    case = _open_case(db, obs.astronaut_id, rule, rs, now)
    c = m.MonitoringConcern(concern_id=m.new_id("CON"), astronaut_id=obs.astronaut_id, type=obs.type, unit=obs.unit,
                            rule_id=rule["rule_id"], ruleset_version=rs, baseline_id=bl.baseline_id,
                            baseline_version=bl.version, direction=direction, status="open", case_id=case.case_id,
                            opened_at=now, first_evidence_at=min(e.observed_at for e in evidence),
                            last_triggered_at=obs.observed_at, trigger_count=1, suppressed_count=0,
                            evidence_observation_ids=[e.observation_id for e in evidence], consecutive_within=0,
                            reassessment_passed=False, last_case_update_at=now, updated_at=now)
    db.add(c)
    db.flush()
    values = ", ".join(f"{e.value:g}" for e in evidence)
    case_svc.add_evidence(case, "monitoring_concern", c.concern_id,
                          f"{rule['title']} ({rule['rule_id']}): {len(evidence)} consecutive readings ({values} "
                          f"{obs.unit}) {direction} baseline v{bl.version} (centre {bl.centre:g} {obs.unit}). "
                          "Configured demonstration rule; not a diagnosis.")
    audit(db, "detection-engine", "monitoring_concern.opened", "monitoring_concern", c.concern_id, case.case_id,
          rule=rule["rule_id"], ruleset_version=rs, baseline_id=bl.baseline_id, baseline_version=bl.version,
          direction=direction, evidence_observation_ids=c.evidence_observation_ids,
          disclaimer=ruleset(fx)["disclaimer"])
    if case.state == "detected":
        case_svc.transition(db, case, "investigating", "detection-engine",
                            f"{rule['rule_id']}: sustained change from individual baseline opens investigation")
    req = case.requested_assessment
    pending = bool(req) and req.get("status") == "requested"
    assess = rule.get("assessment")
    if assess and not pending and case_svc.can_transition(case.state, "awaiting_assessment"):
        case.requested_assessment = {"assessment_id": None, "capability": assess["capability"],
                                     "procedure_id": assess["procedure_id"], "status": "requested",
                                     "configured_reason": f"{assess['reason']} Requested by {rule['rule_id']}."}
        case_svc.transition(db, case, "awaiting_assessment", "detection-engine",
                            f"{rule['rule_id']}: configured assessment {assess['procedure_id']} requested "
                            "(demonstration configuration)")
        case_svc.set_next_action(case, NEXT_ACTION_CONCERN_ASSESS.format(procedure_id=assess["procedure_id"]))
    elif case.state == "investigating":
        case_svc.transition(db, case, "monitoring", "detection-engine",
                            f"{rule['rule_id']}: no configured assessment; monitoring with scheduled reassessment")
        case_svc.set_next_action(case, NEXT_ACTION_CONCERN_MONITOR)
    _schedule_reassessment(db, case, c, rule, now)
    case.updated_at = now
    return c


def _result(fx: dict, rule: dict | None, **kw) -> dict:
    base = {"ruleset_version": ruleset(fx)["ruleset_version"], "rule_id": rule["rule_id"] if rule else None,
            "baseline_id": None, "baseline_version": None, "baseline_centre": None, "baseline_spread": None,
            "threshold": None, "difference": None, "deviation_direction": None, "deviating_count": 0,
            "required_count": rule["required_consecutive"] if rule else None, "concern_id": None, "case_id": None,
            "alert_raised": False, "alert_suppressed": False, "disclaimer": ruleset(fx)["disclaimer"],
            "evaluated_at": utcnow().isoformat()}
    base.update(kw)
    return base


def evaluate(db: Session, fx: dict, obs: m.HealthObservation, now: datetime | None = None) -> dict:
    now = now or utcnow()
    spec = obs_svc.catalogue(fx)[obs.type]
    rule = rule_for(fx, obs.type)
    if obs.quality == "poor":
        return _result(fx, rule, gate="excluded_poor_quality", outcome="excluded_poor_quality",
                       explanation="Reading marked poor quality by its source. It is stored but not used for "
                                   "detection, and no health conclusion is drawn from it.")
    if now - obs.observed_at > timedelta(minutes=spec["stale_after_minutes"]):
        return _result(fx, rule, gate="excluded_stale", outcome="excluded_stale",
                       explanation=f"Reading was already older than the {spec['stale_after_minutes']}-minute "
                                   "freshness limit when it arrived. It is stored but not used for detection.")
    if rule is None:
        return _result(fx, None, gate="passed", outcome="not_monitored",
                       explanation=f"No detection rule is configured for '{obs.type}'.")
    bl = bl_svc.active(db, obs.astronaut_id, obs.type)
    if bl is None:
        return _result(fx, rule, gate="passed", outcome="no_baseline",
                       explanation="No individual baseline exists yet for this measurement, so no comparison is "
                                   "made. Nothing is inferred.")
    direction, diff, threshold = _direction(rule, bl, obs.value)
    ref = dict(baseline_id=bl.baseline_id, baseline_version=bl.version, baseline_centre=bl.centre,
               baseline_spread=bl.spread, threshold=round(threshold, 3), difference=round(diff, 3),
               deviation_direction=direction)
    # Store the gate result first so this reading is part of its own sustained-change window.
    obs.detection = {"gate": "passed", "deviation_direction": direction, "baseline_id": bl.baseline_id}
    db.flush()
    c = open_concern(db, obs.astronaut_id, obs.type)
    if c is not None:
        return _with_open_concern(db, fx, obs, rule, c, direction, ref, now)
    if direction is None:
        return _result(fx, rule, gate="passed", outcome="within_baseline", **ref,
                       explanation=f"Within the configured range of baseline v{bl.version} "
                                   f"({bl.centre:g} {obs.unit}, threshold {threshold:g}).")
    start = obs.observed_at - timedelta(minutes=rule["window_minutes"])
    window = db.scalars(select(m.HealthObservation).where(
        m.HealthObservation.astronaut_id == obs.astronaut_id, m.HealthObservation.type == obs.type,
        m.HealthObservation.observed_at >= start, m.HealthObservation.observed_at <= obs.observed_at)
        .order_by(m.HealthObservation.observed_at.desc(), m.HealthObservation.recorded_at.desc())).all()
    passing = [o for o in window if (o.detection or {}).get("gate") == "passed"]
    run = []
    for o in passing:
        if o.detection.get("deviation_direction") != direction or o.detection.get("baseline_id") != bl.baseline_id:
            break
        run.append(o)
    need = rule["required_consecutive"]
    if len(run) < need:
        return _result(fx, rule, gate="passed", outcome="deviation_not_sustained", deviating_count=len(run), **ref,
                       explanation=f"{len(run)} of {need} consecutive readings {direction} the configured range "
                                   f"within {rule['window_minutes']} minutes. No concern yet.")
    evidence = list(reversed(run[:need]))
    c = _open_concern(db, fx, obs, rule, bl, evidence, direction, now)
    return _result(fx, rule, gate="passed", outcome="concern_opened", deviating_count=need, concern_id=c.concern_id,
                   case_id=c.case_id, alert_raised=True, **ref,
                   explanation=f"{need} consecutive readings {direction} baseline v{bl.version} within "
                               f"{rule['window_minutes']} minutes: monitoring concern {c.concern_id} opened and "
                               "an investigation started. Configured demonstration rule; not a diagnosis.")


def _with_open_concern(db: Session, fx: dict, obs: m.HealthObservation, rule: dict, c: m.MonitoringConcern,
                       direction: str | None, ref: dict, now: datetime) -> dict:
    case = db.get(m.MedicalCase, c.case_id)
    fu = _outstanding_reassessment(db, c.concern_id)
    _mark_due(db, case, fu, now)
    reassessed = fu is not None and obs.observed_at >= fu.due_at and obs.quality == "good"
    common = dict(gate="passed", concern_id=c.concern_id, case_id=c.case_id, **ref)
    c.updated_at = now
    if direction is not None:  # D-2 equivalent trigger
        c.trigger_count += 1
        c.evidence_observation_ids = [*c.evidence_observation_ids, obs.observation_id]
        c.last_triggered_at = obs.observed_at
        c.consecutive_within = 0
        c.reassessment_passed = False
        if c.status == "awaiting_review":
            c.status = "open"
            audit(db, "detection-engine", "monitoring_concern.reopened", "monitoring_concern", c.concern_id,
                  case.case_id, rule=rule["rule_id"], observation_id=obs.observation_id)
        if reassessed:
            _complete_follow_up(db, case, fu, obs, "deviation_persists", now)
            fu = None
        if fu is None:
            _schedule_reassessment(db, case, c, rule, now)
        window = timedelta(minutes=rule["suppression_minutes"])
        suppressed = c.last_case_update_at is not None and now - c.last_case_update_at < window
        if suppressed:
            c.suppressed_count += 1
            audit(db, "detection-engine", "monitoring_concern.alert_suppressed", "monitoring_concern", c.concern_id,
                  case.case_id, rule=rule["rule_id"], observation_id=obs.observation_id,
                  suppression_minutes=rule["suppression_minutes"])
        else:
            c.last_case_update_at = now
            case_svc.add_evidence(case, "monitoring_concern", c.concern_id,
                                  f"{rule['rule_id']}: equivalent reading {obs.value:g} {obs.unit} {direction} "
                                  f"baseline; concern {c.concern_id} updated (trigger {c.trigger_count}).")
            audit(db, "detection-engine", "monitoring_concern.updated", "monitoring_concern", c.concern_id,
                  case.case_id, rule=rule["rule_id"], observation_id=obs.observation_id,
                  trigger_count=c.trigger_count)
        case.updated_at = now
        return _result(fx, rule, outcome="concern_updated", deviating_count=1, alert_raised=not suppressed,
                       alert_suppressed=suppressed, **common,
                       explanation=(f"Equivalent change while concern {c.concern_id} is open: the existing concern "
                                    "and case were updated; no new concern or case was created."
                                    + (" Alert suppressed (already raised within "
                                       f"{rule['suppression_minutes']} minutes)." if suppressed else "")))
    # D-3 back within baseline
    c.consecutive_within += 1
    outcome = "within_baseline_concern_open"
    if reassessed:
        _complete_follow_up(db, case, fu, obs, "within_baseline", now)
        c.reassessment_passed = True
        outcome = "reassessment_completed"
    explanation = (f"Within baseline ({c.consecutive_within} of {rule['recovery_count']} needed in a row"
                   f"{'' if c.reassessment_passed else ', reassessment not yet completed'}). The concern stays "
                   "open; it is never closed automatically.")
    if c.status == "open" and c.reassessment_passed and c.consecutive_within >= rule["recovery_count"]:
        c.status = "awaiting_review"
        outcome = "concern_ready_for_review"
        audit(db, "detection-engine", "monitoring_concern.ready_for_review", "monitoring_concern", c.concern_id,
              case.case_id, rule=rule["rule_id"], consecutive_within=c.consecutive_within)
        case_svc.add_evidence(case, "monitoring_concern", c.concern_id,
                              f"Concern {c.concern_id}: reassessment completed and {c.consecutive_within} readings "
                              "back within baseline; awaiting human review.")
        case_svc.set_next_action(case, NEXT_ACTION_REVIEW)
        explanation = ("Reassessment completed and readings are back within baseline. The concern now waits for a "
                       "crew member's review; it is not closed automatically.")
    case.updated_at = now
    return _result(fx, rule, outcome=outcome, **common, explanation=explanation)


def ingest(db: Session, fx: dict, body: ObservationCreate) -> tuple[m.HealthObservation, bool]:
    """Validate, store and evaluate one observation. Duplicates return the stored record and are not re-evaluated."""
    if db.get(m.Astronaut, body.astronaut_id) is None:
        raise not_found("Astronaut", body.astronaut_id)
    obs_svc.validate(fx, body)
    existing = db.scalars(select(m.HealthObservation).where(
        m.HealthObservation.astronaut_id == body.astronaut_id, m.HealthObservation.type == body.type,
        m.HealthObservation.observed_at == body.observed_at, m.HealthObservation.value == body.value,
        m.HealthObservation.source == body.source)).first()
    if existing is not None:
        return existing, True
    now = utcnow()
    obs = m.HealthObservation(observation_id=m.new_id("OBS"), astronaut_id=body.astronaut_id, type=body.type,
                              value=body.value, unit=body.unit, observed_at=body.observed_at, recorded_at=now,
                              source=body.source, quality=body.quality, simulated=True)
    db.add(obs)
    db.flush()
    audit(db, body.astronaut_id, "observation.recorded", "health_observation", obs.observation_id,
          type=body.type, source=body.source)
    result = evaluate(db, fx, obs, now)
    obs.detection = result
    if result["gate"] != "passed":
        audit(db, "detection-engine", "detection.excluded", "health_observation", obs.observation_id,
              reason=result["gate"], type=obs.type)
    db.commit()
    return obs, False


def review(db: Session, fx: dict, concern_id: str, actor_id: str, decision: str, note: str) -> m.MonitoringConcern:
    c = get_concern(db, concern_id)
    if db.get(m.Astronaut, actor_id) is None:
        raise not_found("Astronaut", actor_id)
    if c.status == "closed":
        raise ApiError(409, "CONCERN_CLOSED", "This monitoring concern is already closed.", {"concern_id": concern_id})
    rule = rule_for(fx, c.type)
    case = db.get(m.MedicalCase, c.case_id)
    now = utcnow()
    if decision == "close":
        if c.status != "awaiting_review":
            raise ApiError(409, "CONCERN_NOT_READY_FOR_REVIEW",
                           "The concern can be closed only after a completed reassessment and readings back within "
                           "baseline.", {"status": c.status, "reassessment_passed": c.reassessment_passed,
                                         "consecutive_within_baseline": c.consecutive_within,
                                         "recovery_count": rule["recovery_count"] if rule else None})
        c.status, c.closed_at, c.closed_by, c.review_note = "closed", now, actor_id, note
        case_svc.add_evidence(case, "monitoring_concern", c.concern_id,
                              f"Concern {c.concern_id} closed by {actor_id} after review. The case is not resolved by "
                              "this.")
        audit(db, actor_id, "monitoring_concern.closed", "monitoring_concern", c.concern_id, case.case_id, note=note,
              detail="Closing a monitoring concern does not resolve the case and unfreezes the baseline.")
        if not db.scalars(select(m.MonitoringConcern).where(m.MonitoringConcern.case_id == case.case_id,
                                                            m.MonitoringConcern.status.in_(OPEN))).first():
            case_svc.set_next_action(case, "Monitoring concern closed after review. The case stays open until the "
                                           "crew medical officer resolves it.")
    else:
        c.status, c.review_note = "open", note
        c.consecutive_within, c.reassessment_passed = 0, False
        if _outstanding_reassessment(db, c.concern_id) is None and rule:
            _schedule_reassessment(db, case, c, rule, now)
        audit(db, actor_id, "monitoring_concern.continue_monitoring", "monitoring_concern", c.concern_id,
              case.case_id, note=note)
    c.updated_at = case.updated_at = now
    db.commit()
    return c


def get_concern(db: Session, concern_id: str) -> m.MonitoringConcern:
    c = db.get(m.MonitoringConcern, concern_id)
    if c is None:
        raise not_found("Monitoring concern", concern_id)
    return c

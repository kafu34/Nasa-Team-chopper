"""Simulated zone-level positioning and equipment routing.

Location method (LOC-P0-1.1; 1.1 adds step 5)
  1. Reject observations from unknown or disabled anchors, stale (> 30 s) or future (> 5 s) timestamps.
  2. Score each zone by its strongest valid RSSI.
  3. confidence = min(0.95, 0.5 + margin_dB / 30), margin = best minus runner-up zone (15 dB if only one zone).
  4. Hysteresis: if a previous BLE estimate is < 60 s old, the margin is < 3 dB and the previous zone is still a
     candidate, keep the previous zone (source = ble_simulated_smoothed).
  5. Unobserved zones: a zone none of whose enabled anchors produced a valid observation cannot be ruled out.
     If such a zone is next to the chosen zone (any connection, open or closed), confidence is capped at 0.5 and the
     zone is listed in `unobserved_zone_ids`. Found with the movement simulator (SIM-MISSING-ANCHOR): without this
     rule a failed laboratory anchor produced a wrong crew-quarters estimate at 0.63-0.67 confidence.
  No distance is ever computed from RSSI.

Equipment method (EQ-P0-1.0)
  Breadth-first search over accessible zone connections; candidates must match capability, have readiness
  'verified_ready' checked within 24 h, have every required supply, and be reachable. Shortest route wins;
  ties break by equipment_id. Wireless signal strength is never used to rank equipment.
"""
from __future__ import annotations

from collections import deque
from datetime import timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import utcnow
from ..errors import ApiError, not_found
from ..schemas.spatial import (EquipmentRecommendation, ExcludedEquipment, LocationEstimateOut,
                               LocationEstimateRequest, LocationLatestOut, RejectedObservation, ZoneScore)
from . import habitat
from .audit import audit

STALE_AFTER = timedelta(seconds=30)
FUTURE_TOLERANCE = timedelta(seconds=5)
HYSTERESIS_WINDOW = timedelta(seconds=60)
MANUAL_STALE_AFTER = timedelta(minutes=15)
HYSTERESIS_MARGIN_DB = 3
READINESS_MAX_AGE = timedelta(hours=24)


def _require_astronaut(db: Session, astronaut_id: str) -> None:
    if db.get(m.Astronaut, astronaut_id) is None:
        raise not_found("Astronaut", astronaut_id)


def _map_version(db: Session) -> Optional[str]:
    hab = db.scalars(select(m.Habitat)).first()
    return hab.map_version if hab is not None else None


def _store(db: Session, out: LocationEstimateOut) -> LocationEstimateOut:
    out.map_version = _map_version(db)
    db.add(m.LocationEstimate(estimate_id=out.estimate_id, astronaut_id=out.astronaut_id, zone_id=out.zone_id,
                              confidence=out.confidence, source=out.source, observed_at=out.observed_at,
                              estimated_at=out.estimated_at,
                              details=out.model_dump(mode="json", include={"used_anchor_ids", "rejected",
                                                                           "zone_scores", "method",
                                                                           "explanation",
                                                                           "unobserved_zone_ids"})))
    audit(db, "location-engine", "location.estimated", "location_estimate", out.estimate_id,
          zone_id=out.zone_id, confidence=out.confidence, source=out.source)
    db.commit()
    return out


def estimate(db: Session, body: LocationEstimateRequest) -> LocationEstimateOut:
    _require_astronaut(db, body.astronaut_id)
    now = utcnow()
    anchors = {a.anchor_id: a for a in db.scalars(select(m.WirelessAnchor))}
    rejected: list[RejectedObservation] = []
    best: dict[str, int] = {}
    counts: dict[str, int] = {}
    used: list[str] = []
    newest = None
    for o in body.observations:
        a = anchors.get(o.anchor_id)
        if a is None:
            rejected.append(RejectedObservation(anchor_id=o.anchor_id, reason="unknown_anchor"))
            continue
        if not a.enabled:
            rejected.append(RejectedObservation(anchor_id=o.anchor_id, reason="disabled_anchor"))
            continue
        if o.observed_at > now + FUTURE_TOLERANCE:
            rejected.append(RejectedObservation(anchor_id=o.anchor_id, reason="future_timestamp"))
            continue
        if now - o.observed_at > STALE_AFTER:
            rejected.append(RejectedObservation(anchor_id=o.anchor_id, reason="stale_signal"))
            continue
        used.append(o.anchor_id)
        best[a.zone_id] = max(best.get(a.zone_id, -999), o.rssi_dbm)
        counts[a.zone_id] = counts.get(a.zone_id, 0) + 1
        newest = o.observed_at if newest is None or o.observed_at > newest else newest

    scores = sorted((ZoneScore(zone_id=z, best_rssi_dbm=r, anchor_count=counts[z]) for z, r in best.items()),
                    key=lambda s: (-s.best_rssi_dbm, s.zone_id))
    base = dict(estimate_id=m.new_id("LOC"), astronaut_id=body.astronaut_id, estimated_at=now,
                method="LOC-P0-1.1 strongest-anchor-per-zone with margin confidence, hysteresis and "
                       "unobserved-zone cap",
                used_anchor_ids=used, rejected=rejected, zone_scores=scores)
    if not scores:
        return _store(db, LocationEstimateOut(
            **base, zone_id=None, confidence=0.0, source="unavailable", observed_at=None,
            explanation="No valid trusted, fresh signals. Location unavailable; confirm the zone manually if needed."))

    margin = scores[0].best_rssi_dbm - scores[1].best_rssi_dbm if len(scores) > 1 else 15
    confidence = round(min(0.95, 0.5 + margin / 30), 3)
    zone, source = scores[0].zone_id, "ble_simulated"
    explanation = f"Strongest trusted anchor zone is {zone} with a {margin} dB margin over the next zone."
    if margin < HYSTERESIS_MARGIN_DB:
        prev = db.scalars(select(m.LocationEstimate)
                          .where(m.LocationEstimate.astronaut_id == body.astronaut_id,
                                 m.LocationEstimate.source.in_(["ble_simulated", "ble_simulated_smoothed", "manual"]),
                                 m.LocationEstimate.estimated_at >= now - HYSTERESIS_WINDOW)
                          .order_by(m.LocationEstimate.estimated_at.desc())).first()
        if prev is not None and prev.zone_id in best and prev.zone_id != zone:
            zone, source = prev.zone_id, "ble_simulated_smoothed"
            explanation = (f"Conflicting signals ({margin} dB margin). Kept the recent estimate {zone} "
                           "to avoid zone flicker.")
        else:
            explanation = f"Conflicting signals ({margin} dB margin); low confidence in {zone}."
    unobserved = _unobserved_neighbours(db, zone, set(best))
    if unobserved:
        confidence = min(confidence, UNOBSERVED_CAP)
        explanation += (f" No anchor in {', '.join(unobserved)} reported, so the person could be there; "
                        f"confidence capped at {UNOBSERVED_CAP}.")
    return _store(db, LocationEstimateOut(**base, zone_id=zone, confidence=confidence, source=source,
                                          observed_at=newest, explanation=explanation,
                                          unobserved_zone_ids=unobserved))


UNOBSERVED_CAP = 0.5


def _unobserved_neighbours(db: Session, zone: str, observed: set[str]) -> list[str]:
    neighbours = set()
    for c in db.scalars(select(m.ZoneConnection)):
        if c.from_zone_id == zone:
            neighbours.add(c.to_zone_id)
        elif c.to_zone_id == zone:
            neighbours.add(c.from_zone_id)
    return sorted(z for z in neighbours if z not in observed)


def confirm(db: Session, astronaut_id: str, zone_id: str, confirmed_by: str) -> LocationEstimateOut:
    _require_astronaut(db, astronaut_id)
    _require_astronaut(db, confirmed_by)
    if db.get(m.Zone, zone_id) is None:
        raise not_found("Zone", zone_id)
    now = utcnow()
    return _store(db, LocationEstimateOut(
        estimate_id=m.new_id("LOC"), astronaut_id=astronaut_id, zone_id=zone_id, confidence=1.0, source="manual",
        observed_at=now, estimated_at=now, method="manual confirmation", used_anchor_ids=[], rejected=[],
        zone_scores=[], explanation=f"Zone confirmed manually by {confirmed_by}."))


def latest(db: Session, astronaut_id: str) -> LocationLatestOut:
    """Newest stored estimate with an honest freshness label. Old observations are never shown as current."""
    _require_astronaut(db, astronaut_id)
    row = db.scalars(select(m.LocationEstimate).where(m.LocationEstimate.astronaut_id == astronaut_id)
                     .order_by(m.LocationEstimate.estimated_at.desc())).first()
    if row is None:
        return LocationLatestOut(astronaut_id=astronaut_id, display_mode="unavailable", estimate=None,
                                 age_seconds=None, stale_after_seconds=None, label="No location estimate yet.")
    d = row.details or {}
    est = LocationEstimateOut(
        estimate_id=row.estimate_id, astronaut_id=row.astronaut_id, zone_id=row.zone_id, confidence=row.confidence,
        source=row.source, observed_at=row.observed_at, estimated_at=row.estimated_at,
        method=d.get("method", "unknown"), used_anchor_ids=d.get("used_anchor_ids", []),
        rejected=d.get("rejected", []), zone_scores=d.get("zone_scores", []),
        explanation=d.get("explanation", "Stored estimate."), map_version=_map_version(db),
        unobserved_zone_ids=d.get("unobserved_zone_ids", []))
    if row.zone_id is None:
        return LocationLatestOut(astronaut_id=astronaut_id, display_mode="unavailable", estimate=est,
                                 age_seconds=None, stale_after_seconds=None,
                                 label="Location unavailable at the last estimate.")
    limit = MANUAL_STALE_AFTER if row.source == "manual" else STALE_AFTER
    age = (utcnow() - (row.observed_at or row.estimated_at)).total_seconds()
    if age > limit.total_seconds():
        est.display_mode = "stale"
        label = f"Last known zone {row.zone_id}, {int(age)} s old. Not a current position."
    else:
        label = f"Current zone estimate {row.zone_id} ({row.source}, confidence {row.confidence})."
    return LocationLatestOut(astronaut_id=astronaut_id, display_mode=est.display_mode, estimate=est,
                             age_seconds=round(age, 1), stale_after_seconds=int(limit.total_seconds()), label=label)


def accessible_routes(db: Session, start: str) -> dict[str, list[str]]:
    """BFS over accessible connections. Returns zone_id -> route (inclusive)."""
    adj: dict[str, list[str]] = {}
    for c in db.scalars(select(m.ZoneConnection).where(m.ZoneConnection.accessible.is_(True))):
        adj.setdefault(c.from_zone_id, []).append(c.to_zone_id)
        adj.setdefault(c.to_zone_id, []).append(c.from_zone_id)
    routes = {start: [start]}
    q = deque([start])
    while q:
        z = q.popleft()
        for n in sorted(adj.get(z, [])):
            if n not in routes:
                routes[n] = routes[z] + [n]
                q.append(n)
    return routes


UNCERTAIN_BELOW = 0.7
CANDIDATE_WITHIN_DB = 6


def _resolve_start(db: Session, body) -> dict:
    if body.zone_id is not None:
        if body.astronaut_id is not None:
            _require_astronaut(db, body.astronaut_id)
        return {"zone_id": body.zone_id, "start_basis": "request_zone", "estimate": None}
    if body.astronaut_id is None:
        raise ApiError(422, "START_REQUIRED", "Send zone_id, or astronaut_id to start from their latest estimate.", {})
    lat = latest(db, body.astronaut_id)
    if lat.display_mode in ("stale", "unavailable") or lat.estimate is None:
        raise ApiError(409, "LOCATION_UNAVAILABLE", f"No current location for {body.astronaut_id} "
                       f"({lat.display_mode}). Confirm the zone manually or send zone_id.",
                       {"astronaut_id": body.astronaut_id, "display_mode": lat.display_mode, "label": lat.label})
    return {"zone_id": lat.estimate.zone_id, "start_basis": "latest_estimate", "estimate": lat.estimate}


def _uncertainty(db: Session, est, target_zone: str):
    if est is None or est.confidence >= UNCERTAIN_BELOW or not est.zone_scores:
        return None
    best = est.zone_scores[0].best_rssi_dbm
    cands = []
    zones = [(s.zone_id, s.best_rssi_dbm) for s in est.zone_scores if best - s.best_rssi_dbm <= CANDIDATE_WITHIN_DB]
    zones += [(z, None) for z in est.unobserved_zone_ids]
    for zid, rssi in zones:
        route = accessible_routes(db, zid).get(target_zone)
        cands.append({"zone_id": zid, "best_rssi_dbm": rssi, "route_hops": len(route) - 1 if route else None})
    hops = [c["route_hops"] for c in cands if c["route_hops"] is not None]
    return {"confidence": est.confidence, "candidates": cands,
            "hop_spread": (max(hops) - min(hops)) if hops else None}


def get_recommendation(db: Session, recommendation_id: str) -> EquipmentRecommendation:
    rec = db.get(m.EquipmentRecommendationRecord, recommendation_id)
    if rec is None:
        raise not_found("Equipment recommendation", recommendation_id)
    return EquipmentRecommendation(**{**rec.response, "status": rec.status,
                                      "invalidated_reason": rec.invalidated_reason})


def recommend(db: Session, fx: dict, body) -> EquipmentRecommendation:
    case_id, capability = body.case_id, body.capability
    if db.get(m.MedicalCase, case_id) is None:
        raise not_found("Case", case_id)
    start = _resolve_start(db, body)
    zone_id = start["zone_id"]
    if db.get(m.Zone, zone_id) is None:
        raise not_found("Zone", zone_id)
    now = utcnow()
    routes = accessible_routes(db, zone_id)
    devices = db.scalars(select(m.Equipment).where(m.Equipment.capability == capability)
                         .order_by(m.Equipment.equipment_id)).all()
    if not devices:
        raise ApiError(404, "NO_SUITABLE_EQUIPMENT", f"No equipment with capability '{capability}' is registered.",
                       {"capability": capability, "excluded": []})
    candidates, excluded = [], []
    for d in devices:
        reasons = []
        if d.readiness != "verified_ready":
            reasons.append(f"readiness_{d.readiness}")
        elif d.readiness_verified_at is None or now - d.readiness_verified_at > READINESS_MAX_AGE:
            reasons.append("readiness_check_stale")
        missing = [s for s in d.required_supplies if not d.supplies.get(s, False)]
        if missing:
            reasons.append("missing_supplies:" + ",".join(missing))
        if d.zone_id not in routes:
            reasons.append("zone_not_accessible")
        if reasons:
            excluded.append(ExcludedEquipment(equipment_id=d.equipment_id, zone_id=d.zone_id, reasons=reasons))
        else:
            candidates.append(d)
    if not candidates:
        raise ApiError(404, "NO_SUITABLE_EQUIPMENT", "No ready, supplied and accessible equipment was found.",
                       {"capability": capability, "excluded": [e.model_dump() for e in excluded]})
    pick = min(candidates, key=lambda d: (len(routes[d.zone_id]), d.equipment_id))
    route = routes[pick.zone_id]
    procedure_id = pick.compatible_procedure_ids[0] if pick.compatible_procedure_ids else None
    geo = habitat.route_geometry(db, fx, route, pick)
    est = start["estimate"]
    hab = db.get(m.Habitat, fx["habitat"]["habitat_id"])
    out = EquipmentRecommendation(
        recommendation_id=m.new_id("REC"), habitat_state_version=hab.state_version or 1,
        start_basis=start["start_basis"], start_role=body.start_role, start_astronaut_id=body.astronaut_id,
        start_estimate_id=est.estimate_id if est else None, start_confidence=est.confidence if est else None,
        start_uncertainty=_uncertainty(db, est, pick.zone_id),
        map_version=geo["geometry"]["map_version"], coordinate_frame_id=geo["geometry"]["frame_id"],
        start_reference=geo["start_reference"], route_hatch_ids=geo["hatch_ids"], route_geometry=geo["geometry"],
        equipment_id=pick.equipment_id, device_model=pick.device_model, zone_id=pick.zone_id,
        readiness=pick.readiness, readiness_verified_at=pick.readiness_verified_at, route_zone_ids=route,
        route_hops=len(route) - 1, procedure_id=procedure_id, capability=capability, supplies=pick.supplies,
        excluded=excluded,
        explanation=(f"{pick.equipment_id} is the nearest accessible device with verified readiness and supplies "
                     f"({len(route) - 1} zone hop(s)). {len(excluded)} other device(s) excluded."))
    audit(db, "equipment-engine", "equipment.recommended", "equipment", pick.equipment_id, case_id,
          from_zone_id=zone_id, route_zone_ids=route, route_hatch_ids=geo["hatch_ids"],
          map_version=geo["geometry"]["map_version"], excluded=[e.equipment_id for e in excluded],
          recommendation_id=out.recommendation_id, start_basis=out.start_basis, start_role=out.start_role)
    db.add(m.EquipmentRecommendationRecord(
        recommendation_id=out.recommendation_id, case_id=case_id, equipment_id=pick.equipment_id,
        start_zone_id=zone_id, route_zone_ids=route, route_hatch_ids=geo["hatch_ids"],
        habitat_state_version=out.habitat_state_version, status="active", created_at=now,
        response=out.model_dump(mode="json")))
    db.commit()
    return out

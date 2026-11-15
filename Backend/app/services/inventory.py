"""Equipment inventory updates (plan step 41, contract 2.11.0).

Rules
-----
I-1  `device_reasons` is the single definition of whether a device can be used. The equipment recommendation and
     the inventory list both use it (plus zone accessibility, which depends on the route start).
I-2  Only crew roles may update a device (`inventory.update`). Setting `verified_ready` counts as a fresh check.
     Unknown supply keys and unknown zones are refused (422).
I-3  Every change is audited with its before and after values. It invalidates the active recommendations for the
     device and for its capability, because a better or a worse device may now apply. In-progress sessions bound
     to the device are listed; they are not cancelled.
Device records are fictional demonstration data; no hardware is queried.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import utcnow
from ..errors import ApiError, not_found
from . import access
from .audit import audit

READINESS_MAX_AGE = timedelta(hours=24)


def device_reasons(d: m.Equipment, now: datetime) -> list[str]:
    reasons = []
    if d.readiness != "verified_ready":
        reasons.append(f"readiness_{d.readiness}")
    elif d.readiness_verified_at is None or now - d.readiness_verified_at > READINESS_MAX_AGE:
        reasons.append("readiness_check_stale")
    missing = [s for s in d.required_supplies if not (d.supplies or {}).get(s, False)]
    if missing:
        reasons.append("missing_supplies:" + ",".join(missing))
    return reasons


def listing(db: Session) -> list[tuple[m.Equipment, list[str]]]:
    now = utcnow()
    return [(d, device_reasons(d, now)) for d in db.scalars(select(m.Equipment).order_by(m.Equipment.equipment_id))]


def update(db: Session, fx: dict, equipment_id: str, actor_id: str, readiness: str | None,
           supplies: dict[str, bool] | None, zone_id: str | None, note: str) -> dict:
    d = db.get(m.Equipment, equipment_id)
    if d is None:
        raise not_found("Equipment", equipment_id)
    access.require(db, fx, actor_id, "inventory.update", "equipment", equipment_id)
    if supplies:
        unknown = sorted(set(supplies) - set(d.required_supplies) - set(d.supplies or {}))
        if unknown:
            raise ApiError(422, "UNKNOWN_SUPPLY", "These supply items are not tracked for this device.",
                           {"unknown": unknown, "tracked": sorted(set(d.required_supplies) | set(d.supplies or {}))})
    if zone_id is not None and db.get(m.Zone, zone_id) is None:
        raise ApiError(422, "UNKNOWN_ZONE", f"Zone '{zone_id}' is not part of the habitat.", {"zone_id": zone_id})
    now = utcnow()
    before = {"readiness": d.readiness, "supplies": dict(d.supplies or {}), "zone_id": d.zone_id,
              "usable": not device_reasons(d, now)}
    if readiness is not None:
        d.readiness = readiness
        if readiness == "verified_ready":
            d.readiness_verified_at = now
    if supplies:
        d.supplies = {**(d.supplies or {}), **supplies}
    if zone_id is not None:
        d.zone_id = zone_id
    after = {"readiness": d.readiness, "supplies": dict(d.supplies or {}), "zone_id": d.zone_id,
             "usable": not device_reasons(d, now)}
    changed = before != after or readiness == "verified_ready"
    invalid, sessions = [], []
    if changed:
        d.status_updated_at = now
        for rec in db.scalars(select(m.EquipmentRecommendationRecord).where(
                m.EquipmentRecommendationRecord.status == "active")):
            rec_dev = db.get(m.Equipment, rec.equipment_id)
            if rec.equipment_id == equipment_id or (rec_dev is not None and rec_dev.capability == d.capability):
                rec.status, rec.invalidated_at = "invalidated", now
                rec.invalidated_reason = (f"Equipment {equipment_id} status changed ({note}); request a new "
                                          "recommendation.")
                invalid.append(rec.recommendation_id)
                audit(db, "equipment-engine", "equipment_recommendation.invalidated", "equipment_recommendation",
                      rec.recommendation_id, rec.case_id, reason=rec.invalidated_reason)
        sessions = list(db.scalars(select(m.ProcedureSession.session_id).where(
            m.ProcedureSession.equipment_id == equipment_id, m.ProcedureSession.status == "in_progress")))
        audit(db, actor_id, "equipment.status_changed", "equipment", equipment_id, None, before=before,
              after=after, note=note, invalidated=invalid, affected_session_ids=sessions)
    db.commit()
    return {"equipment": d, "usable": after["usable"], "unusable_reasons": device_reasons(d, now), "changed": changed,
            "before": before, "invalidated_recommendation_ids": invalid, "affected_session_ids": sessions}

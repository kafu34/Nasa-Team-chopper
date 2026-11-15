"""Repeatable movement simulation (SIM-RSSI-1.0) for testing zone localisation.

Three separate layers, never mixed:
  1. Ground truth: points interpolated along fixture waypoints, and the compartment (or passage) each lies in.
  2. Generated observations: simulated BLE RSSI from every registered anchor (log-distance path loss, a fixed
     loss per wall, seeded Gaussian noise). Failed anchors send nothing. This is not a calibrated radio model.
  3. Backend estimate: the observations go through the normal `spatial.estimate` engine (LOC-P0-1.1) and are
     stored like any other estimate.

User-facing endpoints (map, latest location, equipment) only ever see layer 3. Ground truth is returned only in
the `evaluation` block of the simulation endpoint and is never stored.
"""
from __future__ import annotations

import math
import random
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import utcnow
from ..errors import ApiError, not_found
from ..schemas.spatial import BleObservation, LocationEstimateRequest
from . import spatial
from .habitat import _inside, _passages


def _scenario(fx: dict, scenario_id: str) -> dict:
    sc = next((s for s in fx.get("movement_scenarios", []) if s["scenario_id"] == scenario_id), None)
    if sc is None:
        raise ApiError(404, "NOT_FOUND", f"Movement scenario '{scenario_id}' was not found.",
                       {"scenario_ids": [s["scenario_id"] for s in fx.get("movement_scenarios", [])]})
    return sc


def _path(sc: dict) -> list[list[float]]:
    pts = [list(sc["waypoints"][0])]
    n = sc["ticks_per_segment"]
    for a, b in zip(sc["waypoints"], sc["waypoints"][1:]):
        for k in range(1, n + 1):
            pts.append([round(a[0] + (b[0] - a[0]) * k / n, 4), round(a[1] + (b[1] - a[1]) * k / n, 4)])
    return pts


def _where(fx: dict, pt) -> dict:
    for c in fx["habitat"]["geometry"]["compartments"]:
        if _inside(pt, c["polygon"]):
            return {"zone_id": c["zone_id"], "passage_id": None, "joins": None}
    for p in _passages(fx):
        if _inside(pt, p["polygon"]):
            return {"zone_id": None, "passage_id": p["passage_id"], "joins": [p["from_zone_id"], p["to_zone_id"]]}
    return {"zone_id": None, "passage_id": None, "joins": None}


def _rssi(model: dict, pt, place: dict, anchor_pt, anchor_zone: str) -> float:
    """Noise-free simulated RSSI in dBm."""
    d = max(model["min_distance_m"], math.dist(pt, anchor_pt))
    loss = 10 * model["path_loss_exponent"] * math.log10(d)
    if place["zone_id"] is not None:
        walls = 0 if place["zone_id"] == anchor_zone else model["wall_loss_db"]
    elif place["joins"] is not None:
        walls = model["passage_wall_loss_db"] if anchor_zone in place["joins"] else model["wall_loss_db"]
    else:
        walls = model["wall_loss_db"]
    return model["tx_rssi_at_1m_dbm"] - loss - walls


def run(db: Session, fx: dict, scenario_id: str, astronaut_id: str) -> dict:
    sc = _scenario(fx, scenario_id)
    if db.get(m.Astronaut, astronaut_id) is None:
        raise not_found("Astronaut", astronaut_id)
    model = fx["movement_model"]
    rng = random.Random(sc["seed"])
    anchor_pts = {a["anchor_id"]: a["point"] for a in fx["habitat"]["geometry"]["anchor_positions"]}
    anchors = db.scalars(select(m.WirelessAnchor).order_by(m.WirelessAnchor.anchor_id)).all()
    ticks, truth, matches = [], [], []
    for i, pt in enumerate(_path(sc)):
        place = _where(fx, pt)
        observed_at = utcnow() - timedelta(seconds=sc["observation_age_seconds"])
        obs = []
        for a in anchors:
            if a.anchor_id in sc["dropped_anchor_ids"] or a.anchor_id not in anchor_pts:
                continue
            base = _rssi(model, pt, place, anchor_pts[a.anchor_id], a.zone_id)
            value = int(round(base + rng.gauss(0, sc["noise_db"])))
            obs.append({"anchor_id": a.anchor_id, "rssi_dbm": max(-120, min(0, value)), "observed_at": observed_at})
        est = spatial.estimate(db, LocationEstimateRequest(
            astronaut_id=astronaut_id, observations=[BleObservation(**o) for o in obs]))
        ticks.append({"tick": i, "generated_observations": obs,
                      "estimate": {"estimate_id": est.estimate_id, "zone_id": est.zone_id,
                                   "confidence": est.confidence, "source": est.source,
                                   "display_mode": est.display_mode,
                                   "rejected": [r.model_dump() for r in est.rejected]}})
        ok_zones = [place["zone_id"]] if place["zone_id"] else (place["joins"] or [])
        match = est.zone_id is not None and est.zone_id in ok_zones
        truth.append({"tick": i, "point": pt, "true_zone_id": place["zone_id"], "passage_id": place["passage_id"]})
        matches.append({"tick": i, "estimated_zone_id": est.zone_id, "acceptable_zone_ids": ok_zones,
                        "match": match})
    n = len(matches)
    return {"scenario_id": sc["scenario_id"], "description": sc["description"], "astronaut_id": astronaut_id,
            "model": model, "ticks": ticks,
            "evaluation": {"ground_truth": truth, "per_tick": matches,
                           "zone_matches": sum(x["match"] for x in matches), "tick_count": n,
                           "unavailable_ticks": sum(t["estimate"]["zone_id"] is None for t in ticks)}}

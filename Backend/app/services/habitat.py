"""Authoritative habitat geometry (map HAB-01-map-1.1, frame HAB-01-D1-LOCAL, metres).

Static geometry comes from the fixture (`habitat.geometry`); live state (hatch open/closed, anchor enabled, device
zone and readiness) comes from the database. The route network is derived from the geometry: each zone has a
navigation reference node, each passage a hatch node, and edges join zone reference -> hatch -> zone reference.
Rooms and passages are convex, so every edge is a straight segment inside walkable space; `check_geometry`
verifies that at startup and refuses to run with inconsistent geometry.
"""
from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..errors import not_found


def _inside(pt, poly) -> bool:
    """Point in polygon, boundary inclusive."""
    x, y = pt
    n = len(poly)
    for i in range(n):  # on an edge
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        cross = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
        if abs(cross) < 1e-9 and min(x1, x2) - 1e-9 <= x <= max(x1, x2) + 1e-9 \
                and min(y1, y2) - 1e-9 <= y <= max(y1, y2) + 1e-9:
            return True
    inside = False
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _dist(a, b) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def nav_node(zone_id: str) -> str:
    return f"NAV-{zone_id}"


def hatch_node(hatch_id: str) -> str:
    return f"HATCH-{hatch_id}"


def _passages(fx: dict) -> list[dict]:
    """Fixture passages joined with their connection (from/to zone, note)."""
    by_hatch = {c["hatch_id"]: c for c in fx["habitat"]["connections"] if c.get("hatch_id")}
    out = []
    for p in fx["habitat"]["geometry"]["passages"]:
        c = by_hatch.get(p["hatch_id"], {})
        out.append({**p, "from_zone_id": c.get("from_zone_id"), "to_zone_id": c.get("to_zone_id"),
                    "note": c.get("note", "")})
    return out


def _segment_walkable(a, b, polys) -> bool:
    return all(any(_inside((a[0] + (b[0] - a[0]) * t / 20, a[1] + (b[1] - a[1]) * t / 20), p) for p in polys)
               for t in range(21))


def check_geometry(fx: dict) -> list[str]:
    """Return a list of problems (empty when the geometry is consistent)."""
    hab, problems = fx["habitat"], []
    g = hab.get("geometry")
    if g is None:
        return ["habitat.geometry is missing"]
    rooms = {c["zone_id"]: c for c in g["compartments"]}
    zones = {z["zone_id"] for z in hab["zones"]}
    if set(rooms) != zones:
        problems.append(f"compartments {sorted(rooms)} do not match zones {sorted(zones)}")
    for zid, c in rooms.items():
        if not _inside(c["navigation_reference"], c["polygon"]):
            problems.append(f"navigation reference of {zid} lies outside its polygon")
    for c in hab["connections"]:
        if not c.get("hatch_id"):
            problems.append(f"connection {c['from_zone_id']}-{c['to_zone_id']} has no hatch_id")
    passages = _passages(fx)
    if {p["hatch_id"] for p in passages} != {c.get("hatch_id") for c in hab["connections"]}:
        problems.append("passage hatches do not match connection hatches")
    for p in passages:
        if not _inside(p["hatch_point"], p["polygon"]):
            problems.append(f"hatch point of {p['passage_id']} lies outside its passage")
        for zid in (p["from_zone_id"], p["to_zone_id"]):
            room = rooms.get(zid)
            if room is None:
                problems.append(f"{p['passage_id']} joins unknown zone {zid}")
            elif not _segment_walkable(room["navigation_reference"], p["hatch_point"],
                                       [room["polygon"], p["polygon"]]):
                problems.append(f"route edge {zid} -> {p['hatch_id']} leaves walkable space")
    anchor_zone = {a["anchor_id"]: a["zone_id"] for a in fx["anchors"]}
    for a in g["anchor_positions"]:
        zid = anchor_zone.get(a["anchor_id"])
        if zid is None or not _inside(a["point"], rooms[zid]["polygon"]):
            problems.append(f"anchor {a['anchor_id']} position is not inside its zone")
    equip_zone = {e["equipment_id"]: e["zone_id"] for e in fx["equipment"]}
    for e in g["equipment_positions"]:
        zid = equip_zone.get(e["equipment_id"])
        if zid is None or not _inside(e["point"], rooms[zid]["polygon"]):
            problems.append(f"equipment {e['equipment_id']} position is not inside its zone")
        elif not _segment_walkable(rooms[zid]["navigation_reference"], e["point"], [rooms[zid]["polygon"]]):
            problems.append(f"equipment {e['equipment_id']} is not reachable in a straight line in its zone")
    return problems


def _live_connections(db: Session, habitat_id: str) -> dict[str, m.ZoneConnection]:
    rows = db.scalars(select(m.ZoneConnection).where(m.ZoneConnection.habitat_id == habitat_id))
    return {r.hatch_id: r for r in rows if r.hatch_id}


def _equipment_point(fx: dict, e: m.Equipment):
    g = fx["habitat"]["geometry"]
    reg = next((p["point"] for p in g["equipment_positions"] if p["equipment_id"] == e.equipment_id), None)
    room = next((c for c in g["compartments"] if c["zone_id"] == e.zone_id), None)
    if reg is None or room is None or not _inside(reg, room["polygon"]):
        return None
    return reg


def build_map(db: Session, fx: dict, habitat_id: str) -> dict:
    hab_row = db.get(m.Habitat, habitat_id)
    if hab_row is None or habitat_id != fx["habitat"]["habitat_id"]:
        raise not_found("Habitat", habitat_id)
    g = fx["habitat"]["geometry"]
    names = {z.zone_id: z.name for z in db.scalars(select(m.Zone).where(m.Zone.habitat_id == habitat_id))}
    live = _live_connections(db, habitat_id)
    compartments = [{**c, "name": names.get(c["zone_id"], c["zone_id"]),
                     "navigation_node_id": nav_node(c["zone_id"])} for c in g["compartments"]]
    passages, nodes, edges = [], [], []
    for c in g["compartments"]:
        nodes.append({"node_id": nav_node(c["zone_id"]), "kind": "zone_reference", "point": c["navigation_reference"],
                      "zone_id": c["zone_id"]})
    refs = {c["zone_id"]: c["navigation_reference"] for c in g["compartments"]}
    for p in _passages(fx):
        row = live.get(p["hatch_id"])
        accessible = bool(row.accessible) if row is not None else False
        passages.append({**{k: p[k] for k in ("passage_id", "hatch_id", "deck_id", "from_zone_id", "to_zone_id",
                                              "polygon", "hatch_point")},
                         "accessible": accessible, "hatch_state": "open" if accessible else "closed",
                         "note": row.note if row is not None else p["note"]})
        hn = hatch_node(p["hatch_id"])
        nodes.append({"node_id": hn, "kind": "hatch", "point": p["hatch_point"], "hatch_id": p["hatch_id"]})
        for zid in (p["from_zone_id"], p["to_zone_id"]):
            edges.append({"from_node_id": nav_node(zid), "to_node_id": hn, "passage_id": p["passage_id"],
                          "length_m": round(_dist(refs[zid], p["hatch_point"]), 3), "accessible": accessible})
    anchor_pts = {a["anchor_id"]: a["point"] for a in g["anchor_positions"]}
    anchors = [{"anchor_id": a.anchor_id, "zone_id": a.zone_id, "enabled": a.enabled,
                "point": anchor_pts[a.anchor_id]}
               for a in db.scalars(select(m.WirelessAnchor).order_by(m.WirelessAnchor.anchor_id))
               if a.anchor_id in anchor_pts]
    equipment = []
    for e in db.scalars(select(m.Equipment).order_by(m.Equipment.equipment_id)):
        pt = _equipment_point(fx, e)
        equipment.append({"equipment_id": e.equipment_id, "device_model": e.device_model, "capability": e.capability,
                          "zone_id": e.zone_id, "readiness": e.readiness, "point": pt,
                          "position_status": "registered" if pt is not None else "not_registered_for_current_zone"})
    return {"habitat_id": habitat_id, "name": hab_row.name, "map_version": hab_row.map_version,
            "description": g["description"], "coordinate_frame": g["coordinate_frame"], "decks": g["decks"],
            "compartments": compartments, "passages": passages, "anchors": anchors, "equipment": equipment,
            "route_network": {"nodes": nodes, "edges": edges}}


def route_geometry(db: Session, fx: dict, zone_path: list[str], equipment: m.Equipment) -> dict:
    """Polyline for an accessible zone path, plus the hatches it passes through."""
    g = fx["habitat"]["geometry"]
    refs = {c["zone_id"]: c["navigation_reference"] for c in g["compartments"]}
    by_pair = {}
    for p in _passages(fx):
        by_pair[(p["from_zone_id"], p["to_zone_id"])] = by_pair[(p["to_zone_id"], p["from_zone_id"])] = p
    points, node_ids, hatches = [refs[zone_path[0]]], [nav_node(zone_path[0])], []
    for a, b in zip(zone_path, zone_path[1:]):
        p = by_pair[(a, b)]
        points += [p["hatch_point"], refs[b]]
        node_ids += [hatch_node(p["hatch_id"]), nav_node(b)]
        hatches.append(p["hatch_id"])
    end = _equipment_point(fx, equipment)
    if end is not None:
        points.append(end)
    length = sum(_dist(a, b) for a, b in zip(points, points[1:]))
    hab = db.get(m.Habitat, fx["habitat"]["habitat_id"])
    return {"geometry": {"frame_id": g["coordinate_frame"]["frame_id"], "map_version": hab.map_version,
                         "points": points, "node_ids": node_ids, "length_m": round(length, 3),
                         "end_equipment_point": end},
            "hatch_ids": hatches,
            "start_reference": {"kind": "zone_navigation_reference", "zone_id": zone_path[0],
                                "node_id": nav_node(zone_path[0]), "point": refs[zone_path[0]]}}

"""Contract 2.2.0 habitat geometry: floor plan, route geometry and honest location display modes (v3.1 §6)."""
from __future__ import annotations

import copy
import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app import models as m
from app.db import utcnow
from app.services import habitat
from app.services.habitat import _inside, check_geometry


def _case(client, symptom_payload):
    return client.post("/api/v1/symptoms", json=symptom_payload).json()["case_id"]


def _recommend(client, case_id, zone="crew-quarters"):
    return client.post("/api/v1/equipment/recommend",
                       json={"case_id": case_id, "zone_id": zone, "capability": "blood_pressure"})


def _db(client):
    return client.app.state.session_factory()


def test_fixture_geometry_is_consistent(fixture_data):
    assert check_geometry(fixture_data) == []


@pytest.mark.parametrize("breakage,expected", [
    (lambda fx: fx["habitat"]["geometry"]["equipment_positions"][0].update(point=[1.0, 1.0]), "EQ-BP-01"),
    (lambda fx: fx["habitat"]["connections"][0].pop("hatch_id"), "has no hatch_id"),
    (lambda fx: fx["habitat"]["geometry"]["compartments"][0].update(navigation_reference=[20, 20]),
     "navigation reference"),
    (lambda fx: fx["habitat"]["geometry"]["anchor_positions"][0].update(point=[8.0, 8.0]), "ANC-CQ-01"),
    (lambda fx: fx["habitat"]["geometry"]["passages"][0].update(hatch_point=[0.1, 0.1]), "hatch point"),
])
def test_geometry_check_catches_inconsistency(fixture_data, breakage, expected):
    fx = copy.deepcopy(fixture_data)
    breakage(fx)
    assert any(expected in p for p in check_geometry(fx))


def test_map_lists_full_layout_in_one_frame(client):
    r = client.get("/api/v1/habitats/HAB-01/map")
    assert r.status_code == 200
    mp = r.json()
    assert mp["map_version"] == "HAB-01-map-1.1" and mp["coordinate_frame"]["units"] == "metres"
    assert mp["coordinate_frame"]["frame_id"] == "HAB-01-D1-LOCAL" and [d["deck_id"] for d in mp["decks"]] == ["D1"]
    rooms = {c["zone_id"]: c for c in mp["compartments"]}
    assert set(rooms) == {"crew-quarters", "exercise", "medical", "laboratory"}
    states = {p["hatch_id"]: p["hatch_state"] for p in mp["passages"]}
    assert states == {"H-CQ-EX": "open", "H-EX-MED": "open", "H-CQ-LAB": "open", "H-LAB-MED": "closed"}
    assert len(mp["anchors"]) == 5 and len(mp["equipment"]) == 7
    for e in mp["equipment"]:
        assert e["position_status"] == "registered" and _inside(e["point"], rooms[e["zone_id"]]["polygon"])
    for a in mp["anchors"]:
        assert _inside(a["point"], rooms[a["zone_id"]]["polygon"])
    net = mp["route_network"]
    assert len(net["nodes"]) == 8 and len(net["edges"]) == 8
    closed = [e for e in net["edges"] if not e["accessible"]]
    assert {e["passage_id"] for e in closed} == {"P-LAB-MED"}
    assert "never drawn as precise points" in mp["note"]
    assert client.get("/api/v1/habitats/HAB-99/map").status_code == 404


def test_route_polyline_follows_open_passages(client, symptom_payload):
    rec = _recommend(client, _case(client, symptom_payload)).json()
    mp = client.get("/api/v1/habitats/HAB-01/map").json()
    assert rec["route_zone_ids"] == ["crew-quarters", "exercise", "medical"]
    assert rec["route_hatch_ids"] == ["H-CQ-EX", "H-EX-MED"]
    geo = rec["route_geometry"]
    assert geo["points"] == [[2.5, 2.0], [5.5, 2.0], [8.5, 2.0], [8.5, 4.5], [8.5, 7.0], [10.0, 6.0]]
    assert geo["node_ids"] == ["NAV-crew-quarters", "HATCH-H-CQ-EX", "NAV-exercise", "HATCH-H-EX-MED", "NAV-medical"]
    assert geo["map_version"] == mp["map_version"] == rec["map_version"]
    assert geo["frame_id"] == rec["coordinate_frame_id"] == mp["coordinate_frame"]["frame_id"]
    assert rec["start_reference"]["kind"] == "zone_navigation_reference"
    assert "not the person's precise position" in rec["start_reference"]["note"]
    walkable = [c["polygon"] for c in mp["compartments"]] + [p["polygon"] for p in mp["passages"] if p["accessible"]]
    for a, b in zip(geo["points"], geo["points"][1:]):
        assert habitat._segment_walkable(a, b, walkable)
    assert geo["length_m"] == pytest.approx(3 + 3 + 2.5 + 2.5 + (1.5 ** 2 + 1) ** 0.5, abs=1e-3)


def test_closing_a_hatch_changes_the_route(client, symptom_payload):
    case_id = _case(client, symptom_payload)
    with _db(client) as db:
        row = db.scalars(select(m.ZoneConnection).where(m.ZoneConnection.hatch_id == "H-EX-MED")).one()
        row.accessible = False
        db.commit()
    mp = client.get("/api/v1/habitats/HAB-01/map").json()
    assert next(p for p in mp["passages"] if p["hatch_id"] == "H-EX-MED")["hatch_state"] == "closed"
    r = _recommend(client, case_id)
    assert r.status_code == 404 and r.json()["error"]["code"] == "NO_SUITABLE_EQUIPMENT"
    reasons = {e["equipment_id"]: e["reasons"] for e in r.json()["error"]["details"]["excluded"]}
    assert "zone_not_accessible" in reasons["EQ-BP-01"]
    with _db(client) as db:  # reopening the hatch restores the route
        row = db.scalars(select(m.ZoneConnection).where(m.ZoneConnection.hatch_id == "H-EX-MED")).one()
        row.accessible = True
        db.commit()
    assert _recommend(client, case_id).json()["route_hatch_ids"] == ["H-CQ-EX", "H-EX-MED"]


def test_moved_equipment_has_no_stale_point(client):
    with _db(client) as db:
        db.get(m.Equipment, "EQ-THERM-01").zone_id = "laboratory"
        db.commit()
    eq = {e["equipment_id"]: e for e in client.get("/api/v1/habitats/HAB-01/map").json()["equipment"]}
    assert eq["EQ-THERM-01"]["point"] is None
    assert eq["EQ-THERM-01"]["position_status"] == "not_registered_for_current_zone"


def test_location_display_modes(client, ble_payload):
    assert client.get("/api/v1/location/DEMO-001/latest").json()["display_mode"] == "unavailable"
    est = client.post("/api/v1/location/estimate", json=ble_payload).json()
    assert est["display_mode"] == "zone_only" and est["position"] is None and est["map_version"] == "HAB-01-map-1.1"
    latest = client.get("/api/v1/location/DEMO-001/latest").json()
    assert latest["display_mode"] == "zone_only" and latest["estimate"]["zone_id"] == "crew-quarters"
    assert latest["stale_after_seconds"] == 30 and latest["estimate"]["explanation"] == est["explanation"]
    with _db(client) as db:
        row = db.get(m.LocationEstimate, est["estimate_id"])
        row.observed_at = utcnow() - timedelta(seconds=45)
        db.commit()
    stale = client.get("/api/v1/location/DEMO-001/latest").json()
    assert stale["display_mode"] == "stale" and stale["estimate"]["display_mode"] == "stale"
    assert "Not a current position" in stale["label"] and stale["estimate"]["zone_id"] == "crew-quarters"
    none = client.post("/api/v1/location/estimate", json={"astronaut_id": "DEMO-001", "observations": []}).json()
    assert none["display_mode"] == "unavailable"
    assert client.get("/api/v1/location/DEMO-001/latest").json()["display_mode"] == "unavailable"
    client.post("/api/v1/location/confirm", json={"astronaut_id": "DEMO-001", "zone_id": "medical",
                                                  "confirmed_by": "DEMO-001"})
    manual = client.get("/api/v1/location/DEMO-001/latest").json()
    assert manual["display_mode"] == "zone_only" and manual["stale_after_seconds"] == 900
    assert client.get("/api/v1/location/NOBODY/latest").status_code == 404


def test_older_database_gets_hatch_ids_and_map_version(harness):
    harness.start()
    harness.stop()
    db = Path(harness.db_url.removeprefix("sqlite:///"))
    with sqlite3.connect(db) as conn:
        conn.execute("ALTER TABLE zone_connections DROP COLUMN hatch_id")
        conn.execute("UPDATE habitats SET map_version = 'HAB-01-map-1.0'")
    c = harness.start()
    mp = c.get("/api/v1/habitats/HAB-01/map").json()
    assert mp["map_version"] == "HAB-01-map-1.1" and all(p["hatch_id"] for p in mp["passages"])
    assert {p["hatch_id"]: p["hatch_state"] for p in mp["passages"]}["H-LAB-MED"] == "closed"
    boot = c.get("/api/v1/demo/bootstrap").json()
    assert {x["hatch_id"] for x in boot["habitat"]["connections"]} == {"H-CQ-EX", "H-EX-MED", "H-CQ-LAB", "H-LAB-MED"}

"""Optional structured `surface_point` on symptom reports (3D Anatomical Twin, model sentinel-body-v1)."""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

import pytest

from app.config import REPO_DIR
from app.services import surface_sites
from tests.conftest import now_iso

FRONTEND_SITES = Path(os.environ.get("SENTINEL_FRONTEND_SITES", REPO_DIR / "Frontend" / "src" / "anatomy-sites.ts"))
SHOULDER = {"model_id": "sentinel-body-v1", "site_id": "right_shoulder", "x": -0.468, "y": 0.704, "z": 0.131}


def report(region="upper_arm", side="right", severity=4, point=SHOULDER, **extra):
    body = {"astronaut_id": "DEMO-001", "region_id": region, "laterality": side, "severity": severity,
            "onset": now_iso(600), **extra}
    if point is not None:
        body["surface_point"] = point
    return body


def test_point_stored_and_returned_in_case(client):
    r = client.post("/api/v1/symptoms", json=report(note="Ache when lifting"))
    assert r.status_code == 201
    created = r.json()
    sp = created["surface_point"]
    assert {k: sp[k] for k in SHOULDER} == SHOULDER and sp["site_label"] == "Right shoulder"
    assert sp["model_version"] == "1.0.0" and sp["marker_status"] == "current" and sp["render_hint"] == "exact_point"
    case = client.get(f"/api/v1/cases/{created['case_id']}").json()
    sym = case["symptoms"][0]
    assert sym["region_id"] == "upper_arm" and sym["laterality"] == "right"
    assert sym["surface_point"]["site_id"] == "right_shoulder" and sym["surface_point"]["x"] == -0.468
    assert sym["note"] == "Ache when lifting"  # user text kept apart from the machine-readable point
    assert "surface site right_shoulder" in case["evidence"][0]["summary"]
    audit = next(a for a in case["audit"] if a["action"] == "symptom.reported")
    assert audit["details"]["surface_site_id"] == "right_shoulder"


def test_point_is_optional_and_old_clients_unchanged(client, symptom_payload):
    created = client.post("/api/v1/symptoms", json=symptom_payload).json()
    assert created["surface_point"] is None
    sym = client.get(f"/api/v1/cases/{created['case_id']}").json()["symptoms"][0]
    assert sym["surface_point"] is None


def test_rules_still_use_broad_region(client):
    with_point = client.post("/api/v1/symptoms", json=report(severity=9)).json()
    case = client.get(f"/api/v1/cases/{with_point['case_id']}").json()
    assert case["priority"] == "urgent" and case["state"] == "awaiting_assessment"


def test_different_sites_in_one_region_are_not_duplicates(client):
    elbow = {**SHOULDER, "site_id": "right_elbow", "x": -0.7, "y": 0.19, "z": 0.12}
    a = client.post("/api/v1/symptoms", json=report())
    b = client.post("/api/v1/symptoms", json=report(point=elbow))
    assert a.status_code == b.status_code == 201 and b.json()["duplicate"] is False
    again = client.post("/api/v1/symptoms", json=report(point={**elbow, "x": -0.71}))
    assert again.status_code == 200 and again.json()["duplicate"] is True
    assert again.json()["symptom_id"] == b.json()["symptom_id"]
    sites = [s["surface_point"]["site_id"] for s in client.get(f"/api/v1/cases/{a.json()['case_id']}").json()["symptoms"]]
    assert sorted(sites) == ["right_elbow", "right_shoulder"]


@pytest.mark.parametrize("point,region,side,code", [
    ({**SHOULDER, "site_id": "right_spleen"}, "upper_arm", "right", "UNKNOWN_SURFACE_SITE"),
    (SHOULDER, "chest", "right", "SURFACE_SITE_MISMATCH"),
    (SHOULDER, "upper_arm", "left", "SURFACE_SITE_MISMATCH"),
    ({**SHOULDER, "x": 0.47}, "upper_arm", "right", "SURFACE_POINT_WRONG_SIDE"),
    ({**SHOULDER, "site_id": "left_knee", "x": -0.3, "y": -1.34}, "lower_leg_foot", "left", "SURFACE_POINT_WRONG_SIDE"),
    ({**SHOULDER, "model_id": "other-body"}, "upper_arm", "right", "UNKNOWN_SURFACE_MODEL"),
    ({**SHOULDER, "y": 7.5}, "upper_arm", "right", "VALIDATION_ERROR"),
    ({**SHOULDER, "z": "1e999"}, "upper_arm", "right", "VALIDATION_ERROR"),
    ({k: v for k, v in SHOULDER.items() if k != "z"}, "upper_arm", "right", "VALIDATION_ERROR"),
    ({**SHOULDER, "depth_cm": 2}, "upper_arm", "right", "VALIDATION_ERROR"),
])
def test_invalid_points_rejected(client, point, region, side, code):
    r = client.post("/api/v1/symptoms", json=report(region=region, side=side, point=point))
    assert r.status_code == 422 and r.json()["error"]["code"] == code
    assert client.get("/api/v1/demo/bootstrap").json()["open_cases"] == []  # nothing stored


def test_midline_sites_and_inner_edge_tolerance(client):
    pelvis = {**SHOULDER, "site_id": "pelvis", "x": 0.2, "y": -0.38, "z": 0.2}
    assert client.post("/api/v1/symptoms", json=report("abdomen", "midline", point=pelvis)).status_code == 201
    chest_edge = {**SHOULDER, "site_id": "right_chest", "x": 0.05, "y": 0.6, "z": 0.26}
    assert client.post("/api/v1/symptoms", json=report("chest", "right", point=chest_edge)).status_code == 201


def test_bootstrap_lists_the_site_catalogue(client):
    model = client.get("/api/v1/demo/bootstrap").json()["surface_model"]
    assert model["model_id"] == "sentinel-body-v1" and len(model["sites"]) == 35
    regions = {r["region_id"] for r in client.app.state.fixture["anatomical_regions"]}
    assert {s["region_id"] for s in model["sites"]} <= regions
    assert "not a diagnosis" in model["coordinate_note"]


def test_catalogue_matches_frontend_model():
    """Same site IDs and broad-region mapping as Frontend/src/anatomy-sites.ts, when that file is checked out."""
    if not FRONTEND_SITES.is_file():
        pytest.skip("Frontend anatomy-sites.ts is not in this checkout")
    src = FRONTEND_SITES.read_text(encoding="utf-8")
    found = {}
    for sid, region, side in re.findall(r"id: '([a-z_]+)'.*?regionId: '([a-z_]+)', laterality: '([a-z]+)'", src):
        found[sid] = (region, side)
    for sid, region in re.findall(r"id: `\$\{side\}_([a-z_]+)`.*?regionId: '([a-z_]+)'", src):
        for side in ("left", "right"):
            found[f"{side}_{sid}"] = (region, side)
    assert found == {k: (v["region_id"], v["laterality"]) for k, v in surface_sites.SITES.items()}


def test_point_survives_restart_and_reset_clears_it(harness):
    c = harness.start()
    case_id = c.post("/api/v1/symptoms", json=report()).json()["case_id"]
    c = harness.restart()
    assert c.get(f"/api/v1/cases/{case_id}").json()["symptoms"][0]["surface_point"]["site_id"] == "right_shoulder"
    c.post("/api/v1/demo/reset")
    assert c.get(f"/api/v1/cases/{case_id}").status_code == 404


def test_older_database_gets_the_column(harness):
    harness.start()
    harness.stop()
    db = Path(harness.db_url.removeprefix("sqlite:///"))
    with sqlite3.connect(db) as conn:
        conn.execute("ALTER TABLE symptom_reports DROP COLUMN surface_point")
        assert "surface_point" not in {r[1] for r in conn.execute("PRAGMA table_info(symptom_reports)")}
    c = harness.start()
    assert c.post("/api/v1/symptoms", json=report()).status_code == 201

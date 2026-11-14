"""Contract 2.3.0: Codex's anatomical reference mesh `sentinel-human-male-v1` is registered and its exact
markers persist (Frontend/V3_1_BACKEND_HANDOFF.md items 1-5)."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from app.config import REPO_DIR
from app.services import surface_sites
from tests.conftest import now_iso

MANIFEST = REPO_DIR / "shared" / "anatomy" / "sentinel-human-male-v1.json"
# The GLB is Codex's file; the hash check runs when it is checked out or pointed to.
GLB = Path(os.environ.get("SENTINEL_FRONTEND_HUMAN_GLB", REPO_DIR / "Frontend" / "public" / "models" / "anatomy-male.glb"))


@pytest.fixture
def examples(fixture_data):
    return fixture_data["surface_marker_examples"]


def report(example, **point_patch):
    return {"astronaut_id": "DEMO-001", "region_id": example["region_id"], "laterality": example["laterality"],
            "severity": 4, "onset": now_iso(600), "surface_point": {**example["surface_point"], **point_patch}}


def test_model_registered_with_asset_meshes_and_same_sites(client):
    models = {m["model_id"]: m for m in client.get("/api/v1/demo/bootstrap").json()["surface_models"]}
    human = models["sentinel-human-male-v1"]
    assert human["model_version"] == "1.0.0" and human["status"] == "active"
    assert human["asset"]["licence"] == "CC BY 4.0" and "BodyParts3D" in human["asset"]["attribution"]
    skin = human["meshes"][0]
    assert skin["mesh_id"] == "skin" and skin["selectable"] and skin["triangle_count"] == 40676
    assert {s["site_id"]: (s["region_id"], s["laterality"]) for s in human["sites"]} == \
        {k: (v["region_id"], v["laterality"]) for k, v in surface_sites.SITES.items()}
    assert all(s["plausibility"] for s in human["sites"])
    assert models["sentinel-body-v1"]["status"] == "active"  # legacy diagram markers stay valid


def test_manifest_matches_frontend_asset():
    if not GLB.is_file():
        pytest.skip("Frontend anatomy-male.glb is not in this checkout")
    raw = GLB.read_bytes()
    asset = json.loads(MANIFEST.read_text(encoding="utf-8"))["asset"]
    assert len(raw) == asset["bytes"] and hashlib.sha256(raw).hexdigest() == asset["sha256"]


def test_right_shoulder_marker_survives_restart_and_reopen(harness, examples):
    c = harness.start()
    sent = examples["right_shoulder"]["surface_point"]
    created = c.post("/api/v1/symptoms", json=report(examples["right_shoulder"]))
    assert created.status_code == 201, created.text
    case_id = created.json()["case_id"]
    c = harness.restart()
    sym = c.get(f"/api/v1/cases/{case_id}").json()["symptoms"][0]
    sp = sym["surface_point"]
    assert (sp["model_id"], sp["model_version"], sp["mesh_id"], sp["site_id"]) == \
        ("sentinel-human-male-v1", "1.0.0", "skin", "right_shoulder")
    assert (sym["region_id"], sym["laterality"]) == ("upper_arm", "right")
    assert (sp["x"], sp["y"], sp["z"]) == (sent["x"], sent["y"], sent["z"])
    assert sp["mesh_local_point"] == sent["mesh_local_point"] and sp["attachment"] == sent["attachment"]
    assert sp["mesh_validation"] == "validated" and sp["marker_status"] == "current"
    assert sp["render_hint"] == "exact_point" and sym["record_kind"] == "patient_reported_symptom"


def test_left_counterpart_and_v1_markers_coexist(client, examples):
    left = client.post("/api/v1/symptoms", json=report(examples["left_shoulder"]))
    assert left.status_code == 201 and left.json()["surface_point"]["site_id"] == "left_shoulder"
    v1 = {"model_id": "sentinel-body-v1", "site_id": "right_shoulder", "x": -0.468, "y": 0.704, "z": 0.131}
    old = client.post("/api/v1/symptoms", json={**report(examples["right_shoulder"]), "surface_point": v1})
    assert old.status_code == 201
    points = {s["surface_point"]["model_id"]: s["surface_point"]
              for s in client.get(f"/api/v1/cases/{left.json()['case_id']}").json()["symptoms"]}
    assert points["sentinel-body-v1"]["x"] == -0.468  # kept on its own model, never reprojected
    assert points["sentinel-human-male-v1"]["x"] == 0.2


def test_rejected_region_mismatch_from_shared_fixture(client, examples):
    ex = examples["rejected_region_mismatch"]
    r = client.post("/api/v1/symptoms", json=report(ex))
    assert r.status_code == 422 and r.json()["error"]["code"] == ex["expected_error"]


@pytest.mark.parametrize("patch,code", [
    ({"x": 0.2}, "SURFACE_POINT_WRONG_SIDE"),
    ({"y": 0.6}, "SURFACE_POINT_OUTSIDE_SITE"),
    ({"mesh_id": None, "mesh_local_point": None, "attachment": None}, "MESH_REQUIRED"),
    ({"mesh_id": "deltoid_r"}, "UNKNOWN_MESH"),
    ({"z": 0.4}, "MESH_POINT_MISMATCH"),
    ({"mesh_local_point": {"x": -0.1, "y": 0.65, "z": 0.06}}, "MESH_POINT_MISMATCH"),
    ({"attachment": {"triangle_index": 40676, "barycentric": [1, 0, 0]}}, "TRIANGLE_OUT_OF_RANGE"),
    ({"model_version": "1"}, "SURFACE_MODEL_VERSION_MISMATCH"),
    ({"x": -2.5}, "SURFACE_POINT_OUT_OF_RANGE"),
])
def test_invalid_human_points_rejected(client, examples, patch, code):
    r = client.post("/api/v1/symptoms", json=report(examples["right_shoulder"], **patch))
    assert r.status_code == 422 and r.json()["error"]["code"] == code, r.text
    assert client.get("/api/v1/demo/bootstrap").json()["open_cases"] == []


def test_front_and_back_sites_are_checked(client, examples):
    chest = {**examples["right_shoulder"]["surface_point"], "site_id": "right_chest", "y": 1.3, "z": -0.08}
    chest["mesh_local_point"] = None
    r = client.post("/api/v1/symptoms", json={**report(examples["right_shoulder"]), "region_id": "chest",
                                               "surface_point": chest})
    assert r.status_code == 422 and r.json()["error"]["code"] == "SURFACE_POINT_OUTSIDE_SITE"
    back = {**chest, "site_id": "right_upper_back", "attachment": None}
    r = client.post("/api/v1/symptoms", json={**report(examples["right_shoulder"]), "region_id": "upper_back",
                                               "surface_point": back})
    assert r.status_code == 201


def test_non_selectable_mesh_rejected(client, examples, monkeypatch):
    model = copy.deepcopy(surface_sites.MODELS["sentinel-human-male-v1"])
    model["mesh_by_id"]["skin"]["selectable"] = False
    monkeypatch.setitem(surface_sites.MODELS, "sentinel-human-male-v1", model)
    r = client.post("/api/v1/symptoms", json=report(examples["right_shoulder"]))
    assert r.status_code == 422 and r.json()["error"]["code"] == "MESH_NOT_SELECTABLE"

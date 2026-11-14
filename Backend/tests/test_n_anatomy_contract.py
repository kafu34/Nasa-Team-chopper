"""Contract 2.2.0 anatomical marker schema: model registry, versions, mesh attachment and marker migration."""
from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path

import pytest

from app.config import REPO_DIR
from app.services import surface_sites
from tests.conftest import now_iso

V1 = {"model_id": "sentinel-body-v1", "site_id": "right_shoulder", "x": -0.468, "y": 0.704, "z": 0.131}
TEST_MODEL = {
    "manifest_version": "1.0", "model_id": "test-mesh-body", "model_version": "2.0.0", "status": "active",
    "kind": "test_mesh", "description": "Test-only model.",
    "coordinate_frame": {"space": "model_local", "units": "metres", "x": "left (+)", "y": "up", "z": "front (+)",
                         "limit": 5.0},
    "side_tolerance": 0.1, "meshes": [{"mesh_id": "arm_r", "triangle_count": 5000}], "previous_versions": [],
    "sites": [{"site_id": "right_shoulder", "label": "Right shoulder", "region_id": "upper_arm",
               "laterality": "right"}],
}
MESH_POINT = {"model_id": "test-mesh-body", "model_version": "2.0.0", "site_id": "right_shoulder",
              "x": -0.2, "y": 1.4, "z": 0.05, "mesh_id": "arm_r",
              "attachment": {"triangle_index": 1204, "barycentric": [0.2, 0.3, 0.5]}}


def report(point, severity=4):
    return {"astronaut_id": "DEMO-001", "region_id": "upper_arm", "laterality": "right", "severity": severity,
            "onset": now_iso(600), "surface_point": point}


def register(monkeypatch, manifest):
    manifest = copy.deepcopy(manifest)
    manifest["sites_by_id"] = {s["site_id"]: s for s in manifest["sites"]}
    manifest["mesh_by_id"] = ({m["mesh_id"]: m for m in manifest["meshes"]}
                              if manifest.get("meshes") is not None else None)
    monkeypatch.setitem(surface_sites.MODELS, manifest["model_id"], manifest)
    return manifest


def symptom_point(client, case_id):
    return client.get(f"/api/v1/cases/{case_id}").json()["symptoms"][0]["surface_point"]


def test_shared_manifest_is_the_registry_source():
    manifest = json.loads((REPO_DIR / "shared" / "anatomy" / "sentinel-body-v1.json").read_text(encoding="utf-8"))
    assert manifest["model_version"] == "1.0.0" and manifest["status"] == "active" and manifest["meshes"] is None
    assert {s["site_id"]: s for s in manifest["sites"]} == surface_sites.SITES and len(manifest["sites"]) == 35


def test_bootstrap_lists_models_and_annotation_kinds(client):
    boot = client.get("/api/v1/demo/bootstrap").json()
    models = {m["model_id"]: m for m in boot["surface_models"]}
    assert models["sentinel-body-v1"]["model_version"] == "1.0.0" and len(models["sentinel-body-v1"]["sites"]) == 35
    assert boot["surface_model"]["model_id"] == "sentinel-body-v1"  # v2.2 shape kept
    kinds = {k["kind"]: k["description"] for k in boot["anatomical_annotation_kinds"]}
    assert set(kinds) == {"surface_selection", "region_classification", "patient_reported_symptom",
                          "monitoring_concern", "verified_finding"}
    assert "never creates" in kinds["verified_finding"]


def test_record_kind_marks_self_report(client):
    created = client.post("/api/v1/symptoms", json=report(V1)).json()
    assert created["record_kind"] == "patient_reported_symptom"
    sym = client.get(f"/api/v1/cases/{created['case_id']}").json()["symptoms"][0]
    assert sym["record_kind"] == "patient_reported_symptom"


def test_model_version_recorded_and_checked(client):
    assert client.post("/api/v1/symptoms", json=report({**V1, "model_version": "1.0.0"})).status_code == 201
    r = client.post("/api/v1/symptoms", json=report({**V1, "model_version": "0.9.0"}, severity=5))
    assert r.status_code == 422 and r.json()["error"]["code"] == "SURFACE_MODEL_VERSION_MISMATCH"


def test_mesh_and_attachment_stored_when_model_declares_no_meshes(client):
    point = {**V1, "mesh_id": "body_upper_arm_r", "attachment": {"triangle_index": 17, "barycentric": [1, 0, 0]}}
    created = client.post("/api/v1/symptoms", json=report(point)).json()
    sp = symptom_point(client, created["case_id"])
    assert sp["mesh_id"] == "body_upper_arm_r" and sp["mesh_validation"] == "not_declared_by_model"
    assert sp["attachment"] == {"triangle_index": 17, "barycentric": [1.0, 0.0, 0.0]}


@pytest.mark.parametrize("point,code", [
    ({**V1, "attachment": {"triangle_index": 1, "barycentric": [0.2, 0.3, 0.5]}}, "ATTACHMENT_REQUIRES_MESH"),
    ({**V1, "mesh_id": "m", "attachment": {"triangle_index": 1, "barycentric": [0.2, 0.3, 0.4]}}, "VALIDATION_ERROR"),
    ({**V1, "mesh_id": "m", "attachment": {"triangle_index": 1, "barycentric": [1.2, -0.2, 0]}}, "VALIDATION_ERROR"),
    ({**V1, "mesh_id": "m", "attachment": {"triangle_index": -1, "barycentric": [1, 0, 0]}}, "VALIDATION_ERROR"),
    ({**V1, "mesh_id": "m", "attachment": {"triangle_index": 1, "barycentric": [1, 0]}}, "VALIDATION_ERROR"),
    ({**V1, "mesh_id": "bad id!"}, "VALIDATION_ERROR"),
])
def test_invalid_attachments_rejected(client, point, code):
    r = client.post("/api/v1/symptoms", json=report(point))
    assert r.status_code == 422 and r.json()["error"]["code"] == code
    assert client.get("/api/v1/demo/bootstrap").json()["open_cases"] == []


def test_declared_meshes_are_validated(client, monkeypatch):
    register(monkeypatch, TEST_MODEL)
    bad_mesh = client.post("/api/v1/symptoms", json=report({**MESH_POINT, "mesh_id": "arm_l"}))
    assert bad_mesh.status_code == 422 and bad_mesh.json()["error"]["code"] == "UNKNOWN_MESH"
    bad_tri = client.post("/api/v1/symptoms", json=report(
        {**MESH_POINT, "attachment": {"triangle_index": 5000, "barycentric": [1, 0, 0]}}))
    assert bad_tri.status_code == 422 and bad_tri.json()["error"]["code"] == "TRIANGLE_OUT_OF_RANGE"
    ok = client.post("/api/v1/symptoms", json=report(MESH_POINT))
    assert ok.status_code == 201 and ok.json()["surface_point"]["mesh_validation"] == "validated"


@pytest.mark.parametrize("change,status,hint", [
    ({}, "current", "exact_point"),
    ({"model_version": "2.1.0", "previous_versions": [
        {"model_version": "2.0.0", "coordinates_compatible": True, "note": "Material change only."}]},
     "model_version_changed", "exact_point"),
    ({"model_version": "3.0.0", "previous_versions": [
        {"model_version": "2.0.0", "coordinates_compatible": False, "note": "Re-sculpted mesh."}]},
     "model_version_incompatible", "site_only"),
    ({"status": "retired"}, "model_retired", "site_only"),
])
def test_marker_migration_status(client, monkeypatch, change, status, hint):
    register(monkeypatch, TEST_MODEL)
    case_id = client.post("/api/v1/symptoms", json=report(MESH_POINT)).json()["case_id"]
    register(monkeypatch, {**TEST_MODEL, **change})
    sp = symptom_point(client, case_id)
    assert sp["marker_status"] == status and sp["render_hint"] == hint
    assert sp["model_version"] == "2.0.0" and sp["x"] == -0.2  # stored coordinates are never rewritten


def test_unregistered_model_marker_not_renderable_and_retired_model_rejects_reports(client, monkeypatch):
    register(monkeypatch, TEST_MODEL)
    case_id = client.post("/api/v1/symptoms", json=report(MESH_POINT)).json()["case_id"]
    monkeypatch.delitem(surface_sites.MODELS, "test-mesh-body")
    sp = symptom_point(client, case_id)
    assert sp["marker_status"] == "model_unknown" and sp["render_hint"] == "not_renderable"
    register(monkeypatch, {**TEST_MODEL, "status": "retired"})
    r = client.post("/api/v1/symptoms", json=report(MESH_POINT, severity=6))
    assert r.status_code == 422 and r.json()["error"]["code"] == "SURFACE_MODEL_RETIRED"


def test_points_stored_before_contract_2_2_read_as_version_1(harness):
    c = harness.start()
    case_id = c.post("/api/v1/symptoms", json=report(V1)).json()["case_id"]
    harness.stop()
    db = Path(harness.db_url.removeprefix("sqlite:///"))
    legacy = {**V1, "site_label": "Right shoulder"}  # exactly what contract 2.1/2.2-beta stored
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE symptom_reports SET surface_point = ?", (json.dumps(legacy),))
    c = harness.start()
    sp = symptom_point(c, case_id)
    assert sp["model_version"] == "1.0.0" and sp["marker_status"] == "current" and sp["mesh_id"] is None

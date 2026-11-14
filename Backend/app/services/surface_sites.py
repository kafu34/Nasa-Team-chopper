"""Anatomical surface-model registry for the frontend's 3D Anatomical Twin.

Every model the frontend can render is described by one manifest in `shared/anatomy/<model_id>.json`
(model version, coordinate frame, declared meshes, detailed sites -> broad region + laterality, earlier versions).

A surface point is a location on a diagram. It is NOT a measured physical location, does not identify an internal
structure and is never used by the rules engine to draw a clinical conclusion. The rules keep using the broad
fixture `region_id`; each detailed site maps to exactly one broad region and laterality.

Marker migration (contract 2.2.0): a stored point keeps the model ID and version it was reported on. On read it is
labelled `current`, `model_version_changed` (older version whose coordinates are declared compatible),
`model_version_incompatible`, `model_retired` or `model_unknown`, with a render hint. Incompatible markers are
shown at site level only and are never moved onto another surface silently.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from ..config import REPO_DIR
from ..errors import ApiError

ANATOMY_DIR = Path(os.environ.get("SENTINEL_ANATOMY_DIR", REPO_DIR / "shared" / "anatomy"))
DEFAULT_MODEL_ID = "sentinel-body-v1"
# Points stored before contract 2.2.0 carry no version; only this version of the default model existed then.
LEGACY_MODEL_VERSION = "1.0.0"
BARYCENTRIC_TOLERANCE = 1e-3

ANNOTATION_KINDS = [
    {"kind": "surface_selection", "description": "A point or site the user selected on the 3D model. A diagram "
     "location, not a measurement."},
    {"kind": "region_classification", "description": "The broad anatomical region and side used by the rules "
     "engine (fixture region_id + laterality)."},
    {"kind": "patient_reported_symptom", "description": "What the crew member reported (severity, onset, note). "
     "Self-report, not a clinical finding."},
    {"kind": "monitoring_concern", "description": "A configured demonstration rule flagged a pattern in "
     "monitoring data. Not a diagnosis."},
    {"kind": "verified_finding", "description": "A finding confirmed by a qualified clinician. SENTINEL never "
     "creates this kind automatically."},
]


def _load_models(directory: Path) -> dict[str, dict]:
    models: dict[str, dict] = {}
    for path in sorted(directory.glob("*.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["sites_by_id"] = {s["site_id"]: s for s in manifest["sites"]}
        manifest["mesh_by_id"] = ({m["mesh_id"]: m for m in manifest["meshes"]}
                                  if manifest.get("meshes") is not None else None)
        models[manifest["model_id"]] = manifest
    if DEFAULT_MODEL_ID not in models:
        raise RuntimeError(f"Anatomy manifest for {DEFAULT_MODEL_ID} is missing from {directory}")
    return models


MODELS = _load_models(ANATOMY_DIR)

# Backwards-compatible names used by earlier code and tests (default model only).
MODEL_ID = DEFAULT_MODEL_ID
SITES: dict[str, dict] = MODELS[DEFAULT_MODEL_ID]["sites_by_id"]
COORDINATE_LIMIT = MODELS[DEFAULT_MODEL_ID]["coordinate_frame"]["limit"]
SIDE_TOLERANCE = MODELS[DEFAULT_MODEL_ID]["side_tolerance"]
COORDINATE_NOTE = ("Model units on a stylised diagram: x = body left (+) / right (-), y = up, z = front (+). "
                   "Not a measured physical location and not a diagnosis.")


def _model_for_report(model_id: str) -> dict:
    model = MODELS.get(model_id)
    if model is None:
        raise ApiError(422, "UNKNOWN_SURFACE_MODEL", f"Surface model '{model_id}' is not registered.",
                       {"registered_model_ids": sorted(MODELS)})
    if model["status"] != "active":
        raise ApiError(422, "SURFACE_MODEL_RETIRED", f"Surface model '{model_id}' is {model['status']}; new "
                       "reports must use an active model.", {"active_model_ids": active_model_ids()})
    return model


def active_model_ids() -> list[str]:
    return sorted(k for k, v in MODELS.items() if v["status"] == "active")


def validate(point, region_id: str, laterality: str) -> dict:
    """Return the stored form of a surface point, or raise a 422 ApiError."""
    model = _model_for_report(point.model_id)
    version = point.model_version or model["model_version"]
    if version != model["model_version"]:
        raise ApiError(422, "SURFACE_MODEL_VERSION_MISMATCH",
                       f"Model '{model['model_id']}' is at version {model['model_version']}, not {version}.",
                       {"model_id": model["model_id"], "current_version": model["model_version"]})
    limit = model["coordinate_frame"]["limit"]
    if max(abs(point.x), abs(point.y), abs(point.z)) > limit:
        raise ApiError(422, "SURFACE_POINT_OUT_OF_RANGE", f"Coordinates must be within +/-{limit} model units.",
                       {"limit": limit})
    site = model["sites_by_id"].get(point.site_id)
    if site is None:
        raise ApiError(422, "UNKNOWN_SURFACE_SITE", f"Surface site '{point.site_id}' is not defined for "
                       f"{model['model_id']}.", {"allowed_site_ids": sorted(model["sites_by_id"])})
    if site["region_id"] != region_id or site["laterality"] != laterality:
        raise ApiError(422, "SURFACE_SITE_MISMATCH",
                       f"Surface site '{site['site_id']}' belongs to region '{site['region_id']}' "
                       f"({site['laterality']}), not '{region_id}' ({laterality}).",
                       {"site_id": site["site_id"], "expected_region_id": site["region_id"],
                        "expected_laterality": site["laterality"]})
    tol = model["side_tolerance"]
    if (laterality == "right" and point.x > tol) or (laterality == "left" and point.x < -tol):
        raise ApiError(422, "SURFACE_POINT_WRONG_SIDE",
                       f"x={point.x} is on the other side of the model from a {laterality} site "
                       "(right is negative x, left is positive x).",
                       {"site_id": site["site_id"], "x": point.x, "tolerance": tol})
    _check_site_plausibility(model, site, point)
    if (point.attachment is not None or point.mesh_local_point is not None) and point.mesh_id is None:
        raise ApiError(422, "ATTACHMENT_REQUIRES_MESH",
                       "A triangle/barycentric attachment or mesh_local_point needs mesh_id.", {})
    mesh_validation = "not_supplied"
    meshes = model["mesh_by_id"]
    if point.mesh_id is None and meshes is not None:
        raise ApiError(422, "MESH_REQUIRED", f"Model '{model['model_id']}' declares its meshes; a tapped point "
                       "must name the mesh it lies on.", {"selectable_mesh_ids": _selectable(meshes)})
    if point.mesh_id is not None:
        if meshes is None:
            mesh_validation = "not_declared_by_model"
        else:
            mesh = meshes.get(point.mesh_id)
            if mesh is None:
                raise ApiError(422, "UNKNOWN_MESH", f"Mesh '{point.mesh_id}' is not declared for "
                               f"{model['model_id']}.", {"declared_mesh_ids": sorted(meshes)})
            if not mesh.get("selectable", True):
                raise ApiError(422, "MESH_NOT_SELECTABLE", f"Mesh '{point.mesh_id}' is not used for symptom "
                               "reports.", {"selectable_mesh_ids": _selectable(meshes)})
            if point.attachment is not None and point.attachment.triangle_index >= mesh["triangle_count"]:
                raise ApiError(422, "TRIANGLE_OUT_OF_RANGE", f"Mesh '{point.mesh_id}' has "
                               f"{mesh['triangle_count']} triangles.", {"triangle_count": mesh["triangle_count"]})
            _check_mesh_geometry(model, mesh, point)
            mesh_validation = "validated"
    return {"model_id": model["model_id"], "model_version": version, "site_id": site["site_id"],
            "site_label": site["label"], "x": point.x, "y": point.y, "z": point.z,
            "mesh_id": point.mesh_id, "mesh_validation": mesh_validation,
            "attachment": point.attachment.model_dump() if point.attachment is not None else None,
            "mesh_local_point": point.mesh_local_point.model_dump() if point.mesh_local_point is not None else None}


def _selectable(meshes: dict) -> list[str]:
    return sorted(k for k, v in meshes.items() if v.get("selectable", True))


def _check_site_plausibility(model: dict, site: dict, point) -> None:
    """Coarse check that the point is at a plausible height and face for its site (models that declare it)."""
    band = site.get("plausibility")
    if band is None:
        return
    tol = model.get("surface_tolerance_m", 0.0)
    problems = []
    if not band["y_min_m"] - tol <= point.y <= band["y_max_m"] + tol:
        problems.append(f"y={point.y} is outside {band['y_min_m']}-{band['y_max_m']} m")
    if band["surface"] == "front" and point.z < -tol:
        problems.append("the point is on the back of the model")
    if band["surface"] == "back" and point.z > tol:
        problems.append("the point is on the front of the model")
    if problems:
        raise ApiError(422, "SURFACE_POINT_OUTSIDE_SITE",
                       f"Point does not fit site '{site['site_id']}': " + "; ".join(problems) + ".",
                       {"site_id": site["site_id"], "plausibility": band})


def _check_mesh_geometry(model: dict, mesh: dict, point) -> None:
    """For meshes that declare their transform: the point lies in the mesh bounds, and the mesh-local point (if
    sent) maps onto the reported point. The backend holds no triangles, so exact surface contact is not checked."""
    xf, bounds = mesh.get("node_transform"), mesh.get("local_bounds")
    if xf is None or bounds is None:
        return
    tol = model.get("surface_tolerance_m", 0.0)
    t, s = xf["translation"], xf["scale"]
    world = (point.x, point.y, point.z)
    lo = [t[k] + s[k] * bounds["min"][k] for k in range(3)]
    hi = [t[k] + s[k] * bounds["max"][k] for k in range(3)]
    if any(not lo[k] - tol <= world[k] <= hi[k] + tol for k in range(3)):
        raise ApiError(422, "MESH_POINT_MISMATCH", f"The point lies outside mesh '{mesh['mesh_id']}'.",
                       {"mesh_bounds_min": lo, "mesh_bounds_max": hi})
    if point.mesh_local_point is not None:
        local = (point.mesh_local_point.x, point.mesh_local_point.y, point.mesh_local_point.z)
        mapped = [t[k] + s[k] * local[k] for k in range(3)]
        gap = max(abs(mapped[k] - world[k]) for k in range(3))
        if gap > tol:
            raise ApiError(422, "MESH_POINT_MISMATCH", f"mesh_local_point does not map onto the reported point "
                           f"(gap {gap:.4f} m, tolerance {tol} m).", {"mapped_point": mapped, "gap_m": gap})


def describe(stored: dict) -> dict:
    """Add marker migration status and render hint to a stored point (read side)."""
    out = {"model_version": LEGACY_MODEL_VERSION, "mesh_id": None, "mesh_validation": "not_supplied",
           "attachment": None, "mesh_local_point": None, **stored}
    model = MODELS.get(out["model_id"])
    if model is None:
        status, hint = "model_unknown", "not_renderable"
    elif model["status"] != "active":
        status, hint = "model_retired", "site_only"
    elif out["model_version"] == model["model_version"]:
        status, hint = "current", "exact_point"
    else:
        prev = next((p for p in model.get("previous_versions", []) if p["model_version"] == out["model_version"]),
                    None)
        if prev is not None and prev.get("coordinates_compatible"):
            status, hint = "model_version_changed", "exact_point"
        else:
            status, hint = "model_version_incompatible", "site_only"
    if hint == "site_only" and model is not None and out["site_id"] not in model["sites_by_id"]:
        hint = "not_renderable"
    out["marker_status"], out["render_hint"] = status, hint
    return out


def _public(model: dict) -> dict:
    return {"model_id": model["model_id"], "model_version": model["model_version"], "status": model["status"],
            "kind": model["kind"], "description": model["description"], "asset": model.get("asset"),
            "coordinate_frame": model["coordinate_frame"], "side_tolerance": model["side_tolerance"],
            "meshes": model.get("meshes"), "previous_versions": model.get("previous_versions", []),
            "sites": model["sites"]}


def models_catalogue() -> list[dict]:
    return [_public(MODELS[k]) for k in sorted(MODELS)]


def catalogue() -> dict:
    """The default model in the v2.2 `surface_model` shape (kept for existing clients)."""
    return {"model_id": MODEL_ID, "coordinate_limit": COORDINATE_LIMIT, "coordinate_note": COORDINATE_NOTE,
            "sites": list(SITES.values())}

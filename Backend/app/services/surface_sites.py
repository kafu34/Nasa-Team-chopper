"""Detailed surface sites of the frontend's 3D Anatomical Twin model (`sentinel-body-v1`).

A surface point is a location on a stylised diagram. It is NOT a measured physical location, does not identify
an internal structure and is never used by the rules engine to draw a clinical conclusion. The rules keep using
the broad fixture `region_id`; each detailed site maps to exactly one broad region and laterality, mirroring
`Frontend/src/anatomy-sites.ts` at commit aa25e6b.

Model coordinates: x is the body's left (+) / right (-) axis, y is up, z is front (+). Units are model units
(the figure is about 4.2 units tall), not centimetres.
"""
from __future__ import annotations

from ..errors import ApiError

MODEL_ID = "sentinel-body-v1"
COORDINATE_LIMIT = 5.0
# The right side of the model is at negative x. A small tolerance allows taps on the inner edge of the chest,
# abdomen and back halves, which reach slightly past the midline (up to x = +/-0.055).
SIDE_TOLERANCE = 0.1
COORDINATE_NOTE = ("Model units on a stylised diagram: x = body left (+) / right (-), y = up, z = front (+). "
                   "Not a measured physical location and not a diagnosis.")

_CENTRED = [("head", "Head", "head", "midline"),
            ("neck", "Neck", "neck", "midline"),
            ("pelvis", "Pelvis", "abdomen", "midline")]
_PAIRED = [("eye", "eye", "eyes"), ("chest", "chest", "chest"), ("upper_back", "upper back", "upper_back"),
           ("abdomen", "abdomen", "abdomen"), ("lower_back", "lower back", "lower_back"),
           ("shoulder", "shoulder", "upper_arm"), ("upper_arm", "upper arm", "upper_arm"),
           ("elbow", "elbow", "upper_arm"), ("forearm", "forearm", "forearm_hand"),
           ("wrist", "wrist", "forearm_hand"), ("hand", "hand", "forearm_hand"),
           ("upper_leg", "upper leg", "upper_leg"), ("knee", "knee", "lower_leg_foot"),
           ("lower_leg", "lower leg", "lower_leg_foot"), ("ankle", "ankle", "lower_leg_foot"),
           ("foot", "foot", "lower_leg_foot")]

SITES: dict[str, dict] = {}
for _id, _label, _region, _side in _CENTRED:
    SITES[_id] = {"site_id": _id, "label": _label, "region_id": _region, "laterality": _side}
for _side in ("right", "left"):
    for _id, _label, _region in _PAIRED:
        sid = f"{_side}_{_id}"
        SITES[sid] = {"site_id": sid, "label": f"{_side.capitalize()} {_label}", "region_id": _region,
                      "laterality": _side}


def validate(point, region_id: str, laterality: str) -> dict:
    """Return the stored form of a surface point, or raise a 422 ApiError."""
    site = SITES.get(point.site_id)
    if site is None:
        raise ApiError(422, "UNKNOWN_SURFACE_SITE", f"Surface site '{point.site_id}' is not defined for "
                       f"{MODEL_ID}.", {"allowed_site_ids": sorted(SITES)})
    if site["region_id"] != region_id or site["laterality"] != laterality:
        raise ApiError(422, "SURFACE_SITE_MISMATCH",
                       f"Surface site '{site['site_id']}' belongs to region '{site['region_id']}' "
                       f"({site['laterality']}), not '{region_id}' ({laterality}).",
                       {"site_id": site["site_id"], "expected_region_id": site["region_id"],
                        "expected_laterality": site["laterality"]})
    if (laterality == "right" and point.x > SIDE_TOLERANCE) or (laterality == "left" and point.x < -SIDE_TOLERANCE):
        raise ApiError(422, "SURFACE_POINT_WRONG_SIDE",
                       f"x={point.x} is on the other side of the model from a {laterality} site "
                       "(right is negative x, left is positive x).",
                       {"site_id": site["site_id"], "x": point.x, "tolerance": SIDE_TOLERANCE})
    return {"model_id": point.model_id, "site_id": site["site_id"], "site_label": site["label"],
            "x": point.x, "y": point.y, "z": point.z}


def catalogue() -> dict:
    return {"model_id": MODEL_ID, "coordinate_limit": COORDINATE_LIMIT, "coordinate_note": COORDINATE_NOTE,
            "sites": list(SITES.values())}

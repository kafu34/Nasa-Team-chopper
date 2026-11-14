"""Contract 2.2.0 visual-procedure data for PROC-BP-01 (v3.1 §5, backend part)."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

from app.config import REPO_DIR
from app.services import surface_sites
from tests.conftest import now_iso

# Codex's visual-action/asset registry, when checked out (v3.1 §5). The path is not fixed yet.
VISUAL_REGISTRY = Path(os.environ.get("SENTINEL_FRONTEND_VISUAL_REGISTRY",
                                      REPO_DIR / "Frontend" / "src" / "visual-registry.ts"))
# Instruction text frozen at 1.0.0-demo: the visual contract must not change what the crew member is told.
INSTRUCTION_STARTS = {"S1": "Restrain yourself", "S2": "Use the left upper arm", "S3": "Wrap the cuff snugly",
                      "S4": "Keep the arm relaxed", "S5": "Press start", "S6": "Read the systolic"}


@pytest.fixture
def proc(client):
    return client.get("/api/v1/procedures/PROC-BP-01").json()


def test_every_step_has_a_distinct_visual_action(proc):
    actions = [s["visual"]["action_id"] for s in proc["steps"]]
    assert len(actions) == len(set(actions)) == 6
    assert [r["action_id"] for r in proc["visual_requirements"]] == actions
    for step, req in zip(proc["steps"], proc["visual_requirements"]):
        v = step["visual"]
        assert req["asset_ids"] == [v["asset_id"], *v["additional_asset_ids"]]
        assert v["expected_visible_action"] and v["replay_allowed"] and v["pause_allowed"]
        assert step["requires_confirmation"] is True


def test_validation_level_and_sources(proc):
    assert proc["validation_level"] == "EDUCATIONAL_DEMONSTRATION" and proc["version"] == "1.1.0-demo"
    sources = {s["source_id"] for s in proc["instruction_sources"]}
    assert all(not s["reviewed_by_flight_surgeon"] for s in proc["instruction_sources"])
    for step in proc["steps"]:
        assert step["instruction_source_ids"] and set(step["instruction_source_ids"]) <= sources


def test_anatomy_targets_are_valid(proc, fixture_data):
    regions = {r["region_id"] for r in fixture_data["anatomical_regions"]}
    for step in proc["steps"]:
        assert step["target_region_id"] in regions
        assert step["visual"]["camera"]["target_region_id"] in regions
        if step["target_site_id"]:
            site = surface_sites.SITES[step["target_site_id"]]
            assert (site["region_id"], site["laterality"]) == (step["target_region_id"], step["target_laterality"])
    arm_steps = [s["step_id"] for s in proc["steps"] if s["target_site_id"] == "left_upper_arm"]
    assert arm_steps == ["S2", "S3", "S4", "S5"]  # S2 says "Use the left upper arm"


def test_equipment_matches_inventory(proc, fixture_data):
    for step in proc["steps"]:
        eq = step["equipment"]
        assert eq["required_capability"] == proc["required_capability"]
        assert eq["compatible_device_models"] == proc["compatible_device_models"] and eq["components"]
    models = {e["device_model"] for e in fixture_data["equipment"] if e["capability"] == proc["required_capability"]}
    assert set(proc["compatible_device_models"]) <= models


def test_instructions_and_limitations_unchanged(proc):
    for step in proc["steps"]:
        assert step["instruction"].startswith(INSTRUCTION_STARTS[step["step_id"]])
    s4 = next(s for s in proc["steps"] if s["step_id"] == "S4")
    assert any("microgravity" in w for w in s4["warnings"])
    assert any("does not prove" in lim for lim in proc["safety_limitations"])


def test_older_database_receives_new_definition_and_sessions_keep_their_version(harness, symptom_payload):
    c = harness.start()
    case_id = c.post("/api/v1/symptoms", json=symptom_payload).json()["case_id"]
    sid = c.post("/api/v1/procedure-sessions", json={"case_id": case_id, "procedure_id": "PROC-BP-01",
                                                      "actor_id": "DEMO-001", "mode": "self"}).json()["session_id"]
    harness.stop()
    db = Path(harness.db_url.removeprefix("sqlite:///"))
    with sqlite3.connect(db) as conn:
        old = json.loads(conn.execute("SELECT definition FROM procedure_definitions").fetchone()[0])
        old["version"] = "1.0.0-demo"
        for s in old["steps"]:
            for k in ("visual", "equipment", "warnings", "target_region_id", "target_laterality", "target_site_id",
                      "patient_role", "instruction_source_ids"):
                s.pop(k)
        conn.execute("UPDATE procedure_definitions SET definition = ?, version = '1.0.0-demo'", (json.dumps(old),))
        conn.execute("UPDATE procedure_sessions SET procedure_version = '1.0.0-demo'")
    c = harness.start()
    p = c.get("/api/v1/procedures/PROC-BP-01").json()
    assert p["version"] == "1.1.0-demo" and len(p["visual_requirements"]) == 6
    session = c.get(f"/api/v1/procedure-sessions/{sid}").json()
    assert session["procedure_version"] == "1.0.0-demo" and session["current_step"]["visual"]["action_id"]
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT count(*) FROM audit_events WHERE action = 'configuration.synced'").fetchone()[0] == 1
    harness.restart()  # an unchanged fixture syncs nothing
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT count(*) FROM audit_events WHERE action = 'configuration.synced'").fetchone()[0] == 1


def test_frontend_visual_registry_covers_every_action(proc):
    """Joint gate (v3.1 §11): every required visual action has an implemented frontend entry."""
    if not VISUAL_REGISTRY.is_file():
        pytest.skip("Codex's visual-action registry is not in this checkout yet")
    src = VISUAL_REGISTRY.read_text(encoding="utf-8")
    missing = [r["action_id"] for r in proc["visual_requirements"] if r["action_id"] not in src]
    assert missing == []

"""Contract: committed shared/openapi.yaml must match the running app; baseline routes must exist."""
import json

import yaml

from app.config import REPO_DIR
from app.main import create_app

BASELINE = [
    ("get", "/healthz"),
    ("get", "/api/v1/demo/bootstrap"),
    ("post", "/api/v1/symptoms"),
    ("get", "/api/v1/cases/{case_id}"),
    ("post", "/api/v1/location/estimate"),
    ("post", "/api/v1/equipment/recommend"),
    ("get", "/api/v1/procedures/{procedure_id}"),
    ("post", "/api/v1/procedure-sessions"),
    ("post", "/api/v1/procedure-sessions/{session_id}/steps"),
    ("post", "/api/v1/measurements"),
    ("get", "/api/v1/research/osd-575"),
    ("post", "/api/v1/emergencies"),
    ("post", "/api/v1/demo/reset"),
    ("get", "/api/v1/research/datasets"),
    ("get", "/api/v1/research/datasets/{dataset_id}"),
    ("get", "/api/v1/research/datasets/{dataset_id}/records"),
    ("get", "/api/v1/environment/timeseries"),
    ("get", "/api/v1/radiation/timeseries"),
]


def _spec():
    return json.loads(json.dumps(create_app().openapi()))


def test_all_baseline_and_v21_routes_present():
    paths = _spec()["paths"]
    for method, path in BASELINE:
        assert method in paths.get(path, {}), f"missing {method.upper()} {path}"


def test_contract_version():
    assert _spec()["info"]["version"] == "2.11.1"


def test_committed_contract_matches_app():
    committed = yaml.safe_load((REPO_DIR / "shared" / "openapi.yaml").read_text(encoding="utf-8"))
    assert committed == _spec(), "Run: .venv/Scripts/python scripts/export_openapi.py"


def test_required_contract_fields():
    s = _spec()["components"]["schemas"]
    req = lambda name: set(s[name]["properties"])  # noqa: E731
    assert {"astronaut_id", "region_id", "laterality", "severity", "onset", "note"} <= req("SymptomCreate")
    assert {"symptom_id", "case_id", "case_state", "next_action"} <= req("SymptomCreated")
    assert {"zone_id", "confidence", "source", "observed_at"} <= req("LocationEstimateOut")
    assert {"equipment_id", "device_model", "zone_id", "readiness", "route_zone_ids", "procedure_id"} <= \
        req("EquipmentRecommendation")
    assert {"case_id", "procedure_id", "actor_id", "mode"} <= req("SessionCreate")
    assert {"step_id", "completion_source"} <= req("StepConfirm")
    assert {"case_id", "session_id", "astronaut_id", "type", "value", "unit", "source", "observed_at"} <= \
        req("MeasurementCreate")
    assert {"dataset_id", "source_url", "source_file", "records"} <= req("ResearchRecordsPage")
    assert {"astronaut_id", "responder_id", "trigger"} <= req("EmergencyCreate")

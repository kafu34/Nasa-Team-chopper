"""Part E: NASA OSD-575 ingestion, provenance, missing values, duplicates, registry, isolation."""
import csv
import json

import pytest

from app import models as m
from app.importers.osd575 import ImportFormatError, parse_number, parse_timepoint, parse_rows
from tests.conftest import REAL_CSV

ORDERED_TPS = ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"]


def _source_rows():
    with REAL_CSV.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def imported(harness):
    harness.add_real_csv()
    return harness.start(auto_import=True)


def test_real_csv_present_with_expected_shape():
    rows = _source_rows()
    assert len(rows) == 531
    assert list(rows[0].keys()) == ["ANALYTE", "VALUE", "RANGE_MIN", "RANGE_MAX", "UNITS", "TEST_TYPE",
                                    "SUBJECT_ID", "SEX", "timepoint"]


def test_parse_helpers():
    assert parse_number("NA") is None and parse_number("N/A") is None and parse_number("") is None
    assert parse_number("1.24") == 1.24 and parse_number("0") == 0.0
    with pytest.raises(ImportFormatError):
        parse_number("abc")
    assert parse_timepoint("L-92")[:2] == ("PREFLIGHT", -92)
    assert parse_timepoint("R+194")[:2] == ("POSTFLIGHT", 194)
    orders = [parse_timepoint(t)[2] for t in ORDERED_TPS]
    assert orders == sorted(orders)
    with pytest.raises(ImportFormatError):
        parse_timepoint("FD2")


def test_parse_rows_rejects_missing_columns():
    with pytest.raises(ImportFormatError, match="missing required columns"):
        parse_rows("ANALYTE,VALUE\nGLUCOSE,83\n")


def test_import_all_rows_with_provenance(imported):
    r = imported.get("/api/v1/research/osd-575")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["dataset_id"] == "OSD-575" and b["total"] == 531 and len(b["records"]) == 531
    assert b["source_url"] == "https://osdr.nasa.gov/bio/repo/data/studies/OSD-575"
    assert b["source_file"] == "LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv"
    assert len(b["provenance"]["sha256"]) == 64 and b["data_category"] == "NASA_RESEARCH"
    assert b["available_subjects"] == ["C001", "C002", "C003", "C004"]
    assert b["available_timepoints"] == ORDERED_TPS
    assert all(rec["data_category"] == "NASA_RESEARCH" for rec in b["records"])


def test_values_units_subjects_timepoints_preserved(imported):
    src = _source_rows()
    recs = {r["source_row_number"]: r for r in imported.get("/api/v1/research/osd-575").json()["records"]}
    for i, row in enumerate(src, start=1):
        rec = recs[i]
        assert rec["analyte"] == row["ANALYTE"] and rec["unit"] == row["UNITS"]
        assert rec["subject_id"] == row["SUBJECT_ID"] and rec["timepoint"] == row["timepoint"]
        assert rec["value_raw"] == row["VALUE"] and rec["range_max_raw"] == row["RANGE_MAX"]
        if row["VALUE"] not in ("NA", "N/A", ""):
            assert rec["value"] == float(row["VALUE"])
    first = recs[1]
    assert (first["analyte"], first["value"], first["range_min"], first["range_max"], first["unit"]) == \
        ("GLUCOSE", 83.0, 65.0, 99.0, "mg/dL")
    assert first["timepoint_phase"] == "PREFLIGHT" and first["timepoint_day_offset"] == -92
    assert {r["timepoint_phase"] for r in recs.values()} == {"PREFLIGHT", "POSTFLIGHT"}


def test_missing_values_are_null_not_zero(imported):
    src = _source_rows()
    recs = {r["source_row_number"]: r for r in imported.get("/api/v1/research/osd-575").json()["records"]}
    na_rows = [i for i, r in enumerate(src, start=1) if r["VALUE"] == "NA"]
    open_max = [i for i, r in enumerate(src, start=1) if r["RANGE_MAX"] == "N/A"]
    assert na_rows and open_max
    assert all(recs[i]["value"] is None and recs[i]["value_raw"] == "NA" for i in na_rows)
    assert all(recs[i]["range_max"] is None for i in open_max)
    detail = imported.get("/api/v1/research/datasets/OSD-575").json()
    assert detail["latest_import"]["missing_values"]["VALUE"] == len(na_rows)
    assert detail["latest_import"]["missing_values"]["RANGE_MAX"] == len(open_max)


def test_filters_and_pagination(imported):
    b = imported.get("/api/v1/research/osd-575", params={"subject_id": "C001", "analyte": "GLUCOSE"}).json()
    assert b["total"] == 7 and [r["timepoint"] for r in b["records"]] == ORDERED_TPS
    p = imported.get("/api/v1/research/datasets/OSD-575/records", params={"limit": 10, "offset": 20}).json()
    assert p["total"] == 531 and len(p["records"]) == 10 and p["offset"] == 20
    bad = imported.get("/api/v1/research/osd-575", params={"subject_id": "C999"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "UNKNOWN_FILTER_VALUE"
    assert imported.get("/api/v1/research/osd-575", params={"limit": 5000}).status_code == 422


def test_duplicate_import_is_skipped(imported, harness):
    from app.importers.osd575 import import_if_available

    with imported.app.state.session_factory() as db:
        result = import_if_available(db, harness.settings(True))
        assert result.outcome == "skipped_duplicate" and result.rows_imported == 0
        assert db.query(m.ResearchMeasurement).count() == 531
    c = harness.restart(auto_import=True)
    assert c.get("/api/v1/research/osd-575").json()["total"] == 531
    with c.app.state.session_factory() as db:
        assert db.query(m.DatasetImport).filter_by(status="IMPORTED").count() == 1


def test_import_log_written(imported, harness):
    logs = list((harness.tmp / "var" / "import_logs").glob("OSD-575_*.json"))
    assert len(logs) == 1
    log = json.loads(logs[0].read_text())
    assert log["outcome"] == "imported" and log["rows_imported"] == 531 and len(log["sha256"]) == 64


def test_absent_csv_returns_honest_unavailable(client):
    r = client.get("/api/v1/research/osd-575")
    assert r.status_code == 503 and r.json()["error"]["code"] == "DATASET_UNAVAILABLE"
    assert r.json()["error"]["details"]["status"] == "NOT_DOWNLOADED"
    assert r.json()["error"]["details"]["source_url"].endswith("OSD-575")


def test_ready_to_import_status(harness):
    harness.add_real_csv()
    c = harness.start(auto_import=False)
    d = c.get("/api/v1/research/datasets/OSD-575").json()
    assert d["status"] == "READY_TO_IMPORT" and d["records_available"] == 0


def test_malformed_csv_marks_import_failed(harness):
    (harness.raw / REAL_CSV.name).write_text("ANALYTE,VALUE\nGLUCOSE,83\n", encoding="utf-8")
    c = harness.start(auto_import=True)
    d = c.get("/api/v1/research/datasets/OSD-575").json()
    assert d["status"] == "IMPORT_FAILED" and "missing required columns" in d["status_reason"]
    assert c.get("/api/v1/research/osd-575").status_code == 503


def test_registry_lists_eight_canonical_ids(imported):
    b = imported.get("/api/v1/research/datasets").json()
    ids = [d["dataset_id"] for d in b["datasets"]]
    assert ids == ["OSD-575", "OSD-656", "NASA-EDA", "NASA-RADLAB", "OSD-654", "OSD-684", "OSD-573", "OSD-817"]
    st = {d["dataset_id"]: d["status"] for d in b["datasets"]}
    assert st["OSD-575"] == "IMPORTED" and all(v == "NOT_DOWNLOADED" for k, v in st.items() if k != "OSD-575")
    assert set(b["status_values"]) == {"NOT_DOWNLOADED", "READY_TO_IMPORT", "IMPORTED", "IMPORT_FAILED",
                                       "UNSUPPORTED_FORMAT"}
    assert imported.get("/api/v1/research/datasets/osd-575").status_code == 404  # case-sensitive


def test_unimported_datasets_and_timeseries_unavailable(imported):
    r = imported.get("/api/v1/research/datasets/OSD-656/records")
    assert r.status_code == 503 and r.json()["error"]["details"]["status"] == "NOT_DOWNLOADED"
    for path in ("/api/v1/environment/timeseries", "/api/v1/radiation/timeseries"):
        r = imported.get(path)
        assert r.status_code == 503 and r.json()["error"]["code"] == "DATASET_UNAVAILABLE"
    assert imported.get("/api/v1/environment/timeseries", params={"dataset_id": "OSD-575"}).status_code == 422


def test_research_isolated_from_demo_and_survives_reset(imported, symptom_payload):
    with imported.app.state.session_factory() as db:
        assert db.query(m.HealthObservation).filter(m.HealthObservation.source.like("%NASA%")).count() == 0
    r = imported.post("/api/v1/demo/reset").json()
    assert r["research_records_before"] == r["research_records_after"] == 531
    assert imported.get("/api/v1/research/osd-575").json()["total"] == 531
    b = imported.get("/api/v1/demo/bootstrap").json()
    assert all(o["data_category"] == "SIMULATED_ASTRONAUT" for o in b["observations"])
    assert {s["type"] for s in b["observation_status"]}.isdisjoint({r["analyte"] for r in
                                                                    imported.get("/api/v1/research/osd-575").json()["records"]})

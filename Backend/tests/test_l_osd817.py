"""OSD-817 (LSDS-135) TUNEL / CTB counts in ex vivo human optic-nerve tissue.

Synthetic TRANSFORMED CSVs below are TEST-ONLY inputs in the real NASA layout, written to a temporary folder.
The `real_817` tests copy the genuine NASA files (CSVs and SUBMITTED workbooks) from data/nasa/raw/OSD-817/.
"""
from __future__ import annotations

import csv
import shutil

import pytest

from app import models as m
from app.config import REPO_DIR
from app.importers import osd817

REAL_DIR = REPO_DIR / "data" / "nasa" / "raw" / "OSD-817"
TUNEL, CTB = osd817.ASSAYS["TUNEL"][0], osd817.ASSAYS["CTB"][0]
TEST_TUNEL = "﻿Sample Name,Counts,Normalized Counts\n7346_OD_FN,200,1\n7346_OS_FN,336,1.68\n"
TEST_CTB = "Sample Name,Counts,Normalized Counts,\n7346_OD_FN,202,1.00,\n7346_OS_FN,NA,0.76,\n,,,\n"


def write(harness, tunel=TEST_TUNEL, ctb=TEST_CTB):
    folder = harness.raw / "OSD-817"
    folder.mkdir(exist_ok=True)
    if tunel is not None:
        (folder / TUNEL).write_text(tunel, encoding="utf-8")
    if ctb is not None:
        (folder / CTB).write_text(ctb, encoding="utf-8")
    return folder


def page(c, **params):
    return c.get("/api/v1/research/datasets/OSD-817/records", params=params)


def test_not_downloaded(client):
    d = client.get("/api/v1/research/datasets/OSD-817").json()
    assert d["status"] == "NOT_DOWNLOADED" and d["record_schema"] == "HISTOLOGY_COUNTS_V1"
    assert page(client).status_code == 503


def test_partial_files_not_imported(harness):
    write(harness, ctb=None)
    c = harness.start(auto_import=True)
    assert c.get("/api/v1/research/datasets/OSD-817").json()["records_available"] == 0


def test_import_without_workbooks(harness):
    write(harness)
    c = harness.start(auto_import=True)
    d = c.get("/api/v1/research/datasets/OSD-817").json()
    assert d["status"] == "IMPORTED" and d["records_available"] == 8  # 2 assays x 2 samples x 2 measures
    assert d["latest_import"]["missing_values"]["CTB.counts"] == 1
    p = page(c, analyte="TUNEL", measure="counts").json()
    assert p["records"] == [] and p["total"] == 2 and p["study_type"] == "HUMAN_DERIVED_CELLS"
    r = p["histology_records"][0]
    assert r["sample_name"] == "7346_OD_FN" and r["donor_id"] == "7346" and r["eye"] == "OD"
    assert r["fixation"] == "FN" and r["value"] == 200 and r["value_raw"] == "200"
    assert r["group_number"] is None and r["annotation_file"] is None  # no workbook -> nothing invented
    assert r["data_category"] == "NASA_RESEARCH" and "astronaut_id" not in r
    na = page(c, analyte="CTB", subject_id="7346", measure="counts").json()["histology_records"]
    assert [x["value"] for x in na] == [202, None] and na[1]["value_raw"] == "NA"
    assert p["available_analytes"] == ["CTB", "TUNEL"] and p["available_measures"] == ["counts", "normalized_counts"]


def test_filters(harness):
    write(harness)
    c = harness.start(auto_import=True)
    r = page(c, analyte="PPD")
    assert r.status_code == 422 and r.json()["error"]["code"] == "UNKNOWN_FILTER_VALUE"
    r = page(c, timepoint="L-3")
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_FILTER_FOR_DATASET"
    r = page(c, gene_symbol="GFAP")
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_FILTER_FOR_DATASET"


def test_duplicate_skipped(harness):
    write(harness)
    c = harness.start(auto_import=True)
    with c.app.state.session_factory() as db:
        assert osd817.import_if_available(db, c.app.state.settings).outcome == "skipped_duplicate"
        assert db.query(m.HistologyCount).count() == 8


@pytest.mark.parametrize("tunel,needle", [
    ("Sample Name,Counts,Normalized Counts\nbad_sample,1,1\n", "unrecognised sample name"),
    ("Sample Name,Counts,Normalized Counts\n7346_OD_FN,abc,1\n", "non-numeric"),
    ("Sample Name,Counts,Normalized Counts\n7346_OD_FN,1,1\n7346_OD_FN,2,1\n", "duplicate sample"),
    ("Sample,Counts\n7346_OD_FN,1\n", "expected columns"),
])
def test_malformed_fails_atomically(harness, tunel, needle):
    write(harness, tunel=tunel)
    d = harness.start(auto_import=True).get("/api/v1/research/datasets/OSD-817").json()
    assert d["status"] == "IMPORT_FAILED" and needle in d["status_reason"] and d["records_available"] == 0


def test_separation_and_reset(harness, symptom_payload):
    write(harness)
    c = harness.start(auto_import=True)
    case = c.post("/api/v1/symptoms", json=symptom_payload).json()
    assert "7346_OD_FN" not in c.get(f"/api/v1/cases/{case['case_id']}").text
    reset = c.post("/api/v1/demo/reset").json()
    assert reset["research_records_before"] == reset["research_records_after"] == 8


# ----------------------------------------------------------------------------- the real NASA files


@pytest.fixture
def real_817(harness):
    if not (REAL_DIR / TUNEL).is_file():
        pytest.skip("real OSD-817 files not present")
    dst = harness.raw / "OSD-817"
    dst.mkdir()
    for pair in osd817.ASSAYS.values():
        for name in pair:
            shutil.copyfile(REAL_DIR / name, dst / name)
    return harness.start(auto_import=True)


def test_real_files_match_source_and_workbook(real_817):
    c = real_817
    d = c.get("/api/v1/research/datasets/OSD-817").json()
    assert d["status"] == "IMPORTED" and d["records_available"] == 72  # 2 assays x 18 eyes x 2 measures
    assert any("NOT mapped to pressure/tilt" in x for x in d["limitations"])
    for assay, (csv_name, _) in osd817.ASSAYS.items():
        with open(REAL_DIR / csv_name, encoding="utf-8-sig", newline="") as fh:
            rows = [r for r in csv.DictReader(fh) if (r.get("Sample Name") or "").strip()]
        recs = page(c, analyte=assay, limit=1000).json()["histology_records"]
        got = {(r["sample_name"], r["measure"]): r["value_raw"] for r in recs}
        want = {}
        for r in rows:
            want[(r["Sample Name"], "counts")] = r["Counts"]
            want[(r["Sample Name"], "normalized_counts")] = r["Normalized Counts"]
        assert got == want and len(rows) == 18
    p = page(c, analyte="TUNEL", subject_id="7346", measure="counts").json()
    od = {r["eye"]: r for r in p["histology_records"]}["OD"]
    assert od["group_number"] == "6" and od["donor_age"] == 64 and od["donor_sex"] == "Female"
    assert od["days_on_system"] == 14 and od["annotation_file"] == osd817.ASSAYS["TUNEL"][1]
    noted = page(c, analyte="CTB", subject_id="15380", measure="counts").json()["histology_records"]
    assert {r["eye"]: r["notes"] for r in noted}["OS"] == "Missing; Very faint stain - had to repeat"
    groups = {r["group_number"] for r in page(c, limit=1000).json()["histology_records"]}
    assert groups == {"1", "2", "3", "4", "5", "6"}
    assert len(page(c, limit=1).json()["source_files"]) == 4

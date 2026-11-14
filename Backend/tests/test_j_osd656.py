"""OSD-656 Inspiration4 urine inflammation panel (BIO_ASSAY_TABLE) importer and API.

Synthetic inputs below are TEST-ONLY files in the real NASA layout, written to a temporary folder. The
`real_656` tests copy the genuine NASA files from data/nasa/raw/OSD-656/ when present.
"""
from __future__ import annotations

import csv
import hashlib
import shutil

import pytest

from app import models as m
from app.config import REPO_DIR
from app.importers import osd656

REAL_DIR = REPO_DIR / "data" / "nasa" / "raw" / "OSD-656"

TEST_TABLE = ("Sample Name,il6_concentration_npq,,il6_percent_normalized_value,ifna1;_ifna13_concentration_npq\n"
              "C001_urine_L-92,10.5,99,100.1,NA\n"
              "C002_urine_R+1,11.25,98,NA,7.0\n")
TEST_TARGETS = ("Target,AlamarTargetID,UniProtID,ProteinName,GeneName\n"
                '"IL6, Human",t1,P05231,Interleukin-6,IL6\n'
                '"IFNA1; IFNA13, Human",t2,P01562,Interferon alpha-1/13,IFNA1\n')


def write(harness, table=TEST_TABLE, targets=TEST_TARGETS):
    folder = harness.raw / "OSD-656"
    folder.mkdir(exist_ok=True)
    (folder / osd656.SOURCE_FILE).write_text(table, encoding="utf-8")
    if targets is not None:
        (folder / osd656.TARGET_FILE).write_text(targets, encoding="utf-8")
    return folder


def page(c, **params):
    return c.get("/api/v1/research/datasets/OSD-656/records", params=params)


def test_not_downloaded_by_default(client):
    d = client.get("/api/v1/research/datasets/OSD-656").json()
    assert d["status"] == "NOT_DOWNLOADED" and d["study_type"] == "HUMAN_SPACEFLIGHT"
    assert osd656.SOURCE_FILE in d["status_reason"]
    assert page(client).status_code == 503


def test_import_values_annotation_and_skipped_blank_column(harness):
    write(harness)
    c = harness.start(auto_import=True)
    d = c.get("/api/v1/research/datasets/OSD-656").json()
    assert d["status"] == "IMPORTED" and d["records_available"] == 6  # 2 samples x 3 named columns
    li = d["latest_import"]
    assert li["missing_values"] == {"ifna1;_ifna13_concentration_npq": 1, "il6_percent_normalized_value": 1}
    assert "1 column(s) with an empty header" in li["message"]
    p = page(c, analyte="il6", subject_id="C001").json()
    assert p["records"] == [] and p["expression_records"] == [] and p["total"] == 2
    recs = {r["measure"]: r for r in p["assay_records"]}
    conc = recs["concentration_npq"]
    assert conc["value"] == 10.5 and conc["value_raw"] == "10.5" and conc["source_column"] == "il6_concentration_npq"
    assert conc["sample_name"] == "C001_urine_L-92" and conc["specimen"] == "urine"
    assert conc["timepoint"] == "L-92" and conc["timepoint_phase"] == "PREFLIGHT" and conc["timepoint_day_offset"] == -92
    assert conc["gene_name"] == "IL6" and conc["uniprot_id"] == "P05231" and conc["target_name"] == "IL6, Human"
    assert conc["data_category"] == "NASA_RESEARCH" and "astronaut_id" not in conc
    assert "99" not in {r["value_raw"] for r in page(c, limit=1000).json()["assay_records"]}  # blank column skipped
    na = page(c, subject_id="C002", analyte="il6", measure="percent_normalized_value").json()["assay_records"][0]
    assert na["value"] is None and na["value_raw"] == "NA"
    ifn = page(c, analyte="ifna1;_ifna13").json()["assay_records"]
    assert all(r["gene_name"] == "IFNA1" for r in ifn)  # matched on normalised target name
    assert p["available_measures"] == ["concentration_npq", "percent_normalized_value"]
    assert p["available_timepoints"] == ["L-92", "R+1"] and p["study_type"] == "HUMAN_SPACEFLIGHT"


def test_without_target_file_annotation_is_null(harness):
    write(harness, targets=None)
    recs = page(harness.start(auto_import=True), limit=1000).json()["assay_records"]
    assert recs and all(r["gene_name"] is None and r["uniprot_id"] is None for r in recs)


def test_duplicate_and_changed_target_file(harness):
    folder = write(harness)
    c = harness.start(auto_import=True)
    with c.app.state.session_factory() as db:
        assert osd656.import_if_available(db, c.app.state.settings).outcome == "skipped_duplicate"
        (folder / osd656.TARGET_FILE).write_text(TEST_TARGETS + "\n", encoding="utf-8")
        assert osd656.import_if_available(db, c.app.state.settings).outcome == "imported"
        assert db.query(m.AssayMeasurement).count() == 6


@pytest.mark.parametrize("table,needle", [
    ("Sample Name,il6_concentration_npq\nC001_urine_L-92,abc\n", "non-numeric"),
    ("Sample Name,il6_concentration_npq\nbad-sample,1\n", "unrecognised sample name"),
    ("Sample Name,il6_weird\nC001_urine_L-92,1\n", "unrecognised measurement column"),
    ("Sample Name,il6_concentration_npq\nC001_urine_L-92,1\nC001_urine_L-92,2\n", "duplicate sample"),
    ("Sample,il6_concentration_npq\nC001_urine_L-92,1\n", "first column must be 'Sample Name'"),
])
def test_malformed_fails_atomically(harness, table, needle):
    write(harness, table=table)
    c = harness.start(auto_import=True)
    d = c.get("/api/v1/research/datasets/OSD-656").json()
    assert d["status"] == "IMPORT_FAILED" and needle in d["status_reason"] and d["records_available"] == 0


def test_filters(harness):
    write(harness)
    c = harness.start(auto_import=True)
    r = page(c, measure="nope")
    assert r.status_code == 422 and r.json()["error"]["code"] == "UNKNOWN_FILTER_VALUE"
    r = page(c, gene_symbol="IL6")
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_FILTER_FOR_DATASET"
    harness.add_real_csv()
    c = harness.restart(auto_import=True)
    r = c.get("/api/v1/research/datasets/OSD-575/records", params={"measure": "concentration_npq"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_FILTER_FOR_DATASET"


def test_research_separation_and_reset(harness, symptom_payload):
    write(harness)
    c = harness.start(auto_import=True)
    case = c.post("/api/v1/symptoms", json=symptom_payload).json()
    assert "il6" not in c.get(f"/api/v1/cases/{case['case_id']}").text
    reset = c.post("/api/v1/demo/reset").json()
    assert reset["research_records_before"] == reset["research_records_after"] == 6


# ----------------------------------------------------------------------------- the real NASA file


@pytest.fixture
def real_656(harness):
    if not (REAL_DIR / osd656.SOURCE_FILE).is_file():
        pytest.skip("real OSD-656 file not present in data/nasa/raw/OSD-656/")
    dst = harness.raw / "OSD-656"
    dst.mkdir()
    for name in (osd656.SOURCE_FILE, osd656.TARGET_FILE):
        shutil.copyfile(REAL_DIR / name, dst / name)
    return harness.start(auto_import=True)


def test_real_file_counts_and_values(real_656):
    c = real_656
    with open(REAL_DIR / osd656.SOURCE_FILE, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    header, data = rows[0], rows[1:]
    named = [i for i, h in enumerate(header) if i > 0 and h.strip()]
    d = c.get("/api/v1/research/datasets/OSD-656").json()
    assert d["status"] == "IMPORTED" and d["records_available"] == len(data) * len(named) == 22 * 404
    assert sum(d["latest_import"]["missing_values"].values()) == 52
    assert d["latest_import"]["sha256"] == hashlib.sha256((REAL_DIR / osd656.SOURCE_FILE).read_bytes()).hexdigest()
    # every value equals the source cell (spot check every 37th column of every row)
    p = page(c, limit=1000, subject_id="C001", analyte="il6").json()
    assert {r["timepoint"] for r in p["assay_records"]} == {"L-92", "L-44", "R+45", "R+82"}
    for i in named[::37]:
        col = header[i]
        analyte, measure = osd656.MEASURE_RE.match(col).groups()
        recs = page(c, analyte=analyte, measure=measure, limit=1000).json()["assay_records"]
        by_sample = {r["sample_name"]: r["value_raw"] for r in recs}
        assert by_sample == {row[0]: row[i] for row in data}
    full = page(c, limit=1).json()
    assert len(full["available_analytes"]) == 203 and len(full["available_subjects"]) == 4
    assert full["available_timepoints"] == ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82"]

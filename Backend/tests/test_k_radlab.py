"""NASA-RADLAB: saved RadLab API snapshot importer and /radiation/timeseries.

Synthetic CSVs below are TEST-ONLY inputs in the real RadLab column layout, written to a temporary folder. The
`real_radlab` tests use the genuine snapshot in data/nasa/raw/NASA-RADLAB/ when present.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil

import pytest

from app import models as m
from app.config import REPO_DIR
from app.importers import radlab

REAL_DIR = REPO_DIR / "data" / "nasa" / "raw" / "NASA-RADLAB"
HEADER = ("timestamp,instrument_id,absorbed_dose_rate,altitude,dose_equivalent_rate,instrument_family,latitude,"
          "longitude,module,spacecraft\n")
TEST_CSV = (HEADER
            + '"2022-04-01T00:00:00","DosTel1",9.5,416.8,,"DosTel",-8.3,162.9,"Columbus","ISS"\n'
            + '"2022-04-01T00:00:00","REM-Lid",0.91,416.8,,"Timepix",-8.3,162.9,"Columbus","ISS"\n'
            + '"2022-04-01T00:01:00","DosTel1",10.25,416.9,12.5,"DosTel",-7.9,163.4,"Columbus","ISS"\n')


def write(harness, csv_text=TEST_CSV, query=True, sha=None):
    folder = harness.raw / "NASA-RADLAB"
    folder.mkdir(exist_ok=True)
    (folder / radlab.SOURCE_FILE).write_text(csv_text, encoding="utf-8")
    if query:
        digest = sha or hashlib.sha256((folder / radlab.SOURCE_FILE).read_bytes()).hexdigest()
        (folder / radlab.QUERY_FILE).write_text(json.dumps(
            {"query_url": "https://visualization.osdr.nasa.gov/radlab/api/?test", "sha256": digest}), encoding="utf-8")
    return folder


def ts(c, **params):
    return c.get("/api/v1/radiation/timeseries", params=params)


def test_not_downloaded_is_503(client):
    d = client.get("/api/v1/research/datasets/NASA-RADLAB").json()
    assert d["status"] == "NOT_DOWNLOADED" and d["study_type"] == "SPACEFLIGHT_ENVIRONMENT"
    r = ts(client)
    assert r.status_code == 503 and r.json()["error"]["code"] == "DATASET_UNAVAILABLE"


def test_import_values_units_and_provenance(harness):
    write(harness)
    c = harness.start(auto_import=True)
    d = c.get("/api/v1/research/datasets/NASA-RADLAB").json()
    assert d["status"] == "IMPORTED" and d["records_available"] == 4  # 3 absorbed + 1 dose-equivalent
    assert d["records_endpoint"] == "/api/v1/radiation/timeseries?dataset_id=NASA-RADLAB"
    assert d["latest_import"]["missing_values"] == {"absorbed_dose_rate": 0, "dose_equivalent_rate": 2}
    p = ts(c).json()
    assert p["metric"] == "absorbed_dose_rate" and p["unit"] == "μGy/hour" and p["total"] == 3
    assert p["available_metrics"] == ["absorbed_dose_rate", "dose_equivalent_rate"]
    assert p["available_instruments"] == ["DosTel1", "REM-Lid"] and p["study_type"] == "SPACEFLIGHT_ENVIRONMENT"
    first = p["points"][0]
    assert first["timestamp"].startswith("2022-04-01T00:00:00") and first["timestamp_raw"] == "2022-04-01T00:00:00"
    assert first["instrument_id"] == "DosTel1" and first["value"] == 9.5 and first["module"] == "Columbus"
    assert first["latitude"] == -8.3 and first["altitude"] == 416.8 and first["spacecraft"] == "ISS"
    assert p["provenance"]["source_url"] == "https://visualization.osdr.nasa.gov/radlab/api/?test"
    assert p["data_category"] == "NASA_RESEARCH" and any("not live data" in x for x in p["limitations"])
    eq = ts(c, metric="dose_equivalent_rate").json()
    assert eq["unit"] == "μSv/hour" and [x["value"] for x in eq["points"]] == [12.5]


def test_filters(harness):
    write(harness)
    c = harness.start(auto_import=True)
    assert ts(c, instrument_id="REM-Lid").json()["total"] == 1
    p = ts(c, start="2022-04-01T00:00:30Z", end="2022-04-01T00:02:00Z").json()
    assert [x["timestamp_raw"] for x in p["points"]] == ["2022-04-01T00:01:00"]
    assert ts(c, end="2022-04-01T00:00:00Z").json()["total"] == 0  # end is exclusive
    assert ts(c, limit=1, offset=1).json()["points"][0]["instrument_id"] == "REM-Lid"
    for params in ({"metric": "flux"}, {"instrument_id": "dostel1"}):
        r = ts(c, **params)
        assert r.status_code == 422 and r.json()["error"]["code"] == "UNKNOWN_FILTER_VALUE"
    r = c.get("/api/v1/research/datasets/NASA-RADLAB/records")
    assert r.status_code == 422 and r.json()["error"]["details"]["use_endpoint"] == "/api/v1/radiation/timeseries"
    assert c.get("/api/v1/environment/timeseries").status_code == 503  # EDA still not imported


def test_duplicate_import_skipped(harness):
    write(harness)
    c = harness.start(auto_import=True)
    with c.app.state.session_factory() as db:
        assert radlab.import_if_available(db, c.app.state.settings).outcome == "skipped_duplicate"
        assert db.query(m.TimeseriesValue).count() == 4


@pytest.mark.parametrize("kwargs,needle", [
    ({"query": False}, "query_url is required"),
    ({"sha": "0" * 64}, "does not match"),
    ({"csv_text": HEADER + '"bad-time","DosTel1",1,,,,,,,\n'}, "unrecognised timestamp"),
    ({"csv_text": HEADER + '"2022-04-01T00:00:00","DosTel1",abc,,,,,,,\n'}, "non-numeric absorbed_dose_rate"),
    ({"csv_text": "timestamp,instrument_id\n"}, "missing required columns"),
])
def test_malformed_fails_atomically(harness, kwargs, needle):
    write(harness, **kwargs)
    c = harness.start(auto_import=True)
    d = c.get("/api/v1/research/datasets/NASA-RADLAB").json()
    assert d["status"] == "IMPORT_FAILED" and needle in d["status_reason"] and d["records_available"] == 0
    assert ts(c).status_code == 503


def test_repeated_reading_kept_as_published(harness):
    write(harness, csv_text=HEADER + '"2022-04-01T00:00:00","DosTel1",1.5,,,,,,,\n'
                                     '"2022-04-01T00:00:00","DosTel1",1.25,,,,,,,\n')
    c = harness.start(auto_import=True)
    p = ts(c).json()
    assert sorted(x["value"] for x in p["points"]) == [1.25, 1.5]  # neither picked nor averaged
    with c.app.state.session_factory() as db:
        imp = db.query(m.DatasetImport).filter_by(dataset_id="NASA-RADLAB", status="IMPORTED").one()
        assert imp.summary["repeated_readings"] == {"2022-04-01T00:00:00 DosTel1": [1, 2]}


def test_separation_and_reset(harness, symptom_payload):
    write(harness)
    c = harness.start(auto_import=True)
    case = c.post("/api/v1/symptoms", json=symptom_payload).json()
    assert "DosTel" not in c.get(f"/api/v1/cases/{case['case_id']}").text
    assert "DosTel" not in c.get("/api/v1/demo/bootstrap").text
    reset = c.post("/api/v1/demo/reset").json()
    assert reset["research_records_before"] == reset["research_records_after"] == 4


# ----------------------------------------------------------------------------- the real snapshot


@pytest.fixture
def real_radlab(harness):
    if not (REAL_DIR / radlab.SOURCE_FILE).is_file():
        pytest.skip("real RadLab snapshot not present")
    dst = harness.raw / "NASA-RADLAB"
    dst.mkdir()
    for name in (radlab.SOURCE_FILE, radlab.QUERY_FILE):
        shutil.copyfile(REAL_DIR / name, dst / name)
    return harness.start(auto_import=True)


def test_real_snapshot_matches_source(real_radlab):
    c = real_radlab
    with open(REAL_DIR / radlab.SOURCE_FILE, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    query = json.loads((REAL_DIR / radlab.QUERY_FILE).read_text(encoding="utf-8"))
    assert query["sha256"] == hashlib.sha256((REAL_DIR / radlab.SOURCE_FILE).read_bytes()).hexdigest()
    numeric = [r for r in rows if r["absorbed_dose_rate"].strip()]
    d = c.get("/api/v1/research/datasets/NASA-RADLAB").json()
    assert d["status"] == "IMPORTED"
    p = ts(c, limit=5000).json()
    assert p["total"] == len(numeric) == 2847
    assert p["available_instruments"] == sorted({r["instrument_id"] for r in rows})
    by_row = {x["source_row_number"]: x for x in p["points"]}
    for n, r in enumerate(rows, start=1):  # every reading equals its source row, verbatim
        pt = by_row[n]
        assert (pt["timestamp_raw"], pt["instrument_id"]) == (r["timestamp"], r["instrument_id"])
        assert pt["value"] == float(r["absorbed_dose_rate"]) and pt["module"] == r["module"]
        assert pt["altitude"] == float(r["altitude"]) and pt["latitude"] == float(r["latitude"])
    assert p["provenance"]["source_url"] == query["query_url"]
    with c.app.state.session_factory() as db:
        imp = db.query(m.DatasetImport).filter_by(dataset_id="NASA-RADLAB", status="IMPORTED").one()
        assert len(imp.summary["repeated_readings"]) == 3

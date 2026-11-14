"""v2.2: OSD-195 / OSD-546 classification, processed gene-expression import, provenance and separation.

All expression files written here are SYNTHETIC TEST INPUTS created in a temporary folder to exercise the
parser. They are never copied into data/nasa/raw and are not NASA values.
"""
from __future__ import annotations

import hashlib

import pytest

from app import models as m
from app.importers import expression as ex

GSM_BEFORE, GSM_AFTER = "GSM2813749", "GSM2813750"  # subject 14, verified OSDR metadata


def f195(gsm: str) -> str:
    return f"GLDS-195_microarray_{gsm}_processed.txt"


def write_195(harness, gsm: str, body: str):
    folder = harness.raw / "OSD-195"
    folder.mkdir(exist_ok=True)
    p = folder / f195(gsm)
    p.write_text(body, encoding="utf-8")
    return p


TEST_195 = "ID_REF\tVALUE\n16657436\t5.25\n16657440\tNA\n16657450\t7.75\n"

SAMPLE_COLS = ["GSM2696758_R1211_FM_OM_1", "GSM2696761_R1211_FM_SM_1", "GSM2696765_R1211_GM_OM_1",
               "GSM2696768_R1234_GM_SM_1"]
TEST_546 = ("PROBESETID,ENSEMBL,SYMBOL," + ",".join(SAMPLE_COLS) + "\n"
            "7892501,ENSG000001,GENE_A,6.1,6.2,6.3,6.4\n"
            "7892502,ENSG000002,NA,8.0,NA,8.2,8.3\n")
TEST_546_TABLE = ('"sample","group"\n'  # same layout as the real NASA GLDS-546_array_SampleTable.csv
                  '"GSM2696758","(Space Flight & osteogenic)"\n"GSM2696761","(Space Flight & standard)"\n'
                  '"GSM2696765","(Ground Control & osteogenic)"\n"GSM2696768","(Ground Control & standard)"\n')


def write_546(harness, expr: str = TEST_546, table: str = TEST_546_TABLE):
    folder = harness.raw / "OSD-546"
    folder.mkdir(exist_ok=True)
    (folder / ex.OSD546_EXPRESSION).write_text(expr, encoding="utf-8")
    (folder / ex.OSD546_SAMPLE_TABLE).write_text(table, encoding="utf-8")


def datasets(c) -> dict:
    return {d["dataset_id"]: d for d in c.get("/api/v1/research/datasets").json()["datasets"]}


# ----------------------------------------------------------------------------- classification


def test_scientific_classification(client):
    d = datasets(client)
    assert d["OSD-195"]["study_type"] == "HUMAN_GROUND_ANALOGUE"
    assert d["OSD-546"]["study_type"] == "HUMAN_DERIVED_CELLS"
    assert d["OSD-575"]["study_type"] == "HUMAN_SPACEFLIGHT"
    assert d["OSD-654"]["study_type"] == "ANIMAL_RESEARCH" and d["OSD-654"]["organism"] == "Mus musculus"
    assert d["OSD-654"]["human_health_analysis"] == "SEPARATE_ANIMAL_RESEARCH"
    assert d["NASA-EDA"]["human_health_analysis"] == "ENVIRONMENT_CONTEXT"
    assert d["OSD-195"]["human_health_analysis"] == d["OSD-546"]["human_health_analysis"] == "PRIMARY_HUMAN_RESEARCH"
    assert d["OSD-195"]["body_systems"] == ["skeletal_muscle"] and d["OSD-546"]["body_systems"] == ["bone"]
    assert "muscle strength" in d["OSD-195"]["not_a_measurement_of"]
    assert "astronaut bone density" in d["OSD-546"]["not_a_measurement_of"]
    assert all(v["astronaut_specific_findings_allowed"] is False for v in d.values())
    assert all(v["data_category"] == "NASA_RESEARCH" for v in d.values())
    primary = {k for k, v in d.items() if v["human_health_analysis"] == "PRIMARY_HUMAN_RESEARCH"}
    assert "OSD-654" not in primary and all(d[k]["organism"] == "Homo sapiens" for k in primary)


def test_study_type_legend_includes_fictional_demo(client):
    legend = {t["study_type"] for t in client.get("/api/v1/research/datasets").json()["study_types"]}
    assert legend == {"HUMAN_SPACEFLIGHT", "HUMAN_GROUND_ANALOGUE", "HUMAN_DERIVED_CELLS", "ANIMAL_RESEARCH",
                      "SPACEFLIGHT_ENVIRONMENT", "FICTIONAL_DEMONSTRATION"}


def test_detail_states_limitations(client):
    d = client.get("/api/v1/research/datasets/OSD-195").json()
    assert d["record_schema"] == "GENE_EXPRESSION_V1" and d["priority"] == "P1"
    assert any("not a measurement of muscle mass, strength" in x for x in d["limitations"])
    assert "Nobody in this study flew" in d["experimental_context"]
    assert d["raw_dir"].endswith("OSD-195")


# ----------------------------------------------------------------------------- missing / unsupported files


def test_missing_files_reported_and_records_503(client):
    for ds_id in ("OSD-195", "OSD-546"):
        d = client.get(f"/api/v1/research/datasets/{ds_id}").json()
        assert d["status"] == "NOT_DOWNLOADED" and d["records_available"] == 0 and d["records_endpoint"] is None
        r = client.get(f"/api/v1/research/datasets/{ds_id}/records")
        assert r.status_code == 503 and r.json()["error"]["code"] == "DATASET_UNAVAILABLE"
    assert "GLDS-546_array_SampleTable.csv" in client.get("/api/v1/research/datasets/OSD-546").json()["status_reason"]


def test_raw_cel_only_is_unsupported_and_not_imported(harness):
    folder = harness.raw / "OSD-195"
    folder.mkdir()
    (folder / "GLDS-195_microarray_GSM2813750_ER24_S14_NBR_2_H05.CEL.gz").write_bytes(b"\x1f\x8b not parsed")
    c = harness.start(auto_import=True)
    d = c.get("/api/v1/research/datasets/OSD-195").json()
    assert d["status"] == "UNSUPPORTED_FORMAT" and "raw microarray processing is not implemented" in d["status_reason"]
    with c.app.state.session_factory() as db:
        assert db.query(m.GeneExpressionValue).count() == 0
        assert ex.import_dataset(db, c.app.state.settings, "OSD-195")[0].outcome == "unsupported_format"


def test_partial_osd546_download_is_reported(harness):
    folder = harness.raw / "OSD-546"
    folder.mkdir()
    (folder / ex.OSD546_EXPRESSION).write_text(TEST_546, encoding="utf-8")
    d = harness.start(auto_import=True).get("/api/v1/research/datasets/OSD-546").json()
    assert d["status"] == "UNSUPPORTED_FORMAT" and ex.OSD546_SAMPLE_TABLE in d["status_reason"]


# ----------------------------------------------------------------------------- OSD-195 import


@pytest.fixture
def imported195(harness):
    write_195(harness, GSM_BEFORE, TEST_195)
    write_195(harness, GSM_AFTER, "ID_REF\tVALUE\n16657436\t5.5\n16657440\t6.0\n16657450\t7.0\n")
    return harness.start(auto_import=True)


def test_osd195_import_values_provenance_and_missing(imported195, harness):
    c = imported195
    d = c.get("/api/v1/research/datasets/OSD-195").json()
    assert d["status"] == "IMPORTED" and d["records_available"] == 6
    page = c.get("/api/v1/research/datasets/OSD-195/records", params={"sample_id": GSM_BEFORE}).json()
    assert page["records"] == [] and page["total"] == 3 and page["study_type"] == "HUMAN_GROUND_ANALOGUE"
    vals = {r["probe_id"]: r for r in page["expression_records"]}
    assert vals["16657436"]["value"] == 5.25 and vals["16657436"]["value_raw"] == "5.25"
    assert vals["16657440"]["value"] is None and vals["16657440"]["value_raw"] == "NA"  # missing stays missing
    r0 = vals["16657436"]
    assert r0["subject_id"] == "14" and r0["condition_label"] == "Subject 14, before bed rest"
    assert r0["gene_symbol"] is None  # never inferred
    assert r0["normalization_verified"] is False and r0["source_column"] == "VALUE"
    assert r0["source_file"] == f195(GSM_BEFORE) and r0["source_row_number"] == 1
    assert r0["data_category"] == "NASA_RESEARCH" and "astronaut_id" not in r0
    files = {p["source_file"]: p for p in page["source_files"]}
    assert set(files) == {f195(GSM_BEFORE), f195(GSM_AFTER)}
    sha = hashlib.sha256((harness.raw / "OSD-195" / f195(GSM_BEFORE)).read_bytes()).hexdigest()
    assert files[f195(GSM_BEFORE)]["sha256"] == sha
    assert files[f195(GSM_BEFORE)]["source_url"] == "https://osdr.nasa.gov/bio/repo/data/studies/OSD-195"
    detail = c.get("/api/v1/research/datasets/OSD-195").json()["latest_import"]
    assert detail["missing_values"] in ({"value": 1}, {"value": 0})


def test_osd195_sample_matching_and_comparison_not_ready(imported195):
    page = imported195.get("/api/v1/research/datasets/OSD-195/records", params={"subject_id": "14"}).json()
    assert page["total"] == 6 and page["available_subjects"] == ["14"]
    samples = {s["sample_id"]: s for s in page["samples"]}
    assert len(samples) == 24 and samples[GSM_BEFORE]["imported"] and samples[GSM_AFTER]["imported"]
    assert samples[GSM_BEFORE]["factors"] == {"Bed Rest": "Before Bed Rest"}
    assert samples[GSM_AFTER]["factors"] == {"Bed Rest": "After Bed Rest"}
    assert samples[GSM_BEFORE]["factors_verified"] == {"Bed Rest": True}
    assert not samples["GSM2813727"]["imported"]
    cr = page["comparison_readiness"]
    assert cr["ready"] is False  # normalisation not yet verified verbatim
    assert any("subject(s): ['14']" in r for r in cr["reasons"])
    assert any("single pair cannot show a general effect" in r for r in cr["reasons"])


def test_osd195_single_sample_is_not_a_matched_pair(harness):
    write_195(harness, GSM_AFTER, TEST_195)
    page = harness.start(auto_import=True).get("/api/v1/research/datasets/OSD-195/records").json()
    cr = page["comparison_readiness"]
    assert cr["ready"] is False and any("No subject has both" in r for r in cr["reasons"])


def test_osd195_duplicate_import_skipped(imported195):
    c = imported195
    with c.app.state.session_factory() as db:
        results = ex.import_dataset(db, c.app.state.settings, "OSD-195")
        assert [r.outcome for r in results] == ["skipped_duplicate", "skipped_duplicate"]
        assert db.query(m.GeneExpressionValue).count() == 6


def test_osd195_changed_file_replaces_only_its_rows(imported195, harness):
    write_195(harness, GSM_AFTER, "ID_REF\tVALUE\n16657436\t9.0\n")
    c = harness.restart(auto_import=True)
    with c.app.state.session_factory() as db:
        assert db.query(m.GeneExpressionValue).filter_by(sample_id=GSM_AFTER).count() == 1
        assert db.query(m.GeneExpressionValue).filter_by(sample_id=GSM_BEFORE).count() == 3


def test_osd195_headerless_two_column_file(harness):
    write_195(harness, GSM_BEFORE, "# comment\n16657436\t5.25\n16657440\t6.5\n")
    page = harness.start(auto_import=True).get("/api/v1/research/datasets/OSD-195/records").json()
    assert page["total"] == 2 and page["expression_records"][0]["source_column"] == "(value)"


@pytest.mark.parametrize("body,needle", [
    ("ID_REF\tVALUE\n16657436\tabc\n", "non-numeric"),
    ("ID_REF\tVALUE\n16657436\t1.0\n16657436\t2.0\n", "duplicate probe ID"),
    ("ID_REF\tA\tB\n1\t2\t3\n", "single value column"),
    ("ID_REF\tVALUE\n", "no data rows"),
])
def test_osd195_malformed_file_fails_atomically(harness, body, needle):
    write_195(harness, GSM_BEFORE, body)
    c = harness.start(auto_import=True)
    d = c.get("/api/v1/research/datasets/OSD-195").json()
    assert d["status"] == "IMPORT_FAILED" and needle in d["status_reason"]
    assert d["records_available"] == 0
    assert c.get("/api/v1/research/datasets/OSD-195/records").status_code == 503


def test_osd195_unverified_sample_rejected(harness):
    write_195(harness, "GSM9999999", TEST_195)
    d = harness.start(auto_import=True).get("/api/v1/research/datasets/OSD-195").json()
    assert d["status"] == "IMPORT_FAILED" and "not in the verified OSD-195 sample metadata" in d["status_reason"]


# ----------------------------------------------------------------------------- OSD-546 import


def test_osd546_import_with_verified_groups(harness):
    write_546(harness)
    c = harness.start(auto_import=True)
    d = c.get("/api/v1/research/datasets/OSD-546").json()
    assert d["status"] == "IMPORTED" and d["records_available"] == 8
    page = c.get("/api/v1/research/datasets/OSD-546/records", params={"gene_symbol": "GENE_A"}).json()
    assert page["total"] == 4 and page["study_type"] == "HUMAN_DERIVED_CELLS"
    rec = {r["sample_id"]: r for r in page["expression_records"]}
    assert rec["GSM2696758"]["value"] == 6.1 and rec["GSM2696758"]["condition_label"] == \
        "Space Flight, osteogenic medium"
    assert rec["GSM2696765"]["subject_id"] is None
    assert rec["GSM2696758"]["normalization_verified"] is True
    assert "log2" in rec["GSM2696758"]["value_unit"]
    na = c.get("/api/v1/research/datasets/OSD-546/records", params={"probe_id": "7892502"}).json()
    by = {r["sample_id"]: r for r in na["expression_records"]}
    assert by["GSM2696761"]["value"] is None and by["GSM2696761"]["gene_symbol"] is None
    samples = {s["sample_id"]: s for s in page["samples"]}
    assert len(samples) == 13 and sum(s["imported"] for s in samples.values()) == 4
    assert samples["GSM2696758"]["factors"] == {"Spaceflight": "Space Flight", "Treatment": "osteogenic"}
    assert samples["GSM2696758"]["factors_verified"] == {"Spaceflight": True, "Treatment": True}
    cr = page["comparison_readiness"]
    assert cr["ready"] is True and any("same medium: ['osteogenic', 'standard']" in r for r in cr["reasons"])
    folder = harness.raw / "OSD-546"
    assert page["provenance"]["sha256"] == hashlib.sha256((folder / ex.OSD546_EXPRESSION).read_bytes()).hexdigest()


def test_osd546_changed_sample_table_triggers_reimport(harness):
    write_546(harness)
    c = harness.start(auto_import=True)
    with c.app.state.session_factory() as db:
        assert ex.import_dataset(db, c.app.state.settings, "OSD-546")[0].outcome == "skipped_duplicate"
    (harness.raw / "OSD-546" / ex.OSD546_SAMPLE_TABLE).write_text(TEST_546_TABLE + "\n", encoding="utf-8")
    with c.app.state.session_factory() as db:
        assert ex.import_dataset(db, c.app.state.settings, "OSD-546")[0].outcome == "imported"
        assert db.query(m.GeneExpressionValue).count() == 8


def test_osd546_sample_table_disagreement_fails(harness):
    bad = TEST_546_TABLE.replace("(Ground Control & osteogenic)", "(Space Flight & osteogenic)")
    write_546(harness, table=bad)
    d = harness.start(auto_import=True).get("/api/v1/research/datasets/OSD-546").json()
    assert d["status"] == "IMPORT_FAILED" and "disagrees with the verified OSDR factors" in d["status_reason"]


def test_osd546_sample_table_medium_disagreement_fails(harness):
    write_546(harness, table=TEST_546_TABLE.replace("(Space Flight & standard)", "(Space Flight & osteogenic)"))
    d = harness.start(auto_import=True).get("/api/v1/research/datasets/OSD-546").json()
    assert d["status"] == "IMPORT_FAILED" and "GSM2696761" in d["status_reason"]


def test_osd546_sample_missing_from_sample_table_fails(harness):
    write_546(harness, table='"sample","group"\n"GSM2696758","(Space Flight & osteogenic)"\n')
    d = harness.start(auto_import=True).get("/api/v1/research/datasets/OSD-546").json()
    assert d["status"] == "IMPORT_FAILED" and "is not listed in" in d["status_reason"]


# ----------------------------------------------------------------------------- filters and compatibility


def test_filters_must_match_schema(imported195, harness):
    harness.add_real_csv()
    c = harness.restart(auto_import=True)
    r = c.get("/api/v1/research/datasets/OSD-195/records", params={"analyte": "GLUCOSE"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_FILTER_FOR_DATASET"
    r = c.get("/api/v1/research/datasets/OSD-575/records", params={"sample_id": GSM_BEFORE})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_FILTER_FOR_DATASET"
    r = c.get("/api/v1/research/datasets/OSD-195/records", params={"sample_id": "GSM2813727"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "UNKNOWN_FILTER_VALUE"


def test_osd575_response_unchanged_shape(harness):
    harness.add_real_csv()
    page = harness.start(auto_import=True).get("/api/v1/research/osd-575").json()
    assert page["total"] == 531 and len(page["records"]) == 531
    assert page["expression_records"] == [] and page["samples"] == [] and page["comparison_readiness"] is None
    assert page["study_type"] == "HUMAN_SPACEFLIGHT" and len(page["source_files"]) == 1


# ----------------------------------------------------------------------------- research / patient separation


def test_research_never_enters_patient_workflow(imported195, symptom_payload):
    c = imported195
    case = c.post("/api/v1/symptoms", json=symptom_payload).json()
    case_text = c.get(f"/api/v1/cases/{case['case_id']}").text
    for token in (GSM_BEFORE, GSM_AFTER, "16657436", "OSD-195", "expression"):
        assert token not in case_text
    boot = c.get("/api/v1/demo/bootstrap").text  # lists dataset metadata only, never research values
    assert "16657436" not in boot and "expression_records" not in boot
    reset = c.post("/api/v1/demo/reset").json()
    assert reset["research_records_before"] == reset["research_records_after"] == 6
    assert c.get("/api/v1/research/datasets/OSD-195").json()["records_available"] == 6

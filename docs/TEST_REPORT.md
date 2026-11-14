# SENTINEL AI Backend — Test Report

Run date: 2026-11-14. Environment: Windows 11, Python 3.13.15, FastAPI 0.115.6, SQLAlchemy 2.0.36,
Pydantic 2.10.4, pytest 8.3.4. Commands run from `Backend/`.

## OSD-656 importer, run 2026-11-14

| Suite | Result |
|---|---|
| `.venv/Scripts/python -m pytest` | **123 passed, 0 failed** (adds 12 in `test_j_osd656.py`) |
| `scripts/http_smoke.py` | **22/22** (adds an OSD-656 check; reported `IMPORTED`) |
| `scripts/import_nasa.py --dataset OSD-656` with the real NASA file | `imported` 8,888 values (203 targets × 22 samples), 52 NA → null, 2 blank-header columns skipped. Re-run: `skipped_duplicate` |
| Spot check against the source | IL6 `concentration_npq`, C001, all 4 timepoints: API equals the CSV |

`test_j_osd656.py` covers:
- the not-downloaded state and a 503 from the records endpoint;
- values, `value_raw`, NA → null, timepoint parsing and target annotation, including the normalised
  `ifna1;_ifna13` match;
- skipping blank-header columns, and nulls when the target file is absent;
- duplicate imports, and a changed target file triggering a re-import;
- 5 malformed-file cases that must fail atomically, plus schema-specific filters;
- separation from the patient workflow, and reset safety;
- the **real NASA file**: 22 × 404 values, 52 NAs, SHA-256, every 37th column of every row equal to the
  source, 203 analytes, 4 subjects and 6 timepoints.

## v2.2 update (OSD-195 / OSD-546), run 2026-11-14

| Suite | Result |
|---|---|
| `.venv/Scripts/python -m pytest` | **111 passed, 0 failed** (86 earlier tests + 25 new in `test_i_expression.py`; two earlier tests updated for the 10-ID registry) |
| `scripts/export_openapi.py --check` | matches the app |
| `scripts/http_smoke.py` | **21/21** (adds OSD-195 and OSD-546 checks; OSD-546 reported `IMPORTED`) |
| `scripts/import_nasa.py` with the real NASA files | OSD-546 `imported` 432,861 values / 13 samples in about 17 s; re-run `skipped_duplicate`. OSD-195 `not_found` (no processed files). OSD-575 unchanged (531). |
| Spot check against the source | TSPAN6, probeset 8173941: all 13 API values equal the NASA CSV digit for digit |

`test_i_expression.py` covers:
- the classification of every dataset, OSD-654 kept apart as animal research, and the study-type legend;
- missing files (503 responses and status messages), raw CEL-only → `UNSUPPORTED_FORMAT`, and a partial
  OSD-546 download;
- OSD-195 import:
  - values, `value_raw`, NA → null, provenance and SHA-256;
  - verified before/after pairing and `comparison_readiness`;
  - duplicate imports, a changed file replacing only its own rows, and headerless files;
  - malformed files failing atomically (4 cases) and unverified samples being rejected;
- OSD-546 import with verified groups, failure when the SampleTable disagrees or lacks a sample;
- schema-specific filters and unchanged OSD-575 response shape;
- research values never appearing in case or bootstrap responses, and reset leaving them intact.

**Not covered:**
- **OSD-546:** the importer was run on the real NASA probeset table and SampleTable; the tests use synthetic
  files with the same layout.
- **OSD-195:** the parser has only been tested on synthetic files, because no real processed file was supplied.

## Results

| Suite | Command | Result |
|---|---|---|
| All pytest suites | `.venv/Scripts/python -m pytest` | **86 passed, 0 failed** |
| Contract drift | `.venv/Scripts/python scripts/export_openapi.py --check` | `shared/openapi.yaml matches the app.` |
| Real HTTP (uvicorn on 127.0.0.1:8765, temporary DB) | `.venv/Scripts/python scripts/http_smoke.py` | **19/19 checks passed** |
| NASA import CLI | `.venv/Scripts/python scripts/import_nasa.py` (run twice) | `imported` 531 rows, then `skipped_duplicate` |

| File | Tests | Covers |
|---|---|---|
| `test_a_demo.py` | 8 | health check, bootstrap identifiers, due assessment, observation freshness (current/stale/missing), data categories, persistence across restart, demo reset, error envelope |
| `test_b_cases.py` | 22 | symptom → case, state transitions + audit, duplicate symptom, joining an open case, high-severity priority, symptom validation (7 cases), unknown astronaut/case, acknowledge-not-resolve, transition table, observation validation (6 cases) and dedupe |
| `test_c_spatial.py` | 12 | fixture zone estimate, unknown/stale/disabled anchors, missing signals, conflicting signals + hysteresis, RSSI validation, manual confirmation, BP monitor recommendation and exclusions, route around closed hatch, stale readiness, unreachable zone, unknown inputs |
| `test_d_procedures.py` | 18 | procedure definition, session creation/reuse/validation, ordered + idempotent steps, incomplete session, measurement technical validation (11 cases), case update + single follow-up, follow-up becoming due |
| `test_e_research.py` | 15 | real CSV shape, parser helpers, missing-column rejection, 531-row import with provenance, value/unit/subject/timepoint preservation row by row, NA → null, filters + pagination, duplicate import, import log, absent file → 503, READY_TO_IMPORT, malformed file → IMPORT_FAILED, 8-ID registry + case sensitivity, unimported datasets/timeseries 503, research/demo isolation and reset safety |
| `test_f_emergency.py` | 6 | emergency with all anchors disabled, no treatment wording, duplicate activation, acknowledge-not-resolve on urgent case, validation, equipment assist as optional step |
| `test_g_smoke.py` | 1 | full 16-step canonical scenario incl. restart persistence, OSD-575 records, emergency with localisation unavailable, reset |
| `test_h_contract.py` | 4 | all 18 baseline + v2.1 routes present, version 2.1.0, committed YAML equals app, required request/response fields |

## Not tested / not covered

- Frontend integration (Codex's UI against this backend) — not run by the backend; the frontend must verify it
  displays the same OSD-575 values and units.
- Timeseries endpoints with real data (no EDA/RadLab importer; only the 503 path is tested).
- Linux/macOS case-sensitive file systems (developed on Windows; see folder-casing note in the handoff).
- Concurrent multi-client load.

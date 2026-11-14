# SENTINEL AI Backend — Test Report

Run date: 2026-11-14. Environment: Windows 11, Python 3.13.15, FastAPI 0.115.6, SQLAlchemy 2.0.36,
Pydantic 2.10.4, pytest 8.3.4. Commands run from `Backend/`.

## Contract 2.2.0 (Specification v3.1 Milestone 1, backend contracts), run 2026-11-14

| Suite | Result |
|---|---|
| `.venv/Scripts/python -m pytest` with `SENTINEL_FRONTEND_SITES` pointing at `anatomy-sites.ts` from `origin/main` (9430a3d) | **201 passed, 1 skipped, 0 failed** (adds 36 tests in `test_n_anatomy_contract.py`, `test_o_habitat_contract.py`, `test_p_procedure_visual.py`) |
| Skipped | `test_frontend_visual_registry_covers_every_action`: Codex's visual-action registry does not exist yet |
| `scripts/export_openapi.py --check` | matches the app (24 paths, version 2.2.0) |
| `scripts/http_smoke.py` | **25/25** (adds latest-location and habitat-map checks; procedure check now requires 6 distinct visual actions) |
| Live server restart on the existing database | contract 2.2.0; `zone_connections.hatch_id` added; procedure upgraded to 1.1.0-demo; map `HAB-01-map-1.1`; OSD-575, OSD-656, OSD-546, OSD-817 and RadLab still `IMPORTED` |

Existing tests changed only where the plan changed behaviour: the contract and procedure version strings, the
unknown-model error code (`UNKNOWN_SURFACE_MODEL`), and the surface-point equality check (the response now has
extra fields).

New tests cover:
- **anatomy:** the shared manifest equals the site registry; bootstrap model list and annotation kinds;
  `record_kind`; model version recorded and checked; mesh/attachment stored when the model declares no meshes;
  6 invalid attachments; declared meshes and triangle ranges; marker status for current, compatible,
  incompatible, retired and unregistered models (stored coordinates never rewritten); points stored before 2.2.0
  read as version 1.0.0;
- **procedure:** six distinct visual actions matching `visual_requirements`; validation level and sources;
  anatomy targets valid (left upper arm for S2-S5); equipment matches inventory; instruction text and
  limitations unchanged, microgravity warning on S4; an old database receives the new definition once while a
  running session keeps its version;
- **habitat:** fixture geometry consistent; 5 kinds of broken geometry detected; full map in one frame with the
  closed lab-medical hatch; route polyline through open hatches only, inside walkable space, same frame and map
  version as the map; closing the exercise-medical hatch makes the BP monitor unreachable and reopening restores
  the route; moved equipment loses its point; location display modes (zone_only, stale after 30 s, unavailable,
  manual 15 min); an old database gains hatch IDs and the new map version.

## 3D Anatomical Twin `surface_point`, run 2026-11-14

| Suite | Result |
|---|---|
| `.venv/Scripts/python -m pytest` with `SENTINEL_FRONTEND_SITES` pointing at Codex's `anatomy-sites.ts` (aa25e6b) | **165 passed, 0 failed** (adds 19 in `test_m_surface_point.py`) |
| Same suite without that file | the frontend-match test is skipped; all others pass |
| `scripts/export_openapi.py --check` | matches the app |
| `scripts/http_smoke.py` | **23/23** |
| Live server restart on the existing database | `symptom_reports.surface_point` column added; bootstrap lists 35 sites |

`test_m_surface_point.py` covers:
- the point is stored, returned on create and in the case, kept separate from the user's note, and recorded in
  evidence and audit;
- old clients without the field are unchanged, and the rules still use only the broad region;
- shoulder and elbow reports in one region are not deduplicated against each other, while a repeat of the same
  site is;
- 10 rejection cases (unknown site, region or side mismatch, wrong side of the model, unknown model, out of range,
  infinite, missing coordinate, extra field), none of which stores anything;
- midline sites and the chest inner-edge tolerance;
- the bootstrap catalogue, and the same 35 site IDs and region mapping as the frontend file;
- persistence across restart, reset, and upgrading a database created before the column existed.

## OSD-817 importer, run 2026-11-14

| Suite | Result |
|---|---|
| `.venv/Scripts/python -m pytest` | **146 passed, 0 failed** (adds 11 in `test_l_osd817.py`) |
| `scripts/http_smoke.py` | **23/23** (adds an OSD-817 check; reported `IMPORTED`) |
| Live server spot check | 34085_OD_FN TUNEL counts = 1560 and 34085_OS_FN = 682, both equal to the CSV |

`test_l_osd817.py` covers:
- the not-downloaded state, and nothing imported when only one of the two CSVs is present;
- an import without workbooks (group stays null and nothing is invented), and NA → null;
- filters, including 422 for a wrong-schema filter, and duplicate imports;
- 4 malformed-file cases that must fail atomically;
- separation from the patient workflow, and reset safety;
- the **real NASA files**: all 72 values equal the CSVs, the workbook annotation joins correctly (group, age,
  sex, days, notes), all six group numbers are present, and 4 source files are listed with their hashes.

## RadLab snapshot (NASA-RADLAB), run 2026-11-14

Run in the separate backend worktree (`Chopper/Nasa-Team-chopper-backend`, branch `backend/p0-v2.1`).

| Suite | Result |
|---|---|
| `.venv/Scripts/python -m pytest` | **135 passed, 0 failed** (adds 12 in `test_k_radlab.py`) |
| `scripts/http_smoke.py` | **22/22**: `/radiation/timeseries` now returns 200 (DosTel1: 1,192 readings) |
| `scripts/export_openapi.py` | contract regenerated (additive fields only) |

`test_k_radlab.py` covers:
- a 503 when the snapshot is missing;
- units, ISS position, `timestamp_raw`, and the query URL as provenance;
- the dose-equivalent metric, and the `instrument_id` / `start` / `end` / paging filters;
- unknown filter values (422) and the records endpoint redirect (422);
- duplicate imports;
- 5 malformed or tampered snapshot cases (missing `query.json`, hash mismatch, bad timestamp, non-numeric
  value, missing columns), each failing atomically;
- repeated readings kept as published, separation from the patient workflow, and reset safety;
- the **real snapshot**: all 2,847 readings equal their source rows, and the 3 repeated DosTel1 timestamps
  are recorded.

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

## P0 baseline results (first run, superseded by the sections above)

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
- `/environment/timeseries` with real data (no EDA importer; only the 503 path is tested). RadLab is covered
  by `test_k_radlab.py`.
- OSD-195 with real NASA files (only synthetic files; the processed files have not been supplied).
- Linux/macOS case-sensitive file systems (developed on Windows; see folder-casing note in the handoff).
- Concurrent multi-client load.
- Any v3.1 visual result (3D model, layers, animations, floor-plan rendering). These are Codex's; the backend
  tests only the data contracts.

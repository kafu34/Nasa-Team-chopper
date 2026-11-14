# SENTINEL AI Backend — Test Report

Run date: 2026-11-14. Environment: Windows 11, Python 3.13.15, FastAPI 0.115.6, SQLAlchemy 2.0.36,
Pydantic 2.10.4, pytest 8.3.4. Commands run from `Backend/`.

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

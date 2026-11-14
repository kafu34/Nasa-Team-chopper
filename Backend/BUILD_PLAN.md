# SENTINEL AI Backend — Build Plan (contract v2.1)

This plan implements the Claude Backend Master Prompt v2.0 and the Shared Synchronisation
Amendment v2.1. Every step maps to a requirement in those documents; nothing outside them is added
except small optional endpoints the prompt explicitly permits.

## Fixed design decisions (made up front so the build never stalls)

| Topic | Decision |
|---|---|
| Layout | `backend/app/` modular monolith: `main.py` (app factory), `config.py`, `db.py`, `models.py`, `schemas/`, `routers/`, `services/`, `importers/`, `errors.py`, `seed.py`. Tests in `backend/tests/`. Scripts in `backend/scripts/`. |
| Environment | `backend/.venv`, `requirements.txt`: fastapi, uvicorn, sqlalchemy 2, pydantic 2, pyyaml, pytest, httpx. |
| Database | SQLite file `backend/var/sentinel.db` (override with `SENTINEL_DB_URL`). Tests use a temporary file DB per test through `create_app(settings)`. |
| Single source of demo truth | `shared/fixtures/demo_scenario.json` is read by `seed.py`. Relative times (`*_minutes_ago`) are resolved at seed/reset time so the demo is always fresh and deterministic in shape. |
| Contract | FastAPI generates OpenAPI; `scripts/export_openapi.py` writes `shared/openapi.yaml` (`info.version: 2.1.0`). A test fails if the committed file drifts from the app. |
| Errors | Every non-2xx body: `{"error": {"code", "message", "details"}}`. 404 not found, 409 conflict/state, 422 validation, 503 dataset unavailable. |
| Data categories | `NASA_RESEARCH`, `SIMULATED_ASTRONAUT`, `SIMULATED_ENVIRONMENT_OR_DEVICE` on every record-bearing response. |
| Dataset states | `NOT_DOWNLOADED`, `READY_TO_IMPORT`, `IMPORTED`, `IMPORT_FAILED`, `UNSUPPORTED_FORMAT`. |
| NASA file | Copied unchanged to `data/nasa/raw/LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv`. Imported automatically on startup if present; also via `scripts/import_nasa.py`. Dedupe by SHA-256 + unique (dataset, file, row). `NA`/`N/A` → `null`. |
| Timepoints | `L-92` → phase `PREFLIGHT`, day offset −92; `R+1` → `POSTFLIGHT` (+1 day after return). Sort by (phase, offset). Never labelled in-flight. |
| Case states | `detected`, `investigating`, `awaiting_assessment`, `awaiting_results`, `action_required`, `monitoring`, `follow_up_due`, `escalated`, `resolved`, with an explicit transition table. Acknowledge never resolves. |
| Rules | Deterministic ruleset `RULESET-P0-1.0`; every decision writes an `AuditEvent` with rule ID and reason. |
| Location | Trusted anchor registry; reject unknown/disabled/stale (>30 s) signals; zone score = strongest valid RSSI per zone; confidence from margin to the runner-up; hysteresis with previous estimate (<60 s, margin <3 dB). No distances claimed. |
| Equipment | BFS over accessible zone connections; filter capability, readiness `verified_ready` and fresh (<24 h), supplies, accessibility; shortest route wins, ties by ID. Readiness is never inferred from BLE. |
| Measurement | `value: {systolic, diastolic, pulse?}`, `unit: mmHg`, `source` must be a simulated source. Technical checks only; no clinical interpretation. Requires a completed session for the same case. |
| Emergency | Synchronous, no dependency on location, equipment, NASA data or network. Explicit limitation: no reviewed mission emergency procedure → escalation instructions only, no treatment. |

## Steps

1. Create branch `backend/p0-v2.1`; create `backend/`, `shared/`, `docs/`, `data/nasa/raw/` (never touch `frontend/`).
2. Copy the owner's NASA CSV unchanged into `data/nasa/raw/` and record its SHA-256.
3. Create venv, `requirements.txt`, install, `backend/.gitignore`.
4. Write `shared/fixtures/demo_scenario.json` (astronaut, habitat, zones, anchors, BLE observations, 6+ equipment, procedure, scheduled assessment, observations, symptom, emergency, anatomical regions).
5. `config.py`, `db.py` (engine, session dependency, SQLite foreign keys), `errors.py` (error envelope + handlers).
6. `models.py`: all P0 entities + ScheduledAssessment, FollowUpTask, LocationEstimate, ResearchDataset, DatasetImport.
7. `seed.py`: load fixture, seed if empty, `reset_demo()` that deletes only synthetic tables.
8. `main.py` app factory: lifespan creates tables, seeds, auto-imports NASA; CORS for 127.0.0.1:5173 and localhost:5173; `/healthz`.
9. Schemas + routers: `/demo/bootstrap`, `/demo/reset`.
10. Tests part A: health, bootstrap, persistence across app restart, reset. Run.

**Review 1 (after step 10).** Check: identifiers in fixture exactly match the prompt (`DEMO-001`, `DEMO-002`, `HAB-01`, four zones, `blood_pressure`, `PROC-BP-01`, `OSD-575`)? Reset leaves research tables alone? Contract export not yet needed — but schemas must be explicit `response_model`s from the start so the export in step 21 needs no rework.
*Reflection:* the slowest risk is fixture/seed mismatch causing churn in every later step. Mitigation: seed reads the fixture directly (one source), and step 10 tests assert the fixture IDs. Efficiency gain: write the test `conftest.py` once here with a `client` fixture and a `restart()` helper reused by all later parts.

11. Case service: state machine, transition table, audit writer, attention block.
12. Symptom router + rules engine: region/laterality validation against fixture, dedupe window 10 min, link to configured assessment, next action. `GET /cases/{case_id}`. Optional `POST /cases/{id}/acknowledge`.
13. Observation service: optional `POST /observations` with catalogue validation; freshness (`current`/`stale`/`missing`) in bootstrap.
14. Tests part B: symptom, case creation/transitions, duplicates, observation validation, acknowledge-not-resolve. Run.
15. Location service + `POST /location/estimate` (+ optional `POST /location/confirm` manual).
16. Equipment service + `POST /equipment/recommend` with route and excluded reasons.
17. Tests part C: zone estimate, unknown/stale/missing/conflicting anchors, equipment suitability, readiness, route accessibility. Run.
18. Procedure endpoints: `GET /procedures/{id}`, `POST /procedure-sessions`, `POST /procedure-sessions/{id}/steps` (ordered, idempotent re-confirm, completion).
19. Measurement endpoint: technical validation, store, case update, assessment completion, follow-up creation without duplicates.
20. Tests part D: session creation, step confirmation, measurement validation errors, follow-up creation/dedupe. Run.

**Review 2 (after step 20).** Check: does measurement validation ever imply clinical normality (it must not)? Do step confirmations claim correct execution (they must not — `confirmation_note`)? Do routine tasks stay `interrupt: false`? Is every route still named exactly as the baseline list?
*Reflection:* NASA import (step 21) is the only competition-eligibility blocker and depends on nothing above except `models.py`; it was placed after the workflow because the prompt's work order puts it at item 9, but the CSV is already available, so no blocker exists. Efficiency gain: the importer is a pure function (`parse_csv` → rows) tested without HTTP, so failures are isolated from routing.

21. OSD-575 importer (`importers/osd575.py`): column validation, provenance, null handling, timepoint parsing, SHA-256 dedupe, import log (DB `DatasetImport` + JSON log file under `backend/var/import_logs/`). CLI `scripts/import_nasa.py`.
22. Dataset registry for the 8 canonical IDs (status computed from DB + raw file presence, unverified metadata flagged honestly).
23. Research routers: `/research/osd-575` (filters subject/analyte/timepoint, pagination), `/research/datasets`, `/research/datasets/{id}`, `/research/datasets/{id}/records`, `/environment/timeseries`, `/radiation/timeseries` (503 `DATASET_UNAVAILABLE` with source link until imported).
24. Tests part E: ingestion, provenance/subject/timepoint/unit preservation, missing values, duplicate import, absent file → honest 503, registry statuses, research/demo isolation. Run.
25. Emergency service + `POST /emergencies` (no location needed, dedupe repeated activation, urgent attention).
26. Tests part F: emergency without localisation, urgent case not resolved by acknowledge. Run.
27. Integrated smoke test: the 16-step canonical scenario over real HTTP state (TestClient) plus one real `uvicorn` run hit with HTTP.
28. Export `shared/openapi.yaml`; add drift test.
29. Docs: `API.md`, `BACKEND.md`, `NASA_DATASETS.md`, `INTEGRATION_HANDOFF.md`, `TEST_REPORT.md` (with real results).
30. Full test run, commit on branch, report.

**Review 3 (after step 30).** Check against the amendment: 5 research endpoints present, `/research/osd-575` still compatible, 8 IDs case-sensitive everywhere, three data categories, five dataset states, null not zero, no research values in demo astronaut records, P1 importers not claimed. Check against the master prompt: 13 baseline endpoints, docs list, no frontend files touched, no public deploy/push without approval.
*Reflection:* docs and the OpenAPI file are generated last because they depend on final schemas; generating the contract from code (not by hand) removes the risk of contradictory definitions. The drift test makes later edits safe for Codex. Pushing to a shared remote branch is outward-facing, so it waits for the owner's go-ahead.

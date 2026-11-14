# SENTINEL AI Backend

Offline-capable FastAPI modular monolith that runs one complete, persisted astronaut medical-assistance
workflow plus a NASA research-data API. **Research demonstration prototype — not a clinically validated medical
device.** No diagnoses, prescriptions, invasive instructions or treatment plans are produced.

## Run

```bash
cd Backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
.venv/Scripts/python -m pytest                    # unit + integration tests
.venv/Scripts/python scripts/http_smoke.py        # canonical scenario over real HTTP (temporary DB)
.venv/Scripts/python scripts/export_openapi.py    # regenerate shared/openapi.yaml after schema changes
.venv/Scripts/python scripts/import_nasa.py       # (re)import OSD-575; safe to repeat
```

Environment variables (optional): `SENTINEL_DB_URL` (default `sqlite:///Backend/var/sentinel.db`),
`SENTINEL_NASA_RAW_DIR` (default `data/nasa/raw`), `SENTINEL_FIXTURE_PATH`, `SENTINEL_VAR_DIR`,
`SENTINEL_AUTO_IMPORT=0` to disable import on start.

Stack: Python 3.13, FastAPI 0.115, Pydantic 2, SQLAlchemy 2, SQLite, PyYAML, Pytest, httpx, Uvicorn.
No Docker, PostgreSQL, Redis, cloud service, paid API or internet dependency.

## Layout

```
Backend/
  app/
    main.py            app factory, startup (create tables, seed, auto-import), CORS
    config.py          settings, CONTRACT_VERSION 2.1.0, RULESET_VERSION RULESET-P0-1.0
    db.py              engine, sessions, UTC datetime column
    errors.py          error envelope and handlers
    models.py          SQLite models (synthetic tables + research tables)
    seed.py            seeds/resets from shared/fixtures/demo_scenario.json
    schemas/           Pydantic request/response models (the contract)
    services/          rules, cases, observations, spatial, procedures, emergency, datasets, audit
    routers/           demo, cases, spatial, procedures, research, emergency
    importers/osd575.py NASA OSD-575 CMP importer
  scripts/             export_openapi.py, import_nasa.py, http_smoke.py
  tests/               pytest suites A–H
```

## Persistence

SQLite tables: `astronauts`, `habitats`, `zones`, `zone_connections`, `wireless_anchors`, `equipment`,
`procedure_definitions`, `health_observations`, `scheduled_assessments`, `medical_cases`, `symptom_reports`,
`follow_up_tasks`, `procedure_sessions`, `assessment_measurements`, `location_estimates`, `emergency_events`,
`audit_events` (synthetic) and `dataset_imports`, `research_measurements` (NASA). Foreign keys are enforced and
lookup columns indexed. All workflow state survives restarts (tested). The demo seeds itself only when the
database is empty.

## Workflow logic

**Rules engine (`services/rules.py`, RULESET-P0-1.0)** — deterministic and audited:
R-SYM-00 validate region/laterality/onset; R-SYM-01 identical report within 10 min is a duplicate;
R-SYM-02 open or join the astronaut's open routine case (`detected → investigating`); R-SYM-03 link the
configured scheduled assessment (`→ awaiting_assessment`) — a fictional configuration, not a clinical indication;
R-SYM-04 severity ≥ 8 raises priority to urgent and advises notifying the crew medical officer.

**Case state machine (`services/cases.py`)** — explicit transition table over `detected, investigating,
awaiting_assessment, awaiting_results, action_required, monitoring, follow_up_due, escalated, resolved`.
Invalid transitions return 409. Acknowledgement records who/when and never changes state or resolves.

**Location (LOC-P0-1.0)** — trusted anchor registry; rejects unknown, disabled, stale (>30 s) and future
signals; zone score = strongest valid RSSI per zone; confidence = min(0.95, 0.5 + margin/30 dB); hysteresis keeps
a recent estimate when signals conflict (<3 dB). Missing signals → `zone_id: null, source: unavailable`.
No distances are computed. Manual confirmation supported.

**Equipment (EQ-P0-1.0)** — BFS over accessible connections; requires capability match, readiness
`verified_ready` checked within 24 h, all required supplies, reachable zone. Shortest route wins. Signal
strength never ranks equipment; a BLE advertisement never implies readiness.

**Procedures** — `PROC-BP-01` v1.0.0-demo (educational, paraphrased from general published home
blood-pressure guidance, not mission-approved). Sessions in self or responder mode; ordered, idempotent step
confirmations recorded as acknowledgements only.

**Measurements** — simulated sources only; structure, integer types, unit, plausible input range,
systolic > diastolic, timestamp within session and not in the future, session/case/astronaut association,
one measurement per session. Passing is technical validity, not clinical normality. On success: stored (plus
derived observations), scheduled assessment completed, case `awaiting_results → monitoring`, one 24 h
follow-up created (never duplicated), follow-ups become `due` lazily when the case is read.

**Emergency** — synchronous, local only; creates an urgent `emergency` case in `escalated`, records patient,
responder, trigger and time, raises a simulated crew alert, queues flight-surgeon escalation, states that no
reviewed emergency procedure is loaded, and offers equipment assistance as an optional secondary step. It does
not depend on localisation, equipment, AR, NASA data, cloud AI or Earth communication.

**Attention** — urgent items `interrupt: true`; routine items and follow-ups `interrupt: false`.

## Offline operation

Everything runs from local files: SQLite database, JSON fixture, stored procedure definitions and the local
NASA CSV. The browser frontend talks to this server over localhost or a local network; it does not run backend
workflows itself if the server is unavailable.

## Which data is what

| Data | Category | Origin |
|---|---|---|
| DEMO-001/002, symptoms, cases, observations, BP reading | `SIMULATED_ASTRONAUT` | Fictional fixture and user input |
| HAB-01, zones, anchors, BLE signals, equipment | `SIMULATED_ENVIRONMENT_OR_DEVICE` | Fictional fixture |
| OSD-575 CMP values | `NASA_RESEARCH` | Genuine NASA OSDR file, imported unchanged (see `NASA_DATASETS.md`) |

## Submission technical notes

- **Problem and impact**: on a Mars-class mission, a non-medical crew member must notice health changes, decide
  what to measure, find working equipment, perform the assessment correctly and follow up — without real-time
  help from Earth. SENTINEL turns that into one guided, persisted workflow.
- **Workload reduction**: the backend decides the next action, links the due assessment, finds the nearest
  *ready and supplied* device and an accessible route, serves step-by-step instructions, validates the reading,
  schedules the follow-up and keeps routine items noninterruptive. In an emergency it skips all routine steps.
- **Explainability**: every decision writes an audit event with the rule ID and ruleset version; location and
  equipment responses list what was rejected and why.
- **Medical limitations / future validation**: procedures are educational demo content; thresholds are input
  plausibility only; no clinical interpretation; emergency guidance is escalation only. Real use would need
  flight-surgeon-reviewed procedures, validated devices and positioning, clinical validation of rules, and
  regulatory review.

## Deferred (not implemented)

Done since P0: OSD-656, RadLab (saved ISS snapshot), OSD-546 and OSD-817 importers; the OSD-195 importer
(waiting for NASA's processed files); the optional 3D `surface_point` on symptoms.

P1 still open: NASA-EDA importer (`/environment/timeseries` returns 503); OSD-195 data; additional OSD-575
assays; multiple habitats; more procedures and observation categories; symptom-history analysis; richer
attention scheduling.

P2: real wearables/BLE/UWB, live AR, body-scan twin, advanced clinical models, medical data compression and
DTN networking, onboard mission integration; OSD-654, OSD-684 and OSD-573 importers.

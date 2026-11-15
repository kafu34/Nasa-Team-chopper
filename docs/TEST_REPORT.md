# SENTINEL AI Backend — Test Report

Run date: 2026-11-14. Environment: Windows 11, Python 3.13.15, FastAPI 0.115.6, SQLAlchemy 2.0.36,
Pydantic 2.10.4, pytest 8.3.4. Commands run from `Backend/`.

## Contract 2.11.0 (inventory and controlled closure, plan steps 41–43), run 2026-11-15

| Suite | Result |
|---|---|
| `.venv/Scripts/python -m pytest` (same environment variables as 2.6.0) | **355 passed, 0 failed, 0 skipped** (adds 9 in `test_za_inventory_closure.py`) |
| `scripts/export_openapi.py` | regenerated (52 paths, version 2.11.0) |
| `scripts/http_smoke.py` | **47/47** (adds the inventory list and a blocked resolution) |
| Live server restart | contract 2.11.0; new case columns added; 5 datasets still `IMPORTED`; every device reports `readiness_check_stale` because its readiness checks date from 2026-11-14 (expected; reset or re-verify) |

The tests cover:
- **Inventory:** usability reasons; a device out of service invalidating its route and leaving no device;
  restocking another device making it the pick; `verified_ready` counting as a fresh check, and a device move
  being audited with before and after values; validation (unknown device, supply or zone, invalid readiness,
  ground role refused, no-change); an in-progress session listed but not cancelled.
- **Closure:** blockers listed together and cleared step by step; explicit follow-up cancellation; resolution
  recorded and audited; a second resolution refused; a new symptom opening a new case; an open concern blocking;
  role refusals; an urgent emergency case resolving with its priority kept, no longer interrupting, and an
  unacknowledged-message warning.

## Contracts 2.9.0 and 2.10.0 (Milestones 6–7 software part, plan steps 35–40), run 2026-11-15

| Suite | Result |
|---|---|
| `.venv/Scripts/python -m pytest` (same environment variables as 2.6.0) | **346 passed, 0 failed, 0 skipped** (adds 13 in `test_y_screening_access.py` and 14 in `test_z_comms_env_recovery.py`) |
| `scripts/export_openapi.py` | regenerated (49 paths, version 2.10.0) |
| `scripts/http_smoke.py` | **45/45** (adds assessments, access roles, a comms message, environment context with 4 RadLab readings, and recovery) |
| Live server restart | contract 2.10.0; the sync added SA-PO-001 and SA-TEMP-001 to the existing database; new tables created; environment context shows 4 RadLab readings; 5 datasets still `IMPORTED` |

The tests cover:
- **Screening:** due, upcoming and overdue states; symptoms still link only BP; deduplicated durable reminders;
  acknowledging without completing; an upcoming assessment becoming due; starting a screening without a symptom
  and completing it with a measurement (recurrence, reminders closed, second start refused); a pending-request
  conflict; a BP symptom reading completing the BP screening; an old database receiving the schedule.
- **Roles:**
  - the published matrix;
  - the flight surgeon closing a concern, and ground support refused for both close and continue;
  - viewer-checked reads (own record, medical officer, flight surgeon, ground support refused, unknown 404),
    audited;
  - acknowledgement and recompute roles;
  - ground personnel refused at hatches.
- **Communications:**
  - delay, then delivery, then receiver-only acknowledgement (idempotent);
  - sending roles;
  - an idempotent resend;
  - an outage queueing messages, with urgent first after restore and one transmission at a time;
  - a sent message continuing through an outage;
  - an emergency queueing one urgent escalation (deduplicated);
  - a ground reply acknowledged by the crew.
- **Environment:** attribution and caution flags; the real RadLab snapshot imported and shown with source file
  and row.
- **Recovery:**
  - the recovery list;
  - a restart in the middle of a session, an outage and a concern;
  - a restart in the middle of a transmission, delivered on time;
  - safe resend of an observation and a message;
  - reset clearing comms and restoring the link.

## Contract 2.8.0 (pulse oximeter and thermometer procedures, plan step 34), run 2026-11-15

| Suite | Result |
|---|---|
| `.venv/Scripts/python -m pytest` (same environment variables as 2.6.0) | **319 passed, 0 failed, 0 skipped** (adds 20 in `test_x_more_procedures.py`) |
| `scripts/export_openapi.py` | regenerated (38 paths, version 2.8.0) |
| `scripts/http_smoke.py` | **40/40** (adds the procedure list and the PROC-PO-01 visual requirements) |
| Live server restart | contract 2.8.0; configuration sync added both procedures and the device links to the existing database; 5 datasets still `IMPORTED` |

The tests cover:
- the procedure list;
- the complete visual contract of each new procedure (sources, regions, sites, devices, disclaimers, microgravity
  caveat);
- 16 action IDs, unique across all procedures;
- PROC-BP-01 identical to the fixture;
- full PO and TEMP runs with their derived observations;
- 8 measurement-validation cases (type mismatch, range, unit, shape, non-integer SpO2);
- BP still valid;
- device recommendation returning the new procedures;
- an SpO2 concern requesting PROC-PO-01, refusing PROC-BP-01 and completing through PO while the concern stays
  open;
- a temperature concern requesting PROC-TEMP-01;
- an old database receiving the procedures and device links.

Two existing tests changed, as planned: the ruleset version is now DET-1.1, and an SpO2 concern now moves its
case to `awaiting_assessment`.

## Contract 2.7.0 (history, live scenarios, review role check), run 2026-11-15

| Suite | Result |
|---|---|
| `.venv/Scripts/python -m pytest` (same environment variables as 2.6.0) | **299 passed, 0 failed, 0 skipped** (adds 11 in `test_w_history_scenarios_roles.py`) |
| `scripts/export_openapi.py` | regenerated (37 paths, version 2.7.0) |
| `scripts/http_smoke.py` | **38/38** (adds the history read, a 403 for a crew-member close, and the three scenarios) |
| Live server restart | contract 2.7.0; history returns the live database's readings; 5 datasets still `IMPORTED` |

The tests cover:
- history order, origin, detection and baseline flags, filters, paging and validation, and procedure readings;
- each scenario's state (due reassessment completed by one reading; urgent interruption in the session; emergency
  in `urgent_events`), isolation between scenarios, and an unknown scenario;
- a crew member closing a concern (403, audited, state unchanged) and the medical officer closing it;
  `continue_monitoring` by a crew member; a baseline recompute by a crew member (403); and role codes in
  bootstrap.

## Contract 2.6.0 (proactive health intelligence, Milestone 5 backend), run 2026-11-15

| Suite | Result |
|---|---|
| `.venv/Scripts/python -m pytest` with `SENTINEL_FRONTEND_SITES`, `SENTINEL_FRONTEND_HUMAN_GLB` and `SENTINEL_FRONTEND_VISUAL_REGISTRY` set (the registry is Codex's **uncommitted** draft `Frontend/src/visual-registry.ts`) | **288 passed, 0 failed, 0 skipped** (adds 31: 20 in `test_u_health_intelligence.py`, 11 in `test_v_priority_followup.py`) |
| `scripts/export_openapi.py` | regenerated (35 paths, version 2.6.0) |
| `scripts/http_smoke.py` | **33/33** (adds a batch that opens a DET-1.0 concern, the monitoring view, a concern read and the frozen-baseline 409) |
| Live server restart | contract 2.6.0; new tables and columns added; version-1 baselines created (heart rate 66, SpO2 98, body temperature 36.7); 5 datasets still `IMPORTED` |

The tests cover the v3.1 §7 scenarios:
- **A, sustained change:** 3 consecutive valid readings open a concern and an investigation with no symptom.
  The configured PROC-BP-01 is requested; SpO2 opens a below-only concern with no configured assessment. A
  reading back in range breaks the run. A concern joins an existing symptom case. Batch ingestion works in time
  order and is all-or-nothing.
- **B, bad or missing data:** poor and stale deviating readings open no concern and no case. An excluded reading
  does not reset a run. A missing baseline gives no comparison. Missing, stale and poor data appear only as
  data-quality items.
- **C, duplicates:** equivalent readings update one concern; 3 suppressed alerts are counted and audited; there
  is one case, one evidence line and one reassessment. An identical resubmission is not counted. One new alert
  is raised after the suppression window.
- **D, urgent event:** an urgent symptom during a routine procedure:
  - interrupts the session;
  - stays urgent after the reading and after the follow-up becomes due;
  - keeps the urgent instruction first;
  - makes earlier follow-ups interrupt.

  An emergency during the procedure appears in `urgent_events` and the session is not cancelled. A second urgent
  event is audited without a second raise. Detection on an urgent case keeps it urgent.
- **E, follow-up:**
  - readings back in range do not close a concern, and closing early is refused;
  - a fair-quality reading cannot complete the reassessment;
  - a good reading after the due time completes it, and the concern then waits for review;
  - closing does not resolve the case, and the recompute that follows excludes all 10 readings from the concern
    period;
  - a persisting change schedules a new reassessment, and a new deviation reopens the concern;
  - `continue_monitoring` works;
  - state survives a restart, and an old database is upgraded.

Also tested: baseline versioning, the freeze, no automatic update, recompute validation, the published ruleset,
and reset.

Defect found and fixed: `scripts/http_smoke.py` sent the server log to a pipe it never read. Once the log passed
about 4 KB (4,118 bytes after the new checks), uvicorn blocked writing to it and `POST /demo/reset` timed out. The
script now writes the log to `var/http-smoke/server.log`.

## Contract 2.5.0 (habitat operations, Milestone 4 backend), run 2026-11-15

| Suite | Result |
|---|---|
| `.venv/Scripts/python -m pytest` with `SENTINEL_FRONTEND_SITES`, `SENTINEL_FRONTEND_HUMAN_GLB` and `SENTINEL_FRONTEND_VISUAL_REGISTRY` set (the registry is Codex's **uncommitted** draft `Frontend/src/visual-registry.ts`) | **257 passed, 0 failed, 0 skipped** (adds 18 in `test_s_habitat_operations.py` and `test_t_movement_simulation.py`) |
| `scripts/export_openapi.py` | regenerated (28 paths, version 2.5.0) |
| `scripts/http_smoke.py` | **29/29** (adds recommendation read-back, a movement run and a hatch change) |
| `scripts/simulate_movement.py` | walk 9/9 ticks in an acceptable zone; passage conflict 5/5 with low confidence and smoothing; missing anchor 0/3 correct but every tick capped at 0.5 with `laboratory` unobserved; stale 2/2 unavailable |
| Live server restart | contract 2.5.0; `habitats.state_version` and `equipment_recommendations` added; 5 datasets still `IMPORTED` |

The tests cover:
- recommendations stored and read back;
- closing a route hatch invalidates both affected recommendations and leaves medical unreachable;
- opening the lab-medical hatch gives the new route via `H-CQ-LAB` and `H-LAB-MED`;
- an unrelated hatch keeps the recommendation;
- opening a hatch invalidates active recommendations;
- no-change and validation cases (404 and 403);
- hatch state survives a restart and reset restores it;
- a responder route from a confirmed location;
- `START_REQUIRED` and `LOCATION_UNAVAILABLE` (none or stale);
- uncertain-start candidates and hop spread;
- the unobserved-neighbour confidence cap;
- an old database upgrade;
- simulation:
  - moving between compartments, with the latest estimate following;
  - repeatability;
  - conflicting passage signals;
  - a missing anchor flagged rather than confident;
  - stale observations giving unavailable;
  - ground truth absent from the location, map and recommendation responses and from stored estimates;
  - unknown scenario or astronaut.

Known limitation found by testing: with the laboratory's only enabled anchor failed, the engine still picks
crew quarters. It now reports that at 0.5 confidence with the laboratory flagged, instead of 0.63–0.67 with no
warning. A zone-only BLE engine cannot do better without an anchor in that zone.

## Contract 2.4.0 (procedure session state, Milestone 3 backend), run 2026-11-15

| Suite | Result |
|---|---|
| `.venv/Scripts/python -m pytest` with `SENTINEL_FRONTEND_SITES` and `SENTINEL_FRONTEND_HUMAN_GLB` set (Codex's files at 0240a94) | **238 passed, 1 skipped, 0 failed** (adds 21 in `test_r_procedure_session_state.py`; the skip is still the visual-registry check) |
| `scripts/export_openapi.py` | regenerated (25 paths, version 2.4.0) |
| `scripts/http_smoke.py` | **26/26** (session now binds the recommended device; adds an events check for all six steps) |
| Live server restart | contract 2.4.0; `procedure_sessions.equipment_id`/`equipment_snapshot` added; `procedure_step_events` created; 5 datasets still `IMPORTED` |

`test_r_procedure_session_state.py` covers:
- binding the recommended device;
- rejecting an incompatible, unknown-readiness, missing-cuff, unknown or stale-readiness device;
- no device switch on a reused session, and late binding on an open session;
- events recorded apart from acknowledgement, with no change to step order, session status or case state;
- 6 invalid-event cases that store nothing;
- `client_event_id` idempotence, and the `visual_unavailable` stage;
- a full run where all seven stages complete, including a rejected wrong-device reading;
- restore after restart (identical step states and device), and reset removing events;
- an old database gaining the session columns, and events audited as visual-only records.

## Contract 2.3.0 (`sentinel-human-male-v1` registration), run 2026-11-15

| Suite | Result |
|---|---|
| `.venv/Scripts/python -m pytest` with `SENTINEL_FRONTEND_SITES` and `SENTINEL_FRONTEND_HUMAN_GLB` pointing at Codex's files from `origin/main` (43e2703) | **217 passed, 1 skipped, 0 failed** (adds 16 in `test_q_human_model.py`; the skip is still the visual-registry check) |
| `scripts/export_openapi.py` | regenerated (24 paths, version 2.3.0) |
| `scripts/http_smoke.py` | **25/25** |
| Live server restart | contract 2.3.0; bootstrap lists `sentinel-body-v1` and `sentinel-human-male-v1`, both active |

`test_q_human_model.py` covers:
- the registration (asset, licence, skin mesh with 40,676 triangles, the same 35 sites, plausibility bands);
- the manifest's byte count and SHA-256 against the real GLB;
- right-shoulder persistence across a restart and case reopen (model, version, mesh, site, side, local point,
  attachment);
- the left counterpart, and v1 markers kept on their own model;
- the shared-fixture region mismatch;
- 9 rejection cases (wrong side, height band, missing mesh, muscle mesh, outside bounds, local point mismatch,
  triangle range, numeric version "1", coordinate limit);
- the front/back face check, and a non-selectable mesh.

Not covered: exact surface contact (the backend has no triangle data), and a real ray-cast tap. Codex's browser
test must cover that.

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

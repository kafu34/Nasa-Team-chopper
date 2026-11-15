# SENTINEL AI Backend — Build Plan for Engineering Specification v3.1

This plan follows the owner's planning rule from the original Master Prompt: the steps describe how the backend is
built, they never deviate from the specifications (v2.0, v2.1, v2.2, v3.1), every 10th step is followed by a
review and a reflection, and the system is built part by part. Only `Backend/`, `shared/` and `docs/` are
changed. `Frontend/` is read-only for Claude (Codex owns it).

The earlier plan (`BUILD_PLAN.md`, contract v2.1) is complete and stays as the record of P0.

## 1. Gap report (from the code on `backend/p0-v2.1` at b3c13b0 and `origin/main` at 9430a3d)

Status words follow v3.1 §12. "Backend" means only Claude's part; no visual feature is reported complete here.

| v3.1 area | Backend status before this plan | Evidence | Missing for the backend |
|---|---|---|---|
| §3 Contract | PARTIAL | `shared/openapi.yaml` v2.1.0 generated and drift-tested | v3.1 schemas below; version bump |
| §4 Anatomical Twin (Claude part) | PARTIAL | `surface_point` with `model_id`, `site_id`, x/y/z; region and side validated; persisted | model version, mesh ID, triangle + barycentric attachment, model registry, marker migration status, annotation-kind distinction |
| §5 Procedure Coach (Claude part) | PARTIAL | PROC-BP-01 with 6 text steps, ordered sessions, measurement validation, follow-up | per-step visual contract fields, validation level, displayed/viewed/replayed events, equipment identity on session, PROC-PO-01 and PROC-TEMP-01 |
| §6 Habitat (Claude part) | PARTIAL | 4 zones, connection graph, zone-only BLE estimate, BFS routing with exclusions | polygons in metres, coordinate frame, hatches, anchor and equipment positions, route network and geometry, location display modes, latest/stale location, hatch state changes, movement simulator, multi-crew access |
| §7 Autonomous health intelligence | NOT STARTED (only freshness current/stale/missing) | `services/observations.py` | baselines, versioning, windows, trends, persistence, auto-investigation, dedupe, urgent protection, scenarios A–E |
| §8 Communications, roles, attention manager | NOT STARTED / PARTIAL | `attention` block on cases only | queues with delay and acknowledgement, role-based access, notification priority |
| §9 NASA research integrity | COMPLETE for imported data (simulated-and-tested level is n/a; real data) | 165 tests, importers for OSD-575/656/546/817, RadLab | keep intact through every migration; OSD-195 BLOCKED (processed files not supplied) |
| §10 Cross-system workflow | PARTIAL | backend steps 1–5, 9–12 exist | map/route/visual steps need the contracts below and Codex's rendering |

## 2. Fixed design decisions (taken now so the build never stalls)

| Topic | Decision |
|---|---|
| Contract version | `2.2.0`. All changes are additive except one: an unknown `surface_point.model_id` now returns `422 UNKNOWN_SURFACE_MODEL` instead of the generic `VALIDATION_ERROR`. Paths stay under `/api/v1`. |
| Anatomical model registry | One JSON manifest per model in `shared/anatomy/<model_id>.json` (backend-owned, shared). It lists model version, kind, coordinate frame, status, declared mesh IDs (or `null` = not declared), sites → broad region + side, and earlier versions with a `coordinates_compatible` flag. Codex supplies the details of a new mesh model; Claude adds the manifest. |
| Marker attachment | Optional `mesh_id` and `attachment {triangle_index, barycentric[3]}` beside the model-local x/y/z. Barycentric values are 0–1 and sum to 1 ± 0.001. Mesh IDs are validated only when the manifest declares them. |
| Marker migration | On read, each stored point gets `marker_status`: `current`, `model_version_changed` (same model, older compatible version), `model_version_incompatible` or `model_retired`; and `render_hint`: `exact_point` or `site_only`. Old markers are never moved onto another surface silently. |
| Annotation kinds | `surface_selection`, `region_classification`, `patient_reported_symptom`, `monitoring_concern`, `verified_finding`. SENTINEL never creates `verified_finding`. Symptoms carry `record_kind = patient_reported_symptom`. |
| Procedure visual contract | Every step carries `target_region_id`, `equipment`, `instruction_source`, `visual {action_id, asset_id, additional_asset_ids, camera {view, target_region_id}, expected_visible_action, replay_allowed}`, `warnings`, `requires_confirmation`. Action IDs are unique per step. Procedure carries `validation_level` (`EDUCATIONAL_DEMONSTRATION`, `SIMULATED_EQUIPMENT_WORKFLOW`, `HARDWARE_TESTED_WORKFLOW`, `MISSION_APPROVED_PROCEDURE`) and `visual_requirements`. |
| Procedure re-sync | Procedure definitions are configuration: on startup they are upserted from the fixture, so a database created earlier receives the new step fields. Sessions keep their own `procedure_version`. |
| Habitat geometry | Lives in the fixture under `habitat.geometry`. Frame `HAB-01-D1-LOCAL`: origin at the deck's south-west outer corner, +x east, +y north, metres, 2D per deck. Compartments and passages are polygons; each connection has a `hatch_id`; route network nodes are zone navigation references and hatch points. Rooms are convex rectangles so straight segments stay inside walkable space. |
| Geometry check | The app refuses to start if geometry is inconsistent (point outside its zone, connection without hatch, unknown IDs). |
| Routing geometry | Route = zone path (unchanged BFS) + polyline through navigation reference → hatch → navigation reference. The start is the zone's navigation reference and is labelled as such; no precise patient position is fabricated. |
| Location display mode | `zone_only`, `estimated_xy` (never produced by the current zone engine), `unavailable`, `stale`. `position` stays `null` for zone-only estimates. |

## 3. Steps

### Milestone 1 + 2 (backend part) — contracts and marker storage

**Part A — anatomy**
1. Generate `shared/anatomy/sentinel-body-v1.json` from the current 35 sites without changing any value.
2. Turn `services/surface_sites.py` into a registry that loads every manifest in `shared/anatomy/`; keep `SITES`, `MODEL_ID` and `catalogue()` working for existing callers and tests.
3. Extend `SurfacePoint`: `model_id` becomes a validated string, plus optional `model_version`, `mesh_id`, `attachment`. Extend `SurfacePointOut` with `model_version`, `marker_status`, `render_hint`.
4. Validation: unknown model, unknown version, mesh rules, attachment needs a mesh, barycentric range and sum. The stored form always records the model version.
5. Marker status on read (migration strategy) in one helper used by create and case responses.
6. `record_kind` on symptoms; bootstrap adds `surface_models` and `anatomical_annotation_kinds` (keeps `surface_model`).
7. Tests `test_n_anatomy_contract.py`; update the one old test that expected `VALIDATION_ERROR` for an unknown model.
8. Run the full suite.

**Part B — procedure visual contract**
9. Extend the fixture's PROC-BP-01: version `1.1.0-demo`, `validation_level`, six distinct visual actions, step equipment, region, source, camera, expected visible action and warnings (including the microgravity positioning caveat). Instruction text is unchanged.
10. Upsert procedure definitions from the fixture on startup.

**Review 1 (after step 10).** Check: do the new procedure fields change any instruction text, safety limitation or measurement rule (they must not)? Is every anatomy change additive for Codex's current client (it sends `model_id`, `site_id`, x/y/z only)? Does the manifest file reproduce the 35 sites exactly (the frontend-match test proves it)?
*Reflection:* the slowest risk is schema churn in the procedure output breaking `ProcedureOut` response validation. Mitigation: define the new step model once in `schemas/procedures.py` with every field required, and let the fixture test fail first. Efficiency: the procedure upsert reuses the seed's own mapping, so there is one code path for fresh and upgraded databases.

11. `ProcedureStep` / `ProcedureOut` schemas with the new fields and `visual_requirements`.
12. Tests `test_p_procedure_visual.py`: distinct actions, required fields, valid regions, equipment capability exists in inventory, upgrade of an old database, and a check against Codex's visual registry when one is checked out (skipped otherwise).

**Part C — habitat geometry**
13. Fixture `habitat.geometry`: frame, deck, compartments, passages with hatches, navigation references, anchor positions, equipment positions, route network.
14. `hatch_id` on `ZoneConnection` (column + `add_missing_columns`), seeded from the fixture.
15. `services/habitat.py`: build the map from fixture geometry plus live database state; startup geometry check.
16. `GET /api/v1/habitats/{habitat_id}/map`.
17. Equipment recommendation adds `map_version`, `coordinate_frame`, `start_reference`, `route_hatch_ids`, `route_geometry`.
18. Location estimates add `display_mode`, `position`, `map_version`; new `GET /api/v1/location/{astronaut_id}/latest` returns the newest estimate and marks it `stale` after 30 s.
19. Tests `test_o_habitat_contract.py`: geometry consistency, polygons contain their points, closed hatch shown, route polyline follows passages and avoids the closed hatch, display modes, stale latest.
20. Run the full suite, regenerate `shared/openapi.yaml`, run `scripts/http_smoke.py`.

**Review 2 (after step 20).** Check: does any response now imply a precise astronaut position (it must not)? Are route coordinates and map in the same frame and version? Do research counts stay identical (no NASA data lost)? Did any existing test need a behaviour change other than the planned model-ID error code?
*Reflection:* the risk is that Codex needs a different shape. Mitigation: publish the contract in the handoff with a "Codex confirmation needed" list before building M3–M5 on top of it. Efficiency: hatch state lives in the existing `ZoneConnection.accessible` column, so the later hatch-change endpoint (step 25) only flips that value and routing already reacts.

21. Docs: `API.md`, `INTEGRATION_HANDOFF.md` (v3.1 contract section and confirmation list), `TEST_REPORT.md`, `BACKEND.md` (stale spots found in review), this plan's status table.
22. Commit on `backend/p0-v2.1` (local). Pushing and merging wait for the owner.

### Milestone 3 (backend part) — procedure session state
23. Session `equipment_id` (must be compatible with the procedure and match inventory); `POST /procedure-sessions/{id}/events` for `instruction_displayed`, `animation_viewed`, `animation_replayed`; per-step state in `SessionOut`; session stages `device_reading_received`, `technical_validation`, `assessment_completed`, `follow_up_created`.
    Detailed sub-steps (planned 2026-11-15, after Codex confirmed 2.3.0 and started the visual coach):
    - 23.1 Model `ProcedureStepEvent` (event_id, session_id, step_id, event_type, visual_action_id, client_event_id,
      actor_id, occurred_at, recorded_at); reset deletes it; unique (session_id, client_event_id).
    - 23.2 Columns `procedure_sessions.equipment_id` and `procedure_sessions.equipment_snapshot` (JSON) via
      `add_missing_columns`.
    - 23.3 `SessionCreate.equipment_id` (optional). Rules: device exists (404); capability, model and
      `compatible_procedure_ids` match the procedure (422 `EQUIPMENT_INCOMPATIBLE`); readiness verified and fresh
      (409 `EQUIPMENT_NOT_READY`). The snapshot stores model, zone and readiness at start. Reusing an in-progress
      session with another device returns 409 `SESSION_EQUIPMENT_MISMATCH`.
    - 23.4 Event types `instruction_displayed`, `animation_viewed`, `animation_replayed`, `visual_unavailable`.
      Rules: the step exists (422 `UNKNOWN_STEP`); `visual_action_id` equals the step's (422
      `VISUAL_ACTION_MISMATCH`); a repeated `client_event_id` returns the first event (`duplicate: true`).
      Events never change step order, session status or case state.
    - 23.5 `SessionOut` gains `equipment`, `step_states[]` (displayed_at, view_count, replay_count, last_viewed_at,
      visual_unavailable, acknowledged_at, completion_source), `stages[]` (instruction_displayed, animation_viewed,
      steps_acknowledged, device_reading_received, technical_validation, assessment_completed, follow_up_created)
      and `visual_note`.
    - 23.6 `MeasurementCreate.equipment_id` (optional) must equal the session's device (422 `EQUIPMENT_MISMATCH`).
24. Tests `test_r_procedure_session_state.py`: equipment rules, event rules and idempotence, stages through a full
    run, restore after restart, events not changing order or state, reset, old database upgrade. Then contract
    export, smoke test, live restart, docs, commit.

### Milestone 4 (backend part) — habitat operations
25. `POST /habitats/{id}/hatches/{hatch_id}` (open/close, audited, role-checked); routes recomputed; earlier recommendations marked invalid.
26. Repeatable movement simulator (`scripts/simulate_movement.py` + service) with separate ground truth, generated observations and backend estimate; ground truth never returned by user-facing endpoints.
27. Route start from responder or patient location; uncertainty: when confidence < 0.7, route from each candidate zone and report the spread.
28. Tests: movement between compartments, conflicting, missing and stale anchors, hatch change invalidating a route.
    Detailed sub-steps (planned 2026-11-15; the picture guide is Codex's work, so the backend moves to M4):
    - 25.1 Table `equipment_recommendations` (id, case, equipment, start zone, route zones, route hatches,
      habitat state version, status `active|invalidated`, invalidated reason/time). `recommend` stores each result
      and returns `recommendation_id`, `status`, `habitat_state_version`.
    - 25.2 `Habitat.state_version` column (starts at 1). Hatch change: body `{state: open|closed, actor_id,
      reason}`; 404 unknown hatch; actor must be a registered crew member of this habitat (full role-based access is
      step 36, documented as PARTIAL); unchanged state returns `changed: false`. A change flips
      `ZoneConnection.accessible`, bumps `state_version`, audits, and invalidates every active recommendation
      that uses the closed hatch (closing) or every active recommendation (opening, because a shorter route may
      now exist). The response lists the invalidated IDs.
    - 25.3 `GET /equipment/recommendations/{id}` returns the stored recommendation with its status. Map gains
      `state_version`.
    - 26.1 Fixture `movement_scenarios`: waypoints in the map frame, ticks per segment, seed, noise, dropped
      anchors, observation age. Four scenarios: walk crew-quarters -> medical, stand in the CQ-EX passage
      (conflicting), lab with its enabled anchor failed (missing), stale observations.
    - 26.2 `services/simulation.py`: ground truth (interpolated points, true zone by polygon), generated RSSI
      (log-distance model, wall attenuation, seeded noise; documented as a simulation, not a calibrated radio
      model), backend estimate through the normal `spatial.estimate`. Ground truth is returned only inside an
      `evaluation` block of the simulation endpoint and never by map, location or recommendation endpoints.
    - 26.3 `POST /simulation/movement` `{scenario_id, astronaut_id}` and `scripts/simulate_movement.py`.
    - 27.1 `EquipmentRecommendRequest`: `zone_id` becomes optional; new optional `astronaut_id` and
      `start_role: patient|responder`. Without `zone_id` the start is the astronaut's latest estimate; stale or
      unavailable gives 409 `LOCATION_UNAVAILABLE` (manual confirmation advised).
    - 27.2 When the start estimate's confidence is below 0.7, `start_uncertainty` lists every candidate zone
      within 6 dB of the best with its route hops to the chosen device and the spread.
    - 28.1 Tests `test_s_habitat_operations.py` and `test_t_movement_simulation.py`.

### Milestone 5 (backend part) — proactive health intelligence
29. Baseline model (versioned, per astronaut and observation type, quality rules, frozen while a concern is open so deterioration never becomes the new normal).
30. Detection rules `DET-1.0` (window, sustained-change count, data-quality gate) creating `monitoring_concern` findings and investigations.
    Detailed sub-steps (planned 2026-11-15; contract 2.6.0; every value is fictional demonstration configuration):
    - 29.1 Fixture `baseline_method` (`BASELINE-1.0`): per type `min_samples`, `window_days`, allowed qualities
      (`good`, `fair`), centre = median, spread = 1.4826 × MAD with a per-type floor. Fixture `baseline_history`:
      fictional daily resting readings for DEMO-001 (heart rate, SpO2, body temperature), seeded as simulated
      observations. Sleep and blood pressure get no history, so they show `insufficient_data`.
    - 29.2 Table `health_baselines` (baseline_id, astronaut, type, version, status `active|superseded`, method,
      centre, spread, sample count, window, source observation IDs, created by, reason). Seed creates version 1.
    - 29.3 Baselines never update automatically. `POST /astronauts/{id}/baselines/{type}/recompute
      {actor_id, reason}` makes a new version and supersedes the old one. While a concern for that type is not
      closed: 409 `BASELINE_FROZEN`. Readings observed while a concern was open are always excluded from later
      baselines, so deterioration never becomes the new normal. Too few samples: 422
      `INSUFFICIENT_BASELINE_DATA`. `GET /astronauts/{id}/baselines` lists every version.
    - 30.1 Fixture `detection_ruleset` (`DET-1.0`): one rule per baselined type with direction, `k` spread
      multiples, absolute minimum change, window minutes, required consecutive deviating readings, configured
      assessment (heart rate -> PROC-BP-01, whose monitor reports pulse; SpO2 and temperature -> none until step 34),
      reassessment delay, recovery count and alert-suppression minutes.
    - 30.2 Data-quality gate, applied to every ingested reading before any rule: `poor` quality ->
      `excluded_poor_quality`; older than the type's stale limit at ingestion -> `excluded_stale`; no active
      baseline -> `no_baseline`. Excluded readings never count towards, or reset, a sustained change.
    - 30.3 `services/detection.py` runs on `POST /observations` and new `POST /observations/batch` (wearable
      sync, processed in time order). Outcomes: `within_baseline`, `deviation_not_sustained` (n of N),
      `concern_opened`, `concern_updated`, `within_baseline_concern_open`, `reassessment_completed`. The result is
      stored on the observation and returned as `detection`, with rule, baseline version, explanation and the
      fixed disclaimer that a deviation from a synthetic baseline is not a diagnosis.
    - 30.4 `concern_opened` creates table `monitoring_concerns` (annotation kind `monitoring_concern`) and joins
      the astronaut's open routine case, or opens one (`detected -> investigating`), through the case service. The
      configured assessment is requested (`awaiting_assessment`) when the case has none pending; a
      `monitoring_reassessment` follow-up is scheduled.
    - 30.5 `GET /astronauts/{id}/monitoring`: per type freshness, active baseline, latest reading and its
      difference from the baseline, descriptive trend (slope per hour, no rule on it), open concern, and
      data-quality items (`missing`, `stale`, `recent_poor_quality`, `baseline_insufficient`) that never open a case.
      `GET /monitoring-concerns/{id}`.

**Review 3 (after step 30).** Check: can a stale or poor-quality reading ever create a health finding (it must not)? Is every detection labelled a configured demonstration rule, never a diagnosis? Is the urgent priority protected from downgrade?
*Reflection:* the risk is tangling detection with the symptom rules. Mitigation: a separate `services/detection.py` that writes through the existing case service, so audit and state machine stay single-sourced.

31. Deduplication and alert suppression for repeated equivalent triggers.
32. Urgent-event priority protection during routine procedures and follow-ups.
33. Tests for scenarios A–E (v3.1 §7).
    Detailed sub-steps:
    - 31.1 While a concern for the same astronaut and type is not closed, an equivalent deviating reading updates
      that concern (evidence, trigger count) and never opens a second concern or case. Case evidence and an alert
      are added at most once per suppression window; the rest count as `suppressed_count`, audited.
    - 31.2 Concern statuses `open`, `awaiting_review`, `closed`. Return within baseline never closes a concern:
      it needs the reassessment follow-up completed by a good-quality reading observed after its due time, then
      `recovery_count` consecutive in-baseline readings, which moves it to `awaiting_review`. A new deviation sends
      it back to `open` and schedules a new reassessment. Only `POST /monitoring-concerns/{id}/review {actor_id,
      decision: continue_monitoring|close, note}` closes it (409 `CONCERN_NOT_READY_FOR_REVIEW` otherwise); closing
      never resolves the case. Role check is PARTIAL until step 36.
    - 32.1 `case_svc.raise_priority` is the only priority writer: it can only raise, records `urgent_since` and
      the reason (new columns), sets `interrupt` on open follow-ups, and is audited. CaseOut gains
      `priority_protection` (`automatic_downgrade_allowed: false`).
    - 32.2 Fix: recording the routine reading and a follow-up becoming due overwrote `next_action` and dropped the
      urgent instruction. Both now keep it while the case is urgent.
    - 32.3 SessionOut gains `case_priority`, `attention` and `urgent_events` (other open urgent cases for the same
      astronaut, e.g. an emergency activated during the routine procedure), so the coach can interrupt.
    - 33.1 Tests `test_u_health_intelligence.py` (A, B, C, baselines) and `test_v_priority_followup.py` (D, E);
      contract export, smoke checks, docs, commit.

**2.7.0 add-on (planned 2026-11-15 after Codex's review of 2.6.0).** Codex asked for three things; none changes
an earlier rule.
- 33.2 `GET /astronauts/{id}/observations` returns the full observation history with filters and paging. Each
  item has its stored `detection`, an `origin` (`baseline_history`, `seed_fixture`, `ingested`,
  `procedure_measurement`) and `in_active_baseline`.
- 33.3 `POST /demo/scenarios/{scenario_id}` sets up isolated live-browser scenarios. It resets the demo first,
  then builds the state through the normal services: `SCN-REASSESSMENT-DUE`, `SCN-URGENT-DURING-PROCEDURE` and
  `SCN-EMERGENCY-DURING-PROCEDURE`. The only shortcut is moving the reassessment due time, which is audited as a
  simulated clock change.
- 36.1 (first part of step 36, brought forward) Fixture `role_code` per crew member (`crew_member`,
  `crew_medical_officer`). Closing a concern and recomputing a baseline need `crew_medical_officer`; otherwise
  403 `ROLE_NOT_PERMITTED`, audited. `continue_monitoring` stays open to any crew member. The other sensitive
  endpoints stay in step 36.

### Milestones 6–7 (backend part) — expanded and operational capability
34. PROC-PO-01 (finger pulse oximeter) and PROC-TEMP-01 (non-contact infrared thermometer) definitions with their own visual contract, measurement validation and tests.
    Detailed sub-steps (planned 2026-11-15; contract 2.8.0):
    - 34.1 Fixture `additional_procedures`: PROC-PO-01 (fictional Demo Fingertip Pulse Oximeter P1, left index
      finger, site `left_hand`) and PROC-TEMP-01 (fictional Demo Infrared Thermometer T1, forehead, site `head`).
      Each has 5 steps with the full 2.2.0 visual contract, distinct `VA-PO-*` and `VA-TEMP-*` action IDs,
      paraphrased general consumer guidance (sources marked not reviewed by a flight surgeon), safety
      limitations, the microgravity caveat, validation level `EDUCATIONAL_DEMONSTRATION` and its own follow-up.
      PROC-BP-01 stays byte-for-byte unchanged.
    - 34.2 Seed and the startup configuration sync handle every procedure. The sync also brings equipment
      `compatible_procedure_ids` up to date (EQ-PO-01 -> PROC-PO-01, EQ-THERM-01 -> PROC-TEMP-01), so an existing
      database can start the new sessions.
    - 34.3 `MeasurementCreate.type` adds `pulse_oximetry` (`{spo2, pulse?}`, unit `%`) and `body_temperature`
      (`{temperature}`, unit `degC`). The type must match the procedure's capability (422
      `MEASUREMENT_TYPE_MISMATCH`), and the value shape and unit must match the type. Technical ranges: SpO2
      50–100, pulse 20–250, temperature 30–43. Derived observations: spo2 + heart_rate, or body_temperature.
      These are still technical checks, not clinical interpretation.
    - 34.4 `DET-1.1`: DET-SPO2-01 requests PROC-PO-01 and DET-TEMP-01 requests PROC-TEMP-01 (both configured
      demonstration assessments, not clinical indications). The other rule values are unchanged. Detection
      results record the new ruleset version.
    - 34.5 `GET /procedures` lists every procedure summary (bootstrap `procedures` already does).
    - 34.6 Tests `test_x_more_procedures.py`: the visual contract for every procedure, distinct action IDs across
      all procedures, anatomy targets, equipment match, full PO and TEMP runs with derived observations, range
      and type errors, an SpO2 concern leading to PROC-PO-01, BP unchanged, and an old database receiving the
      procedures and device links.
35. Multiple scheduled assessment types with due/overdue state.
36. Role-based access (crew member, crew medical officer, flight surgeon, ground support) on sensitive endpoints, with audit.
37. Medical communications queue with simulated delay, priority and acknowledgement.
38. Environmental intelligence: attributed EDA/RadLab context with cautious wording (EDA stays BLOCKED until a source file is imported).
39. Offline and recovery tests (restart mid-session, loss of server behaviour documented).
40. Full regression, contract export, smoke test, docs and status table.

**Scope decision (owner, 2026-11-15).** Milestone 8 (hardware and AR) is out of scope. It is reported as NOT
STARTED and nothing simulated is labelled as hardware. Milestones 6 and 7 are built for the software part only.

Detailed sub-steps for steps 35–40 (planned 2026-11-15):
- **Part A, contract 2.9.0 (steps 35–36).**
  - 35.1 Fixture `screening_schedule`: three configured, fictional screening types for DEMO-001. They are
    SA-BP-001 (weekly blood pressure, due 30 min ago, unchanged), SA-PO-001 (daily pulse oximetry, due in 6 h)
    and SA-TEMP-001 (daily temperature, overdue). Each has `interval_hours` and `grace_hours`; columns are added
    via `add_missing_columns`, and the sync adds missing schedule rows to existing databases.
  - 35.2 Derived `due_state`: `upcoming`, `due`, `overdue` (past due + grace) or `completed`.
    `GET /astronauts/{id}/assessments`.
  - 35.3 Durable reminders: table `assessment_reminders`, one row per assessment and kind (`due`, `overdue`),
    created on read. `GET /astronauts/{id}/reminders` and `POST /reminders/{id}/acknowledge`. Acknowledging
    never completes the assessment.
  - 35.4 `POST /assessments/{id}/start {actor_id, mode, equipment_id?}` opens a routine screening case
    (`awaiting_assessment`, no symptom needed) and its session through the normal services. A measurement from
    that procedure completes the assessment and schedules the next one (`due_at = completed + interval`).
  - 36.1 is done (2.7.0). 36.2: fixture `ground_personnel` (fictional flight surgeon GND-FS-01 and ground support
    GND-SUP-01). They are valid actors for role checks but are not habitat crew.
  - 36.3 A permission matrix covering concern close, baseline recompute, hatch change, case acknowledgement,
    sensitive case and history reads (optional `viewer_id`), and comms send and acknowledge (Part B). Every
    refusal is 403 `ROLE_NOT_PERMITTED` and audited. `GET /access/roles` publishes the matrix.
  - 36.4 Honest limit: there is no authentication. The actor or viewer ID is self-declared, so this is role
    enforcement in a simulation, not security. Requests without `viewer_id` keep the demo behaviour.
- **Part B, contract 2.10.0 (steps 37–38).**
  - 37.1 Table `comms_messages`: direction (`to_ground` or `to_crew`), priority, sender, recipient role, case,
    `client_message_id` (idempotent), and status (`queued`, `in_transit`, `delivered`, `acknowledged`) with
    times. Fixture `comms`: fictional one-way delay of 300 s.
  - 37.2 Transmission is computed lazily from the clock. Urgent messages go first, and routine messages queue
    behind any urgent message that has not been sent. `POST /comms/link {state: up|down, actor_id}` simulates
    loss of signal: messages wait while the link is down and get a new delivery time when it returns.
  - 37.3 Endpoints: `POST /comms/messages`, `GET /comms/messages`, `POST /comms/messages/{id}/acknowledge`
    (409 `NOT_DELIVERED`; the recipient side's role is required) and `GET /comms/link`.
  - 37.4 An emergency activation now queues a real urgent `to_ground` message to the flight surgeon (it was a
    status text before). Onboard crew response still does not wait for it.
  - 38.1 `GET /environment/context`: the latest RadLab reading per instrument, with the dataset ID, source link,
    unit and the location "ISS", stated as not the fictional habitat. It says explicitly that no relationship to
    the crew member's health is inferred. NASA-EDA stays BLOCKED.
- **Part C, steps 39–40.**
  - 39.1 `GET /system/recovery` (2.10.0): what a client must restore after reconnecting (open sessions, open
    concerns, due reminders, queued or undelivered messages, link state).
  - 39.2 Tests: restart mid-session and mid-transmission; resend after a lost response (client IDs); outage
    across a restart. The handoff documents the loss-of-server behaviour.
  - 40.1 Full regression, contract export, smoke test, live restart, `docs/ACCEPTANCE_RECORD.md` (backend
    acceptance record per v3.1 §8 subsystem with status and validation level), and the status table. Then
    Review 4.

**Review 4 (after step 40).** Check every status against v3.1 §12; nothing simulated is labelled hardware-tested or clinically validated.
*Reflection:* Milestone 8 (hardware, AR) needs real devices; it stays NOT STARTED and is documented as such.

## 4. Status table (updated as steps finish)

| Step range | Status |
|---|---|
| 1–22 | done 2026-11-14 (contract 2.2.0; 201 passed, 1 skipped; smoke 25/25) |
| 2.3.0 add-on | done 2026-11-15: `sentinel-human-male-v1` registered from Codex's GLB; 217 passed, 1 skipped |
| 23–24 | done 2026-11-15: contract 2.4.0 procedure session state; 238 passed, 1 skipped; smoke 26/26 |
| 25–28 | done 2026-11-15: contract 2.5.0 habitat operations and movement simulator; 257 passed; smoke 29/29 |
| 29–33 | done 2026-11-15: contract 2.6.0 proactive health intelligence (scenarios A–E); 288 passed; smoke 33/33 |
| 2.7.0 add-on | done 2026-11-15: steps 33.2, 33.3, 36.1 (history, live scenarios, review role check); 299 passed; smoke 38/38 |
| 34 | done 2026-11-15: contract 2.8.0 PROC-PO-01 and PROC-TEMP-01, DET-1.1; 319 passed; smoke 40/40 |
| 35–36 | done 2026-11-15: contract 2.9.0 screening and role matrix |
| 37–40 | done 2026-11-15: contract 2.10.0 comms queue, environment context, recovery; 346 passed; smoke 45/45 |
| Milestone 8 | NOT STARTED: out of scope by owner decision |

**Review 1 outcome.** Instruction text, safety limitations and measurement rules are unchanged (test
`test_instructions_and_limitations_unchanged`). Anatomy changes are additive for Codex's current client; the only
behaviour change is the `UNKNOWN_SURFACE_MODEL` code. The manifest reproduces the 35 frontend sites (test against
`anatomy-sites.ts` at 9430a3d).

**Review 2 outcome.** No response gives a precise crew position (`position` is always null; route starts are
labelled navigation references). Map, routes and location share `HAB-01-map-1.1` and `HAB-01-D1-LOCAL`. Research
counts are equal before and after reset, and the live database kept every imported dataset after the upgrade.
Deviations from the plan: none. Efficiency note for step 25: hatch state already lives in
`ZoneConnection.accessible`, and `test_closing_a_hatch_changes_the_route` already proves routing reacts.

**Review 3 outcome (2026-11-15).**
- Stale or poor readings: the gate runs before any rule. The sustained-change window counts only readings stored
  with `gate: passed`. Scenario B tests show that three poor and three stale deviating readings open no concern
  and no case, and that an excluded reading neither counts towards a run nor breaks it. Missing data only creates
  `data_quality` items.
- Wording: every detection result, concern and case-evidence line carries the DET-1.0 disclaimer ("not a
  diagnosis"). A search of the detection, baseline and monitoring code and the fixture finds no clinical
  condition names.
- Urgent priority: `cases.raise_priority` is now the only code that sets `urgent`. No code path sets `routine` on
  an existing case. `cases.set_next_action` is the only writer of `next_action` and keeps the urgent instruction
  first. Measurement completion, a follow-up becoming due, and a new routine symptom joining an urgent case
  used to overwrite that instruction; they now go through it (planned step 32.2). The Scenario D tests come in
  step 33.
- Deviation from the plan: readings recorded by a procedure measurement (blood pressure and pulse) are stored as
  assessment evidence and are not run through DET-1.0, because the assessment itself answers the concern. This
  is documented in the handoff.

*Reflection:* the plan's risk (detection tangled with the symptom rules) did not happen. `detection.py` writes
only through `cases.transition`, `add_evidence`, `set_next_action` and `raise_priority`, so audit and the state
machine have one source each. The remaining risk is time-based behaviour (the reassessment due time and the
suppression window). Tests move the stored timestamps instead of sleeping, as `test_follow_up_becomes_due`
already does. Efficiency: steps 31.1 and 32.1 were built with step 30 because they share the same functions.
Step 31 therefore only adds the closing and review rules (31.2), and step 33 adds the D and E tests.

**Review 4 outcome (2026-11-15, after step 40).**
- Status words: `docs/ACCEPTANCE_RECORD.md` gives every v3.1 §8 subsystem a backend status and a validation
  level. Environmental intelligence, safety and privacy, and habitat intelligence are PARTIAL, with the reason
  given. NASA-EDA and OSD-195 are BLOCKED. Milestone 8 is NOT STARTED.
- Nothing simulated is labelled hardware tested or clinically validated. All three procedures are
  `EDUCATIONAL_DEMONSTRATION`. The only places the higher validation levels appear are the enum definition in
  `schemas/procedures.py`, and every comms message and link response carries `simulated: true`.
- Research integrity: all 5 imported datasets are still `IMPORTED` on the live database after the 2.9.0 and
  2.10.0 upgrades. Reset counts are unchanged (`test_a`).
- Deviations from the plan:
  - Milestone 8 was dropped by the owner.
  - A message created during an outage waits for a free 5-second transmission slot after the link returns. That
    is the planned serial channel, but the first smoke check expected `in_transit` and was corrected to accept
    `queued`.
  - The RadLab context test found the snapshot lives under `raw/NASA-RADLAB/`, not `raw/`.

*Reflection:* the main remaining risk is honesty about security. Role enforcement without authentication can be
mistaken for access control, so the limitation appears in `/access/roles`, the handoff and the acceptance
record. Efficiency: screening, comms and recovery reuse the case, procedure and audit services, so no workflow
has two code paths. The test suite grew to 346 and runs in about 2.5 minutes. The next speed-up would be a
session-scoped app for read-only tests.

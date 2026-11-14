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

### Milestone 5 (backend part) — proactive health intelligence
29. Baseline model (versioned, per astronaut and observation type, quality rules, frozen while a concern is open so deterioration never becomes the new normal).
30. Detection rules `DET-1.0` (window, sustained-change count, data-quality gate) creating `monitoring_concern` findings and investigations.

**Review 3 (after step 30).** Check: can a stale or poor-quality reading ever create a health finding (it must not)? Is every detection labelled a configured demonstration rule, never a diagnosis? Is the urgent priority protected from downgrade?
*Reflection:* the risk is tangling detection with the symptom rules. Mitigation: a separate `services/detection.py` that writes through the existing case service, so audit and state machine stay single-sourced.

31. Deduplication and alert suppression for repeated equivalent triggers.
32. Urgent-event priority protection during routine procedures and follow-ups.
33. Tests for scenarios A–E (v3.1 §7).

### Milestones 6–7 (backend part) — expanded and operational capability
34. PROC-PO-01 (finger pulse oximeter) and PROC-TEMP-01 (non-contact infrared thermometer) definitions with their own visual contract, measurement validation and tests.
35. Multiple scheduled assessment types with due/overdue state.
36. Role-based access (crew member, crew medical officer, flight surgeon, ground support) on sensitive endpoints, with audit.
37. Medical communications queue with simulated delay, priority and acknowledgement.
38. Environmental intelligence: attributed EDA/RadLab context with cautious wording (EDA stays BLOCKED until a source file is imported).
39. Offline and recovery tests (restart mid-session, loss of server behaviour documented).
40. Full regression, contract export, smoke test, docs and status table.

**Review 4 (after step 40).** Check every status against v3.1 §12; nothing simulated is labelled hardware-tested or clinically validated.
*Reflection:* Milestone 8 (hardware, AR) needs real devices; it stays NOT STARTED and is documented as such.

## 4. Status table (updated as steps finish)

| Step range | Status |
|---|---|
| 1–22 | done 2026-11-14 (contract 2.2.0; 201 passed, 1 skipped; smoke 25/25) |
| 2.3.0 add-on | done 2026-11-15: `sentinel-human-male-v1` registered from Codex's GLB; 217 passed, 1 skipped |
| 23–24 | done 2026-11-15: contract 2.4.0 procedure session state; 238 passed, 1 skipped; smoke 26/26 |
| 25–40 | not started |

**Review 1 outcome.** Instruction text, safety limitations and measurement rules are unchanged (test
`test_instructions_and_limitations_unchanged`). Anatomy changes are additive for Codex's current client; the only
behaviour change is the `UNKNOWN_SURFACE_MODEL` code. The manifest reproduces the 35 frontend sites (test against
`anatomy-sites.ts` at 9430a3d).

**Review 2 outcome.** No response gives a precise crew position (`position` is always null; route starts are
labelled navigation references). Map, routes and location share `HAB-01-map-1.1` and `HAB-01-D1-LOCAL`. Research
counts are equal before and after reset, and the live database kept every imported dataset after the upgrade.
Deviations from the plan: none. Efficiency note for step 25: hatch state already lives in
`ZoneConnection.accessible`, and `test_closing_a_hatch_changes_the_route` already proves routing reacts.

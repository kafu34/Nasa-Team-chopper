# SENTINEL AI — Backend → Frontend Integration Handoff

| Item | Value |
|---|---|
| Contract | `shared/openapi.yaml`, **version 2.4.0**, generated from the FastAPI app (do not edit by hand) |
| Fixture | `shared/fixtures/demo_scenario.json`, `fixture_version` 2.4.0; anatomy models in `shared/anatomy/` |
| Backend branch | `backend/p0-v2.1`. PR #1 was merged into `main`; the contract 2.2.0 commits below are on this branch only until the owner merges them. |
| Base URL | `http://127.0.0.1:8000` |
| API prefix | `/api/v1` (plus `/healthz` at the root) |
| Status | All 13 baseline endpoints and all 5 v2.1 research endpoints implemented and tested. `/radiation/timeseries` serves real RadLab data; `/environment/timeseries` returns 503 (no EDA importer). |

This file is how the backend communicates with Codex. Writing it does not mean Codex has read it.

## 1. Start the backend

```bash
cd Backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

(macOS/Linux: `.venv/bin/python`.) On first start the server creates `Backend/var/sentinel.db`, seeds the
fictional demo from the shared fixture, and imports the NASA OSD-575 CSV from `data/nasa/raw/` automatically.
No internet connection is needed.

## 2. How the frontend should connect

- Preferred: Vite dev proxy — `server.proxy = { '/api': 'http://127.0.0.1:8000', '/healthz': 'http://127.0.0.1:8000' }`.
- Or call `http://127.0.0.1:8000` directly: CORS allows only `http://127.0.0.1:5173` and `http://localhost:5173`
  (methods GET/POST/OPTIONS, header Content-Type).
- Generate TypeScript types from the contract, for example
  `npx openapi-typescript ../shared/openapi.yaml -o src/api/schema.ts`. Do not hand-write diverging types.

## 3. Conventions Codex must follow

1. **Timestamps**: ISO 8601 **with a timezone** (`2026-11-14T09:30:00Z`). Naive timestamps are rejected (422).
   Responses are always UTC with offset.
2. **Errors**: every non-2xx body is `{"error": {"code": "...", "message": "...", "details": ...}}`.
   Codes used: `VALIDATION_ERROR`, `NOT_FOUND`, `UNKNOWN_REGION`, `INVALID_LATERALITY`, `TIMESTAMP_IN_FUTURE`,
   `TIMESTAMP_OUTSIDE_SESSION`, `UNKNOWN_OBSERVATION_TYPE`, `UNIT_MISMATCH`, `VALUE_OUT_OF_TECHNICAL_RANGE`,
   `INVALID_CASE_TRANSITION`, `NO_SUITABLE_EQUIPMENT`, `PROCEDURE_MISMATCH`, `CASE_RESOLVED`, `UNKNOWN_STEP`,
   `STEP_OUT_OF_ORDER`, `SESSION_COMPLETED`, `SESSION_INCOMPLETE`, `SESSION_CASE_MISMATCH`, `ASTRONAUT_MISMATCH`,
   `MEASUREMENT_IMPLAUSIBLE`, `MEASUREMENT_ALREADY_RECORDED`, `UNKNOWN_DATASET`, `UNKNOWN_FILTER_VALUE`,
   `DATASET_UNAVAILABLE`, `INVALID_DATASET_FOR_ENDPOINT`.
3. **Request bodies reject unknown fields** (422). Send only contract fields.
4. **Duplicates return 200, new records 201** for `POST /symptoms`, `/procedure-sessions`, `/emergencies`,
   `/observations`. Check the `duplicate` flag where present.
5. **Data category** on every record: `NASA_RESEARCH`, `SIMULATED_ASTRONAUT`, `SIMULATED_ENVIRONMENT_OR_DEVICE`.
   Never display NASA records as live astronaut or habitat readings.
6. **BLE observations**: the fixture gives `age_seconds`; send `observed_at = now - age_seconds`. Signals older
   than 30 s are rejected as stale.
7. **Attention**: show `attention.interrupt == true` items as interrupting alerts; routine items must not interrupt.
8. **Units**: always take units from the API (`unit` fields). Do not guess.

## 4. Shared fixture identifiers

| Thing | ID |
|---|---|
| Astronaut (fictional) | `DEMO-001` |
| Responder (fictional) | `DEMO-002` |
| Habitat | `HAB-01` (map `HAB-01-map-1.0`) |
| Zones | `crew-quarters`, `exercise`, `medical`, `laboratory` |
| Connections | crew-quarters↔exercise, exercise↔medical, crew-quarters↔laboratory (open); laboratory↔medical (**closed**) |
| Anchors | `ANC-CQ-01`, `ANC-EX-01`, `ANC-MED-01`, `ANC-LAB-01`, `ANC-LAB-02` (disabled) |
| Equipment | `EQ-BP-01` (medical, ready), `EQ-BP-02` (laboratory, readiness unknown), `EQ-BP-03` (exercise, cuff missing), `EQ-PO-01`, `EQ-THERM-01`, `EQ-AED-01`, `EQ-EMK-01` |
| Capability | `blood_pressure` |
| Procedure | `PROC-BP-01` version `1.1.0-demo`, steps `S1`–`S6` |
| Scheduled assessment | `SA-BP-001` (due 30 min before seed/reset) |
| NASA dataset | `OSD-575` (plus catalogue IDs `OSD-656`, `NASA-EDA`, `NASA-RADLAB`, `OSD-654`, `OSD-684`, `OSD-573`, `OSD-817`) |
| Anatomical regions | `head`, `eyes`, `neck`, `chest`, `upper_back`, `lower_back`, `abdomen`, `upper_arm`, `forearm_hand`, `upper_leg`, `lower_leg_foot`, `whole_body` |
| Laterality | `left`, `right`, `bilateral`, `midline`, `not_applicable` (non-lateral regions accept only `midline`/`not_applicable`) |

`GET /api/v1/demo/bootstrap` returns all of these plus `demo_inputs` (the canonical symptom, BLE observations,
measurement and emergency payload templates), so the frontend never needs to hard-code demo values.

## 5. Endpoints

| # | Method & path | Status | Success codes |
|---|---|---|---|
| 1 | `GET /healthz` | Working | 200 |
| 2 | `GET /api/v1/demo/bootstrap` | Working | 200 |
| 3 | `POST /api/v1/symptoms` | Working | 201 / 200 duplicate |
| 4 | `GET /api/v1/cases/{case_id}` | Working | 200 |
| 5 | `POST /api/v1/location/estimate` | Working (simulated BLE) | 200 (zone may be null) |
| 6 | `POST /api/v1/equipment/recommend` | Working | 200 / 404 `NO_SUITABLE_EQUIPMENT` |
| 7 | `GET /api/v1/procedures/{procedure_id}` | Working | 200 |
| 8 | `POST /api/v1/procedure-sessions` | Working | 201 / 200 existing |
| 9 | `POST /api/v1/procedure-sessions/{session_id}/steps` | Working | 200 |
| 10 | `POST /api/v1/measurements` | Working | 201 |
| 11 | `GET /api/v1/research/osd-575` | Working (real data) | 200 / 503 if not imported |
| 12 | `POST /api/v1/emergencies` | Working | 201 / 200 duplicate |
| 13 | `POST /api/v1/demo/reset` | Working | 200 |
| v2.1 | `GET /api/v1/research/datasets` | Working | 200 |
| v2.1 | `GET /api/v1/research/datasets/{dataset_id}` | Working | 200 / 404 |
| v2.1 | `GET /api/v1/research/datasets/{dataset_id}/records` | Working for OSD-575 | 200 / 503 others |
| v2.1 | `GET /api/v1/environment/timeseries` | Contract only; no EDA importer yet (P1) | **always 503 `DATASET_UNAVAILABLE` today** |
| v2.1 | `GET /api/v1/radiation/timeseries` | Working (RadLab ISS snapshot, 2022-04-01) | 200 / 422 / 503 if not imported |
| opt | `POST /api/v1/cases/{case_id}/acknowledge` | Working | 200 (never resolves) |
| opt | `POST /api/v1/observations` | Working | 201 / 200 duplicate |
| opt | `POST /api/v1/location/confirm` | Working (manual zone) | 200 |
| opt | `GET /api/v1/procedure-sessions/{session_id}` | Working | 200 |

Research query parameters: `subject_id`, `analyte`, `timepoint` (exact values from `available_*` lists; unknown
values → 422), `limit` (1–1000; default 1000 on `/research/osd-575`, 100 on `/records`), `offset`.
Timeseries: `dataset_id`, `metric`, `start`, `end`, `limit` (1–5000), `offset`.

## 6. Canonical demo sequence (example payloads)

```http
GET  /api/v1/demo/bootstrap

POST /api/v1/symptoms
{"astronaut_id":"DEMO-001","region_id":"head","laterality":"midline","severity":3,
 "onset":"2026-11-14T08:15:00Z","note":"Mild headache and a feeling of facial fullness (fictional demonstration report)."}
→ 201 {"symptom_id":"SYM-…","case_id":"CASE-…","case_state":"awaiting_assessment","next_action":"Complete the scheduled …","duplicate":false,"data_category":"SIMULATED_ASTRONAUT"}

POST /api/v1/location/estimate
{"astronaut_id":"DEMO-001","observations":[
 {"anchor_id":"ANC-CQ-01","rssi_dbm":-52,"observed_at":"<now-2s>"},
 {"anchor_id":"ANC-LAB-01","rssi_dbm":-63,"observed_at":"<now-3s>"},
 {"anchor_id":"ANC-EX-01","rssi_dbm":-78,"observed_at":"<now-2s>"},
 {"anchor_id":"ANC-UNKNOWN-99","rssi_dbm":-40,"observed_at":"<now-1s>"}]}
→ 200 {"zone_id":"crew-quarters","confidence":0.867,"source":"ble_simulated","observed_at":"…",
       "rejected":[{"anchor_id":"ANC-UNKNOWN-99","reason":"unknown_anchor"}], …}

POST /api/v1/equipment/recommend
{"case_id":"CASE-…","zone_id":"crew-quarters","capability":"blood_pressure"}
→ 200 {"equipment_id":"EQ-BP-01","device_model":"Demo Automatic Upper-Arm BP Monitor A1","zone_id":"medical",
       "readiness":"verified_ready","route_zone_ids":["crew-quarters","exercise","medical"],"procedure_id":"PROC-BP-01",
       "excluded":[{"equipment_id":"EQ-BP-02","reasons":["readiness_unknown"]},
                   {"equipment_id":"EQ-BP-03","reasons":["missing_supplies:cuff_adult_standard"]}], …}

GET  /api/v1/procedures/PROC-BP-01

POST /api/v1/procedure-sessions
{"case_id":"CASE-…","procedure_id":"PROC-BP-01","actor_id":"DEMO-001","mode":"self"}
→ 201 {"session_id":"SES-…","current_step_id":"S1","case_state":"awaiting_results", …}

POST /api/v1/procedure-sessions/SES-…/steps   (repeat for S1 … S6, in order)
{"step_id":"S1","completion_source":"self_confirmed"}      // or responder_confirmed | demo_auto

POST /api/v1/measurements
{"case_id":"CASE-…","session_id":"SES-…","astronaut_id":"DEMO-001","type":"blood_pressure",
 "value":{"systolic":118,"diastolic":76,"pulse":70},"unit":"mmHg","source":"SIMULATED_DEVICE",
 "observed_at":"<now>"}
→ 201 {"case_state":"monitoring","follow_up_created":true,"validation":{"technical_checks_passed":true,
       "clinical_interpretation":null, …}, …}

GET  /api/v1/cases/CASE-…        → state "monitoring", follow_up_status "scheduled", one follow-up (24 h)
GET  /api/v1/research/osd-575    → 531 real NASA records with provenance
POST /api/v1/emergencies
{"astronaut_id":"DEMO-001","responder_id":"DEMO-002","trigger":"crew_collapse"}
→ 201 {"priority":"urgent","case_state":"escalated","localisation_required":false, …}
```

Case states: `detected`, `investigating`, `awaiting_assessment`, `awaiting_results`, `action_required`,
`monitoring`, `follow_up_due`, `escalated`, `resolved`.

## 7. Demo reset

`POST /api/v1/demo/reset` deletes every synthetic record (cases, symptoms, sessions, measurements, follow-ups,
location estimates, emergencies, audit, equipment, habitat) and re-seeds from the fixture with fresh relative
timestamps. NASA research tables are untouched (`research_records_before == research_records_after`).
Generated IDs (`CASE-…`, `SES-…`) are random per run; fixture IDs are fixed.

## 8. NASA importer status

- OSD-575 CMP CSV present at `data/nasa/raw/LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv`
  (SHA-256 `dab247eb794edab59aaaa683c85fd1f2dbf4ae3684872739338e10ead4192a0c`).
- Imported: 531/531 rows, 4 subjects (C001–C004), 19 analytes, 7 timepoints. 22 `NA` values and 56 `N/A`
  upper bounds stored as `null`. Status `IMPORTED`.
- **OSD-656 (urine inflammation panel) is `IMPORTED`:** 8,888 values (203 targets × 22 samples, 2 measures).
  - Records come in `assay_records[]`.
  - Filters: `subject_id`, `analyte` (e.g. `il6`), `timepoint` and `measure` (`concentration_npq` |
    `percent_normalized_value`).
  - Example: `GET /api/v1/research/datasets/OSD-656/records?analyte=il6&measure=concentration_npq`.
- **NASA-RADLAB is `IMPORTED`:** 2,847 ISS absorbed dose-rate readings for 2022-04-01 (DosTel1, DosTel2, Lidal,
  REM-Lid; Columbus module).
  - Use `GET /api/v1/radiation/timeseries?instrument_id=DosTel1` (metric defaults to `absorbed_dose_rate`,
    μGy/hour).
  - Label it "ISS, 1 April 2022 (NASA RadLab)". Never show it as HAB-01 or a crew member's dose.
  - See `docs/NASA_DATASETS.md` §2d.
- **OSD-817 (ex vivo human optic nerve, SANS model) is `IMPORTED`:** 72 values (TUNEL and CTB × 18 donor eyes ×
  counts / normalized counts).
  - Records come in `histology_records[]`.
  - Filters: `subject_id` (donor), `analyte` (`TUNEL` | `CTB`) and `measure`.
  - Show `group_number` as published, **with no pressure/tilt label**, and show each eye's `notes`.
  - See `docs/NASA_DATASETS.md` §2e.
- NASA-EDA, OSD-654, OSD-684 and OSD-573 report `NOT_DOWNLOADED` (no importer yet).
  Show their `source_url` and status honestly; do not chart them.
- **v2.2:** OSD-195 (bed-rest muscle, `HUMAN_GROUND_ANALOGUE`) and OSD-546 (bone-marrow stem cells on the
  ISS, `HUMAN_DERIVED_CELLS`) have importers.
  - **OSD-546 is `IMPORTED`:** 432,861 real values (33,297 probesets × 13 samples).
    - Try `GET /api/v1/research/datasets/OSD-546/records?gene_symbol=TSPAN6` → 13 records, one per sample,
      each with a `condition_label` such as "Space Flight, osteogenic medium".
    - `comparison_readiness.ready` is `true`.
  - **OSD-195 is `NOT_DOWNLOADED`:** only raw CEL files were supplied, so it has zero records. The muscle
    panel must show the status message, not values.
  - See `docs/NASA_DATASETS.md` §2b.

## 9. Tests

See `docs/TEST_REPORT.md`. Latest: **238 passed, 1 skipped, 0 failed** (pytest, including the 3D site-catalogue check against Codex's
`anatomy-sites.ts`; the skip is the visual-registry check, see §11) and **26/26** real-HTTP checks against
uvicorn.

## 10. Known contract deviations and coordination notes

1. **Folder casing (decided by the owner)**: the official folder names are **`Backend/`** and **`Frontend/`**
   (capitalised), replacing `backend/` and `frontend/` from the prompts. Linux and CI file systems are
   case-sensitive, so all paths, scripts, proxies and CI config must use the capitalised names. The git branch
   name `backend/p0-v2.1` is unaffected.
2. **`onset`** is an ISO 8601 timestamp (when the symptom began), not a free-text label.
3. **Measurement `value`** is an object `{systolic, diastolic, pulse?}` (integers), not a string like "118/76".
4. **`procedure_id`** in the equipment response is nullable (null for devices with no linked procedure, e.g. AED).
5. `/radiation/timeseries` returns the RadLab ISS snapshot. `/environment/timeseries` (NASA-EDA) still returns
   503 `DATASET_UNAVAILABLE` because no EDA file or importer exists.
6. Backend has never modified `Frontend/`. It has read it only to stay compatible: on 2026-11-14 it read
   Codex's `codex/frontend-followup` branch (aa25e6b) to answer `Frontend/BACKEND_3D_HANDOFF.md` (§11 item 7).

## 11. Changes requiring frontend updates

Changes are listed newest first, each with its contract version.

### Contract 2.4.0 — procedure session state for the visual Procedure Coach (v3.1 §5, Milestone 3 backend)

Additive. All existing session, step and measurement calls work unchanged.

1. **Device identity.** `POST /procedure-sessions` accepts optional `equipment_id`. Normally this is the device
   from `POST /equipment/recommend`.
   - 404 if the device is unknown.
   - 422 `EQUIPMENT_INCOMPATIBLE` if its capability, model or procedure list does not match `PROC-BP-01`.
   - 409 `EQUIPMENT_NOT_READY` if it is not `verified_ready`, the check is older than 24 h, or a supply is
     missing. `details.reasons` uses the recommendation's reason strings.
   - Reusing the case's open session with a different device gives 409 `SESSION_EQUIPMENT_MISMATCH`. Passing a
     device for an open session that has none binds it.
   - The session returns `equipment {equipment_id, device_model, zone_id_at_start, readiness_at_start,
     readiness_verified_at}`.
   - `POST /measurements` accepts optional `equipment_id`. It must equal the session's device (422
     `EQUIPMENT_MISMATCH`). When the session has a device, `validation.checks` includes
     `device_matches_session`.
2. **New `POST /procedure-sessions/{session_id}/events`**
   - Body: `{step_id, event_type, visual_action_id, actor_id, client_event_id?, occurred_at?, note?}`.
   - `event_type` is one of:
     - `instruction_displayed`: the step's text was shown.
     - `animation_viewed`: its scene played to the end.
     - `animation_replayed`: it was played again.
     - `visual_unavailable`: no implemented scene for that action, so the unavailable state was shown.
   - `visual_action_id` must equal the step's `visual.action_id` (422 `VISUAL_ACTION_MISMATCH`).
   - Returns 201 with the event. A repeated `client_event_id` returns 200 with the first event and
     `duplicate: true`.
   - Events may be sent for any step (preview is allowed). They never change step order, session status or case
     state, and they are audited as visual records only. Pausing is not recorded.
3. **`SessionOut` additions**, for restoring the coach after refresh or case reopening:
   - `step_states[]`: `step_id`, `visual_action_id`, `displayed_at`, `view_count`, `replay_count`,
     `last_viewed_at`, `visual_unavailable`, `acknowledged_at`, `completion_source`.
   - `stages[]`, each `{stage, status: done|partial|pending|unavailable, at, detail}`, for these separate
     records: `instruction_displayed`, `animation_viewed`, `steps_acknowledged`, `device_reading_received`,
     `technical_validation`, `assessment_completed`, `follow_up_created`.
   - `visual_note`: viewing and acknowledging do not prove correct real-world execution.
   - To reopen a case's coach: read `GET /cases/{id}` -> `session_ids`, then `GET /procedure-sessions/{id}`.
4. **Visual registry gate.** The backend test still looks for `Frontend/src/visual-registry.ts`, or another path
   in `SENTINEL_FRONTEND_VISUAL_REGISTRY`, and requires all six `VA-BP-*` IDs in it. **Codex: tell Claude the
   registry path when it exists.**

### Contract 2.3.0 — `sentinel-human-male-v1` registered (answers `Frontend/V3_1_BACKEND_HANDOFF.md`)

Additive. Exact points on Codex's anatomical reference mesh can now be saved and restored.

1. **Model registered** in `shared/anatomy/sentinel-human-male-v1.json`, version **`1.0.0`** (send the string
   `"1.0.0"`, not the number `1`).
   - Asset: `Frontend/public/models/anatomy-male.glb`, 7,614,076 bytes, SHA-256 in the manifest, CC BY 4.0 with
     the BodyParts3D / open-anatomy-3d credit.
   - Frame: model coordinates in metres, feet at y = 0, height 1.72 m, x = body left (+) / right (-), z = front.
   - The same 35 site IDs and region/side mapping as `anatomy-sites.ts`.
   - One selectable mesh, `skin` (40,676 triangles), with its node transform and local bounds read from the GLB.
     Muscle and skeleton meshes are not accepted for reports.
2. **Request** (`surface_point`): `{model_id: "sentinel-human-male-v1", model_version: "1.0.0", site_id, x, y, z,
   mesh_id: "skin", mesh_local_point: {x, y, z}, attachment?: {triangle_index, barycentric[3]}}`. Send
   `hit.point` as x/y/z and `mesh.worldToLocal(hit.point)` as `mesh_local_point`. Triangle + barycentric is
   optional but preferred (`hit.faceIndex` and the barycentric weights of `hit.point` in that face).
3. **Validation** (422 codes):
   - `MESH_REQUIRED`: a model that declares meshes needs `mesh_id`.
   - `UNKNOWN_MESH`, `MESH_NOT_SELECTABLE`, `TRIANGLE_OUT_OF_RANGE`.
   - `MESH_POINT_MISMATCH`: the point is outside the skin bounds, or `mesh_local_point` does not map onto
     x/y/z through the declared transform (tolerance 0.02 m).
   - `SURFACE_SITE_MISMATCH`, `SURFACE_POINT_WRONG_SIDE` (tolerance 0.02 m).
   - `SURFACE_POINT_OUTSIDE_SITE`: the point is outside the site's coarse height band, or on the wrong face for
     eyes, chest, abdomen (front) and upper/lower back (back). The bands are in `sites[].plausibility` and are
     wider than the zones in `human-site.ts`.
   - Limitation: the backend holds no triangles, so it cannot prove the point lies exactly on the surface.
4. **Response**: the create response and `GET /cases/{id}` return the stored point with `mesh_local_point`,
   `attachment`, `mesh_validation: "validated"`, `marker_status` and `render_hint`.
5. **Old markers**: `sentinel-body-v1` stays active. Its points keep their model ID and are never reprojected.
   A later GLB revision gets a new `model_version`. Its `previous_versions` entry says whether old coordinates
   stay valid; if not, old markers come back as `site_only`.
6. **Shared fixture** `surface_marker_examples` holds a right-shoulder point, a left counterpart and a rejected
   region mismatch. They are synthetic points inside the skin bounds, not ray-cast taps.
   `tests/test_q_human_model.py` stores the right-shoulder point, restarts the server, reopens the case and gets
   back the same model, version, mesh, site, side, local point and attachment.

### Contract 2.2.0 — Engineering Specification v3.1, Milestone 1 (backend contracts)

`contract_version` is now **2.2.0** (`/healthz`, `info.version`, fixture `contract_version`). Paths stay under
`/api/v1`. Every change is additive except one error code (item 1). **Codex: please confirm each item below
supports the v3.1 interface, or list what is missing, in `Frontend/BACKEND_3D_HANDOFF.md` or a new
`Frontend/V3_1_CONTRACT_FEEDBACK.md`.** The backend will not build Milestones 3-5 on these shapes until then.

1. **Anatomical marker schema (v3.1 §4.3-4.4).**
   - Models are registered in `shared/anatomy/<model_id>.json` (model version, kind, coordinate frame,
     declared meshes, sites -> region + side, earlier versions with `coordinates_compatible`). Only
     `sentinel-body-v1` 1.0.0 exists; its manifest reproduces the 35 sites of `anatomy-sites.ts` exactly.
   - **For the realistic mesh model, Codex sends Claude:** model ID, version, licence/attribution, coordinate
     frame and units, mesh IDs with triangle counts, and each selectable site with its broad region and side.
     Claude adds the manifest. Old `sentinel-body-v1` markers stay readable (see marker status below).
   - `surface_point` request gains optional `model_version`, `mesh_id` and
     `attachment {triangle_index, barycentric[3]}` (weights 0-1, sum 1 +/-0.001; needs `mesh_id`).
     `model_id` is now any registered model. **Changed:** an unregistered `model_id` returns
     `422 UNKNOWN_SURFACE_MODEL` (was `VALIDATION_ERROR`). New 422 codes: `SURFACE_MODEL_RETIRED`,
     `SURFACE_MODEL_VERSION_MISMATCH`, `SURFACE_POINT_OUT_OF_RANGE`, `UNKNOWN_MESH`, `TRIANGLE_OUT_OF_RANGE`,
     `ATTACHMENT_REQUIRES_MESH`.
   - `surface_point` response gains `model_version` (1.0.0 for points stored earlier), `mesh_id`,
     `mesh_validation`, `attachment`, `marker_status` (`current`, `model_version_changed`,
     `model_version_incompatible`, `model_retired`, `model_unknown`) and `render_hint` (`exact_point`,
     `site_only`, `not_renderable`). Draw a marker at the stored coordinates only for `exact_point`; for
     `site_only` highlight the named site. Stored coordinates are never rewritten.
   - Symptoms gain `record_kind: patient_reported_symptom`. Bootstrap gains `surface_models[]` and
     `anatomical_annotation_kinds[]` (surface selection, region classification, patient-reported symptom,
     monitoring concern, verified finding; SENTINEL never creates a verified finding). `surface_model` stays.
2. **Visual procedure contract (v3.1 §5).** `PROC-BP-01` is now `1.1.0-demo`; instruction text, safety
   limitations and measurement rules are unchanged. A database created earlier receives the new definition on
   startup; existing sessions keep their `procedure_version`.
   - Procedure gains `validation_level` (`EDUCATIONAL_DEMONSTRATION`), `intended_patient`,
     `instruction_sources[]` and `visual_requirements[] {step_id, action_id, asset_ids[]}`.
   - Each step gains `target_region_id`, `target_laterality`, `target_site_id`, `patient_role`,
     `equipment {required_capability, compatible_device_models, components}`, `instruction_source_ids`,
     `warnings[]` and `visual {action_id, asset_id, additional_asset_ids, camera {view, target_region_id,
     target_laterality, framing}, expected_visible_action, replay_allowed, pause_allowed}`.
   - Action IDs: `VA-BP-01-PREPARE-EQUIPMENT`, `VA-BP-02-EXPOSE-UPPER-ARM`, `VA-BP-03-WRAP-CUFF`,
     `VA-BP-04-SUPPORT-ARM`, `VA-BP-05-START-MEASUREMENT`, `VA-BP-06-RECORD-RESULT`. Asset IDs:
     `ASSET-BP-MONITOR-A1`, `ASSET-BP-CUFF-ADULT-STD`, `ASSET-CREW-RESTRAINT`, `ASSET-HUMAN-UPPER-ARM-L`.
   - **Codex's visual registry:** the joint check `tests/test_p_procedure_visual.py` looks for
     `Frontend/src/visual-registry.ts` (or `SENTINEL_FRONTEND_VISUAL_REGISTRY`) and requires every action ID in
     it. Tell Claude if you choose another path. Until then the check is skipped and the visual procedure stays
     PARTIAL.
3. **Habitat geometry (v3.1 §6).** Map `HAB-01-map-1.1`, frame `HAB-01-D1-LOCAL` (origin south-west corner of
   deck D1, +x east, +y north, metres).
   - New `GET /api/v1/habitats/{habitat_id}/map`: decks, compartment polygons with navigation references,
     passage polygons with `hatch_id`, `hatch_point` and live `hatch_state`, anchor and equipment points, and the
     route network (zone-reference and hatch nodes, edges with length and accessibility). Draw this plan; do not
     invent another. Equipment whose zone changed has `point: null`.
   - Bootstrap `habitat.connections[]` gain `hatch_id`.
   - `POST /equipment/recommend` gains `map_version`, `coordinate_frame_id`, `start_reference` (the zone's
     navigation reference, labelled as not anyone's position), `route_hatch_ids` and `route_geometry {frame_id,
     map_version, points, node_ids, length_m, end_equipment_point}`. Draw `points` as the route polyline.
   - Location estimates gain `display_mode` (`zone_only`, `unavailable`; `estimated_xy` is reserved and never
     produced by the zone engine), `position` (always null), `position_uncertainty_m` and `map_version`.
   - New `GET /api/v1/location/{astronaut_id}/latest` returns the newest estimate with `display_mode`
     `zone_only`, `stale` (older than 30 s for BLE, 15 min for manual) or `unavailable`, plus `age_seconds` and a
     label. Show `stale` as last-known, never as current.
   - Hatch open/close changes, the movement simulator and multi-crew routes are Milestone 4 (not built yet).


### v2.2 research update (additive; `contract_version` stays `2.1.0`)

Every change is additive. No field, path or identifier was removed or renamed, and OSD-575 responses keep the
same shape. `contract_version` was left at `2.1.0` on purpose, so an existing frontend version check still
passes. Bump it to `2.2.0` together once Codex has adopted the fields below.

1. **Two new dataset IDs** in `DatasetId`: `OSD-195`, `OSD-546`. `GET /research/datasets` now returns **10**
   datasets (the original 8 first, in the same order). Record schema enum gains `GENE_EXPRESSION_V1`.
2. **New fields on every dataset summary and detail:**
   - `study_type`: one of `HUMAN_SPACEFLIGHT`, `HUMAN_GROUND_ANALOGUE`, `HUMAN_DERIVED_CELLS`,
     `ANIMAL_RESEARCH`, `SPACEFLIGHT_ENVIRONMENT`, `FICTIONAL_DEMONSTRATION`
   - `organism`
   - `human_health_analysis`: `PRIMARY_HUMAN_RESEARCH`, `SEPARATE_ANIMAL_RESEARCH` or `ENVIRONMENT_CONTEXT`
   - `astronaut_specific_findings_allowed`: always `false`
   - `body_systems`: for example `["skeletal_muscle"]` for OSD-195 and `["bone"]` for OSD-546; use this to
     connect a dataset to its Anatomical Twin panel
   - `measured`: what the study actually measured
   - `not_a_measurement_of`: list of things the frontend must never present the dataset as
3. **`DatasetList.study_types[]`**: a legend of `{study_type, label, description}` for the five evidence
   classes plus fictional demonstration data.
4. **`/research/datasets/{id}/records`:**
   - New query parameters `sample_id`, `probe_id` and `gene_symbol` (gene-expression datasets only).
   - A filter that does not apply to the dataset's schema returns 422 `INVALID_FILTER_FOR_DATASET`.
   - New response fields on `ResearchRecordsPage`, filled for `GENE_EXPRESSION_V1` and empty or null for
     OSD-575:
     - `study_type`
     - `expression_records[]` (`GeneExpressionRecord`)
     - `samples[]` (`ResearchSample`)
     - `comparison_readiness {ready, reasons[]}`
     - `source_files[]` (one `Provenance` entry per imported file)
   - Each `GeneExpressionRecord` has `sample_id`, `subject_id|null`, `condition_label`, `probe_id`,
     `gene_symbol|null`, `value|null`, `value_raw`, `value_unit`, `normalization`, `normalization_verified`,
     `source_file`, `source_row_number`, `source_column` and `data_category`.
   - Gene-expression datasets leave `records[]` empty.
5. `POST /demo/reset`: `research_records_before/after` now count CMP records, OSD-656 assay values **and**
   expression values. They are still equal before and after a reset.
5b. **OSD-656 (`BIO_ASSAY_TABLE`)** fills `assay_records[]` (`AssayRecord`) and `available_measures[]`.
   - New query parameter `measure`, valid for this schema only.
   - Each `AssayRecord` has:
     - sample fields: `sample_name`, `subject_id`, `specimen`;
     - measurement fields: `analyte`, `measure`, `value|null`, `value_raw`, `unit`;
     - timepoint fields: `timepoint`, `timepoint_phase`, `timepoint_day_offset`, `timepoint_order`;
     - target annotation: `target_name`, `gene_name`, `uniprot_id`, `protein_name` (each nullable);
     - provenance: `source_file`, `source_row_number`, `source_column`, `data_category`.
   - Units are relative assay units (NPQ, percent normalized), not clinical concentrations. Show no reference
     ranges.
5c. **`GET /radiation/timeseries` now returns data** for NASA-RADLAB instead of 503.
   - New query parameter: `instrument_id`.
   - `metric` defaults to `absorbed_dose_rate`. `start` is inclusive and `end` exclusive.
   - New optional fields on each `TimeseriesPoint`: `timestamp_raw`, `instrument_id`, `instrument_family`,
     `spacecraft`, `module`, `latitude`, `longitude`, `altitude`, `source_row_number`.
   - New fields on `TimeseriesPage`: `study_type`, `filters_applied`, `available_metrics`,
     `available_instruments`, `first_timestamp`, `last_timestamp`, `limitations`.
   - `provenance.source_url` is the exact RadLab API query URL.
   - Chart one instrument per line. The instruments are different detectors, so do not merge them.
   - `/research/datasets/NASA-RADLAB/records` returns 422 `INVALID_DATASET_FOR_ENDPOINT` with
     `details.use_endpoint`. The dataset's `records_endpoint` points to the timeseries URL.
   - `research_records_before/after` in `POST /demo/reset` now also count these readings.
5d. **OSD-817** changed `record_schema` from `OMICS_OR_IMAGING` to the new enum value `HISTOLOGY_COUNTS_V1`.
   - Its records come in the new `histology_records[]` (`HistologyRecord`) on `ResearchRecordsPage`.
   - Each `HistologyRecord` has:
     - sample fields: `sample_name`, `donor_id`, `eye` (OD/OS), `fixation`;
     - measurement fields: `assay` (TUNEL/CTB), `measure` (`counts` | `normalized_counts`), `value|null`,
       `value_raw`, `unit`;
     - annotation: `group_number|null`, `days_on_system`, `donor_sex`, `donor_age`, `notes`;
     - provenance: `source_file`, `source_row_number`, `annotation_file`, `data_category`.
   - `source_files[]` lists all 4 NASA files with their SHA-256.
   - Reset counts include these values.
6. Display rules:
   - OSD-195 is a bed-rest study on Earth. OSD-546 is cells in culture.
   - Never label either as an astronaut's muscle mass, strength or bone density.
   - Show `comparison_readiness.reasons` beside any before/after or flight/ground view.
   - OSD-654 is animal research. Keep it out of the human-health panels.
7. **Structured `surface_point` for the 3D Anatomical Twin** (answers `Frontend/BACKEND_3D_HANDOFF.md`).
   - `POST /symptoms` accepts an optional `surface_point` `{model_id: "sentinel-body-v1", site_id, x, y, z}`.
     `SymptomCreated.surface_point` and `CaseOut.symptoms[].surface_point` return it with `site_label` added.
   - `GET /demo/bootstrap` gains `surface_model {model_id, coordinate_limit, coordinate_note, sites[]}`. The 35
     sites and their broad `region_id`/`laterality` are the same as `Frontend/src/anatomy-sites.ts` (aa25e6b);
     `tests/test_m_surface_point.py` checks this when that file is present.
   - Keep sending the broad `region_id` and `laterality`; the `site_id` must match them, or the request is
     rejected with 422 `SURFACE_SITE_MISMATCH`. `UNKNOWN_SURFACE_SITE` and `SURFACE_POINT_WRONG_SIDE` are
     the other new error codes.
   - The frontend can stop writing the diagram string into `note`. Older notes are left as they were: the
     backend does not parse or rewrite them, and historical `upper_arm` records are not reinterpreted.
   - The rules engine still uses only the broad region. The one rule change: R-SYM-01 duplicate detection also
     compares `site_id`, so a shoulder report does not hide an elbow report made within 10 minutes.
   - An existing database gains the nullable `symptom_reports.surface_point` column at startup.

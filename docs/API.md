# SENTINEL AI Backend API (v2.3.0)

The authoritative, machine-readable contract is **`shared/openapi.yaml`**, generated from the running FastAPI
application by `Backend/scripts/export_openapi.py`. A test (`tests/test_h_contract.py`) fails if the committed
file drifts from the code. Interactive docs: `http://127.0.0.1:8000/docs` while the server runs.

## Conventions

| Topic | Rule |
|---|---|
| Base URL | `http://127.0.0.1:8000`, prefix `/api/v1` (except `/healthz`) |
| Timestamps | ISO 8601 with timezone; naive timestamps are rejected; responses in UTC |
| Errors | `{"error": {"code": str, "message": str, "details": any}}` |
| 201 / 200 | 201 creates a record; 200 returns an existing record for a deduplicated request (`duplicate: true`) |
| 404 | Unknown entity (case, astronaut, zone, procedure, session, dataset) or no suitable equipment |
| 409 | Request conflicts with workflow state (step order, incomplete session, already recorded, mismatches) |
| 422 | Validation failure (schema, unknown fields, implausible technical input, unknown filter values) |
| 503 | `DATASET_UNAVAILABLE`: dataset not imported; `details` gives `status` and `source_url` |
| Data category | `NASA_RESEARCH` / `SIMULATED_ASTRONAUT` / `SIMULATED_ENVIRONMENT_OR_DEVICE` on records |
| Unknown request fields | Rejected (422) |

## Endpoints

### System and demo
- `GET /healthz` → `{status, service, contract_version, database, offline_capable, server_time}`
- `GET /api/v1/demo/bootstrap` → astronaut, responder, habitat (zones, connections), anchors, equipment,
  procedures, `surface_model` (3D twin site catalogue), scheduled assessments (`is_due`), observations, observation freshness
  (`current`/`stale`/`missing`), open cases, anatomical regions, laterality values, `demo_inputs`, research dataset
  catalogue.
- `POST /api/v1/demo/reset` → `{reset, fixture_version, reset_at, research_records_before, research_records_after, message}`

### Cases and observations
- `POST /api/v1/symptoms` — body `{astronaut_id, region_id, laterality, severity 0-10, onset, note?, surface_point?}` →
  `{symptom_id, case_id, case_state, next_action, duplicate, surface_point|null, data_category}`.
  - `surface_point` (optional, v2.2) is a tapped point on the 3D Anatomical Twin:
    `{model_id: "sentinel-body-v1", site_id, x, y, z}`, coordinates finite within ±5 model units.
  - `site_id` must be one of `bootstrap.surface_model.sites` and must map to the request's `region_id` and
    `laterality`. Errors (422): `UNKNOWN_SURFACE_SITE`, `SURFACE_SITE_MISMATCH`, `SURFACE_POINT_WRONG_SIDE`
    (right is negative x, left positive, tolerance 0.1); bad model ID, range or extra fields → `VALIDATION_ERROR`.
  - It is stored and returned as `{model_id, site_id, site_label, x, y, z}` on the symptom and in the case.
    Rules still use only the broad region; the point is a diagram location, not a measurement or a diagnosis.
  - Duplicate detection (R-SYM-01) also compares `site_id`, so a shoulder and an elbow report in `upper_arm`
    are kept apart.
- `GET /api/v1/cases/{case_id}` → full case: `state`, `priority`, `attention {priority, interrupt, reason}`,
  `evidence[]`, `requested_assessment`, `next_action`, `follow_up_status`, `follow_ups[]`, `symptoms[]`,
  `session_ids[]`, `measurements[]`, `audit[]`, `ruleset_version`.
- `POST /api/v1/cases/{case_id}/acknowledge` *(optional)* — `{actor_id}`; records acknowledgement, never changes state.
- `POST /api/v1/observations` *(optional)* — `{astronaut_id, type, value, unit, source, observed_at, quality?}`;
  catalogue types: `heart_rate` bpm, `spo2` %, `body_temperature` degC, `sleep_duration` h,
  `blood_pressure_systolic` mmHg, `blood_pressure_diastolic` mmHg.

### Spatial intelligence and equipment
- `POST /api/v1/location/estimate` — `{astronaut_id, observations: [{anchor_id, rssi_dbm (-120..0), observed_at}]}` →
  `{estimate_id, zone_id|null, confidence 0-1, source (ble_simulated | ble_simulated_smoothed | manual | unavailable),
  observed_at, used_anchor_ids, rejected[{anchor_id, reason}], zone_scores[], explanation, limitation}`.
- `POST /api/v1/location/confirm` *(optional)* — `{astronaut_id, zone_id, confirmed_by}` → same shape, `source: manual`.
  Since 2.2.0 estimates also carry `display_mode` (`zone_only` | `unavailable`), `position: null`,
  `position_uncertainty_m: null` and `map_version`.
- `GET /api/v1/location/{astronaut_id}/latest` *(2.2.0)* → `{astronaut_id, display_mode (zone_only | stale |
  unavailable), estimate|null, age_seconds, stale_after_seconds (30 BLE, 900 manual), label}`.
- `GET /api/v1/habitats/{habitat_id}/map` *(2.2.0)* → `{map_version, coordinate_frame (metres), decks[],
  compartments[{zone_id, polygon, navigation_reference}], passages[{passage_id, hatch_id, polygon, hatch_point,
  accessible, hatch_state}], anchors[{anchor_id, point, enabled}], equipment[{equipment_id, point|null,
  position_status}], route_network{nodes[], edges[]}}`.
- `POST /api/v1/equipment/recommend` — `{case_id, zone_id, capability}` →
  `{equipment_id, device_model, zone_id, readiness, readiness_verified_at, route_zone_ids, route_hops, procedure_id,
  capability, supplies, excluded[{equipment_id, zone_id, reasons}], explanation, readiness_note}`.
  Since 2.2.0 it also returns `map_version`, `coordinate_frame_id`, `start_reference` (zone navigation
  reference), `route_hatch_ids[]` and `route_geometry{frame_id, map_version, points[[x,y]], node_ids, length_m,
  end_equipment_point}`.
  Exclusion reasons: `readiness_unknown`, `readiness_needs_service`, `readiness_in_use`, `readiness_check_stale`,
  `missing_supplies:<list>`, `zone_not_accessible`.

### Procedures and measurements
- `GET /api/v1/procedures/{procedure_id}` → definition with `version`, `purpose`, `required_capability`,
  `compatible_device_models`, `anatomical_region_ids`, `content_status: EDUCATIONAL_DEMO_ONLY`, `source_basis`,
  `safety_limitations[]`, ordered `steps[]`, `follow_up`. Since 2.2.0: `validation_level`, `intended_patient`,
  `instruction_sources[]`, `visual_requirements[]`, and per step `target_region_id`, `target_laterality`,
  `target_site_id`, `patient_role`, `equipment`, `instruction_source_ids`, `warnings[]`, `visual{action_id,
  asset_id, additional_asset_ids, camera, expected_visible_action, replay_allowed, pause_allowed}`.
- `POST /api/v1/procedure-sessions` — `{case_id, procedure_id, actor_id, mode: self|responder}` → session.
- `GET /api/v1/procedure-sessions/{session_id}` *(optional)* → session.
- `POST /api/v1/procedure-sessions/{session_id}/steps` — `{step_id, completion_source: self_confirmed|responder_confirmed|demo_auto}`
  → session `{status, current_step_id, current_step, completed_steps[], completed_count, total_steps, case_state, confirmation_note}`.
- `POST /api/v1/measurements` — `{case_id, session_id, astronaut_id, type: blood_pressure,
  value: {systolic:int, diastolic:int, pulse?:int}, unit: mmHg, source: SIMULATED_DEVICE|SIMULATED_MANUAL_ENTRY, observed_at}`
  → `{measurement, case_id, case_state, next_action, validation{technical_checks_passed, checks[], clinical_interpretation: null, note},
  follow_up, follow_up_created}`. Technical input ranges: systolic 50–260, diastolic 30–160, pulse 20–250,
  systolic > diastolic. These are input-plausibility checks, not clinical thresholds.

### Emergency
- `POST /api/v1/emergencies` — `{astronaut_id, responder_id, trigger: crew_collapse|chest_pain_reported|manual_activation}`
  → `{emergency_id, case_id, case_state: escalated, priority: urgent, attention, activated_at, duplicate,
  localisation_required: false, crew_alert, flight_surgeon_escalation, emergency_information
  {reviewed_procedure_available: false, limitation, crew_actions[]}, equipment_assistance, next_action}`.

### Research (NASA)
- `GET /api/v1/research/datasets` → `{datasets[], status_values[], data_categories[], study_types[]}`.
  v2.2 adds `OSD-195` and `OSD-546` (10 datasets total). Each dataset also has `study_type`, `organism`,
  `human_health_analysis`, `astronaut_specific_findings_allowed` (always false), `body_systems`, `measured` and
  `not_a_measurement_of`.
- Gene-expression datasets (`record_schema: GENE_EXPRESSION_V1`: OSD-195, OSD-546) use the same records
  endpoint with filters `subject_id`, `sample_id`, `probe_id` and `gene_symbol`. The page fills
  `expression_records[]`, `samples[]`, `comparison_readiness` and `source_files[]`, and leaves `records[]`
  empty. A filter of the wrong schema returns 422 `INVALID_FILTER_FOR_DATASET`. Details:
  `docs/INTEGRATION_HANDOFF.md` §11.
- OSD-656 (`record_schema: BIO_ASSAY_TABLE`) uses the same endpoint with filters `subject_id`, `analyte`,
  `timepoint` and `measure`. It fills `assay_records[]` and `available_measures[]`.
- `GET /api/v1/research/datasets/{dataset_id}` → summary + `experimental_context`, `limitations`, `latest_import`, `raw_dir`.
- `GET /api/v1/research/datasets/{dataset_id}/records?subject_id&analyte&timepoint&limit(1-1000, default 100)&offset`
- `GET /api/v1/research/osd-575?subject_id&analyte&timepoint&limit(1-1000, default 1000)&offset`
  → `ResearchRecordsPage {dataset_id, title, source_url, source_file, record_schema: CMP_ANALYTE_V1, provenance,
  total, limit, offset, filters_applied, available_subjects, available_analytes, available_timepoints (chronological),
  limitations, records[]}`. Each `CmpRecord`: `record_id, subject_id, sex, analyte, value|null, value_raw, unit,
  range_min|null, range_min_raw, range_max|null, range_max_raw, test_type, timepoint, timepoint_phase
  (PREFLIGHT|POSTFLIGHT), timepoint_day_offset, timepoint_order, source_file, source_row_number, data_category`.
- `GET /api/v1/environment/timeseries?dataset_id=NASA-EDA&metric&start&end&limit&offset` → `TimeseriesPage`
  (503 until an EDA importer exists).
- OSD-817 (`record_schema: HISTOLOGY_COUNTS_V1`) uses the records endpoint with filters `subject_id` (donor),
  `analyte` (TUNEL/CTB) and `measure`. It fills `histology_records[]`.
- `GET /api/v1/radiation/timeseries?dataset_id=NASA-RADLAB|NASA-EDA&metric&instrument_id&start&end&limit&offset`
  → `TimeseriesPage`, served from the saved RadLab ISS snapshot of 2022-04-01 (2,847 readings).
  - `metric` defaults to `absorbed_dose_rate` (μGy/hour).
  - Points carry `instrument_id`, `module` and ISS `latitude`/`longitude`/`altitude`.
  - Returns 503 if the snapshot is not imported.

Full example payloads: `docs/INTEGRATION_HANDOFF.md` section 6.

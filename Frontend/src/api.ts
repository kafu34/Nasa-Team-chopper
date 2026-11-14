/** Client models maintained against shared/openapi.yaml v2.1.0. */
export const DEMO = { astronautId: 'DEMO-001', responderId: 'DEMO-002', habitatId: 'HAB-01', procedureId: 'PROC-BP-01', datasetId: 'OSD-575' } as const
export const DATASET_IDS = ['OSD-575', 'OSD-656', 'NASA-EDA', 'NASA-RADLAB', 'OSD-195', 'OSD-546', 'OSD-654', 'OSD-684', 'OSD-573', 'OSD-817'] as const
export type DatasetAvailability = 'NOT_DOWNLOADED' | 'READY_TO_IMPORT' | 'IMPORTED' | 'IMPORT_FAILED' | 'UNSUPPORTED_FORMAT'
export type DataCategory = 'NASA_RESEARCH' | 'SIMULATED_ASTRONAUT' | 'SIMULATED_ENVIRONMENT_OR_DEVICE'
export type StudyType = 'HUMAN_SPACEFLIGHT' | 'HUMAN_GROUND_ANALOGUE' | 'HUMAN_DERIVED_CELLS' | 'ANIMAL_RESEARCH' | 'SPACEFLIGHT_ENVIRONMENT' | 'FICTIONAL_DEMONSTRATION'
export type ApiObject = Record<string, unknown>
export type CaseState = 'detected' | 'investigating' | 'awaiting_assessment' | 'awaiting_results' | 'action_required' | 'monitoring' | 'follow_up_due' | 'escalated' | 'resolved'
export type CaseSummary = { case_id: string; state: CaseState; priority?: 'routine' | 'urgent'; next_action: string; updated_at: string }
export type SurfacePoint = { model_id: 'sentinel-body-v1'; site_id: string; x: number; y: number; z: number }
export type SurfacePointOut = SurfacePoint & { site_label: string }
export type SymptomOut = { symptom_id: string; region_id: string; laterality: string; severity: number; onset: string; reported_at: string; note: string | null; surface_point?: SurfacePointOut | null }
export type FollowUpOut = { follow_up_id: string; title: string; due_at: string; status: string; interrupt: boolean }
export type CaseOut = CaseSummary & { follow_up_status: string; follow_ups: FollowUpOut[]; symptoms: SymptomOut[]; measurements: ApiObject[] }
export type BootstrapOut = {
  astronaut: { astronaut_id: string; display_name: string }; habitat: { habitat_id: string; zones: { zone_id: string; name: string }[] };
  anchors: { anchor_id: string; zone_id: string; enabled: boolean }[];
  equipment: { equipment_id: string; zone_id: string; readiness: string }[];
  observations: { type: string; value: number | null; unit: string; observed_at: string; source: string }[];
  scheduled_assessments: { title: string; due_at: string; is_due: boolean; status: 'scheduled' | 'completed'; reason: string }[];
  open_cases: CaseSummary[];
  demo_inputs: { ble_observations: { anchor_id: string; rssi_dbm: number; age_seconds: number }[]; symptom: ApiObject; measurement: ApiObject; emergency: ApiObject };
  surface_model?: { model_id: string; coordinate_limit: number; coordinate_note: string; sites: { site_id: string; label: string; region_id: string; laterality: string }[] };
}
export type SymptomCreated = { symptom_id: string; case_id: string; case_state: CaseState; next_action: string; duplicate: boolean; surface_point?: SurfacePointOut | null }
export type LocationEstimate = { zone_id: string | null; confidence: number; source: string; observed_at: string | null; explanation: string }
export type EquipmentRecommendation = { equipment_id: string; device_model: string; zone_id: string; readiness: string; route_zone_ids: string[]; procedure_id: string | null; explanation: string }
export type ProcedureOut = { procedure_id: string; title: string; purpose: string; content_status: string; safety_limitations: string[]; steps: { step_id: string; title: string; instruction: string; responder_note: string }[] }
export type SessionOut = { session_id: string; status: 'in_progress' | 'completed'; current_step_id: string | null; completed_steps: { step_id: string }[]; case_state: CaseState }
export type BloodPressureValue = { systolic: number; diastolic: number; pulse?: number }
export type MeasurementResult = { case_state: CaseState; next_action: string; validation: { technical_checks_passed: boolean; checks: string[]; clinical_interpretation: null }; follow_up_created: boolean }
export type DatasetSummary = { dataset_id: string; title: string; description: string; source_url: string | null; status: DatasetAvailability; status_reason: string; records_available: number; record_schema: string; priority: string; study_type: StudyType; organism: string; human_health_analysis: 'PRIMARY_HUMAN_RESEARCH' | 'SEPARATE_ANIMAL_RESEARCH' | 'ENVIRONMENT_CONTEXT'; astronaut_specific_findings_allowed: false; body_systems: string[]; measured: string; not_a_measurement_of: string[] }
export type DatasetDetail = DatasetSummary & { experimental_context: string; limitations: string[]; expected_files: string[] }
export type DatasetList = { datasets: DatasetSummary[] }
export type ResearchRecord = { analyte: string; value: number | null; unit: string; subject_id: string; timepoint: string; timepoint_order?: number; data_category: DataCategory; [key: string]: unknown }
export type GeneExpressionRecord = { sample_id: string; subject_id: string | null; condition_label: string; probe_id: string; gene_symbol: string | null; value: number | null; value_unit: string; normalization: string; normalization_verified: boolean; source_file: string; data_category: DataCategory }
export type AssayRecord = { sample_name: string; subject_id: string; specimen: string; analyte: string; measure: 'concentration_npq' | 'percent_normalized_value'; value: number | null; unit: string; timepoint: string; source_file: string; data_category: DataCategory }
export type HistologyRecord = { sample_name: string; donor_id: string; eye: 'OD' | 'OS'; fixation: string; assay: string; measure: 'counts' | 'normalized_counts'; value: number | null; value_raw: string; unit: string; group_number: string | null; days_on_system: number | null; donor_sex: string | null; donor_age: number | null; notes: string | null; source_file: string; source_row_number: number; annotation_file: string | null; data_category: DataCategory }
export type ResearchSample = { sample_id: string; subject_id: string | null; study_type: StudyType; factors: Record<string, string>; factors_verified: Record<string, boolean>; condition_label: string; imported: boolean }
export type ResearchRecordsPage = { dataset_id: string; source_url: string; source_file: string; record_schema: string; total: number; available_timepoints: string[]; records: ResearchRecord[]; limitations: string[]; study_type?: StudyType | null; expression_records?: GeneExpressionRecord[]; assay_records?: AssayRecord[]; histology_records?: HistologyRecord[]; available_measures?: string[]; available_analytes?: string[]; samples?: ResearchSample[]; comparison_readiness?: { ready: boolean; reasons: string[] } | null; source_files?: { source_file: string; source_url: string; sha256: string }[] }
export type TimeseriesPoint = { timestamp: string; value: number | null; unit: string; instrument_id?: string | null; instrument_family?: string | null; spacecraft?: string | null; module?: string | null; latitude?: number | null; longitude?: number | null; altitude?: number | null; source_row_number?: number | null; data_category?: DataCategory }
export type TimeseriesPage = { dataset_id: string; metric: string; unit: string; total: number; points: TimeseriesPoint[]; study_type?: StudyType | null; available_metrics?: string[]; available_instruments?: string[]; first_timestamp?: string | null; last_timestamp?: string | null; limitations?: string[]; data_category: DataCategory; provenance?: { source_url: string; source_file?: string } }
export type EmergencyOut = { case_id: string; case_state: CaseState; crew_alert: { status: string }; flight_surgeon_escalation: { status: string }; emergency_information: { limitation: string; crew_actions: string[] }; next_action: string }

export class ApiError extends Error { constructor(message: string, readonly status: number) { super(message) } }
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try { response = await fetch(path, { ...init, headers: { Accept: 'application/json', ...(init?.body ? { 'Content-Type': 'application/json' } : {}), ...init?.headers } }) }
  catch { throw new ApiError('Local backend unavailable. No data was saved or retrieved.', 0) }
  const raw = await response.text()
  let value: unknown
  try { value = raw ? JSON.parse(raw) : {} } catch { throw new ApiError('Backend returned invalid JSON.', response.status) }
  if (!response.ok) {
    const envelope = asObject(value)
    const error = asObject(envelope?.error)
    throw new ApiError(typeof error?.message === 'string' ? error.message : `Backend request failed (${response.status}).`, response.status)
  }
  if (!asObject(value)) throw new ApiError('Backend returned an unexpected response.', response.status)
  return value as T
}
const post = <T>(path: string, data?: ApiObject) => request<T>(path, { method: 'POST', ...(data ? { body: JSON.stringify(data) } : {}) })
export const api = {
  bootstrap: () => request<BootstrapOut>('/api/v1/demo/bootstrap'),
  reset: () => post<ApiObject>('/api/v1/demo/reset'),
  symptom: (data: { astronaut_id: string; region_id: string; laterality: string; severity: number; onset: string; note?: string; surface_point?: SurfacePoint }) => post<SymptomCreated>('/api/v1/symptoms', data),
  case: (id: string) => request<CaseOut>(`/api/v1/cases/${encodeURIComponent(id)}`),
  location: (observations: { anchor_id: string; rssi_dbm: number; observed_at: string }[]) => post<LocationEstimate>('/api/v1/location/estimate', { astronaut_id: DEMO.astronautId, observations }),
  confirmLocation: (zoneId: string) => post<LocationEstimate>('/api/v1/location/confirm', { astronaut_id: DEMO.astronautId, zone_id: zoneId, confirmed_by: DEMO.astronautId }),
  equipment: (caseId: string, zoneId: string) => post<EquipmentRecommendation>('/api/v1/equipment/recommend', { case_id: caseId, zone_id: zoneId, capability: 'blood_pressure' }),
  procedure: (id: string) => request<ProcedureOut>(`/api/v1/procedures/${encodeURIComponent(id)}`),
  createSession: (caseId: string, mode: 'self' | 'responder') => post<SessionOut>('/api/v1/procedure-sessions', { case_id: caseId, procedure_id: DEMO.procedureId, actor_id: mode === 'self' ? DEMO.astronautId : DEMO.responderId, mode }),
  completeStep: (sessionId: string, stepId: string, mode: 'self' | 'responder') => post<SessionOut>(`/api/v1/procedure-sessions/${encodeURIComponent(sessionId)}/steps`, { step_id: stepId, completion_source: mode === 'self' ? 'self_confirmed' : 'responder_confirmed' }),
  measurement: (data: { case_id: string; session_id: string; value: BloodPressureValue }) => post<MeasurementResult>('/api/v1/measurements', { ...data, astronaut_id: DEMO.astronautId, type: 'blood_pressure', unit: 'mmHg', source: 'SIMULATED_MANUAL_ENTRY', observed_at: new Date().toISOString() }),
  datasets: () => request<DatasetList>('/api/v1/research/datasets'),
  dataset: (id: string) => request<DatasetDetail>(`/api/v1/research/datasets/${encodeURIComponent(id)}`),
  records: (id: string, query: { gene_symbol?: string; analyte?: string; measure?: string; limit?: number } = { limit: 1000 }) => {
    const params = new URLSearchParams()
    if (query.gene_symbol) params.set('gene_symbol', query.gene_symbol)
    if (query.analyte) params.set('analyte', query.analyte)
    if (query.measure) params.set('measure', query.measure)
    if (query.limit) params.set('limit', String(query.limit))
    return request<ResearchRecordsPage>(`/api/v1/research/datasets/${encodeURIComponent(id)}/records?${params}`)
  },
  radiation: (instrumentId: string, limit = 100) => request<TimeseriesPage>(`/api/v1/radiation/timeseries?${new URLSearchParams({ dataset_id: 'NASA-RADLAB', instrument_id: instrumentId, metric: 'absorbed_dose_rate', limit: String(limit) })}`),
  emergency: () => post<EmergencyOut>('/api/v1/emergencies', { astronaut_id: DEMO.astronautId, responder_id: DEMO.responderId, trigger: 'crew_collapse' }),
}
export function asObject(value: unknown): ApiObject | null { return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as ApiObject : null }
export function str(value: unknown, fallback = 'Unavailable'): string { return typeof value === 'string' && value.trim() ? value : fallback }
export function num(value: unknown): number | null { return typeof value === 'number' && Number.isFinite(value) ? value : null }
export function list(value: unknown): ApiObject[] { return Array.isArray(value) ? value.map(asObject).filter((v): v is ApiObject => v !== null) : [] }
export function readList(object: ApiObject | null, ...keys: string[]): ApiObject[] { for (const key of keys) { const found = list(object?.[key]); if (found.length) return found } return [] }
export function display(value: unknown): string { if (value == null || value === '') return 'Not recorded'; if (typeof value === 'string' || typeof value === 'number') return String(value); return 'See backend details' }

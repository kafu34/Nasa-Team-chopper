import { useCallback, useEffect, useState } from 'react'
import { NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import { api, DATASET_IDS, DEMO, display, type ApiObject, type BootstrapOut, type CaseOut, type CaseSummary, type LocationEstimate, type EquipmentRecommendation, type ProcedureOut, type SessionOut, type MeasurementResult, type EmergencyOut, type DatasetSummary, type DatasetDetail, type ResearchRecord, type ResearchRecordsPage } from './api'
import { BodyMap, type BodySelection } from './BodyMap'
import { trendRecords } from './research'
import { AnatomyResearchPanel, ExpressionResults } from './AnatomyResearchPanel'
import { AssayResults } from './AssayResults'

type Work = { busy: boolean; error: string | null; notice: string | null }
const initialWork: Work = { busy: false, error: null, notice: null }

function useRequest() {
  const [work, setWork] = useState<Work>(initialWork)
  const run = useCallback(async <T,>(action: () => Promise<T>, success?: string): Promise<T | null> => {
    setWork({ busy: true, error: null, notice: null })
    try { const result = await action(); setWork({ busy: false, error: null, notice: success ?? null }); return result }
    catch (error) { setWork({ busy: false, error: error instanceof Error ? error.message : 'Request failed.', notice: null }); return null }
  }, [])
  return { ...work, run, clear: () => setWork(initialWork) }
}

function Feedback({ busy, error, notice }: Work) {
  return <div aria-live="polite">{busy && <p className="status info">Contacting local backend…</p>}{error && <p className="status error">{error}</p>}{notice && <p className="status success">{notice}</p>}</div>
}
function Field({ label, value, tone }: { label: string; value: unknown; tone?: string }) { return <div className="field"><span>{label}</span><strong className={tone}>{display(value)}</strong></div> }
function DataCard({ title, children, className = '' }: { title: string; children: React.ReactNode; className?: string }) { return <section className={`card ${className}`}><h2>{title}</h2>{children}</section> }
function PageTitle({ eyebrow, title, children }: { eyebrow: string; title: string; children?: React.ReactNode }) { return <header className="page-title"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1>{children && <p className="intro">{children}</p>}</div></header> }

export function App() {
  const [bootstrap, setBootstrap] = useState<BootstrapOut | null>(null)
  const [bootstrapError, setBootstrapError] = useState<string | null>(null)
  const [caseId, setCaseId] = useState<string | null>(null)
  const [caseData, setCaseData] = useState<CaseOut | null>(null)
  const [caseError, setCaseError] = useState<string | null>(null)
  const [location, setLocation] = useState<LocationEstimate | null>(null)
  const [equipment, setEquipment] = useState<EquipmentRecommendation | null>(null)
  const [procedure, setProcedure] = useState<ProcedureOut | null>(null)
  const [session, setSession] = useState<SessionOut | null>(null)
  const [measurement, setMeasurement] = useState<MeasurementResult | null>(null)
  const [emergency, setEmergency] = useState<EmergencyOut | null>(null)
  const navigate = useNavigate()

  const loadBootstrap = useCallback(async () => {
    try {
      const data = await api.bootstrap(); setBootstrap(data); setBootstrapError(null)
      const id = data.open_cases?.[0]?.case_id ?? ''
      if (id) setCaseId(id)
    } catch (error) { setBootstrapError(error instanceof Error ? error.message : 'Local backend unavailable.') }
  }, [])
  const refreshCase = useCallback(async (id: string) => {
    try { const data = await api.case(id); setCaseData(data); setCaseError(null); return data }
    catch (error) { setCaseError(error instanceof Error ? error.message : 'Could not load case.'); return null }
  }, [])
  useEffect(() => { void loadBootstrap() }, [loadBootstrap])
  useEffect(() => { if (caseId) void refreshCase(caseId) }, [caseId, refreshCase])

  const currentCase = caseData ?? bootstrap?.open_cases?.[0] ?? null
  const nextAction = currentCase?.next_action ?? bootstrap?.scheduled_assessments?.find(item => item.is_due)?.title
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark" aria-hidden="true">✦</span><div><strong>SENTINEL <em>AI</em></strong><small>MISSION MEDICAL CONSOLE</small></div></div>
      <div className="mission-stamp"><span className="dot" /> HAB-01 · LOCAL SYSTEM</div>
      <nav aria-label="Main navigation">
        <NavLink end to="/">Overview</NavLink><NavLink to="/body">Anatomical Twin</NavLink><NavLink to="/spatial">Location & Equipment</NavLink><NavLink to="/procedure">Procedure Coach</NavLink><NavLink to="/research">NASA Research</NavLink><NavLink to="/case">Case & Follow-Up</NavLink>
      </nav>
      <NavLink to="/emergency" className="emergency-link">Emergency assistance <span aria-hidden="true">↗</span></NavLink>
      <p className="sidebar-foot">Research prototype · fictional patient data</p>
    </aside>
    <div className="main-column">
      <header className="topbar"><span>NASA SPACE APPS CHALLENGE 2026</span><span className="topbar-right">ASTRONAUT {DEMO.astronautId} <span className="topbar-divider">/</span> {DEMO.habitatId}</span></header>
      <main>
        <Routes>
          <Route path="/" element={<Dashboard bootstrap={bootstrap} error={bootstrapError} currentCase={currentCase} caseId={caseId} nextAction={nextAction} onRetry={loadBootstrap} />} />
          <Route path="/body" element={<Anatomy onCase={id => { setCaseId(id); void refreshCase(id) }} />} />
          <Route path="/spatial" element={<Spatial bootstrap={bootstrap} caseId={caseId} location={location} equipment={equipment} onLocation={setLocation} onEquipment={setEquipment} />} />
          <Route path="/procedure" element={<ProcedureCoach caseId={caseId} equipment={equipment} procedure={procedure} session={session} measurement={measurement} onProcedure={setProcedure} onSession={setSession} onMeasurement={setMeasurement} onCaseRefresh={refreshCase} />} />
          <Route path="/research" element={<Research />} />
          <Route path="/case" element={<CaseView caseId={caseId} currentCase={currentCase} error={caseError} onRefresh={() => caseId && void refreshCase(caseId)} onReset={async () => { await api.reset(); setCaseId(null); setCaseData(null); setLocation(null); setEquipment(null); setProcedure(null); setSession(null); setMeasurement(null); setEmergency(null); await loadBootstrap(); navigate('/') }} />} />
          <Route path="/emergency" element={<Emergency emergency={emergency} onEmergency={setEmergency} />} />
          <Route path="*" element={<PageTitle eyebrow="Navigation" title="Screen not found">Choose a section from the navigation.</PageTitle>} />
        </Routes>
      </main>
      <div className="action-rail"><span className="rail-label">NEXT ACTION</span><strong>{display(nextAction ?? 'Load mission state from the local backend')}</strong><span className="rail-caveat">Backend guidance only · no clinical diagnosis</span></div>
    </div>
  </div>
}

function Dashboard({ bootstrap, error, currentCase, caseId, nextAction, onRetry }: { bootstrap: BootstrapOut | null; error: string | null; currentCase: CaseOut | CaseSummary | null; caseId: string | null; nextAction: unknown; onRetry: () => Promise<void> }) {
  const observations = bootstrap?.observations ?? []
  const dueAssessment = bootstrap?.scheduled_assessments.find(item => item.is_due)
  return <><PageTitle eyebrow="Mission overview / 01" title="Crew health overview">A clear view of what is known, what is due, and what needs attention next.</PageTitle>
    {error && <div className="status error">{error} <button className="text-button" onClick={() => void onRetry()}>Retry</button></div>}
    <div className="hero-grid"><section className="hero-card"><p className="eyebrow">FICTIONAL ASTRONAUT</p><h2>{display(bootstrap?.astronaut.display_name ?? DEMO.astronautId)}</h2><p>{DEMO.astronautId} · {DEMO.habitatId}</p><div className="hero-rule" /><div className="hero-stats"><Field label="Monitoring" value={bootstrap ? `${observations.length} observations available` : null} /><Field label="Current case" value={currentCase?.state ?? (caseId ? 'Loading' : 'No case loaded')} /><Field label="Assessment due" value={dueAssessment?.title} /></div></section>
    <DataCard title="One useful next action" className="next-card"><p className="action-text">{display(nextAction)}</p><p className="muted">This action is shown only when supplied by the local backend. Assessment selection belongs to the fictional demonstration.</p><NavLink className="button" to={caseId ? '/case' : '/body'}>{caseId ? 'Review case' : 'Report a concern'} <span aria-hidden="true">→</span></NavLink></DataCard></div>
    <div className="two-column"><DataCard title="Latest observations">{observations.length ? <div className="observation-list">{observations.map((item, index) => <div className="observation" key={index}><strong>{display(item.type)}</strong><span>{display(item.value)} {display(item.unit)}</span><small>{display(item.observed_at)} · {display(item.source)}</small></div>)}</div> : <Empty text="No observations were provided by the local backend." />}</DataCard>
    <DataCard title="Evidence & uncertainty"><div className="legend-line"><span className="tag simulated">SIMULATED ASTRONAUT</span><p>Mission patient and measurements are fictional.</p></div><div className="legend-line"><span className="tag research">NASA RESEARCH</span><p>Research participants are separate from this patient.</p></div><div className="legend-line"><span className="tag unknown">UNCERTAINTY</span><p>Technical quality and medical meaning are different.</p></div></DataCard></div>
  </>
}

function Empty({ text }: { text: string }) { return <p className="empty">{text}</p> }

function Anatomy({ onCase }: { onCase: (id: string) => void }) {
  const [selection, setSelection] = useState<BodySelection | null>(null)
  const [severity, setSeverity] = useState(3)
  const [onsetMinutes, setOnsetMinutes] = useState(45)
  const [note, setNote] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [result, setResult] = useState<ApiObject | null>(null)
  const request = useRequest()
  async function submit() { if (!selection) return; const onset = new Date(Date.now() - onsetMinutes * 60_000).toISOString(); const data = await request.run(() => api.symptom({ astronaut_id: DEMO.astronautId, region_id: selection.regionId, laterality: selection.laterality, severity, onset, ...(note.trim() ? { note: note.trim() } : {}) }), 'Symptom submitted to local backend.'); if (data) { setResult(data); setConfirm(false); onCase(data.case_id) } }
  return <><PageTitle eyebrow="Health investigation / 02" title="Anatomical Health Twin">Select the surface region where the fictional astronaut reports a concern.</PageTitle><div className="two-column anatomy-layout"><BodyMap value={selection} onChange={value => { setSelection(value); setConfirm(false); setResult(null) }} /><DataCard title="Report a symptom"><span className="tag simulated">SIMULATED ASTRONAUT</span><Field label="Selected region" value={selection?.label} /><label className="form-label">Severity · {severity} / 10<input type="range" min="0" max="10" value={severity} onChange={event => setSeverity(Number(event.target.value))} /></label><label className="form-label">Symptom began<select value={onsetMinutes} onChange={event => setOnsetMinutes(Number(event.target.value))}><option value={5}>5 minutes ago</option><option value={45}>45 minutes ago</option><option value={180}>3 hours ago</option><option value={1440}>1 day ago</option></select></label><label className="form-label">Optional note<textarea value={note} onChange={event => setNote(event.target.value)} rows={3} maxLength={1000} placeholder="Describe what the astronaut reports" /></label>{!confirm ? <button className="button" disabled={!selection} onClick={() => setConfirm(true)}>Review report</button> : <div className="confirmation"><p>Send <strong>{selection?.label}</strong>, severity <strong>{severity}/10</strong>, onset <strong>{onsetMinutes} minutes ago</strong> to the local backend?</p><div className="button-row"><button className="button" disabled={request.busy} onClick={() => void submit()}>Confirm and submit</button><button className="button secondary" onClick={() => setConfirm(false)}>Edit</button></div></div>}<Feedback {...request} />{result && <div className="result-panel"><Field label="Case ID" value={result.case_id} /><Field label="Case state" value={result.case_state} /><Field label="Next action" value={result.next_action} /></div>}</DataCard></div><AnatomyResearchPanel selection={selection} /></>
}

const ZONES = ['crew-quarters', 'exercise', 'medical', 'laboratory'] as const
function Spatial({ bootstrap, caseId, location, equipment, onLocation, onEquipment }: { bootstrap: BootstrapOut | null; caseId: string | null; location: LocationEstimate | null; equipment: EquipmentRecommendation | null; onLocation: (value: LocationEstimate) => void; onEquipment: (value: EquipmentRecommendation) => void }) {
  const [manualZone, setManualZone] = useState('')
  const estimate = useRequest(), confirm = useRequest(), recommend = useRequest()
  const zone = location?.zone_id ?? ''
  const templates = bootstrap?.demo_inputs.ble_observations ?? []
  const fixedEquipment = bootstrap?.equipment ?? []
  async function locate() { if (!templates.length) return; const now = Date.now(); const observations = templates.map(item => ({ anchor_id: item.anchor_id, rssi_dbm: item.rssi_dbm, observed_at: new Date(now - item.age_seconds * 1000).toISOString() })); const result = await estimate.run(() => api.location(observations)); if (result) onLocation(result) }
  async function confirmZone() { if (!manualZone) return; const result = await confirm.run(() => api.confirmLocation(manualZone), 'Zone confirmation saved by local backend.'); if (result) onLocation(result) }
  async function findEquipment() { if (!caseId || !zone) return; const result = await recommend.run(() => api.equipment(caseId, zone)); if (result) onEquipment(result) }
  const route = Array.isArray(equipment?.route_zone_ids) ? equipment.route_zone_ids : []
  return <><PageTitle eyebrow="Habitat intelligence / 03" title="Location & equipment">Simulated wireless observations go to the backend for zone estimation and equipment selection.</PageTitle>
    <div className="two-column"><DataCard title="Habitat zones"><div className="zone-grid">{ZONES.map(item => <div className={`zone ${zone === item ? 'active' : ''}`} key={item}><span className="zone-node" /><strong>{item.replace('-', ' ')}</strong><small>{zone === item ? 'Backend zone' : 'Registered zone'}</small></div>)}</div><p className="muted small">Habitat map is schematic. A route appears only when the backend supplies one.</p></DataCard>
    <DataCard title="Estimate astronaut zone"><span className="tag simulated">SIMULATED WIRELESS OBSERVATION</span><p className="muted small">{templates.length} fixture observations, including any unregistered anchor, will be checked by the backend.</p><button className="button" disabled={!templates.length || estimate.busy} onClick={() => void locate()}>Submit simulated observations</button><Feedback {...estimate} /><div className="result-panel"><Field label="Backend estimated zone" value={location?.zone_id} /><Field label="Confidence" value={location ? `${Math.round(location.confidence * 100)}%` : null} /><Field label="Source" value={location?.source} /><Field label="Observed at" value={location?.observed_at} /><Field label="Explanation" value={location?.explanation} /></div><label className="form-label">Manual zone confirmation<select value={manualZone} onChange={event => setManualZone(event.target.value)}><option value="">Select zone</option>{ZONES.map(item => <option key={item} value={item}>{item.replace('-', ' ')}</option>)}</select></label><button className="button secondary" disabled={!manualZone || confirm.busy} onClick={() => void confirmZone()}>Confirm zone with backend</button><Feedback {...confirm} /></DataCard></div>
    <DataCard title="Suitable equipment & route"><div className="equipment-layout"><div><p className="muted">Registered equipment from mission state</p>{fixedEquipment.length ? fixedEquipment.map((item, index) => <div className="equipment-item" key={index}><strong>{display(item.equipment_id)}</strong><span>{display(item.zone_id)} · {display(item.readiness)}</span></div>) : <Empty text="No equipment registry was supplied by the local backend." />}</div><div><button className="button" disabled={!caseId || !zone || recommend.busy} onClick={() => void findEquipment()}>Request blood pressure device</button>{!caseId && <p className="muted small">Submit a symptom to create a case first.</p>}<Feedback {...recommend} /><div className="result-panel"><Field label="Selected device" value={equipment?.equipment_id} /><Field label="Model" value={equipment?.device_model} /><Field label="Readiness" value={equipment?.readiness} /><Field label="Device zone" value={equipment?.zone_id} /><Field label="Procedure" value={equipment?.procedure_id} /><Field label="Backend route" value={route.length ? route.join(' → ') : null} /></div></div></div></DataCard></>
}

function ProcedureCoach({ caseId, equipment, procedure, session, measurement, onProcedure, onSession, onMeasurement, onCaseRefresh }: { caseId: string | null; equipment: EquipmentRecommendation | null; procedure: ProcedureOut | null; session: SessionOut | null; measurement: MeasurementResult | null; onProcedure: (value: ProcedureOut) => void; onSession: (value: SessionOut) => void; onMeasurement: (value: MeasurementResult) => void; onCaseRefresh: (id: string) => Promise<CaseOut | null> }) {
  const [mode, setMode] = useState<'self' | 'responder'>('self')
  const [systolic, setSystolic] = useState('118')
  const [diastolic, setDiastolic] = useState('76')
  const [pulse, setPulse] = useState('70')
  const [confirmMeasure, setConfirmMeasure] = useState(false)
  const load = useRequest(), start = useRequest(), stepRequest = useRequest(), measureRequest = useRequest()
  const steps = procedure?.steps ?? []
  const sessionId = session?.session_id ?? ''
  const completed = session?.completed_steps.map(item => item.step_id) ?? []
  const validReading = Number.isInteger(Number(systolic)) && Number.isInteger(Number(diastolic)) && Number(systolic) > 0 && Number(diastolic) > 0 && (!pulse || Number.isInteger(Number(pulse)))
  async function loadProcedure() { const result = await load.run(() => api.procedure(DEMO.procedureId)); if (result) onProcedure(result) }
  async function startSession() { if (!caseId) return; const result = await start.run(() => api.createSession(caseId, mode)); if (result) onSession(result) }
  async function acknowledge(stepId: string) { if (!sessionId) return; const result = await stepRequest.run(() => api.completeStep(sessionId, stepId, mode), 'Step acknowledgement saved. Clinical completion is not verified.'); if (result) onSession(result) }
  async function submitMeasurement() { if (!caseId || !sessionId || !validReading) return; const value = { systolic: Number(systolic), diastolic: Number(diastolic), ...(pulse ? { pulse: Number(pulse) } : {}) }; const result = await measureRequest.run(() => api.measurement({ case_id: caseId, session_id: sessionId, value }), 'Simulated measurement submitted to local backend.'); if (result) { onMeasurement(result); setConfirmMeasure(false); await onCaseRefresh(caseId) } }
  return <><PageTitle eyebrow="Guided assessment / 04" title="Procedure Coach">Follow the backend procedure definition for the fictional blood pressure demonstration.</PageTitle><div className="two-column"><DataCard title="Assessment context"><span className="tag simulated">EDUCATIONAL · SIMULATED</span><Field label="Case" value={caseId} /><Field label="Purpose from backend" value={procedure?.purpose} /><Field label="Selected device" value={equipment?.equipment_id} /><Field label="Device readiness" value={equipment?.readiness} /><Field label="Procedure" value={DEMO.procedureId} /><button className="button secondary" disabled={load.busy} onClick={() => void loadProcedure()}>Load procedure definition</button><Feedback {...load} />{procedure && <><p className="muted">{procedure.title}</p><ul className="muted small">{procedure.safety_limitations.map(item => <li key={item}>{item}</li>)}</ul></>}</DataCard><DataCard title="Session"><label className="form-label">Assessment mode<select value={mode} onChange={event => setMode(event.target.value as 'self' | 'responder')}><option value="self">Self assessment</option><option value="responder">Responder assistance</option></select></label><button className="button" disabled={!caseId || !procedure || start.busy} onClick={() => void startSession()}>Start backend session</button><Feedback {...start} /><Field label="Session ID" value={session?.session_id} /><Field label="Actor" value={mode === 'self' ? DEMO.astronautId : DEMO.responderId} /><Field label="Session status" value={session?.status} /><p className="muted small">The session is persisted by the backend. Step acknowledgement means the user confirmed an action, not that it was clinically verified.</p></DataCard></div>
    <DataCard title="Device-specific steps">{!procedure ? <Empty text="Load the backend procedure definition to show instructions." /> : !steps.length ? <Empty text="The backend provided no procedure steps. No instructions are invented here." /> : <ol className="step-list">{steps.map((step, index) => { const id = step.step_id; return <li key={id}><div className="step-number">{String(index + 1).padStart(2, '0')}</div><div><strong>{step.title}</strong><p>{step.instruction}</p>{mode === 'responder' && <p className="muted">Responder: {step.responder_note}</p>}</div><button className="button secondary" disabled={!sessionId || session?.current_step_id !== id || completed.includes(id) || stepRequest.busy} onClick={() => void acknowledge(id)}>{completed.includes(id) ? 'Acknowledged' : 'Acknowledge'}</button></li> })}</ol>}<Feedback {...stepRequest} /></DataCard>
    <DataCard title="Simulated measurement"><p className="muted">Enter the displayed demo reading after every procedure step is acknowledged. The backend validates technical quality and updates the case.</p><div className="measurement-row"><label className="form-label">Systolic · mmHg<input type="number" value={systolic} onChange={event => { setSystolic(event.target.value); setConfirmMeasure(false) }} /></label><label className="form-label">Diastolic · mmHg<input type="number" value={diastolic} onChange={event => { setDiastolic(event.target.value); setConfirmMeasure(false) }} /></label><label className="form-label">Pulse · bpm (optional)<input type="number" value={pulse} onChange={event => { setPulse(event.target.value); setConfirmMeasure(false) }} /></label>{!confirmMeasure ? <button className="button" disabled={session?.status !== 'completed' || !validReading} onClick={() => setConfirmMeasure(true)}>Review measurement</button> : <div className="confirmation"><p>Submit <strong>{systolic}/{diastolic} mmHg</strong> as a simulated measurement?</p><button className="button" disabled={measureRequest.busy} onClick={() => void submitMeasurement()}>Confirm and submit</button></div>}</div><Feedback {...measureRequest} />{measurement && <div className="result-panel"><Field label="Technical checks passed" value={measurement.validation.technical_checks_passed ? 'Yes' : 'No'} /><Field label="Case state" value={measurement.case_state} /><Field label="Next action" value={measurement.next_action} /><p className="muted small">Technical quality does not determine medical significance.</p></div>}</DataCard></>
}

function Research() {
  const [catalogue, setCatalogue] = useState<DatasetSummary[]>([])
  const [dataset, setDataset] = useState<DatasetDetail | null>(null)
  const [page, setPage] = useState<ResearchRecordsPage | null>(null)
  const [selected, setSelected] = useState<string>(DEMO.datasetId)
  const catalogueRequest = useRequest(), datasetRequest = useRequest()
  useEffect(() => { void catalogueRequest.run(api.datasets).then(result => { if (result) setCatalogue(result.datasets) }); void loadDataset(DEMO.datasetId) }, []) // eslint-disable-line react-hooks/exhaustive-deps
  async function loadDataset(id: string) {
    setSelected(id); setDataset(null); setPage(null)
    const detail = await datasetRequest.run(() => api.dataset(id))
    if (!detail) return
    setDataset(detail)
    if (detail.status !== 'IMPORTED') return
    const query = id === 'OSD-656' ? { analyte: 'il6', measure: 'concentration_npq' } : id === 'OSD-546' ? { gene_symbol: 'TSPAN6' } : { limit: 1000 }
    const result = await datasetRequest.run(() => api.records(id, query))
    if (result) setPage(result)
  }
  const records: ResearchRecord[] = page?.records ?? []
  const selectedMetadata = dataset ?? catalogue.find(item => item.dataset_id === selected) ?? null
  const imported = selectedMetadata?.status === 'IMPORTED'
  const studyContext = selectedMetadata?.measured ?? (selected === 'OSD-195' ? 'Human ground-analogue skeletal-muscle gene expression; not muscle strength or mass' : selected === 'OSD-546' ? 'Human-derived bone-marrow cells aboard the ISS; not astronaut bone density' : selected === 'OSD-654' ? 'Animal research; excluded from primary human-health analysis' : 'Check NASA study metadata before interpretation')
  const sourceUrl = selectedMetadata?.source_url ?? (selected === 'OSD-195' || selected === 'OSD-546' || selected === 'OSD-575' ? `https://osdr.nasa.gov/bio/repo/data/studies/${selected}` : null)
  const trend = selected === DEMO.datasetId ? trendRecords(records) : []
  const values = trend.slice(0, 16).map(item => item.value)
  const min = values.length ? Math.min(...values) : 0, max = values.length ? Math.max(...values) : 1
  const points = values.map((value, index) => `${20 + index * (440 / Math.max(values.length - 1, 1))},${170 - (value - min) / (max - min || 1) * 130}`).join(' ')
  return <><PageTitle eyebrow="Scientific context / 05" title="NASA research">Explore imported study records with provenance. Research participants are never the fictional mission patient.</PageTitle><div className="status info">NASA_RESEARCH · Research-use data only. Reference ranges are not astronaut diagnostic thresholds.</div><div className="two-column research-top"><DataCard title="Dataset catalogue"><div className="dataset-list">{DATASET_IDS.map(id => { const item = catalogue.find(entry => entry.dataset_id === id); return <button key={id} className={`dataset-item ${selected === id ? 'active' : ''}`} onClick={() => void loadDataset(id)}><strong>{id}</strong><span>{id === 'OSD-654' ? 'Animal research · ' : ''}{item?.status ?? 'Status unavailable'}</span></button> })}</div><Feedback {...catalogueRequest} /></DataCard><DataCard title="Study provenance"><Field label="Dataset ID" value={selectedMetadata?.dataset_id ?? selected} /><Field label="Availability" value={selectedMetadata?.status} /><Field label="Reason" value={selectedMetadata?.status_reason} /><Field label="Study type" value={selectedMetadata?.study_type} /><Field label="Human-health track" value={selectedMetadata?.human_health_analysis} /><Field label="Measured" value={studyContext} />{selectedMetadata?.not_a_measurement_of?.length ? <p className="muted small">Not a measurement of: {selectedMetadata.not_a_measurement_of.join(", ")}</p> : null}<Field label="Source file" value={page?.source_file} /><Field label="Record count" value={selectedMetadata?.records_available} /><Field label="Record schema" value={selectedMetadata?.record_schema} /><p className="muted small">Only imported datasets can populate numerical views. Missing values remain missing.</p>{sourceUrl && <a href={sourceUrl} target="_blank" rel="noreferrer">NASA source ↗</a>}<Feedback {...datasetRequest} /></DataCard></div>
    <DataCard title="Actual measurements"><div className="research-header"><p className="muted">{selected === DEMO.datasetId ? 'OSD-575 comprehensive metabolic panel' : selected}</p><span className="tag research">NASA RESEARCH</span></div>{!imported ? <Empty text="Numerical records unavailable until the backend reports this dataset as IMPORTED." /> : page?.record_schema === "GENE_EXPRESSION_V1" ? <ExpressionResults page={page} /> : page?.record_schema === "BIO_ASSAY_TABLE" ? <AssayResults page={page} /> : !records.length ? <Empty text="No numerical records returned by the local research API." /> : <><div className="chart-wrap">{values.length > 1 ? <svg viewBox="0 0 480 190" role="img" aria-label={`Trend of ${trend[0].analyte} for ${trend[0].subject} in ${trend[0].unit}; source order`}><line x1="20" y1="170" x2="465" y2="170" className="axis" /><polyline points={points} className="trend" />{points.split(' ').map((point, i) => { const [cx, cy] = point.split(','); return <circle key={i} cx={cx} cy={cy} r="4" className="trend-point" /> })}</svg> : <Empty text="At least two comparable numeric records are needed for a trend chart." />}</div>{values.length > 1 && <p className="muted small">{trend[0].analyte} · subject {trend[0].subject} · {trend[0].unit}. Source order; timepoint labels remain in the table.</p>}<div className="table-scroll"><table><thead><tr><th>Analyte</th><th>Value</th><th>Unit</th><th>Subject</th><th>Timepoint</th></tr></thead><tbody>{records.slice(0, 30).map((record, i) => <tr key={i}><td>{display(record.analyte ?? record.ANALYTE)}</td><td>{display(record.value ?? record.VALUE)}</td><td>{display(record.unit ?? record.units ?? record.UNITS)}</td><td>{display(record.subject_id ?? record.SUBJECT_ID)}</td><td>{display(record.timepoint)}</td></tr>)}</tbody></table></div></>}</DataCard></>
}

function CaseView({ caseId, currentCase, error, onRefresh, onReset }: { caseId: string | null; currentCase: CaseOut | CaseSummary | null; error: string | null; onRefresh: () => void; onReset: () => Promise<void> }) {
  const reset = useRequest()
  return <><PageTitle eyebrow="Closed-loop follow-up / 06" title="Case progress">Persisted case state and the next required action come from the local backend.</PageTitle><div className="two-column"><DataCard title="Current case"><span className="tag simulated">SIMULATED ASTRONAUT</span><Field label="Case ID" value={caseId} /><Field label="State" value={currentCase?.state} /><Field label="Next action" value={currentCase?.next_action} /><Field label="Updated" value={currentCase?.updated_at} /><Field label="Follow-up" value={currentCase && 'follow_up_status' in currentCase ? currentCase.follow_up_status : null} />{error && <p className="status error">{error}</p>}<button className="button secondary" disabled={!caseId} onClick={onRefresh}>Refresh case from backend</button></DataCard><DataCard title="Repeat demonstration"><p className="muted">Reset clears the fictional backend scenario, then reloads its initial state.</p><button className="button secondary" disabled={reset.busy} onClick={() => void reset.run(onReset, 'Demo reset and reloaded.')}>Reset demo scenario</button><Feedback {...reset} /></DataCard></div></>
}

function Emergency({ emergency, onEmergency }: { emergency: EmergencyOut | null; onEmergency: (value: EmergencyOut) => void }) {
  const request = useRequest()
  const [confirm, setConfirm] = useState(false)
  async function activate() { const result = await request.run(api.emergency, 'Emergency request recorded by local backend.'); if (result) { onEmergency(result); setConfirm(false) } }
  return <div className="emergency-page"><PageTitle eyebrow="Immediate response / 07" title="Emergency assistance">For the fictional collapse demonstration. This screen opens without location, equipment, research data, or Earth communications.</PageTitle><div className="emergency-banner"><strong>Urgent scenario</strong><p>Alert the crew and follow authorized onboard emergency protocols. If a verified protocol is unavailable, seek trained crew or ground medical guidance when communications permit.</p></div><div className="two-column"><DataCard title="Response record"><Field label="Patient" value={DEMO.astronautId} /><Field label="Responder" value={DEMO.responderId} /><Field label="Trigger" value="Fictional collapse demonstration" />{!confirm ? <button className="button danger" onClick={() => setConfirm(true)}>Activate emergency assistance</button> : <div className="confirmation"><p>Record emergency activation for {DEMO.astronautId} with responder {DEMO.responderId}?</p><div className="button-row"><button className="button danger" disabled={request.busy} onClick={() => void activate()}>Confirm activation</button><button className="button secondary" onClick={() => setConfirm(false)}>Cancel</button></div></div>}<Feedback {...request} /></DataCard><DataCard title="Backend response"><Field label="Urgent case status" value={emergency?.case_state} /><Field label="Case ID" value={emergency?.case_id} /><Field label="Crew escalation" value={emergency?.crew_alert.status} /><Field label="Ground escalation" value={emergency?.flight_surgeon_escalation.status} /><Field label="Next action" value={emergency?.next_action} />{emergency?.emergency_information && <p className="muted small">{emergency.emergency_information.limitation}</p>}<p className="muted small">Equipment and location assistance are secondary to immediate response.</p></DataCard></div></div>
}

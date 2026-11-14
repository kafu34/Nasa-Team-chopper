import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { api, DATASET_IDS, DEMO, display, type ApiObject, type BootstrapOut, type CaseOut, type CaseSummary, type LocationEstimate, type EquipmentRecommendation, type ProcedureOut, type SessionOut, type MeasurementResult, type EmergencyOut, type DatasetSummary, type DatasetDetail, type ResearchRecord, type ResearchRecordsPage, type TimeseriesPage } from './api'
import type { BodySelection } from './BodyMap'
import { reportedSurfaceSelection, surfaceDetail, surfacePoint, symptomNote } from './anatomy-sites'
import { trendRecords } from './research'
import { AnatomyResearchPanel, ExpressionResults } from './AnatomyResearchPanel'
import { AssayResults } from './AssayResults'
import { HistologyResults, RadiationResults } from './ResearchSpecialResults'
import { ActionReminder } from './ActionReminder'
import { strongestAlert, symptomAlerts, type BodyAlerts } from './mission-ui'

const ThreeBody = lazy(() => import('./ThreeBody').then(module => ({ default: module.ThreeBody })))

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
function readPreference(key: string) { try { return window.localStorage.getItem(key) !== 'off' } catch { return true } }
function savePreference(key: string, enabled: boolean) { try { window.localStorage.setItem(key, enabled ? 'on' : 'off') } catch { /* Session-only preference when storage is unavailable. */ } }

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
  const [focusedRegion, setFocusedRegion] = useState<BodySelection | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [animateAlerts, setAnimateAlerts] = useState(() => readPreference('sentinel-animate-alerts'))
  const [remindersEnabled, setRemindersEnabled] = useState(() => readPreference('sentinel-reminders'))
  const navigate = useNavigate()
  const route = useLocation()

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
  const nextAction = currentCase?.next_action ?? bootstrap?.scheduled_assessments?.find(item => item.status === 'scheduled')?.title
  const reminderDueAt = caseData?.follow_ups?.find(item => item.status !== 'completed')?.due_at ?? bootstrap?.scheduled_assessments?.find(item => item.status === 'scheduled')?.due_at ?? null
  const bodyAlerts = symptomAlerts(caseData)
  const savedPoints = (caseData?.symptoms ?? []).flatMap(symptom => { const selection = reportedSurfaceSelection(symptom); return selection?.point ? [{ selection, severity: symptom.severity }] : [] })
  const openBody = (region: BodySelection | null) => { setFocusedRegion(region); navigate('/body') }
  useEffect(() => { setMenuOpen(false); setSettingsOpen(false) }, [route.pathname])
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
      <header className="topbar"><span>NASA SPACE APPS CHALLENGE 2026</span><div className="topbar-tools"><span className="topbar-right">ASTRONAUT {DEMO.astronautId} <span className="topbar-divider">/</span> {DEMO.habitatId}</span><button type="button" className="menu-toggle" aria-label="Open menu" aria-expanded={menuOpen} aria-controls="utility-menu" onClick={() => setMenuOpen(value => !value)}><svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 6h16M4 12h16M4 18h16" /></svg><span>Menu</span></button>{menuOpen && <div id="utility-menu" className="utility-menu"><div className="utility-menu-heading"><strong>{settingsOpen ? 'Settings' : 'Mission menu'}</strong><button type="button" aria-label="Close menu" onClick={() => setMenuOpen(false)}>×</button></div>{settingsOpen ? <><p className="muted small">Display preferences are saved on this device.</p><label><input type="checkbox" checked={animateAlerts} onChange={event => { setAnimateAlerts(event.target.checked); savePreference('sentinel-animate-alerts', event.target.checked) }} /> Animated symptom highlights</label><label><input type="checkbox" checked={remindersEnabled} onChange={event => { setRemindersEnabled(event.target.checked); savePreference('sentinel-reminders', event.target.checked) }} /> Timed next-action reminders</label><button type="button" className="utility-back" onClick={() => setSettingsOpen(false)}>← Back to menu</button></> : <><NavLink to="/" onClick={() => setMenuOpen(false)}>Overview</NavLink><NavLink to="/body" onClick={() => setMenuOpen(false)}>Anatomical Twin</NavLink><NavLink to="/spatial" onClick={() => setMenuOpen(false)}>Maps · choose my location</NavLink><NavLink to="/procedure" onClick={() => setMenuOpen(false)}>Procedure Coach</NavLink><NavLink to="/research" onClick={() => setMenuOpen(false)}>NASA Research</NavLink><NavLink to="/case" onClick={() => setMenuOpen(false)}>Case & Follow-Up</NavLink><button type="button" onClick={() => setSettingsOpen(true)}>Settings</button></>}</div>}</div></header>
      <main>
        <Routes>
          <Route path="/" element={<Dashboard bootstrap={bootstrap} error={bootstrapError} currentCase={currentCase} alerts={bodyAlerts} savedPoints={savedPoints} animateAlerts={animateAlerts} onOpenBody={openBody} onRetry={loadBootstrap} />} />
          <Route path="/body" element={<Anatomy initialSelection={focusedRegion} alerts={bodyAlerts} savedPoints={savedPoints} animateAlerts={animateAlerts} onCase={id => { setCaseId(id); void refreshCase(id) }} />} />
          <Route path="/spatial" element={<Spatial bootstrap={bootstrap} caseId={caseId} location={location} equipment={equipment} onLocation={setLocation} onEquipment={setEquipment} />} />
          <Route path="/procedure" element={<ProcedureCoach caseId={caseId} equipment={equipment} procedure={procedure} session={session} measurement={measurement} onProcedure={setProcedure} onSession={setSession} onMeasurement={setMeasurement} onCaseRefresh={refreshCase} />} />
          <Route path="/research" element={<Research />} />
          <Route path="/case" element={<CaseView caseId={caseId} currentCase={currentCase} error={caseError} onRefresh={() => caseId && void refreshCase(caseId)} onReset={async () => { await api.reset(); setCaseId(null); setCaseData(null); setFocusedRegion(null); setLocation(null); setEquipment(null); setProcedure(null); setSession(null); setMeasurement(null); setEmergency(null); await loadBootstrap(); navigate('/') }} />} />
          <Route path="/emergency" element={<Emergency emergency={emergency} onEmergency={setEmergency} />} />
          <Route path="*" element={<PageTitle eyebrow="Navigation" title="Screen not found">Choose a section from the navigation.</PageTitle>} />
        </Routes>
      </main>
      <ActionReminder action={typeof nextAction === 'string' ? nextAction : null} dueAt={reminderDueAt} link={currentCase ? '/case' : '/procedure'} enabled={remindersEnabled} hidden={route.pathname === '/emergency'} />
    </div>
  </div>
}

function Dashboard({ bootstrap, error, currentCase, alerts, savedPoints, animateAlerts, onOpenBody, onRetry }: { bootstrap: BootstrapOut | null; error: string | null; currentCase: CaseOut | CaseSummary | null; alerts: BodyAlerts; savedPoints: { selection: BodySelection; severity: number }[]; animateAlerts: boolean; onOpenBody: (region: BodySelection | null) => void; onRetry: () => Promise<void> }) {
  const observations = bootstrap?.observations ?? []
  const latest = observations.filter((item, index) => observations.findIndex(candidate => candidate.type === item.type) === index).slice(0, 4)
  const assessment = bootstrap?.scheduled_assessments.find(item => item.status === 'scheduled')
  const alert = strongestAlert(alerts)
  return <><PageTitle eyebrow="Mission overview / 01" title="Crew health overview">Check observations, report pain on the body, or open the habitat map.</PageTitle>
    {error && <div className="status error">{error} <button className="text-button" onClick={() => void onRetry()}>Retry</button></div>}
    <div className="dashboard-identity"><div><span className="eyebrow">FICTIONAL ASTRONAUT · {DEMO.astronautId}</span><h2>{display(bootstrap?.astronaut.display_name ?? DEMO.astronautId)}</h2><p>{DEMO.habitatId} · {currentCase ? `Case ${currentCase.state.replaceAll('_', ' ')}` : 'No active case loaded'}</p></div><div className="dashboard-actions"><button type="button" className="button" onClick={() => onOpenBody(null)}>Report pain on body</button><NavLink className="button secondary" to="/spatial">Open habitat map</NavLink><NavLink className="button secondary" to="/procedure">Assessment guide</NavLink></div></div>
    <div className="dashboard-grid"><section className="card dashboard-vitals"><div className="dashboard-card-head"><div><p className="eyebrow">HEALTH OBSERVATIONS</p><h2>Vitals at a glance</h2></div><span className="tag simulated">SIMULATED ASTRONAUT</span></div>{latest.length ? <div className="vital-grid">{latest.map((item, index) => <div className="vital-tile" key={`${item.type}-${index}`}><span>{item.type.replaceAll('_', ' ')}</span><strong>{display(item.value)} <small>{display(item.unit)}</small></strong><small>{display(item.source)} · {new Date(item.observed_at).toLocaleString()}</small></div>)}</div> : <Empty text="No observations were supplied by the local backend." />}<p className="muted small">Values come from the fictional mission backend. They are not live sensor readings or clinical interpretations.</p></section>
    <section className={`card dashboard-twin ${alert ? `dashboard-twin--${alert.tone}` : ''}`}><div className="dashboard-card-head"><div><p className="eyebrow">INTERACTIVE ANATOMICAL TWIN</p><h2>Where does it hurt?</h2></div>{alert && <span className={`severity-chip severity-chip--${alert.tone}`}>Reported {alert.severity}/10</span>}</div><p className="muted small">Tap the 3D body to expand it, rotate, zoom, and pinpoint a concern.</p><Suspense fallback={<p className="muted small">Loading 3D body…</p>}><ThreeBody value={null} onChange={onOpenBody} alerts={alerts} savedPoints={savedPoints} compact animateAlerts={animateAlerts} /></Suspense><button type="button" className="button dashboard-expand" onClick={() => onOpenBody(null)}>Expand anatomical twin →</button>{alert && <p className="muted small">{alert.tone === 'red' ? 'Red' : 'Orange'} highlights show self-reported severity, not a diagnosis.</p>}</section></div>
    <div className="dashboard-lower"><section className="card dashboard-schedule"><p className="eyebrow">SCHEDULED ASSESSMENT</p><h2>{assessment?.title ?? 'No assessment scheduled'}</h2><p className="muted">{assessment ? `${assessment.is_due ? 'Due now' : 'Upcoming'} · ${new Date(assessment.due_at).toLocaleString()}` : 'The local backend will supply the next assessment.'}</p><NavLink to={currentCase ? '/case' : '/procedure'}>View assessment details →</NavLink></section><details className="card dashboard-evidence"><summary>Evidence and uncertainty</summary><p>Mission patient data is fictional. NASA research participants are separate from this patient. Technical quality and medical meaning are different.</p></details></div>
  </>
}

function Empty({ text }: { text: string }) { return <p className="empty">{text}</p> }

function Anatomy({ initialSelection, alerts, savedPoints, animateAlerts, onCase }: { initialSelection: BodySelection | null; alerts: BodyAlerts; savedPoints: { selection: BodySelection; severity: number }[]; animateAlerts: boolean; onCase: (id: string) => void }) {
  const [selection, setSelection] = useState<BodySelection | null>(initialSelection)
  const [severity, setSeverity] = useState(3)
  const [onsetMinutes, setOnsetMinutes] = useState(45)
  const [note, setNote] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [result, setResult] = useState<ApiObject | null>(null)
  const request = useRequest()
  async function submit() { if (!selection) return; const onset = new Date(Date.now() - onsetMinutes * 60_000).toISOString(); const savedNote = symptomNote(selection, note); const point = surfacePoint(selection); const data = await request.run(() => api.symptom({ astronaut_id: DEMO.astronautId, region_id: selection.regionId, laterality: selection.laterality, severity, onset, ...(savedNote ? { note: savedNote } : {}), ...(point ? { surface_point: point } : {}) }), 'Symptom submitted to local backend.'); if (data) { setResult(data); setConfirm(false); onCase(data.case_id) } }
  return <><PageTitle eyebrow="Health investigation / 02" title="Point to where it hurts">Rotate and zoom the 3D body, then tap the surface where the fictional astronaut reports a concern.</PageTitle><NavLink className="back-link" to="/">← Back to vitals</NavLink><div className="two-column anatomy-layout"><Suspense fallback={<div className="three-body"><p className="muted">Loading 3D body…</p></div>}><ThreeBody value={selection} alerts={alerts} savedPoints={savedPoints} animateAlerts={animateAlerts} onChange={value => { setSelection(value); setConfirm(false); setResult(null) }} /></Suspense><DataCard title="Report a symptom"><span className="tag simulated">SIMULATED ASTRONAUT</span><Field label="Selected area" value={selection?.label} /><Field label="Backend region" value={selection?.regionId.replaceAll('_', ' ')} />{selection?.point ? <p className="muted small">The exact diagram point is saved separately from your note. Backend rules still use the broader region shown above.</p> : selection && surfaceDetail(selection) && <p className="muted small">This named area has no exact surface point. Its site name is included in the note under the broader backend region.</p>}<label className="form-label">Severity · {severity} / 10<input type="range" min="0" max="10" value={severity} onChange={event => setSeverity(Number(event.target.value))} /></label><label className="form-label">Symptom began<select value={onsetMinutes} onChange={event => setOnsetMinutes(Number(event.target.value))}><option value={5}>5 minutes ago</option><option value={45}>45 minutes ago</option><option value={180}>3 hours ago</option><option value={1440}>1 day ago</option></select></label><label className="form-label">Optional note<textarea value={note} onChange={event => setNote(event.target.value)} rows={3} maxLength={800} placeholder="Describe what the astronaut reports" /></label>{!confirm ? <button className="button" disabled={!selection} onClick={() => setConfirm(true)}>Review report</button> : <div className="confirmation"><p>Send <strong>{selection?.label}</strong>, severity <strong>{severity}/10</strong>, onset <strong>{onsetMinutes} minutes ago</strong> to the local backend?</p>{selection && surfaceDetail(selection) && <p className="muted small">{surfaceDetail(selection)}</p>}<div className="button-row"><button className="button" disabled={request.busy} onClick={() => void submit()}>Confirm and submit</button><button className="button secondary" onClick={() => setConfirm(false)}>Edit</button></div></div>}<Feedback {...request} />{result && <div className="result-panel"><Field label="Case ID" value={result.case_id} /><Field label="Case state" value={result.case_state} /><Field label="Next action" value={result.next_action} /></div>}</DataCard></div><AnatomyResearchPanel selection={selection} /></>
}

const ZONES = ['crew-quarters', 'exercise', 'medical', 'laboratory'] as const
function Spatial({ bootstrap, caseId, location, equipment, onLocation, onEquipment }: { bootstrap: BootstrapOut | null; caseId: string | null; location: LocationEstimate | null; equipment: EquipmentRecommendation | null; onLocation: (value: LocationEstimate) => void; onEquipment: (value: EquipmentRecommendation) => void }) {
  const [manualZone, setManualZone] = useState('')
  const estimate = useRequest(), confirm = useRequest(), recommend = useRequest()
  const zone = location?.zone_id ?? ''
  const templates = bootstrap?.demo_inputs.ble_observations ?? []
  const fixedEquipment = bootstrap?.equipment ?? []
  const zones = bootstrap?.habitat.zones ?? ZONES.map(item => ({ zone_id: item, name: item.replace('-', ' ') }))
  async function locate() { if (!templates.length) return; const now = Date.now(); const observations = templates.map(item => ({ anchor_id: item.anchor_id, rssi_dbm: item.rssi_dbm, observed_at: new Date(now - item.age_seconds * 1000).toISOString() })); const result = await estimate.run(() => api.location(observations)); if (result) onLocation(result) }
  async function confirmZone() { if (!manualZone) return; const result = await confirm.run(() => api.confirmLocation(manualZone), 'Zone confirmation saved by local backend.'); if (result) onLocation(result) }
  async function findEquipment() { if (!caseId || !zone) return; const result = await recommend.run(() => api.equipment(caseId, zone)); if (result) onEquipment(result) }
  const route = Array.isArray(equipment?.route_zone_ids) ? equipment.route_zone_ids : []
  return <><PageTitle eyebrow="Habitat intelligence / 03" title="Habitat map & equipment">Choose where you are on the schematic map, or ask the backend to estimate your zone from simulated wireless observations.</PageTitle>
    <div className="two-column"><DataCard title="Choose my location"><p className="muted small">Tap a registered habitat zone, then confirm it. This is a manual report, not automatic tracking.</p><div className="zone-grid">{zones.map(item => <button type="button" className={`zone ${zone === item.zone_id ? 'active' : ''} ${manualZone === item.zone_id ? 'zone--selected' : ''}`} aria-pressed={manualZone === item.zone_id} onClick={() => setManualZone(item.zone_id)} key={item.zone_id}><span className="zone-node" /><strong>{item.name}</strong><small>{zone === item.zone_id ? 'Backend location' : manualZone === item.zone_id ? 'Selected for confirmation' : 'Registered zone'}</small></button>)}</div><button className="button map-confirm" disabled={!manualZone || confirm.busy} onClick={() => void confirmZone()}>Confirm {manualZone ? zones.find(item => item.zone_id === manualZone)?.name ?? manualZone : 'selected zone'}</button><Feedback {...confirm} /><p className="muted small">The habitat map is schematic. A route appears only when the backend supplies one.</p></DataCard>
    <DataCard title="Estimate astronaut zone"><span className="tag simulated">SIMULATED WIRELESS OBSERVATION</span><p className="muted small">{templates.length} fixture observations, including any unregistered anchor, will be checked by the backend.</p><button className="button" disabled={!templates.length || estimate.busy} onClick={() => void locate()}>Submit simulated observations</button><Feedback {...estimate} /><div className="result-panel"><Field label="Backend estimated zone" value={location?.zone_id} /><Field label="Confidence" value={location ? `${Math.round(location.confidence * 100)}%` : null} /><Field label="Source" value={location?.source} /><Field label="Observed at" value={location?.observed_at} /><Field label="Explanation" value={location?.explanation} /></div></DataCard></div>
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
  const [radiation, setRadiation] = useState<TimeseriesPage | null>(null)
  const [instrument, setInstrument] = useState('DosTel1')
  const [selected, setSelected] = useState<string>(DEMO.datasetId)
  const requestNumber = useRef(0)
  const catalogueRequest = useRequest(), datasetRequest = useRequest()
  useEffect(() => { void catalogueRequest.run(api.datasets).then(result => { if (result) setCatalogue(result.datasets) }); void loadDataset(DEMO.datasetId) }, []) // eslint-disable-line react-hooks/exhaustive-deps
  async function loadDataset(id: string) {
    const current = ++requestNumber.current
    setSelected(id); setDataset(null); setPage(null); setRadiation(null)
    const detail = await datasetRequest.run(() => api.dataset(id))
    if (!detail || current !== requestNumber.current) return
    setDataset(detail)
    if (detail.status !== 'IMPORTED') return
    if (id === 'NASA-RADLAB') {
      setInstrument('DosTel1')
      const result = await datasetRequest.run(() => api.radiation('DosTel1'))
      if (result && current === requestNumber.current) setRadiation(result)
      return
    }
    const query = id === 'OSD-656' ? { analyte: 'il6', measure: 'concentration_npq' } : id === 'OSD-546' ? { gene_symbol: 'TSPAN6' } : { limit: 1000 }
    const result = await datasetRequest.run(() => api.records(id, query))
    if (result && current === requestNumber.current) setPage(result)
  }
  async function loadInstrument(id: string) {
    const current = ++requestNumber.current
    setInstrument(id); setRadiation(null)
    const result = await datasetRequest.run(() => api.radiation(id))
    if (result && current === requestNumber.current) setRadiation(result)
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
    <DataCard title="Actual measurements"><div className="research-header"><p className="muted">{selected === DEMO.datasetId ? 'OSD-575 comprehensive metabolic panel' : selected}</p><span className="tag research">NASA RESEARCH</span></div>{!imported ? <Empty text="Numerical records unavailable until the backend reports this dataset as IMPORTED." /> : selected === 'NASA-RADLAB' ? radiation ? <RadiationResults page={radiation} instrument={instrument} onInstrument={value => void loadInstrument(value)} /> : <Empty text={datasetRequest.error ? 'RadLab readings could not be loaded from the local backend.' : 'Loading historical RadLab readings from the local backend.'} /> : page?.record_schema === "GENE_EXPRESSION_V1" ? <ExpressionResults page={page} /> : page?.record_schema === "BIO_ASSAY_TABLE" ? <AssayResults page={page} /> : page?.record_schema === "HISTOLOGY_COUNTS_V1" ? <HistologyResults page={page} /> : !records.length ? <Empty text="No numerical records returned by the local research API." /> : <><div className="chart-wrap">{values.length > 1 ? <svg viewBox="0 0 480 190" role="img" aria-label={`Trend of ${trend[0].analyte} for ${trend[0].subject} in ${trend[0].unit}; source order`}><line x1="20" y1="170" x2="465" y2="170" className="axis" /><polyline points={points} className="trend" />{points.split(' ').map((point, i) => { const [cx, cy] = point.split(','); return <circle key={i} cx={cx} cy={cy} r="4" className="trend-point" /> })}</svg> : <Empty text="At least two comparable numeric records are needed for a trend chart." />}</div>{values.length > 1 && <p className="muted small">{trend[0].analyte} · subject {trend[0].subject} · {trend[0].unit}. Source order; timepoint labels remain in the table.</p>}<div className="table-scroll"><table><thead><tr><th>Analyte</th><th>Value</th><th>Unit</th><th>Subject</th><th>Timepoint</th></tr></thead><tbody>{records.slice(0, 30).map((record, i) => <tr key={i}><td>{display(record.analyte ?? record.ANALYTE)}</td><td>{display(record.value ?? record.VALUE)}</td><td>{display(record.unit ?? record.units ?? record.UNITS)}</td><td>{display(record.subject_id ?? record.SUBJECT_ID)}</td><td>{display(record.timepoint)}</td></tr>)}</tbody></table></div></>}</DataCard></>
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

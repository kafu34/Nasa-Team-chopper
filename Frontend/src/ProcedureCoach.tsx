import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { api, DEMO, type CaseOut, type EquipmentRecommendation, type MeasurementResult, type ProcedureOut, type SessionOut } from './api'
import { ProcedurePictures } from './ProcedurePictures'
import { stepStateFor, useStepEvents } from './step-events'
import { visualFor } from './visual-registry'
import './procedure.css'

const ProcedureVisual = lazy(() => import('./ProcedureVisual').then(module => ({ default: module.ProcedureVisual })))
type Props = { caseId: string | null; equipment: EquipmentRecommendation | null; procedure: ProcedureOut | null; session: SessionOut | null; measurement: MeasurementResult | null; requestedProcedureId?: string | null; onProcedure: (value: ProcedureOut) => void; onSession: (value: SessionOut) => void; onMeasurement: (value: MeasurementResult) => void; onCaseRefresh: (id: string) => Promise<CaseOut | null> }
type Work = { busy: boolean; error: string | null; notice: string | null }
const empty: Work = { busy: false, error: null, notice: null }
const sessionKey = (caseId: string) => `sentinel:procedure-session:${caseId}`
const viewedKey = (sessionId: string) => `sentinel:visual-viewed:${sessionId}`

function useWork() {
  const [work, setWork] = useState<Work>(empty)
  const run = useCallback(async <T,>(action: () => Promise<T>, notice?: string): Promise<T | null> => {
    setWork({ busy: true, error: null, notice: null })
    try { const value = await action(); setWork({ busy: false, error: null, notice: notice ?? null }); return value }
    catch (error) { setWork({ busy: false, error: error instanceof Error ? error.message : 'Request failed.', notice: null }); return null }
  }, [])
  return { ...work, run }
}
function Feedback({ work }: { work: Work }) { return <div aria-live="polite">{work.busy && <p className="status info">Contacting local backend…</p>}{work.error && <p className="status error">{work.error}</p>}{work.notice && <p className="status success">{work.notice}</p>}</div> }
function readLocal(key: string) { try { return window.localStorage.getItem(key) } catch { return null } }
function writeLocal(key: string, value: string | null) { try { if (value === null) window.localStorage.removeItem(key); else window.localStorage.setItem(key, value) } catch { /* Local memory only when storage is disabled. */ } }

export function ProcedureCoach({ caseId, equipment, procedure, session, measurement, requestedProcedureId, onProcedure, onSession, onMeasurement, onCaseRefresh }: Props) {
  const [mode, setMode] = useState<'self' | 'responder'>('self')
  const [selectedStep, setSelectedStep] = useState('S1')
  const [viewMode, setViewMode] = useState<'pictures' | 'animation'>('pictures')
  const [viewed, setViewed] = useState<string[]>([])
  const [systolic, setSystolic] = useState('118'), [diastolic, setDiastolic] = useState('76'), [pulse, setPulse] = useState('70')
  const [confirmMeasure, setConfirmMeasure] = useState(false)
  const load = useWork(), restore = useWork(), start = useWork(), stepWork = useWork(), measureWork = useWork()
  const steps = procedure?.steps ?? []
  const activeStep = steps.find(step => step.step_id === selectedStep) ?? steps[0]
  const activeIndex = Math.max(0, steps.findIndex(step => step.step_id === activeStep?.step_id))
  const activeScene = activeStep ? visualFor(activeStep) : null
  const completed = new Set(session?.completed_steps.map(item => item.step_id) ?? [])
  const refreshSession = useCallback(() => { if (session?.session_id) void api.getSession(session.session_id).then(onSession).catch(() => { /* The periodic refresh will retry. */ }) }, [session?.session_id, onSession])
  const { recordViewed, recordError } = useStepEvents(session, activeStep, !!activeScene, refreshSession)
  const activeState = stepStateFor(session, activeStep?.step_id)
  const viewedAnywhere = (stepId: string) => viewed.includes(stepId) || (stepStateFor(session, stepId)?.view_count ?? 0) > 0
  const validReading = [systolic, diastolic, pulse].every(value => value === '' || Number.isInteger(Number(value))) && Number(systolic) > 0 && Number(diastolic) > 0 && (!pulse || Number(pulse) > 0)

  useEffect(() => { if (!procedure) void load.run(() => api.procedure(DEMO.procedureId)).then(value => { if (value) onProcedure(value) }) }, [procedure, load.run, onProcedure])
  useEffect(() => {
    if (!caseId || session?.case_id === caseId) return
    const id = readLocal(sessionKey(caseId))
    if (!id) return
    void restore.run(() => api.getSession(id)).then(value => {
      if (value?.case_id === caseId && value.procedure_id === DEMO.procedureId) onSession(value)
      else if (!value || value.case_id !== caseId) writeLocal(sessionKey(caseId), null)
    })
  }, [caseId, session?.case_id, restore.run, onSession])
  useEffect(() => { if (session?.current_step_id) setSelectedStep(session.current_step_id); if (session?.mode) setMode(session.mode) }, [session?.current_step_id, session?.mode])
  useEffect(() => { if (session?.session_id) { const raw = readLocal(viewedKey(session.session_id)); try { setViewed(raw ? JSON.parse(raw) as string[] : []) } catch { setViewed([]) } } }, [session?.session_id])
  useEffect(() => { if (!session?.session_id) return; const refresh = () => { void api.getSession(session.session_id).then(onSession).catch(() => { /* Existing session remains visible during a brief backend outage. */ }) }; refresh(); const timer = window.setInterval(refresh, 15_000); return () => window.clearInterval(timer) }, [session?.session_id, onSession])

  async function startSession() {
    if (!caseId || requestedProcedureId && requestedProcedureId !== DEMO.procedureId) return
    const value = await start.run(() => api.createSession(caseId, mode), 'Backend session started.')
    if (value) { writeLocal(sessionKey(caseId), value.session_id); onSession(value) }
  }
  async function acknowledge(stepId: string) {
    if (!session?.session_id) return
    const value = await stepWork.run(() => api.completeStep(session.session_id, stepId, mode), 'Step acknowledgement saved. Clinical completion is not verified.')
    if (value) onSession(value)
  }
  async function submitMeasurement() {
    if (!caseId || !session?.session_id || !validReading) return
    const value = await measureWork.run(() => api.measurement({ case_id: caseId, session_id: session.session_id, type: 'blood_pressure', unit: 'mmHg', value: { systolic: Number(systolic), diastolic: Number(diastolic), ...(pulse ? { pulse: Number(pulse) } : {}) } }), 'Simulated measurement submitted to local backend.')
    if (value) { onMeasurement(value); setConfirmMeasure(false); await onCaseRefresh(caseId) }
  }
  const markViewed = (stepId: string) => {
    setViewed(current => { const next = current.includes(stepId) ? current : [...current, stepId]; if (session?.session_id) writeLocal(viewedKey(session.session_id), JSON.stringify(next)); return next })
    const target = steps.find(step => step.step_id === stepId)
    if (target) recordViewed(target)
  }
  const deviceMatch = !equipment || procedure?.compatible_device_models.includes(equipment.device_model)

  return <div className="procedure-page">
    <header className="page-title"><div><p className="eyebrow">Guided assessment / 04</p><h1>Visual Procedure Coach</h1><p className="intro">Watch each backend-defined action, then acknowledge the real-world step separately.</p></div></header>
    <div className="procedure-context"><div><span className="tag simulated">{procedure?.validation_level?.replaceAll('_', ' ') ?? 'EDUCATIONAL DEMONSTRATION'}</span><h2>{procedure?.title ?? 'Loading PROC-BP-01'}</h2><p>{procedure?.purpose ?? 'Waiting for the local procedure definition.'}</p></div><div className="procedure-context-facts"><span>Procedure <strong>{DEMO.procedureId}{procedure ? ` · ${procedure.version}` : ''}</strong></span><span>Selected device <strong>{equipment ? `${equipment.equipment_id} · ${equipment.device_model} · ${equipment.readiness}` : 'No device selected yet'}</strong></span><span>Compatible model <strong>{procedure?.compatible_device_models.join(', ') ?? 'Waiting for definition'}</strong></span><span>Case <strong>{caseId ?? 'No case yet'}</strong></span></div></div>
    {!deviceMatch && <p className="status error">The selected device is not listed as compatible with this procedure. Choose a compatible ready device before assessment.</p>}
    {(session?.attention?.interrupt || !!session?.urgent_events?.length) && <div className="status error" role="alert"><strong>Urgent case interruption.</strong> {session.urgent_events?.[0]?.next_action ?? session.attention?.reason} The routine procedure remains recorded, but urgent instructions take priority. <NavLink to="/emergency">Open emergency assistance</NavLink>{session.urgent_events?.slice(1).map(item => <p key={item.case_id}>{item.case_id}: {item.next_action}</p>)}</div>}
    {load.error && <p className="status error">{load.error} <button type="button" onClick={() => void load.run(() => api.procedure(DEMO.procedureId)).then(value => { if (value) onProcedure(value) })}>Retry</button></p>}
    <div className="procedure-main"><section className="card procedure-scene-card">
      {!activeStep ? <p className="muted">The local backend has not supplied the six procedure steps.</p> : <>
        <div className="procedure-stage-meta"><span className="eyebrow">STEP {activeStep.order} OF {steps.length}</span><span className="tag simulated">{activeStep.visual.camera.framing.replaceAll('_', ' ')}</span></div>
        <h2>{activeStep.title}</h2>
        <p className="procedure-instruction">{activeStep.instruction}</p>
        <div className="procedure-view-toggle" role="group" aria-label="Demonstration view">
          <button type="button" aria-pressed={viewMode === 'pictures'} onClick={() => setViewMode('pictures')}>Picture guide</button>
          <button type="button" aria-pressed={viewMode === 'animation'} onClick={() => setViewMode('animation')}>3D replay</button>
        </div>
        {!activeScene ? <p className="status error">This visual action or equipment asset is unavailable. The backend instruction is shown above.</p> : viewMode === 'pictures' ? <section className="procedure-picture-guide" aria-label={`Picture ${activeStep.order} of ${steps.length}: ${activeStep.title}`}>
          <ProcedurePictures scene={activeScene} reading={{ systolic, diastolic, pulse }} />
          <p className="procedure-picture-caption">{activeStep.visual.expected_visible_action}</p>
          <div className="procedure-picture-nav">
            <button type="button" disabled={activeIndex === 0} onClick={() => setSelectedStep(steps[activeIndex - 1].step_id)}>← Previous picture</button>
            <span>Picture {activeStep.order} of {steps.length}</span>
            <button type="button" disabled={activeIndex === steps.length - 1} onClick={() => setSelectedStep(steps[activeIndex + 1].step_id)}>Next picture →</button>
          </div>
          <p className="muted small">Original educational illustration. Reviewing a picture does not acknowledge a real-world step.</p>
        </section> : <Suspense fallback={<p className="muted">Loading visual assets…</p>}><ProcedureVisual key={activeStep.step_id} step={activeStep} reading={{ systolic, diastolic, pulse }} onViewed={markViewed} viewed={viewed.includes(activeStep.step_id)} /></Suspense>}
        {activeStep.warnings.map(warning => <p className="status info" key={warning}>{warning}</p>)}
        {mode === 'responder' && <p className="muted small">Responder: {activeStep.responder_note}</p>}
        <p className="muted small">Instruction sources: {activeStep.instruction_source_ids.map(id => procedure?.instruction_sources.find(source => source.source_id === id)?.description ?? id).join(' ')}</p>
        <div className="procedure-step-actions"><span>{completed.has(activeStep.step_id) ? 'Backend step acknowledged' : activeState?.view_count ? `Animation viewed · ${activeState.view_count} play${activeState.view_count === 1 ? '' : 's'} recorded` : viewed.includes(activeStep.step_id) ? 'Animation viewed on this device' : 'Picture guide available; animation not viewed yet'}</span><button type="button" className="button" disabled={!session || session.current_step_id !== activeStep.step_id || completed.has(activeStep.step_id) || stepWork.busy} onClick={() => void acknowledge(activeStep.step_id)}>{completed.has(activeStep.step_id) ? 'Acknowledged' : 'Acknowledge real-world step'}</button></div>
        <Feedback work={stepWork} />
        {recordError && <p className="muted small" role="status">Visual record not saved to the backend ({recordError}). The step itself is unaffected.</p>}
      </>}
    </section><aside className="card procedure-sequence"><h2>Assessment sequence</h2><p className="muted small">Scenes come from the backend action IDs. Viewing a scene does not complete a step.</p><ol>{steps.map(step => <li key={step.step_id}><button type="button" className={selectedStep === step.step_id ? 'active' : ''} aria-current={selectedStep === step.step_id ? 'step' : undefined} onClick={() => setSelectedStep(step.step_id)}><span>{String(step.order).padStart(2, '0')}</span><strong>{step.title}</strong><small>{completed.has(step.step_id) ? 'Acknowledged' : viewedAnywhere(step.step_id) ? 'Viewed' : step.step_id === session?.current_step_id ? 'Next backend step' : 'Preview'}</small></button></li>)}</ol><div className="procedure-session"><h3>Backend session</h3><label className="form-label">Assessment mode<select value={mode} disabled={session?.status === 'in_progress'} onChange={event => setMode(event.target.value as 'self' | 'responder')}><option value="self">Self assessment</option><option value="responder">Responder assistance</option></select></label><button type="button" className="button secondary" disabled={!caseId || !procedure || !!requestedProcedureId && requestedProcedureId !== DEMO.procedureId || !deviceMatch || start.busy || session?.status === 'in_progress'} onClick={() => void startSession()}>{session?.status === 'in_progress' ? 'Session in progress' : 'Start backend session'}</button><p className="muted small">{session ? `${session.session_id} · ${session.status.replaceAll('_', ' ')}` : 'Report a symptom to create a case, then start.'}</p><Feedback work={restore} /><Feedback work={start} /></div></aside></div>
    <section className="card procedure-reading"><div><p className="eyebrow">AFTER ALL SIX STEPS</p><h2>Record simulated reading</h2><p className="muted">The displayed demo values match these entry fields. Technical validation comes from the backend; no clinical meaning is inferred.</p></div><div className="measurement-row"><label className="form-label">Systolic · mmHg<input type="number" value={systolic} onChange={event => { setSystolic(event.target.value); setConfirmMeasure(false) }} /></label><label className="form-label">Diastolic · mmHg<input type="number" value={diastolic} onChange={event => { setDiastolic(event.target.value); setConfirmMeasure(false) }} /></label><label className="form-label">Pulse · bpm (optional)<input type="number" value={pulse} onChange={event => { setPulse(event.target.value); setConfirmMeasure(false) }} /></label></div>{!confirmMeasure ? <button type="button" className="button" disabled={session?.status !== 'completed' || !validReading} onClick={() => setConfirmMeasure(true)}>Review measurement</button> : <div className="confirmation"><p>Submit <strong>{systolic}/{diastolic} mmHg</strong> as a simulated reading?</p><button type="button" className="button" disabled={measureWork.busy} onClick={() => void submitMeasurement()}>Confirm and submit</button></div>}<Feedback work={measureWork} />{measurement && <p className="status success">Technical checks {measurement.validation.technical_checks_passed ? 'passed' : 'did not pass'} · Case {measurement.case_state}. {measurement.next_action}</p>}</section>
    {procedure && <details className="card procedure-limitations"><summary>Sources and safety limitations</summary><ul>{procedure.safety_limitations.map(item => <li key={item}>{item}</li>)}</ul><p className="muted small">{procedure.instruction_sources.map(source => source.description).join(' ')}</p></details>}
  </div>
}

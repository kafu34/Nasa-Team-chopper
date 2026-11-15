import { lazy, Suspense, useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { api, DEMO, type CaseOut, type EquipmentRecommendation, type HabitatMap, type MeasurementResult, type ProcedureOut, type SessionOut } from './api'
import { ProcedurePictures } from './ProcedurePictures'
import { visualFor } from './visual-registry'
import './procedure.css'

const ProcedureVisual = lazy(() => import('./ProcedureVisual').then(module => ({ default: module.ProcedureVisual })))
type ProcedureId = 'PROC-PO-01' | 'PROC-TEMP-01'
type Props = { procedureId: ProcedureId; caseId: string | null; equipment: EquipmentRecommendation | null; requestedProcedureId?: string | null; onCaseRefresh: (id: string) => Promise<CaseOut | null> }
const storeKey = (caseId: string, procedureId: ProcedureId) => `sentinel:procedure-session:${caseId}:${procedureId}`
const readStored = (key: string) => { try { return localStorage.getItem(key) } catch { return null } }
const writeStored = (key: string, value: string) => { try { localStorage.setItem(key, value) } catch { /* Session still works without local storage. */ } }
const errorText = (cause: unknown) => cause instanceof Error ? cause.message : 'The local backend could not complete this request.'

export function ExpandedProcedureCoach({ procedureId, caseId, equipment, requestedProcedureId, onCaseRefresh }: Props) {
  const [procedure, setProcedure] = useState<ProcedureOut | null>(null)
  const [map, setMap] = useState<HabitatMap | null>(null)
  const [session, setSession] = useState<SessionOut | null>(null)
  const [selectedStep, setSelectedStep] = useState('S1')
  const [viewMode, setViewMode] = useState<'pictures' | 'animation'>('pictures')
  const [viewed, setViewed] = useState<string[]>([])
  const [mode, setMode] = useState<'self' | 'responder'>('self')
  const [spo2, setSpo2] = useState('98'), [pulse, setPulse] = useState('68'), [temperature, setTemperature] = useState('36.7')
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [measurement, setMeasurement] = useState<MeasurementResult | null>(null)
  const pulseOx = procedureId === 'PROC-PO-01'
  const steps = procedure?.steps ?? []
  const activeStep = steps.find(item => item.step_id === selectedStep) ?? steps[0]
  const activeIndex = steps.findIndex(item => item.step_id === activeStep?.step_id)
  const scene = activeStep ? visualFor(activeStep) : null
  const complete = new Set(session?.completed_steps.map(item => item.step_id) ?? [])
  const inventory = map?.equipment.find(item => item.capability === (pulseOx ? 'pulse_oximetry' : 'body_temperature') && item.readiness === 'verified_ready')
  const selectedDevice = equipment?.procedure_id === procedureId ? equipment : inventory
  const deviceMatch = !selectedDevice || procedure?.compatible_device_models.includes(selectedDevice.device_model)
  const valid = pulseOx ? Number.isInteger(Number(spo2)) && Number(spo2) >= 50 && Number(spo2) <= 100 && (pulse === '' || Number.isInteger(Number(pulse)) && Number(pulse) >= 20 && Number(pulse) <= 250) : temperature !== '' && Number.isFinite(Number(temperature)) && Number(temperature) >= 30 && Number(temperature) <= 43

  useEffect(() => { void api.procedure(procedureId).then(setProcedure).catch(cause => setError(errorText(cause))); void api.habitatMap(DEMO.habitatId).then(setMap).catch(() => { /* Procedure definition remains available without a map. */ }) }, [procedureId])
  useEffect(() => {
    if (!caseId) return
    const stored = readStored(storeKey(caseId, procedureId))
    if (!stored) return
    void api.getSession(stored).then(value => { if (value.case_id === caseId && value.procedure_id === procedureId) setSession(value) }).catch(() => { /* A stale local session is ignored. */ })
  }, [caseId, procedureId])
  useEffect(() => { if (session?.current_step_id) setSelectedStep(session.current_step_id); if (session?.mode) setMode(session.mode) }, [session?.current_step_id, session?.mode])

  async function run(action: () => Promise<void>) { setBusy(true); setError(null); setNotice(null); try { await action() } catch (cause) { setError(errorText(cause)) } finally { setBusy(false) } }
  async function start() { if (!caseId || !procedure || requestedProcedureId && requestedProcedureId !== procedureId) return; await run(async () => { const value = await api.createSession(caseId, mode, procedureId, selectedDevice?.equipment_id); setSession(value); writeStored(storeKey(caseId, procedureId), value.session_id); setNotice('Backend procedure session started. Acknowledgements do not prove correct clinical execution.') }) }
  async function acknowledge() { if (!activeStep || !session) return; await run(async () => { const value = await api.completeStep(session.session_id, activeStep.step_id, mode); setSession(value); setNotice('Step acknowledgement saved. Clinical completion is not verified.') }) }
  async function submit() {
    if (!caseId || !session || !valid) return
    await run(async () => {
      const common = { case_id: caseId, session_id: session.session_id }
      const result = pulseOx ? await api.measurement({ ...common, type: 'pulse_oximetry', unit: '%', value: { spo2: Number(spo2), ...(pulse ? { pulse: Number(pulse) } : {}) } }) : await api.measurement({ ...common, type: 'body_temperature', unit: 'degC', value: { temperature: Number(temperature) } })
      setMeasurement(result); setConfirm(false); setNotice('Simulated measurement submitted; technical validation came from the backend.'); await onCaseRefresh(caseId)
    })
  }
  const reading = { systolic: '', diastolic: '', spo2, pulse, temperature }
  return <div className="procedure-page expanded-procedure"><header className="page-title"><p className="eyebrow">Guided assessment / Milestone 6</p><h1>{pulseOx ? 'Pulse oximeter picture guide' : 'Forehead thermometer picture guide'}</h1><p className="intro">Follow the backend-defined educational steps, then record a simulated reading.</p></header>
    <div className="procedure-context"><div><span className="tag simulated">{procedure?.validation_level?.replaceAll('_', ' ') ?? 'EDUCATIONAL DEMONSTRATION'}</span><h2>{procedure?.title ?? 'Loading procedure…'}</h2><p>{procedure?.purpose}</p></div><div className="procedure-context-facts"><span>Procedure <strong>{procedureId}{procedure ? ` · ${procedure.version}` : ''}</strong></span><span>Device <strong>{selectedDevice ? `${selectedDevice.equipment_id} · ${selectedDevice.device_model}` : 'No compatible inventory device loaded'}</strong></span><span>Case <strong>{caseId ?? 'No case yet'}</strong></span></div></div>
    {error && <p className="status error" role="alert">{error}</p>}{notice && <p className="status success" role="status">{notice}</p>}{!deviceMatch && <p className="status error">The selected device is not listed as compatible with this procedure.</p>}
    {(session?.attention?.interrupt || !!session?.urgent_events?.length) && <div className="status error" role="alert"><strong>Urgent case interruption.</strong> {session.urgent_events?.[0]?.next_action ?? session.attention?.reason} The routine procedure remains recorded. <NavLink to="/emergency">Open emergency assistance</NavLink></div>}
    <div className="procedure-main"><section className="card procedure-scene-card">{!activeStep ? <p className="muted">Waiting for the backend procedure steps.</p> : <><div className="procedure-stage-meta"><span className="eyebrow">STEP {activeStep.order} OF {steps.length}</span><span className="tag simulated">{activeStep.visual.camera.framing.replaceAll('_', ' ')}</span></div><h2>{activeStep.title}</h2><p className="procedure-instruction">{activeStep.instruction}</p><div className="procedure-view-toggle" role="group" aria-label="Demonstration view"><button type="button" aria-pressed={viewMode === 'pictures'} onClick={() => setViewMode('pictures')}>Picture guide</button><button type="button" aria-pressed={viewMode === 'animation'} onClick={() => setViewMode('animation')}>3D replay</button></div>{!scene ? <p className="status error">This visual action or asset is unavailable; follow the written instruction.</p> : viewMode === 'pictures' ? <section className="procedure-picture-guide" aria-label={`Picture ${activeStep.order} of ${steps.length}: ${activeStep.title}`}><ProcedurePictures scene={scene} reading={reading} /><p className="procedure-picture-caption">{activeStep.visual.expected_visible_action}</p><div className="procedure-picture-nav"><button type="button" disabled={activeIndex <= 0} onClick={() => setSelectedStep(steps[activeIndex - 1].step_id)}>← Previous picture</button><span>Picture {activeStep.order} of {steps.length}</span><button type="button" disabled={activeIndex >= steps.length - 1} onClick={() => setSelectedStep(steps[activeIndex + 1].step_id)}>Next picture →</button></div><p className="muted small">Viewing an illustration does not acknowledge a real-world step.</p></section> : <Suspense fallback={<p className="muted">Loading 3D demonstration…</p>}><ProcedureVisual key={activeStep.step_id} step={activeStep} reading={reading} viewed={viewed.includes(activeStep.step_id)} onViewed={id => setViewed(current => current.includes(id) ? current : [...current, id])} /></Suspense>}{activeStep.warnings.map(item => <p className="status info" key={item}>{item}</p>)}{mode === 'responder' && <p className="muted small">Responder: {activeStep.responder_note}</p>}<p className="muted small">Instruction sources: {activeStep.instruction_source_ids.map(id => procedure?.instruction_sources.find(source => source.source_id === id)?.description ?? id).join(' ')}</p><div className="procedure-step-actions"><span>{complete.has(activeStep.step_id) ? 'Backend step acknowledged' : viewed.includes(activeStep.step_id) ? 'Animation viewed on this device' : 'Educational picture available'}</span><button className="button" type="button" disabled={!session || session.current_step_id !== activeStep.step_id || complete.has(activeStep.step_id) || busy} onClick={() => void acknowledge()}>Acknowledge real-world step</button></div></>}</section><aside className="card procedure-sequence"><h2>Assessment sequence</h2><p className="muted small">The backend decides step order and session state.</p><ol>{steps.map(item => <li key={item.step_id}><button type="button" className={selectedStep === item.step_id ? 'active' : ''} onClick={() => setSelectedStep(item.step_id)}><span>{String(item.order).padStart(2, '0')}</span><strong>{item.title}</strong><small>{complete.has(item.step_id) ? 'Acknowledged' : item.step_id === session?.current_step_id ? 'Next backend step' : 'Preview'}</small></button></li>)}</ol><div className="procedure-session"><h3>Backend session</h3><label className="form-label">Assessment mode<select value={mode} disabled={session?.status === 'in_progress'} onChange={event => setMode(event.target.value as 'self' | 'responder')}><option value="self">Self assessment</option><option value="responder">Responder assistance</option></select></label><button type="button" className="button secondary" disabled={!caseId || !procedure || !!requestedProcedureId && requestedProcedureId !== procedureId || !deviceMatch || busy || session?.status === 'in_progress'} onClick={() => void start()}>{session?.status === 'in_progress' ? 'Session in progress' : 'Start backend session'}</button><p className="muted small">{session ? `${session.session_id} · ${session.status.replaceAll('_', ' ')}` : caseId ? `Case ${caseId} is ready for an assessment session.` : 'Open a case before starting.'}</p></div></aside></div>
    <section className="card procedure-reading"><div><p className="eyebrow">AFTER ALL {steps.length || 5} STEPS</p><h2>Record simulated {pulseOx ? 'SpO₂ and pulse' : 'temperature'}</h2><p className="muted">Copy values from the fictional display. The backend checks technical plausibility; no clinical meaning is inferred.</p></div><div className="measurement-row">{pulseOx ? <><label className="form-label">SpO₂ · %<input type="number" min="50" max="100" step="1" value={spo2} onChange={event => { setSpo2(event.target.value); setConfirm(false) }} /></label><label className="form-label">Pulse · bpm (optional)<input type="number" min="20" max="250" step="1" value={pulse} onChange={event => { setPulse(event.target.value); setConfirm(false) }} /></label></> : <label className="form-label">Forehead temperature · °C<input type="number" min="30" max="43" step="0.1" value={temperature} onChange={event => { setTemperature(event.target.value); setConfirm(false) }} /></label>}</div>{!confirm ? <button type="button" className="button" disabled={session?.status !== 'completed' || !valid} onClick={() => setConfirm(true)}>Review measurement</button> : <div className="confirmation"><p>Submit <strong>{pulseOx ? `${spo2}%${pulse ? ` and ${pulse} bpm` : ''}` : `${temperature} °C`}</strong> as a simulated reading?</p><button type="button" className="button" disabled={busy} onClick={() => void submit()}>Confirm and submit</button><button type="button" className="button secondary" onClick={() => setConfirm(false)}>Cancel</button></div>}{measurement && <p className="status success">Technical checks {measurement.validation.technical_checks_passed ? 'passed' : 'did not pass'} · Case {measurement.case_state}. {measurement.next_action}</p>}</section>
    {procedure && <details className="card procedure-limitations"><summary>Sources and safety limitations</summary><ul>{procedure.safety_limitations.map(item => <li key={item}>{item}</li>)}</ul></details>}
  </div>
}

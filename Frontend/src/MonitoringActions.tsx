import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { api, DEMO, type BaselineList, type BootstrapOut, type DemoScenario, type MonitoringOut, type ObservationBatch, type ObservationInput } from './api'
import { useDemoAccess } from './DemoAccess'

type Scenario = 'sustained' | 'quality' | 'repeat' | 'spo2' | 'temperature'
const minute = 60_000

export function syntheticBatch(scenario: Scenario, now: number): ObservationInput[] {
  const reading = (value: number, ageMinutes: number, quality: ObservationInput['quality'] = 'good'): ObservationInput => ({ astronaut_id: DEMO.astronautId, type: 'heart_rate', value, unit: 'bpm', source: 'SIMULATED_WEARABLE', observed_at: new Date(now - ageMinutes * minute).toISOString(), quality })
  if (scenario === 'sustained') return [reading(84, 20), reading(86, 10), reading(88, 0)]
  if (scenario === 'spo2') return [20, 10, 0].map((age, index) => ({ ...reading([90, 89, 88][index], age), type: 'spo2', unit: '%' }))
  if (scenario === 'temperature') return [20, 10, 0].map((age, index) => ({ ...reading([38.4, 38.5, 38.6][index], age), type: 'body_temperature', unit: 'degC' }))
  if (scenario === 'quality') return [reading(90, 300), reading(92, 2, 'poor'), reading(94, 1, 'poor')]
  const timestamp = now - minute
  return [reading(89, 1), reading(89, 1)].map(item => ({ ...item, observed_at: new Date(timestamp).toISOString() }))
}

export function MonitoringActions({ summary, history, onUpdated, onCaseDetected, onScenarioLoaded }: { summary: MonitoringOut; history: BaselineList | null; bootstrap?: BootstrapOut | null; onUpdated: () => Promise<void>; onCaseDetected: (caseId: string) => void; onScenarioLoaded?: (result: DemoScenario) => Promise<void> }) {
  const { viewerId, can } = useDemoAccess()
  const [scenario, setScenario] = useState<Scenario>('sustained')
  const [batch, setBatch] = useState<ObservationBatch | null>(null)
  const [syncBusy, setSyncBusy] = useState(false)
  const [syncError, setSyncError] = useState<string | null>(null)
  const [baselineType, setBaselineType] = useState('heart_rate')
  const [baselineReason, setBaselineReason] = useState('Fictional baseline review')
  const [baselineBusy, setBaselineBusy] = useState(false)
  const [baselineMessage, setBaselineMessage] = useState<string | null>(null)
  const [baselineError, setBaselineError] = useState<string | null>(null)
  const [concernId, setConcernId] = useState('')
  const [decision, setDecision] = useState<'continue_monitoring' | 'close'>('continue_monitoring')
  const [reviewNote, setReviewNote] = useState('Continue fictional monitoring')
  const [reviewBusy, setReviewBusy] = useState(false)
  const [reviewMessage, setReviewMessage] = useState<string | null>(null)
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [demoScenario, setDemoScenario] = useState('SCN-REASSESSMENT-DUE')
  const [confirmScenario, setConfirmScenario] = useState(false)
  const [scenarioBusy, setScenarioBusy] = useState(false)
  const [scenarioResult, setScenarioResult] = useState<DemoScenario | null>(null)
  const [scenarioError, setScenarioError] = useState<string | null>(null)
  const officer = can('baseline.recompute')
  const openHeartConcern = summary.concerns.some(item => item.type === 'heart_rate' && item.status !== 'closed')
  const selectedBaseline = history?.baselines.find(item => item.type === baselineType && item.status === 'active')
  const selectedConcern = summary.concerns.find(item => item.concern_id === concernId)

  async function sync() {
    setSyncBusy(true); setSyncError(null); setBatch(null)
    try {
      const result = await api.observationsBatch(syntheticBatch(scenario, Date.now()))
      setBatch(result)
      const caseId = result.results.find(item => item.detection?.case_id)?.detection?.case_id
      if (caseId) onCaseDetected(caseId)
      await onUpdated()
    } catch (cause) { setSyncError(cause instanceof Error ? cause.message : 'Wearable sync failed.') }
    finally { setSyncBusy(false) }
  }
  async function recompute() {
    if (!officer || !selectedBaseline || selectedBaseline.frozen || baselineReason.trim().length < 3) return
    setBaselineBusy(true); setBaselineError(null); setBaselineMessage(null)
    try { const result = await api.recomputeBaseline(DEMO.astronautId, baselineType, baselineReason.trim(), viewerId); setBaselineMessage(`${result.type.replaceAll('_', ' ')} baseline v${result.version} created from ${result.sample_count} readings.`); await onUpdated() }
    catch (cause) { setBaselineError(cause instanceof Error ? cause.message : 'Baseline recompute failed.') }
    finally { setBaselineBusy(false) }
  }
  async function review() {
    if (!selectedConcern || !can(decision === 'close' ? 'monitoring_concern.close' : 'monitoring_concern.continue') || reviewNote.trim().length < 3 || decision === 'close' && (!officer || selectedConcern.status !== 'awaiting_review')) return
    setReviewBusy(true); setReviewError(null); setReviewMessage(null)
    try { const result = await api.reviewConcern(selectedConcern.concern_id, decision, reviewNote.trim(), viewerId); setReviewMessage(`Concern ${result.concern_id} is ${result.status.replaceAll('_', ' ')}. The case is not automatically resolved.`); setDecision('continue_monitoring'); setConcernId(''); await onUpdated() }
    catch (cause) { setReviewError(cause instanceof Error ? cause.message : 'Concern review failed.') }
    finally { setReviewBusy(false) }
  }
  async function loadScenario() {
    if (!confirmScenario) return
    setScenarioBusy(true); setScenarioError(null); setScenarioResult(null)
    try { const result = await api.demoScenario(demoScenario); setScenarioResult(result); setConfirmScenario(false); await onScenarioLoaded?.(result); await onUpdated() }
    catch (cause) { setScenarioError(cause instanceof Error ? cause.message : 'Scenario could not be loaded.') }
    finally { setScenarioBusy(false) }
  }
  async function submitRecovery() {
    setScenarioBusy(true); setScenarioError(null)
    try {
      const now = Date.now()
      await api.observationsBatch([3, 2, 1].map((age, index) => ({ astronaut_id: DEMO.astronautId, type: 'heart_rate', value: [66, 67, 66][index], unit: 'bpm', source: 'SIMULATED_WEARABLE', observed_at: new Date(now - age * minute).toISOString(), quality: 'good' })))
      await onUpdated()
    } catch (cause) { setScenarioError(cause instanceof Error ? cause.message : 'Recovery readings were not submitted.') }
    finally { setScenarioBusy(false) }
  }
  return <>
    <section className="card monitoring-scenarios"><p className="eyebrow">LIVE DEMO SCENARIOS / 2.7.0</p><h2>Load a backend scenario</h2><p className="muted small">Each scenario resets the fictional demo state, then creates its case and procedure state through the backend. NASA research data is separate.</p><label className="form-label">Scenario<select value={demoScenario} onChange={event => { setDemoScenario(event.target.value); setConfirmScenario(false); setScenarioResult(null) }}><option value="SCN-REASSESSMENT-DUE">Reassessment due now</option><option value="SCN-URGENT-DURING-PROCEDURE">Urgent case during BP procedure</option><option value="SCN-EMERGENCY-DURING-PROCEDURE">Emergency during BP procedure</option></select></label>{!confirmScenario ? <button type="button" className="button secondary" onClick={() => setConfirmScenario(true)}>Review scenario reset</button> : <div className="scenario-confirm"><p>Loading this scenario clears current fictional cases, observations, locations and procedure sessions. Continue?</p><div className="button-row"><button type="button" className="button" disabled={scenarioBusy} onClick={() => void loadScenario()}>{scenarioBusy ? 'Loading…' : 'Reset and load scenario'}</button><button type="button" className="button secondary" onClick={() => setConfirmScenario(false)}>Cancel</button></div></div>}{scenarioError && <p className="status error" role="alert">{scenarioError}</p>}{scenarioResult && <div className="scenario-result" aria-live="polite"><strong>{scenarioResult.description}</strong><p>{scenarioResult.note}</p><p className="muted small">Case {scenarioResult.case_id ?? '—'} · procedure session {scenarioResult.session_id ?? '—'} · concern {scenarioResult.concern_id ?? '—'} · emergency case {scenarioResult.emergency_case_id ?? '—'}</p>{scenarioResult.simulated_clock_changes.length > 0 && <p className="muted small">Simulated clock: {scenarioResult.simulated_clock_changes.join('; ')}</p>}{scenarioResult.scenario_id === 'SCN-REASSESSMENT-DUE' && <button type="button" className="button secondary" disabled={scenarioBusy} onClick={() => void submitRecovery()}>Submit three fictional recovery readings</button>}{scenarioResult.session_id && <NavLink className="button secondary" to="/procedure">Open interrupted BP procedure</NavLink>}</div>}</section>
    <section className="card monitoring-actor"><p className="eyebrow">PUBLISHED ROLE MATRIX</p><h2>Acting demo identity</h2><p>{viewerId}</p><p className="muted small">{officer ? 'This role can close a reviewed concern and request baseline recomputation.' : can('monitoring_concern.continue') ? 'This role can continue monitoring. Close and baseline recomputation require a medical officer or flight surgeon.' : 'This role cannot review a monitoring concern.'} The backend checks the self-declared identity selected in the header.</p></section>
    <section className="card monitoring-sync"><p className="eyebrow">FICTIONAL WEARABLE SYNC</p><h2>Test automatic detection</h2><p className="muted small">These sample readings are sent to the backend as fictional wearable observations. The frontend does not decide whether a concern exists.</p>
      <label className="form-label">Scenario<select value={scenario} onChange={event => { setScenario(event.target.value as Scenario); setBatch(null) }}><option value="sustained">Sustained synthetic heart-rate change</option><option value="spo2">Sustained synthetic SpO₂ decrease · pulse oximeter</option><option value="temperature">Sustained synthetic temperature increase · thermometer</option><option value="quality">Poor-quality and stale sensor readings</option><option value="repeat" disabled={!openHeartConcern}>Repeated reading during open concern</option></select></label>
      <p className="muted small">{scenario === 'sustained' ? 'Preview: 84, 86 and 88 bpm; good quality across 20 minutes.' : scenario === 'spo2' ? 'Preview: 90, 89 and 88%; good-quality fictional SpO₂ readings across 20 minutes.' : scenario === 'temperature' ? 'Preview: 38.4, 38.5 and 38.6 °C; good-quality fictional temperature readings across 20 minutes.' : scenario === 'quality' ? 'Preview: one 5-hour-old reading and two recent poor-quality readings.' : 'Preview: 89 bpm submitted twice at the same timestamp; one may be deduplicated.'}</p>
      <button type="button" className="button" disabled={syncBusy || scenario === 'repeat' && !openHeartConcern} onClick={() => void sync()}>{syncBusy ? 'Sending fictional readings…' : 'Submit fictional wearable sync'}</button>
      {syncError && <p className="status error" role="alert">{syncError}</p>}{batch && <div className="monitoring-sync-result" aria-live="polite"><strong>{batch.stored} stored · {batch.duplicates} duplicate(s) · {batch.concern_ids_opened.length} new concern(s)</strong><ul>{batch.results.map((item, index) => <li key={`${item.observation_id}-${index}`}><b>{item.value} {item.unit}</b> · {item.duplicate ? 'duplicate' : item.detection?.outcome.replaceAll('_', ' ') ?? 'no detection result'}<p>{item.detection?.explanation}</p>{item.detection && <small>{item.detection.disclaimer}</small>}</li>)}</ul></div>}
    </section>
    <div className="two-column monitoring-controls"><section className="card"><p className="eyebrow">CONTROLLED BASELINE UPDATE</p><h2>Recompute a personal baseline</h2><p className="muted small">This creates a new version only after a deliberate request. The backend excludes readings during a concern.</p><label className="form-label">Measurement type<select value={baselineType} onChange={event => setBaselineType(event.target.value)}>{summary.types.map(item => <option key={item.type} value={item.type}>{item.type.replaceAll('_', ' ')}</option>)}</select></label><p className="muted small">{selectedBaseline ? `Active v${selectedBaseline.version} · ${selectedBaseline.sample_count} readings · ${selectedBaseline.frozen ? `frozen by ${selectedBaseline.frozen_by_concern_id}` : 'available for review'}` : 'No baseline exists. Recompute requires sufficient valid history.'}</p><label className="form-label">Reason<input value={baselineReason} maxLength={500} onChange={event => setBaselineReason(event.target.value)} /></label><button className="button secondary" disabled={!officer || !selectedBaseline || selectedBaseline.frozen || baselineReason.trim().length < 3 || baselineBusy} onClick={() => void recompute()}>{baselineBusy ? 'Recomputing…' : 'Create next baseline version'}</button>{baselineError && <p className="status error">{baselineError}</p>}{baselineMessage && <p className="status success">{baselineMessage}</p>}</section>
      <section className="card"><p className="eyebrow">HUMAN REVIEW</p><h2>Review a monitoring concern</h2><p className="muted small">Readings returning to baseline never close a concern automatically. Closing requires completed reassessment and recovery evidence.</p><label className="form-label">Concern<select value={concernId} onChange={event => setConcernId(event.target.value)}><option value="">Choose a concern</option>{summary.concerns.filter(item => item.status !== 'closed').map(item => <option key={item.concern_id} value={item.concern_id}>{item.concern_id} · {item.type.replaceAll('_', ' ')} · {item.status.replaceAll('_', ' ')}</option>)}</select></label><label className="form-label">Decision<select value={decision} onChange={event => setDecision(event.target.value as 'continue_monitoring' | 'close')}><option value="continue_monitoring">Continue monitoring</option>{officer && <option value="close">Close after review</option>}</select></label><label className="form-label">Review note<input value={reviewNote} maxLength={1000} onChange={event => setReviewNote(event.target.value)} /></label><button className="button secondary" disabled={!selectedConcern || !can(decision === 'close' ? 'monitoring_concern.close' : 'monitoring_concern.continue') || reviewNote.trim().length < 3 || decision === 'close' && (!officer || selectedConcern.status !== 'awaiting_review') || reviewBusy} onClick={() => void review()}>{reviewBusy ? 'Recording review…' : 'Record crew review'}</button>{selectedConcern && decision === 'close' && selectedConcern.status !== 'awaiting_review' && <p className="muted small">Close remains unavailable until the backend marks this concern awaiting review.</p>}{reviewError && <p className="status error">{reviewError}</p>}{reviewMessage && <p className="status success">{reviewMessage}</p>}</section></div>
  </>
}

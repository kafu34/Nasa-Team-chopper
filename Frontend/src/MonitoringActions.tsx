import { useState } from 'react'
import { api, DEMO, type BaselineList, type MonitoringOut, type ObservationBatch, type ObservationInput } from './api'

type Scenario = 'sustained' | 'quality' | 'repeat'
const minute = 60_000

export function syntheticBatch(scenario: Scenario, now: number): ObservationInput[] {
  const reading = (value: number, ageMinutes: number, quality: ObservationInput['quality'] = 'good'): ObservationInput => ({ astronaut_id: DEMO.astronautId, type: 'heart_rate', value, unit: 'bpm', source: 'SIMULATED_WEARABLE', observed_at: new Date(now - ageMinutes * minute).toISOString(), quality })
  if (scenario === 'sustained') return [reading(84, 20), reading(86, 10), reading(88, 0)]
  if (scenario === 'quality') return [reading(90, 300), reading(92, 2, 'poor'), reading(94, 1, 'poor')]
  const timestamp = now - minute
  return [reading(89, 1), reading(89, 1)].map(item => ({ ...item, observed_at: new Date(timestamp).toISOString() }))
}

export function MonitoringActions({ summary, history, onUpdated, onCaseDetected }: { summary: MonitoringOut; history: BaselineList | null; onUpdated: () => Promise<void>; onCaseDetected: (caseId: string) => void }) {
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
    if (!selectedBaseline || selectedBaseline.frozen || baselineReason.trim().length < 3) return
    setBaselineBusy(true); setBaselineError(null); setBaselineMessage(null)
    try { const result = await api.recomputeBaseline(DEMO.astronautId, baselineType, baselineReason.trim()); setBaselineMessage(`${result.type.replaceAll('_', ' ')} baseline v${result.version} created from ${result.sample_count} readings.`); await onUpdated() }
    catch (cause) { setBaselineError(cause instanceof Error ? cause.message : 'Baseline recompute failed.') }
    finally { setBaselineBusy(false) }
  }
  async function review() {
    if (!selectedConcern || reviewNote.trim().length < 3 || decision === 'close' && selectedConcern.status !== 'awaiting_review') return
    setReviewBusy(true); setReviewError(null); setReviewMessage(null)
    try { const result = await api.reviewConcern(selectedConcern.concern_id, decision, reviewNote.trim()); setReviewMessage(`Concern ${result.concern_id} is ${result.status.replaceAll('_', ' ')}. The case is not automatically resolved.`); await onUpdated() }
    catch (cause) { setReviewError(cause instanceof Error ? cause.message : 'Concern review failed.') }
    finally { setReviewBusy(false) }
  }
  return <>
    <section className="card monitoring-sync"><p className="eyebrow">FICTIONAL WEARABLE SYNC</p><h2>Test automatic detection</h2><p className="muted small">These sample readings are sent to the backend as fictional wearable observations. The frontend does not decide whether a concern exists.</p>
      <label className="form-label">Scenario<select value={scenario} onChange={event => { setScenario(event.target.value as Scenario); setBatch(null) }}><option value="sustained">Sustained synthetic heart-rate change</option><option value="quality">Poor-quality and stale sensor readings</option><option value="repeat" disabled={!openHeartConcern}>Repeated reading during open concern</option></select></label>
      <p className="muted small">{scenario === 'sustained' ? 'Preview: 84, 86 and 88 bpm; good quality across 20 minutes.' : scenario === 'quality' ? 'Preview: one 5-hour-old reading and two recent poor-quality readings.' : 'Preview: 89 bpm submitted twice at the same timestamp; one may be deduplicated.'}</p>
      <button type="button" className="button" disabled={syncBusy || scenario === 'repeat' && !openHeartConcern} onClick={() => void sync()}>{syncBusy ? 'Sending fictional readings…' : 'Submit fictional wearable sync'}</button>
      {syncError && <p className="status error" role="alert">{syncError}</p>}{batch && <div className="monitoring-sync-result" aria-live="polite"><strong>{batch.stored} stored · {batch.duplicates} duplicate(s) · {batch.concern_ids_opened.length} new concern(s)</strong><ul>{batch.results.map((item, index) => <li key={`${item.observation_id}-${index}`}><b>{item.value} {item.unit}</b> · {item.duplicate ? 'duplicate' : item.detection?.outcome.replaceAll('_', ' ') ?? 'no detection result'}<p>{item.detection?.explanation}</p>{item.detection && <small>{item.detection.disclaimer}</small>}</li>)}</ul></div>}
    </section>
    <div className="two-column monitoring-controls"><section className="card"><p className="eyebrow">CONTROLLED BASELINE UPDATE</p><h2>Recompute a personal baseline</h2><p className="muted small">This creates a new version only after a deliberate request. The backend excludes readings during a concern.</p><label className="form-label">Measurement type<select value={baselineType} onChange={event => setBaselineType(event.target.value)}>{summary.types.map(item => <option key={item.type} value={item.type}>{item.type.replaceAll('_', ' ')}</option>)}</select></label><p className="muted small">{selectedBaseline ? `Active v${selectedBaseline.version} · ${selectedBaseline.sample_count} readings · ${selectedBaseline.frozen ? `frozen by ${selectedBaseline.frozen_by_concern_id}` : 'available for review'}` : 'No baseline exists. Recompute requires sufficient valid history.'}</p><label className="form-label">Reason<input value={baselineReason} maxLength={500} onChange={event => setBaselineReason(event.target.value)} /></label><button className="button secondary" disabled={!selectedBaseline || selectedBaseline.frozen || baselineReason.trim().length < 3 || baselineBusy} onClick={() => void recompute()}>{baselineBusy ? 'Recomputing…' : 'Create next baseline version'}</button>{baselineError && <p className="status error">{baselineError}</p>}{baselineMessage && <p className="status success">{baselineMessage}</p>}</section>
      <section className="card"><p className="eyebrow">HUMAN REVIEW</p><h2>Review a monitoring concern</h2><p className="muted small">Readings returning to baseline never close a concern automatically. Closing requires completed reassessment and recovery evidence.</p><label className="form-label">Concern<select value={concernId} onChange={event => setConcernId(event.target.value)}><option value="">Choose a concern</option>{summary.concerns.filter(item => item.status !== 'closed').map(item => <option key={item.concern_id} value={item.concern_id}>{item.concern_id} · {item.type.replaceAll('_', ' ')} · {item.status.replaceAll('_', ' ')}</option>)}</select></label><label className="form-label">Decision<select value={decision} onChange={event => setDecision(event.target.value as 'continue_monitoring' | 'close')}><option value="continue_monitoring">Continue monitoring</option><option value="close">Close after review</option></select></label><label className="form-label">Review note<input value={reviewNote} maxLength={1000} onChange={event => setReviewNote(event.target.value)} /></label><button className="button secondary" disabled={!selectedConcern || reviewNote.trim().length < 3 || decision === 'close' && selectedConcern.status !== 'awaiting_review' || reviewBusy} onClick={() => void review()}>{reviewBusy ? 'Recording review…' : 'Record crew review'}</button>{selectedConcern && decision === 'close' && selectedConcern.status !== 'awaiting_review' && <p className="muted small">Close remains unavailable until the backend marks this concern awaiting review.</p>}{reviewError && <p className="status error">{reviewError}</p>}{reviewMessage && <p className="status success">{reviewMessage}</p>}</section></div>
  </>
}

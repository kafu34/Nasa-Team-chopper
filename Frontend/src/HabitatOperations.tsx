import { useState } from 'react'
import { api, DEMO, type HabitatMap, type HatchChange, type MovementRun } from './api'

const SCENARIOS = [
  ['SIM-WALK-CQ-MED', 'Walk from Crew Quarters to Medical Bay'],
  ['SIM-CONFLICT-PASSAGE', 'Conflicting passage signals'],
  ['SIM-MISSING-ANCHOR', 'Missing wireless anchor'],
  ['SIM-STALE', 'Stale observations'],
] as const

export function HabitatOperations({ map, onHatchChanged, onMovementRun }: { map: HabitatMap; onHatchChanged: (result: HatchChange) => Promise<void>; onMovementRun: () => Promise<void> }) {
  const [hatchId, setHatchId] = useState(map.passages[0]?.hatch_id ?? '')
  const [reason, setReason] = useState('Fictional crew access update')
  const [hatchBusy, setHatchBusy] = useState(false)
  const [hatchError, setHatchError] = useState<string | null>(null)
  const [hatchResult, setHatchResult] = useState<HatchChange | null>(null)
  const [scenarioId, setScenarioId] = useState<string>(SCENARIOS[0][0])
  const [run, setRun] = useState<MovementRun | null>(null)
  const [runBusy, setRunBusy] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const hatch = map.passages.find(item => item.hatch_id === hatchId)
  async function changeHatch() {
    if (!hatch || reason.trim().length < 3) return
    setHatchBusy(true); setHatchError(null)
    try {
      const result = await api.changeHatch(map.habitat_id, hatch.hatch_id, hatch.accessible ? 'closed' : 'open', reason.trim())
      setHatchResult(result)
      await onHatchChanged(result)
    } catch (error) { setHatchError(error instanceof Error ? error.message : 'Hatch change failed.') }
    finally { setHatchBusy(false) }
  }
  async function simulate() {
    setRunBusy(true); setRunError(null)
    try { const result = await api.simulationMovement(scenarioId, DEMO.astronautId); setRun(result); await onMovementRun() }
    catch (error) { setRunError(error instanceof Error ? error.message : 'Simulation failed.') }
    finally { setRunBusy(false) }
  }
  return <div className="two-column habitat-ops">
    <section className="card"><h2>Hatch access</h2><p className="muted small">Crew controlled fictional hatch state. A change updates route access and may invalidate a saved route.</p>
      <label className="form-label">Hatch<select value={hatchId} onChange={event => setHatchId(event.target.value)}>{map.passages.map(item => <option key={item.hatch_id} value={item.hatch_id}>{item.hatch_id} · {item.from_zone_id} ↔ {item.to_zone_id} · {item.hatch_state}</option>)}</select></label>
      <label className="form-label">Reason<input value={reason} maxLength={300} onChange={event => setReason(event.target.value)} /></label>
      <button className="button secondary" disabled={!hatch || reason.trim().length < 3 || hatchBusy} onClick={() => void changeHatch()}>{hatchBusy ? 'Updating hatch…' : `${hatch?.accessible ? 'Close' : 'Open'} ${hatchId}`}</button>
      {hatchError && <p className="status error">{hatchError}</p>}{hatchResult && <p className="status info">{hatchResult.hatch_id} is {hatchResult.state}. Habitat state {hatchResult.state_version}. {hatchResult.invalidated_recommendation_ids.length} saved route(s) invalidated.</p>}
    </section>
    <section className="card"><h2>Fictional movement test</h2><p className="muted small">Runs a repeatable radio simulation through the backend estimator. The map uses the resulting zone estimate; test ground truth is never displayed as crew location.</p>
      <label className="form-label">Scenario<select value={scenarioId} onChange={event => setScenarioId(event.target.value)}>{SCENARIOS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
      <button className="button secondary" disabled={runBusy} onClick={() => void simulate()}>{runBusy ? 'Running simulation…' : 'Run simulated movement'}</button>
      {runError && <p className="status error">{runError}</p>}{run && <div className="result-panel"><p className="muted small">{run.scenario_id} · {run.ticks.length} estimator ticks</p><ol className="movement-ticks">{run.ticks.map(tick => <li key={tick.tick}>Tick {tick.tick}: {tick.estimate.zone_id ?? 'zone unavailable'} · {Math.round(tick.estimate.confidence * 100)}% confidence · {tick.estimate.display_mode.replaceAll('_', ' ')}</li>)}</ol><p className="muted small">These are simulated estimates. The current map uses the latest stored estimate and its freshness status.</p></div>}
    </section>
  </div>
}

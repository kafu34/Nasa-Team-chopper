import { useCallback, useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { api, DEMO, type BaselineList, type DetectionRuleset, type MonitoringOut, type MonitoringType } from './api'
import { MonitoringActions } from './MonitoringActions'
import './monitoring.css'

const name = (value: string) => value.replaceAll('_', ' ')
const when = (value: string | null) => value ? new Date(value).toLocaleString() : 'Not recorded'
const number = (value: number | null) => value == null ? 'Not recorded' : String(value)

export function detectionTone(item: MonitoringType) {
  if (item.open_concern_id) return 'concern'
  if (item.freshness !== 'current' || item.latest_detection?.gate !== 'passed') return 'quality'
  if (item.latest_detection?.outcome === 'deviation_not_sustained') return 'watch'
  return 'steady'
}

export function Monitoring({ onCaseOpened, onCaseDetected }: { onCaseOpened: (caseId: string) => void; onCaseDetected: (caseId: string) => void }) {
  const [summary, setSummary] = useState<MonitoringOut | null>(null)
  const [history, setHistory] = useState<BaselineList | null>(null)
  const [ruleset, setRuleset] = useState<DetectionRuleset | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(true)
  const load = useCallback(async () => {
    setBusy(true)
    try {
      const [monitoring, baselines, rules] = await Promise.all([api.monitoring(DEMO.astronautId), api.baselines(DEMO.astronautId), api.detectionRuleset()])
      if (!Array.isArray(monitoring.types) || !Array.isArray(monitoring.concerns) || !Array.isArray(monitoring.data_quality)) throw new Error('Backend returned an invalid monitoring summary.')
      setSummary(monitoring); setHistory(baselines); setRuleset(rules); setError(null)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Monitoring unavailable.') }
    finally { setBusy(false) }
  }, [])
  useEffect(() => { void load() }, [load])
  return <div className="monitoring-page">
    <header className="page-title"><p className="eyebrow">Health intelligence / 04</p><h1>Health monitoring</h1><p className="intro">Individual baselines, incoming fictional readings, data quality and investigations from the local backend.</p></header>
    <div className="monitoring-toolbar"><span className="tag simulated">SIMULATED ASTRONAUT · {DEMO.astronautId}</span><button type="button" className="button secondary" onClick={() => void load()} disabled={busy}>{busy ? 'Loading…' : 'Refresh monitoring'}</button></div>
    {error && <p className="status error" role="alert">{error}</p>}{!summary && !error && <p className="status info">Loading monitoring evidence…</p>}
    {summary && <>
      <p className="status info">{summary.disclaimer} Data generated {when(summary.generated_at)} · ruleset {summary.ruleset_version} · baseline method {summary.baseline_method_id}.</p>
      <div className="monitoring-metrics"><div><strong>{summary.types.length}</strong><span>Measurement types</span></div><div><strong>{summary.concerns.filter(item => item.status !== 'closed').length}</strong><span>Open concerns</span></div><div><strong>{summary.data_quality.length}</strong><span>Data-quality notices</span></div></div>
      <MonitoringActions summary={summary} history={history} onUpdated={load} onCaseDetected={onCaseDetected} />
      <section className="card"><div className="monitoring-section-head"><div><p className="eyebrow">INDIVIDUAL EVIDENCE</p><h2>Current readings and baselines</h2></div><p className="muted small">A baseline is a fictional personal reference, not a clinical threshold.</p></div><div className="monitoring-types">{summary.types.map(item => <article className={`monitoring-type monitoring-type--${detectionTone(item)}`} key={item.type}>
        <div className="monitoring-type-head"><h3>{name(item.type)}</h3><span className={`monitoring-freshness monitoring-freshness--${item.freshness}`}>{item.freshness}</span></div>
        <div className="monitoring-values"><div><span>Latest reading</span><strong>{item.latest_value == null ? 'Not recorded' : <>{number(item.latest_value)} <small>{item.unit}</small></>}</strong><small>{when(item.latest_observed_at)} · {item.latest_quality ?? 'quality unknown'}</small></div><div><span>Personal baseline</span><strong>{item.baseline ? `${item.baseline.centre} ${item.baseline.unit}` : 'Unavailable'}</strong><small>{item.baseline ? `v${item.baseline.version} · ${item.baseline.sample_count} source readings${item.baseline.frozen ? ' · frozen' : ''}` : 'Too few valid readings or no baseline'}</small></div></div>
        <p className="muted small">{item.difference_from_baseline == null ? 'No comparison available.' : `Difference from baseline: ${item.difference_from_baseline > 0 ? '+' : ''}${item.difference_from_baseline} ${item.unit}.`} Trend: {name(item.trend.description)} ({item.trend.readings} recent readings; descriptive only).</p>
        {item.latest_detection && <div className="monitoring-detection"><strong>{name(item.latest_detection.outcome)}</strong><p>{item.latest_detection.explanation}</p><small>{item.latest_detection.rule_id ?? 'No rule'} · {item.latest_detection.deviating_count}{item.latest_detection.required_count ? `/${item.latest_detection.required_count}` : ''} deviating readings · {item.latest_detection.alert_suppressed ? 'duplicate alert suppressed' : item.latest_detection.alert_raised ? 'alert raised' : 'no alert'}</small><p className="monitoring-disclaimer">{item.latest_detection.disclaimer}</p></div>}
        {item.open_concern_id && <a href={`#concern-${item.open_concern_id}`}>View investigation {item.open_concern_id} →</a>}
      </article>)}</div></section>
      <section className="card"><p className="eyebrow">SENSOR AND RECORD QUALITY</p><h2>Data needing attention</h2><p className="muted small">Missing, stale and poor-quality readings do not establish deterioration.</p>{summary.data_quality.length ? <ul className="monitoring-quality">{summary.data_quality.map((item, index) => <li key={`${item.type}-${item.issue}-${index}`}><strong>{name(item.type)} · {name(item.issue)}</strong><span>{item.note}</span></li>)}</ul> : <p className="muted">No current data-quality notices.</p>}</section>
      <section className="card"><p className="eyebrow">EXPLAINABLE INVESTIGATION</p><h2>Monitoring concerns</h2>{summary.concerns.length ? <div className="monitoring-concerns">{summary.concerns.map(item => <article id={`concern-${item.concern_id}`} key={item.concern_id}><div className="monitoring-type-head"><h3>{name(item.type)} · {item.status.replaceAll('_', ' ')}</h3><span className="tag simulated">{item.rule_id}</span></div><p>{item.rule_title ?? 'Configured detection rule'} · {item.direction} baseline · triggered {item.trigger_count} time(s), {item.suppressed_count} duplicate alert(s) suppressed.</p><p className="muted small">Evidence: {item.evidence_observation_ids.join(', ')}. Baseline v{item.baseline_version}{item.baseline_frozen ? ' frozen during concern' : ''}. Opened {when(item.opened_at)}.</p><p className="muted small">Reassessment: {item.reassessment ? `${item.reassessment.status} · due ${when(item.reassessment.due_at)}` : 'Not scheduled'}. {item.reassessment_passed ? 'Reassessment evidence recorded.' : 'Reassessment pending.'} {item.consecutive_within_baseline}/{item.recovery_count ?? '—'} recovery readings.</p><p className="monitoring-disclaimer">{item.disclaimer}</p><div className="button-row"><button type="button" className="button secondary" onClick={() => onCaseOpened(item.case_id)}>Open case {item.case_id}</button><NavLink className="button secondary" to="/spatial">Find equipment</NavLink></div></article>)}</div> : <p className="muted">No monitoring concern has been opened. Data-quality notices above are separate from investigations.</p>}</section>
      <section className="card"><p className="eyebrow">RULES AND BASELINE VERSIONS</p><h2>Configuration and history</h2><div className="two-column"><div><h3>Configured detection rules</h3>{ruleset?.rules.map(rule => <p className="monitoring-rule" key={rule.rule_id}><strong>{rule.title}</strong><span>{rule.rule_id} · {rule.required_consecutive} readings in {rule.window_minutes} min · {rule.assessment_procedure_id ?? 'No configured assessment'}</span></p>)}</div><div><h3>Baseline version history</h3>{history?.baselines.map(item => <p className="monitoring-rule" key={item.baseline_id}><strong>{name(item.type)} · v{item.version} · {item.status}</strong><span>{item.centre} {item.unit} · spread {item.spread} · {item.sample_count} sources · {item.excluded_count} excluded · {item.frozen ? 'frozen' : 'available'}</span></p>)}<p className="muted small">Full observation time-series history is not exposed by this backend contract.</p></div></div></section>
    </>}
  </div>
}

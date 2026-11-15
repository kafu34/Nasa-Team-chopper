import { useCallback, useEffect, useState } from 'react'
import { api, DEMO, type MonitoringOut, type ObservationHistory as HistoryPage, type ObservationHistoryItem } from './api'

const label = (value: string) => value.replaceAll('_', ' ')
const formatTime = (value: string) => new Date(value).toLocaleString()

export function historyPlot(items: ObservationHistoryItem[], centre: number | null) {
  const values = items.map(item => item.value).concat(centre == null ? [] : [centre])
  const low = Math.min(...values), high = Math.max(...values)
  const span = high - low || 1
  const ordered = [...items].sort((a, b) => Date.parse(a.observed_at) - Date.parse(b.observed_at))
  const firstTime = Date.parse(ordered[0].observed_at), lastTime = Date.parse(ordered.at(-1)!.observed_at)
  const x = (item: ObservationHistoryItem) => 32 + (lastTime === firstTime ? 284 : (Date.parse(item.observed_at) - firstTime) / (lastTime - firstTime) * 568)
  const y = (value: number) => 154 - (value - low) / span * 112
  return { ordered, points: ordered.map(item => `${x(item)},${y(item.value)}`).join(' '), baselineY: centre == null ? null : y(centre), low, high }
}

export function ObservationHistory({ summary, refreshKey }: { summary: MonitoringOut; refreshKey: number }) {
  const [type, setType] = useState(() => summary.types[0]?.type ?? '')
  const [page, setPage] = useState<HistoryPage | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const load = useCallback(async (offset = 0) => {
    setBusy(true)
    try {
      const result = await api.observationHistory(DEMO.astronautId, type, 50, offset)
      setPage(previous => offset && previous ? { ...result, items: [...previous.items, ...result.items] } : result)
      setError(null)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'History unavailable.') }
    finally { setBusy(false) }
  }, [type])
  useEffect(() => { void load() }, [load, refreshKey])
  const baseline = summary.types.find(item => item.type === type)?.baseline
  const chartItems = page?.items.slice(0, 50) ?? []
  const plot = chartItems.length ? historyPlot(chartItems, baseline?.centre ?? null) : null
  return <section className="card observation-history" id="observation-history"><div className="monitoring-section-head"><div><p className="eyebrow">OBSERVATION HISTORY / 2.7.0</p><h2>Readings over time</h2></div><p className="muted small">Fictional astronaut observations returned by the backend. Chart uses the 50 newest loaded readings, arranged by observation time.</p></div>
    <label className="form-label">Measurement type<select value={type} onChange={event => { setType(event.target.value); setPage(null) }}>{summary.types.map(item => <option key={item.type} value={item.type}>{label(item.type)}</option>)}</select></label>
    {error && <p className="status error" role="alert">{error}</p>}
    {!page && !error && <p className="muted">Loading observation history…</p>}
    {page && <><p className="muted small">{page.total} recorded observation(s) · {page.items.length} loaded · newest first in the table. {baseline ? `Active baseline v${baseline.version}: ${baseline.centre} ${baseline.unit}.` : 'No active baseline.'}</p>
      {plot && <div className="history-chart"><svg viewBox="0 0 632 188" role="img" aria-label={`${label(type)} observations from ${formatTime(plot.ordered[0].observed_at)} to ${formatTime(plot.ordered.at(-1)!.observed_at)}; values ${plot.low} to ${plot.high}${baseline ? `; baseline ${baseline.centre}` : ''}`}><line x1="32" y1="154" x2="600" y2="154" className="axis" />{plot.baselineY != null && <line x1="32" y1={plot.baselineY} x2="600" y2={plot.baselineY} className="history-baseline" />}<polyline points={plot.points} className="trend" />{plot.ordered.map((item, index) => { const [cx, cy] = plot.points.split(' ')[index].split(','); return <circle key={item.observation_id} cx={cx} cy={cy} r="4" className="trend-point"><title>{formatTime(item.observed_at)} · {item.value} {item.unit} · {label(item.quality)}</title></circle> })}<text x="32" y="178">{formatTime(plot.ordered[0].observed_at)}</text><text x="600" y="178" textAnchor="end">{formatTime(plot.ordered.at(-1)!.observed_at)}</text></svg><p className="muted small">Solid line: recorded readings · dashed line: active personal baseline. Lines connect observations for display only.</p></div>}
      <div className="table-scroll"><table><thead><tr><th>Observed</th><th>Reading</th><th>Quality</th><th>Origin</th><th>Detection</th><th>Baseline</th></tr></thead><tbody>{page.items.map(item => <tr key={item.observation_id}><td>{formatTime(item.observed_at)}</td><td>{item.value} {item.unit}</td><td>{label(item.quality)}</td><td>{label(item.origin)}<small className="history-source">{item.source}{item.measurement_id ? ` · ${item.measurement_id}` : ''}</small></td><td>{item.detection ? label(item.detection.outcome) : '—'}</td><td>{item.in_active_baseline ? 'Included' : 'Excluded'}</td></tr>)}</tbody></table></div>
      {!page.items.length && <p className="muted">No observations of this type are recorded.</p>}
      {page.items.length < page.total && <button type="button" className="button secondary" disabled={busy} onClick={() => void load(page.items.length)}>{busy ? 'Loading…' : 'Load more readings'}</button>}
    </>}
  </section>
}

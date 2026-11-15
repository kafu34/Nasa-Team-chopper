import { useEffect, useState } from 'react'
import { api, type EnvironmentContext as Context } from './api'
import './environment-context.css'

export function EnvironmentContext() {
  const [context, setContext] = useState<Context | null>(null)
  const [error, setError] = useState<string | null>(null)
  async function refresh() {
    try { setContext(await api.environmentContext()); setError(null) }
    catch (cause) { setError(`${cause instanceof Error ? cause.message : 'Could not load environmental context.'} ${context ? 'Last loaded data may be stale.' : ''}`) }
  }
  useEffect(() => { void refresh() }, []) // eslint-disable-line react-hooks/exhaustive-deps
  return <div className="environment-page"><header className="page-title"><p className="eyebrow">NASA research / environmental context</p><h1>Mission environment</h1><p className="intro">Source-attributed historical readings for research context. These values do not measure this fictional habitat or astronaut.</p></header>
    <section className="card environment-caution"><div className="environment-head"><h2>Interpretation limit</h2><button type="button" className="button secondary" onClick={() => void refresh()}>Refresh context</button></div>{error && <p className="status error" role="alert">{error}</p>}{context ? <><p>{context.caution}</p><div className="environment-flags"><span>Habitat reading: no</span><span>Personal dose: no</span><span>Health relationship: none inferred</span></div></> : <p className="muted">Loading backend attribution and caution…</p>}</section>
    {context && <><section className="card"><h2>{context.radiation.title}</h2><p className="muted">{context.radiation.dataset_id} · {context.radiation.status} · {context.radiation.location}</p>{context.radiation.source_url && <p><a href={context.radiation.source_url} target="_blank" rel="noopener noreferrer">NASA source ↗</a></p>}{context.radiation.latest_readings.length ? <div className="environment-table"><table><thead><tr><th>Instrument</th><th>Latest reading</th><th>Timestamp</th><th>Source row</th></tr></thead><tbody>{context.radiation.latest_readings.map(reading => <tr key={`${reading.instrument_id}-${reading.metric}`}><td><strong>{reading.instrument_id}</strong><small>{[reading.instrument_family, reading.spacecraft, reading.module].filter(Boolean).join(' · ')}</small></td><td>{reading.value_raw || reading.value} {reading.unit}<small>{reading.metric.replaceAll('_', ' ')}</small></td><td>{new Date(reading.timestamp).toLocaleString()}</td><td>{reading.source_file}<small>row {reading.source_row_number}</small></td></tr>)}</tbody></table></div> : <p className="empty">No RadLab readings are imported. No environmental measurement is inferred.</p>}{context.radiation.limitations.length > 0 && <ul className="environment-limits">{context.radiation.limitations.map(item => <li key={item}>{item}</li>)}</ul>}</section>
      <section className="card"><h2>Atmosphere data</h2><p className="environment-blocked">{context.atmosphere.dataset_id} · {context.atmosphere.status}</p><p className="muted">{context.atmosphere.note}</p></section></>}
  </div>
}

import { useState } from 'react'
import { display, type ResearchRecordsPage, type TimeseriesPage } from './api'

export function HistologyResults({ page }: { page: ResearchRecordsPage }) {
  const [assay, setAssay] = useState('TUNEL')
  const [measure, setMeasure] = useState('counts')
  const records = (page.histology_records ?? []).filter(record => record.data_category === 'NASA_RESEARCH' && record.assay === assay && record.measure === measure)
  return <div>
    <p className="muted small">Ex vivo human donor eyes cultured on the ground. TUNEL marks DNA fragmentation; CTB measures axonal transport. These are research counts, not astronaut eye measurements or a SANS diagnosis.</p>
    <div className="research-filters"><label className="form-label">Assay<select value={assay} onChange={event => setAssay(event.target.value)}>{(page.available_analytes ?? ['CTB', 'TUNEL']).map(item => <option key={item} value={item}>{item}</option>)}</select></label><label className="form-label">Measure<select value={measure} onChange={event => setMeasure(event.target.value)}>{(page.available_measures ?? ['counts', 'normalized_counts']).map(item => <option key={item} value={item}>{item === 'normalized_counts' ? 'Normalized counts' : 'Counts'}</option>)}</select></label></div>
    <p className="muted small">{records.length} published values shown. Group numbers are preserved as published; their pressure and tilt conditions are unverified.</p>
    {records.length ? <div className="table-scroll"><table><thead><tr><th>Donor / eye</th><th>Sample</th><th>Value</th><th>Unit</th><th>Group</th><th>Days on system</th><th>Image notes</th><th>Source file</th></tr></thead><tbody>{records.map(record => <tr key={`${record.sample_name}-${record.assay}-${record.measure}`}><td>{record.donor_id} / {record.eye}</td><td>{record.sample_name}</td><td>{display(record.value)}</td><td>{record.unit}</td><td>{display(record.group_number)}</td><td>{display(record.days_on_system)}</td><td>{display(record.notes)}</td><td>{record.source_file}</td></tr>)}</tbody></table></div> : <p className="empty">No imported values match this assay and measure.</p>}
  </div>
}

export function RadiationResults({ page, instrument, onInstrument }: { page: TimeseriesPage; instrument: string; onInstrument: (value: string) => void }) {
  const points = page.points.filter(point => point.instrument_id === instrument && typeof point.value === 'number' && Number.isFinite(point.value))
  const values = points.map(point => point.value as number)
  const min = values.length ? Math.min(...values) : 0
  const max = values.length ? Math.max(...values) : 1
  const chartPoints = values.map((value, index) => `${20 + index * (440 / Math.max(values.length - 1, 1))},${170 - ((value - min) / (max - min || 1)) * 130}`).join(' ')
  return <div>
    <p className="muted small">ISS, 1 April 2022 (NASA RadLab). Historical area dosimeter readings in the Columbus module. They are not live HAB-01 readings or a crew member’s personal dose.</p>
    <label className="form-label">Detector<select value={instrument} onChange={event => onInstrument(event.target.value)}>{(page.available_instruments ?? [instrument]).map(item => <option key={item} value={item}>{item}</option>)}</select></label>
    <p className="muted small">{points.length} of {page.total} readings for {instrument} shown · {page.metric.replaceAll('_', ' ')} · {page.unit}. Detectors are shown separately.</p>
    {points.length > 1 && <div className="chart-wrap"><svg viewBox="0 0 480 190" role="img" aria-label={`${instrument} absorbed dose rate in ${page.unit} over time`}><line x1="20" y1="170" x2="465" y2="170" className="axis" /><polyline points={chartPoints} className="trend" /></svg></div>}
    {points.length ? <div className="table-scroll"><table><thead><tr><th>UTC time</th><th>Detector</th><th>Absorbed dose rate</th><th>Unit</th><th>Module</th><th>ISS latitude</th><th>ISS longitude</th><th>ISS altitude (km)</th></tr></thead><tbody>{points.slice(0, 30).map((point, index) => <tr key={`${point.timestamp}-${point.source_row_number ?? index}`}><td>{point.timestamp}</td><td>{point.instrument_id}</td><td>{display(point.value)}</td><td>{point.unit}</td><td>{display(point.module)}</td><td>{display(point.latitude)}</td><td>{display(point.longitude)}</td><td>{display(point.altitude)}</td></tr>)}</tbody></table></div> : <p className="empty">No numeric readings were returned for this detector.</p>}
    {page.limitations?.map(item => <p className="muted small" key={item}>{item}</p>)}
    {page.provenance?.source_url && <a href={page.provenance.source_url} target="_blank" rel="noreferrer">RadLab source query ↗</a>}
  </div>
}

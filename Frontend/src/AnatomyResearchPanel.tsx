import { useEffect, useState } from 'react'
import { api, type DatasetDetail, type ResearchRecordsPage } from './api'
import type { BodySelection } from './BodyMap'
import './research-context.css'

const studies = {
  'OSD-195': {
    title: 'Muscle research context',
    classification: 'Human ground-analogue experiment',
    explanation: 'Skeletal-muscle gene-expression research involving volunteers in bed-rest experiments. It does not measure this astronaut’s muscle mass or strength.',
    source: 'https://osdr.nasa.gov/bio/repo/data/studies/OSD-195',
  },
  'OSD-546': {
    title: 'Skeletal and bone-cell research context',
    classification: 'Experiment using human-derived cells',
    explanation: 'Bone-marrow stem-cell differentiation research aboard the ISS. It is not a direct astronaut bone-density measurement.',
    source: 'https://osdr.nasa.gov/bio/repo/data/studies/OSD-546',
  },
} as const
type StudyId = keyof typeof studies

export function AnatomyResearchPanel({ selection }: { selection: BodySelection | null }) {
  const [selected, setSelected] = useState<StudyId>('OSD-195')
  const [detail, setDetail] = useState<DatasetDetail | null>(null)
  const [page, setPage] = useState<ResearchRecordsPage | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => { if (selection?.regionId === 'upper_back' || selection?.regionId === 'lower_back') setSelected('OSD-546'); else if (selection?.regionId === 'upper_arm' || selection?.regionId === 'upper_leg') setSelected('OSD-195') }, [selection])
  useEffect(() => {
    let active = true
    setDetail(null); setPage(null); setError(null); setBusy(true)
    void api.dataset(selected).then(async metadata => {
      if (!active) return
      setDetail(metadata)
      if (metadata.status === 'IMPORTED') {
        const records = await api.records(selected, selected === 'OSD-546' ? { gene_symbol: 'TSPAN6' } : { limit: 1000 })
        if (active) setPage(records)
      }
    }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : 'Research data unavailable.') }).finally(() => { if (active) setBusy(false) })
    return () => { active = false }
  }, [selected])
  const study = studies[selected]
  const expectedSystem = selected === 'OSD-195' ? 'skeletal_muscle' : 'bone'
  return <section className="card research-context" aria-label="Anatomical research context">
    <h2>Research context for body systems</h2>
    <p className="muted small">These studies provide scientific context only. No research result is a finding about {selection?.label ?? 'the fictional astronaut'}.</p>
    <div className="segmented" aria-label="Research study"><button type="button" aria-pressed={selected === 'OSD-195'} onClick={() => setSelected('OSD-195')}>Muscle · OSD-195</button><button type="button" aria-pressed={selected === 'OSD-546'} onClick={() => setSelected('OSD-546')}>Bone cells · OSD-546</button></div>
    <div className="context-grid"><div><span className="tag research">NASA RESEARCH</span><h3>{study.title}</h3><p>{study.explanation}</p><p className="muted small">Classification: {detail?.study_type ?? study.classification}</p>{detail?.measured && <p className="muted small">Measured: {detail.measured}</p>}{(detail?.not_a_measurement_of?.length ?? 0) > 0 && <p className="muted small">Does not measure: {detail?.not_a_measurement_of?.join(', ')}</p>}<a href={detail?.source_url ?? study.source} target="_blank" rel="noreferrer">NASA study source ↗</a></div>
    <div><p><strong>Import status:</strong> {detail?.status ?? (busy ? 'Checking local research API…' : 'Unavailable')}</p>{detail?.status_reason && <p className="muted small">{detail.status_reason}</p>}{detail && !detail.body_systems?.includes(expectedSystem) && <p className="status error">The backend did not classify this study for the selected body system.</p>}{detail?.experimental_context && <p className="muted small">{detail.experimental_context}</p>}{detail?.limitations?.map(item => <p className="muted small" key={item}>{item}</p>)}{error && <p className="status error">{error}</p>}{detail?.status !== 'IMPORTED' && <p className="empty">No numerical results shown. This study has not been reported as imported by the backend.</p>}</div></div>
    {detail?.status === 'IMPORTED' && <><p className="muted small">{selected === 'OSD-546' ? 'Example: processed TSPAN6 expression across imported cell samples. These values are not astronaut bone-density measurements.' : 'Processed research values from the local backend.'}</p><ExpressionResults page={page} /></>}
  </section>
}

export function ExpressionResults({ page }: { page: ResearchRecordsPage | null }) {
  const numeric = page?.record_schema === 'GENE_EXPRESSION_V1' ? (page.expression_records ?? []).filter(record => record.data_category === 'NASA_RESEARCH' && typeof record.value === 'number' && Number.isFinite(record.value) && record.normalization_verified) : []
  return <div><h3>Processed gene-expression records{numeric[0]?.gene_symbol ? ` · ${numeric[0].gene_symbol}` : ''}</h3>{page && <p className="muted small">{page.total} matching research records returned by the backend.</p>}{page?.comparison_readiness && <p className="muted small">Research comparison metadata: {page.comparison_readiness.ready ? 'Ready' : 'Not ready'} (no clinical interpretation). {page.comparison_readiness.reasons.join('; ')}</p>}{numeric.length ? <div className="table-scroll"><table><thead><tr><th>Probe / gene</th><th>Value</th><th>Published scale</th><th>Sample</th><th>Condition</th><th>Normalization</th><th>Source file</th></tr></thead><tbody>{numeric.slice(0, 20).map((record, index) => <tr key={index}><td>{record.probe_id}{record.gene_symbol ? ` / ${record.gene_symbol}` : ''}</td><td>{record.value}</td><td>{record.value_unit}</td><td>{record.sample_id}</td><td>{record.condition_label}</td><td>{record.normalization}</td><td>{record.source_file}</td></tr>)}</tbody></table></div> : <p className="empty">No verified processed expression values were returned. Raw microarray files alone do not supply a comparison.</p>}{page?.samples?.length ? <p className="muted small">Sample metadata: {page.samples.slice(0, 5).map(sample => `${sample.sample_id} (${sample.condition_label})`).join(', ')}.</p> : null}</div>
}

import type { ResearchRecordsPage } from './api'

export function AssayResults({ page }: { page: ResearchRecordsPage }) {
  const records = page.record_schema === 'BIO_ASSAY_TABLE' ? (page.assay_records ?? []).filter(item => item.data_category === 'NASA_RESEARCH') : []
  return <div>
    <p className="muted small">OSD-656 example: IL6 in the published urine inflammation panel. Values use relative assay units (NPQ), not clinical concentrations or astronaut diagnostic thresholds.</p>
    <p className="muted small">{page.total} matching assay records · {page.available_measures?.join(', ') ?? 'Measures not listed'}</p>
    {records.length ? <div className="table-scroll"><table><thead><tr><th>Target</th><th>Value</th><th>Published unit</th><th>Sample</th><th>Subject</th><th>Timepoint</th><th>Measure</th></tr></thead><tbody>{records.slice(0, 30).map((item, index) => <tr key={index}><td>{item.analyte}</td><td>{item.value ?? 'Missing'}</td><td>{item.unit}</td><td>{item.sample_name}</td><td>{item.subject_id}</td><td>{item.timepoint}</td><td>{item.measure}</td></tr>)}</tbody></table></div> : <p className="empty">No assay records were returned for this filter.</p>}
  </div>
}

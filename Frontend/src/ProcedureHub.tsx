import { useEffect, useState } from 'react'
import { api, DEMO, type CaseOut, type EquipmentRecommendation, type MeasurementResult, type ProcedureOut, type ProcedureSummary, type SessionOut } from './api'
import { ProcedureCoach } from './ProcedureCoach'
import { ExpandedProcedureCoach } from './ExpandedProcedureCoach'

type Props = { caseId: string | null; equipment: EquipmentRecommendation | null; procedure: ProcedureOut | null; session: SessionOut | null; measurement: MeasurementResult | null; recommendedProcedureId?: string | null; onProcedure: (value: ProcedureOut) => void; onSession: (value: SessionOut) => void; onMeasurement: (value: MeasurementResult) => void; onCaseRefresh: (id: string) => Promise<CaseOut | null> }

export function ProcedureHub({ recommendedProcedureId, ...props }: Props) {
  const [catalogue, setCatalogue] = useState<ProcedureSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState(recommendedProcedureId ?? props.equipment?.procedure_id ?? DEMO.procedureId)
  useEffect(() => { void api.procedures().then(setCatalogue).catch(cause => setError(cause instanceof Error ? cause.message : 'Procedure catalogue unavailable.')) }, [])
  useEffect(() => { if (recommendedProcedureId) setSelectedId(recommendedProcedureId) }, [recommendedProcedureId])
  const selected = catalogue.find(item => item.procedure_id === selectedId)
  return <><section className="card procedure-catalogue"><div><p className="eyebrow">EDUCATIONAL ASSESSMENT CATALOGUE / 2.8.0</p><h2>Choose a visual procedure</h2><p className="muted small">The local backend supplies the catalogue. These demonstrations have not been reviewed by a flight surgeon or tested with real devices.</p></div><label className="form-label">Procedure<select value={selectedId} onChange={event => setSelectedId(event.target.value)}>{catalogue.length ? catalogue.map(item => <option key={item.procedure_id} value={item.procedure_id}>{item.title}</option>) : <option value={selectedId}>{selectedId}</option>}</select></label>{selected && <p className="muted small">{selected.procedure_id} · v{selected.version} · {selected.required_capability.replaceAll('_', ' ')}</p>}{recommendedProcedureId && <p className="status info">This case requests {recommendedProcedureId}. Use that procedure for the configured assessment.</p>}{error && <p className="status error" role="alert">{error}</p>}</section>
    {selectedId === DEMO.procedureId ? <ProcedureCoach {...props} requestedProcedureId={recommendedProcedureId} /> : selectedId === 'PROC-PO-01' || selectedId === 'PROC-TEMP-01' ? <ExpandedProcedureCoach key={selectedId} {...props} procedureId={selectedId} initialSession={props.session} requestedProcedureId={recommendedProcedureId} /> : <p className="status error">No visual coach is implemented for {selectedId}.</p>}
  </>
}

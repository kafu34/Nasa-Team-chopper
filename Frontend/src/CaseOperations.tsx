import { useState } from 'react'
import { api, ApiError, asObject, DEMO, type CaseOut, type CaseResolveOut } from './api'
import './case-operations.css'

type Blocker = { kind: string; id: string; detail: string }
function blockers(cause: unknown): Blocker[] {
  if (!(cause instanceof ApiError) || cause.code !== 'CASE_NOT_READY_TO_RESOLVE') return []
  const rows = asObject(cause.details)?.blockers
  return Array.isArray(rows) ? rows.map(asObject).filter((item): item is Record<string, unknown> => !!item).map(item => ({ kind: String(item.kind), id: String(item.id), detail: String(item.detail) })) : []
}

export function CaseOperations({ caseData, onUpdated }: { caseData: CaseOut; onUpdated: (value: CaseOut) => Promise<void> }) {
  const [ackActor, setAckActor] = useState<string>(DEMO.astronautId)
  const [resolveActor, setResolveActor] = useState<string>(DEMO.responderId)
  const [note, setNote] = useState('')
  const [cancelFollowUps, setCancelFollowUps] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [found, setFound] = useState<Blocker[]>([])
  const [outcome, setOutcome] = useState<CaseResolveOut | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const outstanding = caseData.follow_ups.filter(item => item.status === 'scheduled' || item.status === 'due')

  async function acknowledge() {
    setBusy(true); setError(null); setNotice(null)
    try { const updated = await api.acknowledgeCase(caseData.case_id, ackActor); await onUpdated(updated); setNotice(`Case alert acknowledged by ${updated.acknowledged_by}. The case remains ${updated.state}.`) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not acknowledge case.') }
    finally { setBusy(false) }
  }
  async function resolve() {
    if (note.trim().length < 3) { setError('Enter a resolution note of at least three characters.'); return }
    setBusy(true); setError(null); setNotice(null); setFound([]); setOutcome(null)
    try { const result = await api.resolveCase(caseData.case_id, resolveActor, note.trim(), cancelFollowUps); setOutcome(result); await onUpdated(result.case); setNotice(`Case ${result.case.case_id} resolved by ${result.case.resolved_by}.`) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not resolve case.'); setFound(blockers(cause)) }
    finally { setBusy(false) }
  }

  return <section className="card case-operations" aria-labelledby="case-operations-title"><p className="eyebrow">Controlled closure / 2.11.0</p><h2 id="case-operations-title">Review case status</h2><div className="case-operation-summary"><p><strong>Acknowledgement:</strong> {caseData.acknowledged_at ? `${caseData.acknowledged_by} · ${new Date(caseData.acknowledged_at).toLocaleString()}` : 'Not acknowledged'}</p><p><strong>Resolution:</strong> {caseData.resolved_at ? `${caseData.resolved_by} · ${new Date(caseData.resolved_at).toLocaleString()}` : 'Open'}</p>{caseData.resolution_note && <p><strong>Resolution note:</strong> {caseData.resolution_note}</p>}{caseData.state === 'resolved' && <p><strong>Interrupting attention:</strong> {caseData.attention?.interrupt === false ? 'No' : 'Check backend attention state'}</p>}</div>
    {caseData.state !== 'resolved' && <div className="case-operation-grid"><div><h3>Acknowledge alert</h3><p className="muted small">Acknowledgement records that someone saw the case. It does not complete work or resolve it.</p><label className="form-label">Crew or flight-surgeon actor<select value={ackActor} onChange={event => setAckActor(event.target.value)}><option value={DEMO.astronautId}>Crew member · {DEMO.astronautId}</option><option value={DEMO.responderId}>Crew medical officer · {DEMO.responderId}</option><option value="GND-FS-01">Flight surgeon · GND-FS-01</option></select></label><button type="button" className="button secondary" disabled={busy} onClick={() => void acknowledge()}>Acknowledge case alert</button></div><div><h3>Resolve case</h3><p className="muted small">Only the crew medical officer or flight surgeon can resolve. The backend checks every open concern, session, assessment and follow-up.</p><label className="form-label">Resolving actor<select value={resolveActor} onChange={event => setResolveActor(event.target.value)}><option value={DEMO.responderId}>Crew medical officer · {DEMO.responderId}</option><option value="GND-FS-01">Flight surgeon · GND-FS-01</option></select></label><label className="form-label">Resolution note<textarea value={note} maxLength={2000} rows={3} onChange={event => setNote(event.target.value)} placeholder="Record the reason for this manual decision" /></label>{outstanding.length > 0 && <label className="case-cancel-choice"><input type="checkbox" checked={cancelFollowUps} onChange={event => setCancelFollowUps(event.target.checked)} /> Cancel {outstanding.length} outstanding follow-up(s) as part of resolution; each cancellation is audited</label>}<button type="button" className="button" disabled={busy} onClick={() => void resolve()}>Request case resolution</button></div></div>}
    {error && <p className="status error" role="alert">{error}</p>}{found.length > 0 && <div className="case-blockers"><strong>Backend blockers</strong><ul>{found.map(item => <li key={`${item.kind}-${item.id}`}>{item.detail}</li>)}</ul></div>}{notice && <p className="status success" role="status">{notice}</p>}{outcome && <div className="case-resolution-result"><p>Cancelled follow-ups: {outcome.cancelled_follow_up_ids.length ? outcome.cancelled_follow_up_ids.join(', ') : 'none'}.</p>{outcome.warnings.length > 0 && <><strong>Backend warnings</strong><ul>{outcome.warnings.map(item => <li key={item}>{item}</li>)}</ul></>}</div>}<p className="muted small">Demo identities are self-declared; this is not authentication or clinical clearance.</p>
  </section>
}

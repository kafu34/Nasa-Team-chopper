import { NavLink } from 'react-router-dom'
import type { CaseOut, CaseSummary, EquipmentRecommendation, ScheduledAssessment } from './api'
import './care-coordination.css'

type Props = { currentCase: CaseOut | CaseSummary | null; equipment: EquipmentRecommendation | null }

export function dueLabel(dueAt: string, status: string, now = Date.now(), backendDue = false, backendState?: ScheduledAssessment['due_state']) {
  if (backendState) return backendState === 'due' ? 'Due now' : backendState[0].toUpperCase() + backendState.slice(1)
  if (status === 'completed') return 'Completed'
  if (status === 'overdue') return 'Overdue'
  if (status === 'due' || backendDue) return 'Due now'
  const due = Date.parse(dueAt)
  if (!Number.isFinite(due)) return 'Due time unavailable'
  return due < now ? 'Overdue' : due - now < 60_000 ? 'Due now' : 'Upcoming'
}

const nice = (value: string) => value.replaceAll('_', ' ')
const when = (value: string) => Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString() : 'Time unavailable'

export function CareCoordination({ currentCase, equipment }: Props) {
  const details = currentCase && 'follow_ups' in currentCase ? currentCase : null
  const requested = details?.requested_assessment
  const activeRecommendation = !!requested && !!equipment && equipment.procedure_id === requested.procedure_id && equipment.status !== 'invalidated'
  const followUps = details?.follow_ups ?? []

  return <section className="card care-coordination" aria-labelledby="care-coordination-title">
    <div className="care-heading"><div><p className="eyebrow">MEDICAL WORKFLOW / SOFTWARE DEMONSTRATION</p><h2 id="care-coordination-title">Assessment & follow-up</h2><p className="muted">The case, recommendation and dates come from the local backend. This view does not choose a diagnosis or mark work complete.</p></div>{currentCase?.priority === 'urgent' && <span className="tag care-urgent">Urgent case</span>}</div>
    <div className="care-grid">
      <div className="care-block"><h3>Requested assessment</h3>{requested ? <><strong>{requested.procedure_id}</strong><p>{nice(requested.capability)} · {nice(requested.status)}</p><p className="muted small">{requested.configured_reason}</p><NavLink className="button secondary" to="/procedure">Open picture guide</NavLink></> : <><p className="muted">No procedure request is recorded for this case.</p><NavLink className="button secondary" to="/monitoring">Review monitoring</NavLink></>}</div>
      <div className="care-block"><h3>Compatible device</h3>{activeRecommendation && equipment ? <><strong>{equipment.equipment_id}</strong><p>{equipment.device_model} · {nice(equipment.readiness)}</p><p className="muted small">{nice(equipment.zone_id)} · {equipment.route_zone_ids.length ? `${equipment.route_zone_ids.map(nice).join(' → ')} route` : 'No route returned'}</p>{equipment.excluded?.length ? <p className="muted small">Other devices: {equipment.excluded.map(item => `${item.equipment_id} (${item.reasons.map(nice).join(', ')})`).join('; ')}</p> : null}<NavLink className="button secondary" to="/spatial">View backend route</NavLink></> : <><p className="muted">{requested ? 'No matching active recommendation is loaded. Ask the backend to check device readiness and route.' : 'A device can be requested after the case specifies an assessment.'}</p><NavLink className="button secondary" to="/spatial">Find equipment</NavLink></>}</div>
    </div>
    <div className="care-follow-ups"><h3>Case follow-up</h3>{followUps.length ? <ul>{followUps.map(item => <li key={item.follow_up_id}><span className={`care-due ${dueLabel(item.due_at, item.status).toLowerCase().replaceAll(' ', '-')}`}>{dueLabel(item.due_at, item.status)}</span><strong>{item.title}</strong><span>{when(item.due_at)}</span><small>{nice(item.status)} · {item.follow_up_id}</small></li>)}</ul> : <p className="muted">No follow-up is recorded for this case.</p>}</div>
  </section>
}

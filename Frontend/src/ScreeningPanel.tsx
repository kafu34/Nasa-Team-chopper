import { useEffect, useState } from 'react'
import { api, DEMO, type AssessmentStartOut, type BootstrapOut, type ReminderOut, type ScheduledAssessment } from './api'
import './screening-panel.css'

const order = { overdue: 0, due: 1, upcoming: 2, completed: 3 }
const label = (value: string) => value.replaceAll('_', ' ')
const errorText = (cause: unknown) => cause instanceof Error ? cause.message : 'The local service could not complete this request.'

export function ScreeningPanel({ bootstrap, onStarted }: { bootstrap: BootstrapOut | null; onStarted: (result: AssessmentStartOut) => Promise<void> }) {
  const [assessments, setAssessments] = useState<ScheduledAssessment[] | null>(null)
  const [reminders, setReminders] = useState<ReminderOut[]>([])
  const [mode, setMode] = useState<'self' | 'responder'>('self')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  async function refresh() {
    try { const [schedule, reminderList] = await Promise.all([api.assessments(DEMO.astronautId), api.reminders(DEMO.astronautId)]); setAssessments(schedule.assessments); setReminders(reminderList.reminders); setError(null) }
    catch (cause) { setError(errorText(cause)) }
  }
  useEffect(() => { void refresh() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function acknowledge(reminder: ReminderOut) {
    setBusyId(reminder.reminder_id); setError(null); setNotice(null)
    try { await api.acknowledgeReminder(reminder.reminder_id); await refresh(); setNotice(`Reminder ${reminder.reminder_id} acknowledged. The assessment remains due until a matching measurement is recorded.`) }
    catch (cause) { setError(errorText(cause)) }
    finally { setBusyId(null) }
  }
  async function start(assessment: ScheduledAssessment) {
    setBusyId(assessment.assessment_id); setError(null); setNotice(null)
    try { const result = await api.startAssessment(assessment.assessment_id, mode === 'self' ? DEMO.astronautId : DEMO.responderId, mode); await onStarted(result); await refresh() }
    catch (cause) { setError(errorText(cause)) }
    finally { setBusyId(null) }
  }

  const rows = [...(assessments ?? bootstrap?.scheduled_assessments ?? [])].sort((a, b) => order[a.due_state] - order[b.due_state] || a.due_at.localeCompare(b.due_at))
  return <section className="card screening-panel" aria-labelledby="screening-title"><div className="screening-head"><div><p className="eyebrow">DURABLE SCHEDULE / 2.9.0</p><h2 id="screening-title">Routine assessments</h2><p className="muted">Fictional preventive schedule from the local backend. A reminder acknowledgement does not complete an assessment.</p></div><button type="button" className="button secondary" onClick={() => void refresh()}>Refresh schedule</button></div>
    <label className="form-label screening-mode">Assessment mode<select value={mode} onChange={event => setMode(event.target.value as 'self' | 'responder')}><option value="self">Self assessment · {DEMO.astronautId}</option><option value="responder">Responder assistance · {DEMO.responderId}</option></select></label>
    {error && <p className="status error" role="alert">{error} {assessments ? 'Last loaded schedule may be stale.' : 'Showing bootstrap schedule without action status.'}</p>}{notice && <p className="status success" role="status">{notice}</p>}
    {rows.length ? <div className="screening-list">{rows.map(item => { const openReminder = reminders.find(reminder => reminder.assessment_id === item.assessment_id && reminder.status === 'open' && reminder.kind === item.due_state) ?? reminders.find(reminder => reminder.assessment_id === item.assessment_id && reminder.status === 'open'); const acknowledged = reminders.find(reminder => reminder.assessment_id === item.assessment_id && reminder.status === 'acknowledged'); const canStart = !!assessments && (item.due_state === 'due' || item.due_state === 'overdue') && !busyId; return <article className="screening-item" key={item.assessment_id}><div className="screening-item-main"><span className={`care-due ${item.due_state === 'due' ? 'due-now' : item.due_state}`}>{label(item.due_state)}</span><div><h3>{item.title}</h3><p>{item.procedure_id} · {label(item.capability)} · due {new Date(item.due_at).toLocaleString()}</p><p className="muted small">{item.reason}</p>{acknowledged && <p className="muted small">Reminder acknowledged by {acknowledged.acknowledged_by}; assessment still {item.due_state}.</p>}</div></div><div className="screening-actions">{openReminder && <button type="button" className="button secondary" disabled={!!busyId} onClick={() => void acknowledge(openReminder)}>Acknowledge {openReminder.kind} reminder</button>}<button type="button" className="button" disabled={!canStart} onClick={() => void start(item)}>{item.due_state === 'completed' ? 'Completed' : item.due_state === 'upcoming' ? 'Not due yet' : 'Start assessment'}</button></div></article> })}</div> : <p className="muted">No scheduled assessments were returned.</p>}
  </section>
}

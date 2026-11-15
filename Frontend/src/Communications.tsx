import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, DEMO, type CommsList, type LinkOut } from './api'
import './communications.css'

type Viewpoint = 'crew' | 'ground'
const actor = (view: Viewpoint) => view === 'crew' ? DEMO.responderId : 'GND-FS-01'
const direction = (view: Viewpoint) => view === 'crew' ? 'to_ground' : 'to_crew'
const readable = (value: string) => value.replaceAll('_', ' ')
const date = (value: string | null) => value ? new Date(value).toLocaleString() : 'Waiting for transmission'
const errorText = (cause: unknown) => cause instanceof Error ? cause.message : 'The local service could not complete the request.'

export function Communications({ caseId }: { caseId: string | null }) {
  const [params] = useSearchParams()
  const focusedId = params.get('message')
  const [queue, setQueue] = useState<CommsList | null>(null)
  const [link, setLink] = useState<LinkOut | null>(null)
  const [view, setView] = useState<Viewpoint>('crew')
  const [subject, setSubject] = useState('Medical status update')
  const [body, setBody] = useState('')
  const [priority, setPriority] = useState<'routine' | 'urgent'>('routine')
  const [attachCase, setAttachCase] = useState(true)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const retry = useRef<{ key: string; draft: string } | null>(null)

  const refresh = useCallback(async () => {
    try { const state = await api.commsLink(); const messages = await api.commsMessages(); setLink(state); setQueue(messages); setError(null) }
    catch (cause) { setError(`${errorText(cause)} Previously loaded queue information may be stale.`) }
  }, [])
  useEffect(() => { void refresh(); const timer = window.setInterval(() => { void refresh() }, 15_000); return () => window.clearInterval(timer) }, [refresh])

  async function send() {
    const draft = JSON.stringify({ view, subject: subject.trim(), body: body.trim(), priority, caseId: attachCase ? caseId : null })
    if (!subject.trim() || !body.trim()) { setError('Enter a subject and message before sending.'); return }
    if (retry.current?.draft !== draft) retry.current = { key: crypto.randomUUID(), draft }
    setPending(true); setError(null); setNotice(null)
    try {
      const message = await api.sendCommsMessage({ sender_id: actor(view), direction: direction(view), priority, subject: subject.trim(), body: body.trim(), ...(attachCase && caseId ? { case_id: caseId } : {}), client_message_id: retry.current.key })
      retry.current = null; setBody(''); setNotice(`${message.duplicate ? 'Existing' : 'New'} message ${message.message_id} is ${readable(message.status)}. Ground delivery is simulated and delayed.`); await refresh()
    } catch (cause) { setError(`${errorText(cause)} If the response was lost, retry the same draft; its client ID will be reused.`) }
    finally { setPending(false) }
  }

  async function acknowledge(id: string) {
    setPending(true); setError(null); setNotice(null)
    try { const result = await api.acknowledgeCommsMessage(id, actor(view)); setNotice(`Message ${result.message_id} acknowledged by ${result.acknowledged_by}.`); await refresh() }
    catch (cause) { setError(errorText(cause)) }
    finally { setPending(false) }
  }

  async function toggleLink() {
    if (!link) return
    setPending(true); setError(null); setNotice(null)
    const next = link.state === 'up' ? 'down' : 'up'
    try { await api.changeCommsLink(next, next === 'down' ? 'Fictional ground-link outage demonstration' : 'Fictional ground-link restoration demonstration'); setNotice(`Simulated ground link set to ${next}.`); await refresh() }
    catch (cause) { setError(errorText(cause)) }
    finally { setPending(false) }
  }

  return <div className="communications-page"><header className="page-title"><p className="eyebrow">Medical communications / simulated link</p><h1>Ground messages</h1><p className="intro">The local backend stores this fictional queue. Onboard care does not wait for a message to reach Earth.</p></header>
    <div className="comms-overview"><section className="card"><h2>Ground link</h2><p className={`comms-link ${link?.state === 'down' ? 'down' : ''}`}>{link ? `Simulated link ${link.state}` : 'Checking simulated link…'}</p><p className="muted small">{link ? `${link.one_way_delay_seconds} s one-way delay · ${link.transmit_seconds} s per transmission · ${link.outage_count} simulated outage(s)` : 'Queue timing comes from the local backend.'}</p><button type="button" className="button secondary" disabled={!link || pending} onClick={() => void toggleLink()}>{link?.state === 'up' ? 'Simulate link outage' : 'Restore simulated link'}</button></section>
      <section className="card"><h2>Demo viewpoint</h2><label className="form-label">Acting role<select value={view} onChange={event => { setView(event.target.value as Viewpoint); retry.current = null }}><option value="crew">Crew medical officer · {DEMO.responderId}</option><option value="ground">Flight surgeon · GND-FS-01</option></select></label><p className="muted small">Identities are self-declared in this prototype. This switch demonstrates receiving-side permissions; it is not authentication.</p></section></div>
    <section className="card comms-compose"><h2>{view === 'crew' ? 'Send to ground' : 'Simulate ground reply to crew'}</h2><p className="muted small">Messages are queued locally and sent only when the simulated link permits. An urgent message is prioritized among waiting messages.</p><div className="comms-fields"><label className="form-label">Subject<input value={subject} maxLength={200} onChange={event => setSubject(event.target.value)} /></label><label className="form-label">Priority<select value={priority} onChange={event => setPriority(event.target.value as 'routine' | 'urgent')}><option value="routine">Routine</option><option value="urgent">Urgent</option></select></label></div><label className="form-label">Message<textarea value={body} maxLength={5000} rows={4} onChange={event => setBody(event.target.value)} placeholder="Enter a fictional medical coordination message" /></label>{caseId && <label className="comms-check"><input type="checkbox" checked={attachCase} onChange={event => setAttachCase(event.target.checked)} /> Attach current case {caseId}</label>}<button type="button" className="button" disabled={pending} onClick={() => void send()}>Queue simulated message</button></section>
    <section className="card"><div className="comms-heading"><div><h2>Message queue</h2><p className="muted small">{queue ? `${queue.messages.length} message(s) · ${queue.note}` : 'Loading backend messages…'}</p></div><button type="button" className="button secondary" disabled={pending} onClick={() => void refresh()}>Refresh queue</button></div>{error && <p className="status error" role="alert">{error}</p>}{notice && <p className="status success" role="status">{notice}</p>}{queue?.messages.length ? <div className="comms-list">{queue.messages.map(message => { const receiver = message.direction === 'to_ground' ? 'ground' : 'crew'; const canAcknowledge = message.status === 'delivered' && receiver === view; return <article className={`comms-message ${message.message_id === focusedId ? 'focused' : ''}`} key={message.message_id} id={`message-${message.message_id}`}><div className="comms-message-top"><span className={`comms-priority ${message.priority}`}>{message.priority}</span><strong>{message.subject}</strong><span className="comms-status">{readable(message.status)}</span></div><p className="muted small">{message.message_id} · {readable(message.direction)} · {message.sender_id} → {readable(message.recipient_role)}{message.case_id ? ` · case ${message.case_id}` : ''}</p><p>{message.body}</p><div className="comms-message-foot"><span>Queued {date(message.created_at)} · Expected arrival {date(message.deliver_at)}</span>{message.acknowledged_at && <span>Acknowledged {date(message.acknowledged_at)} by {message.acknowledged_by}</span>}{canAcknowledge && <button type="button" className="button secondary" disabled={pending} onClick={() => void acknowledge(message.message_id)}>Acknowledge as {actor(view)}</button>}</div></article> })}</div> : queue && <p className="empty">No messages are in the simulated queue.</p>}</section>
  </div>
}

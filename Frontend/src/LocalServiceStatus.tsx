import { useCallback, useEffect, useRef, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { api, DEMO, type RecoveryOut } from './api'
import './local-service-status.css'

type State = 'checking' | 'connected' | 'unavailable' | 'recovered'

export function LocalServiceStatus({ onRecovered }: { onRecovered: () => Promise<void> }) {
  const [state, setState] = useState<State>('checking')
  const [checking, setChecking] = useState(false)
  const [snapshot, setSnapshot] = useState<RecoveryOut | null>(null)
  const previous = useRef<'unknown' | 'connected' | 'unavailable'>('unknown')
  const recovery = useRef(onRecovered)
  useEffect(() => { recovery.current = onRecovered }, [onRecovered])

  const check = useCallback(async () => {
    setChecking(true)
    try {
      await api.health()
      const wasUnavailable = previous.current === 'unavailable'
      previous.current = 'connected'
      if (wasUnavailable) {
        try { setSnapshot(await api.recovery(DEMO.astronautId)) } catch { setSnapshot(null) }
        await recovery.current()
      }
      setState(wasUnavailable ? 'recovered' : 'connected')
    } catch {
      previous.current = 'unavailable'
      setState('unavailable')
    } finally { setChecking(false) }
  }, [])

  useEffect(() => { void check(); const timer = window.setInterval(() => { void check() }, 15_000); return () => window.clearInterval(timer) }, [check])

  if (state === 'checking' || state === 'connected') return null
  return <div className={`local-service-status ${state}`} role={state === 'unavailable' ? 'alert' : 'status'}>
    <div><strong>{state === 'unavailable' ? 'Local medical service unavailable' : 'Local medical service restored'}</strong><p>{state === 'unavailable' ? 'Displayed information may be stale. Actions are not queued or saved while the service is down. Emergency guidance remains available; activation needs the local service.' : snapshot ? `Recovered ${snapshot.open_case_ids.length} open case(s), ${snapshot.open_session_ids.length} session(s), ${snapshot.open_reminder_ids.length} reminder(s), and ${snapshot.undelivered_message_ids.length} undelivered message(s). Simulated ground link: ${snapshot.link_state}.` : 'Rechecking the case and schedule from the local service; recovery details are unavailable.'}</p></div>
    <div className="local-service-actions"><button type="button" className="button secondary" disabled={checking} onClick={() => void check()}>{checking ? 'Checking…' : 'Retry connection'}</button><NavLink to="/emergency">Emergency guidance</NavLink></div>
  </div>
}

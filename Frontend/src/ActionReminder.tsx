import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { followUpReminderDelay } from './mission-ui'

export function ActionReminder({ action, dueAt, link, enabled, hidden }: { action: string | null; dueAt: string | null; link: string; enabled: boolean; hidden: boolean }) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (!action || !enabled) return
    const now = Date.now()
    setVisible(true)
    const dismissFirst = window.setTimeout(() => setVisible(false), 20_000)
    const delay = followUpReminderDelay(dueAt, now)
    let showAgain: number | undefined
    let dismissAgain: number | undefined
    if (delay !== null) {
      showAgain = window.setTimeout(() => {
        setVisible(true)
        dismissAgain = window.setTimeout(() => setVisible(false), 20_000)
      }, delay)
    }
    return () => { window.clearTimeout(dismissFirst); if (showAgain) window.clearTimeout(showAgain); if (dismissAgain) window.clearTimeout(dismissAgain) }
  }, [action, dueAt, enabled])

  if (!action || !enabled || hidden || !visible) return null
  return <aside className="action-reminder" role="status" aria-label="Assessment reminder">
    <div><span className="eyebrow">NEXT ACTION · REMINDER</span><strong>{action}</strong>{dueAt && <small>Scheduled: {new Date(dueAt).toLocaleString()}</small>}</div>
    <NavLink className="button" to={link}>Open</NavLink>
    <button type="button" className="reminder-dismiss" aria-label="Dismiss reminder" onClick={() => setVisible(false)}>×</button>
  </aside>
}

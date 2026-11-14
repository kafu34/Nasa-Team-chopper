import type { CaseOut } from './api'

export type BodyAlert = { tone: 'amber' | 'red'; severity: number }
export type BodyAlerts = Record<string, BodyAlert>

/** Highlights only self-reported symptoms from the persisted fictional case. */
export function symptomAlerts(caseData: CaseOut | null): BodyAlerts {
  if (!caseData || caseData.state === 'resolved') return {}
  const alerts: BodyAlerts = {}
  for (const symptom of caseData.symptoms ?? []) {
    if (!Number.isFinite(symptom.severity) || symptom.severity <= 0) continue
    const alert = { tone: symptom.severity >= 7 ? 'red' : 'amber', severity: symptom.severity } as BodyAlert
    const sides = symptom.laterality === 'bilateral' ? ['left', 'right'] : [symptom.laterality]
    for (const side of sides) {
      const key = `${symptom.region_id}:${side}`
      if (!alerts[key] || alerts[key].severity < alert.severity) alerts[key] = alert
    }
  }
  return alerts
}

export function strongestAlert(alerts: BodyAlerts): BodyAlert | null {
  const values = Object.values(alerts)
  return values.reduce<BodyAlert | null>((strongest, alert) => !strongest || alert.severity > strongest.severity ? alert : strongest, null)
}

/** The second reminder starts near a future test or later when it was already due. */
export function followUpReminderDelay(dueAt: string | null, now: number): number | null {
  if (!dueAt) return null
  const due = Date.parse(dueAt)
  if (!Number.isFinite(due)) return null
  const tenMinutes = 10 * 60_000
  if (due <= now + 20_000) return tenMinutes
  const approach = due - tenMinutes
  return Math.max(20_000, (approach > now + 20_000 ? approach : due) - now)
}

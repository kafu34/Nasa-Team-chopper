import { describe, expect, it } from 'vitest'
import { followUpReminderDelay, symptomAlerts, strongestAlert } from './mission-ui'
import type { CaseOut } from './api'

describe('dashboard alert and reminder rules', () => {
  it('uses reported severity and laterality without inferring a diagnosis', () => {
    const caseData = { state: 'awaiting_assessment', symptoms: [
      { region_id: 'chest', laterality: 'left', severity: 3 },
      { region_id: 'upper_arm', laterality: 'bilateral', severity: 8 },
    ] } as CaseOut
    const alerts = symptomAlerts(caseData)
    expect(alerts['chest:left']).toEqual({ tone: 'amber', severity: 3 })
    expect(alerts['upper_arm:left']).toEqual({ tone: 'red', severity: 8 })
    expect(alerts['upper_arm:right']).toEqual({ tone: 'red', severity: 8 })
    expect(strongestAlert(alerts)).toEqual({ tone: 'red', severity: 8 })
    expect(symptomAlerts({ ...caseData, state: 'resolved' })).toEqual({})
  })

  it('schedules a second reminder near a future assessment and later for an overdue one', () => {
    const now = Date.parse('2026-11-14T10:00:00Z')
    expect(followUpReminderDelay('2026-11-14T10:30:00Z', now)).toBe(20 * 60_000)
    expect(followUpReminderDelay('2026-11-14T09:30:00Z', now)).toBe(10 * 60_000)
    expect(followUpReminderDelay(null, now)).toBeNull()
  })
})

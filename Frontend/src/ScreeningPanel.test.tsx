import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, type AssessmentStartOut, type ScheduledAssessment } from './api'
import { ScreeningPanel } from './ScreeningPanel'

afterEach(() => { cleanup(); vi.restoreAllMocks() })
const assessment = (id: string, state: ScheduledAssessment['due_state'], procedureId: string): ScheduledAssessment => ({ assessment_id: id, astronaut_id: 'DEMO-001', title: `${state} ${id}`, capability: 'pulse_oximetry', procedure_id: procedureId, due_at: '2026-11-15T10:00:00Z', status: state === 'completed' ? 'completed' : 'scheduled', is_due: state === 'due' || state === 'overdue', reason: 'Fictional schedule', case_id: null, completed_at: null, due_state: state, overdue_at: null, interval_hours: 24, grace_hours: 2, series_id: id, sequence: 1, symptom_linked: false, completed_by_measurement_id: null })

describe('durable screening UI', () => {
  it('shows backend states, acknowledges a reminder, and carries the returned session', async () => {
    const due = assessment('SA-PO-001', 'due', 'PROC-PO-01'), upcoming = assessment('SA-TEMP-001', 'upcoming', 'PROC-TEMP-01'), overdue = assessment('SA-BP-001', 'overdue', 'PROC-BP-01')
    vi.spyOn(api, 'assessments').mockResolvedValue({ astronaut_id: 'DEMO-001', assessments: [due, upcoming, overdue], note: 'Fictional schedule' })
    vi.spyOn(api, 'reminders').mockResolvedValue({ astronaut_id: 'DEMO-001', reminders: [{ reminder_id: 'REM-1', assessment_id: due.assessment_id, astronaut_id: 'DEMO-001', kind: 'due', status: 'open', created_at: due.due_at, acknowledged_at: null, acknowledged_by: null, closed_at: null, note: 'Acknowledgement is separate.' }] })
    const ack = vi.spyOn(api, 'acknowledgeReminder').mockResolvedValue({ reminder_id: 'REM-1', assessment_id: due.assessment_id, astronaut_id: 'DEMO-001', kind: 'due', status: 'acknowledged', created_at: due.due_at, acknowledged_at: due.due_at, acknowledged_by: 'DEMO-001', closed_at: null, note: 'Acknowledgement is separate.' })
    const startResult = { assessment: due, case_id: 'CASE-PO', case_state: 'awaiting_assessment', session_created: true, session: { session_id: 'SES-PO', case_id: 'CASE-PO', procedure_id: 'PROC-PO-01', status: 'in_progress' } } as AssessmentStartOut
    const start = vi.spyOn(api, 'startAssessment').mockResolvedValue(startResult)
    const onStarted = vi.fn(async () => {})
    render(<ScreeningPanel bootstrap={null} onStarted={onStarted} />)
    expect(await screen.findByText('due SA-PO-001')).toBeInTheDocument()
    expect(screen.getByText('overdue SA-BP-001').closest('article')).toHaveTextContent('overdue')
    expect(screen.getByText('upcoming SA-TEMP-001').closest('article')?.querySelector('button:last-child')).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Acknowledge due reminder' }))
    await waitFor(() => expect(ack).toHaveBeenCalledWith('REM-1'))
    fireEvent.click(screen.getByText('due SA-PO-001').closest('article')!.querySelector('button:last-child')!)
    await waitFor(() => expect(start).toHaveBeenCalledWith('SA-PO-001', 'DEMO-001', 'self'))
    expect(onStarted).toHaveBeenCalledWith(startResult)
  })
})

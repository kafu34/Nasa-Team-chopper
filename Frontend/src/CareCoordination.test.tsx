import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'
import { CareCoordination, dueLabel } from './CareCoordination'
import type { CaseOut, EquipmentRecommendation } from './api'

afterEach(cleanup)

const currentCase = { case_id: 'CASE-1', state: 'awaiting_assessment', next_action: 'Record temperature', updated_at: '2026-11-15T09:00:00Z', priority: 'routine', follow_up_status: 'scheduled', follow_ups: [{ follow_up_id: 'FU-1', title: 'Review reading', due_at: '2026-11-15T10:00:00Z', status: 'scheduled', interrupt: false }], requested_assessment: { capability: 'body_temperature', procedure_id: 'PROC-TEMP-01', status: 'requested', configured_reason: 'Fictional temperature deviation' }, symptoms: [], measurements: [] } as CaseOut

describe('software medical coordination', () => {
  it('uses backend due state and hides a mismatched device', () => {
    const wrongDevice = { equipment_id: 'EQ-PO-01', procedure_id: 'PROC-PO-01', status: 'active' } as EquipmentRecommendation
    render(<MemoryRouter><CareCoordination currentCase={currentCase} equipment={wrongDevice} /></MemoryRouter>)
    expect(screen.getByText('PROC-TEMP-01')).toBeInTheDocument()
    expect(screen.getByText('Fictional temperature deviation')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Case follow-up' })).toBeInTheDocument()
    expect(screen.getByText(/Review reading/)).toBeInTheDocument()
    expect(screen.getByText(/No matching active recommendation/)).toBeInTheDocument()
    expect(screen.queryByText('EQ-PO-01')).not.toBeInTheDocument()
  })

  it('labels completed, overdue and future follow-up states', () => {
    const now = Date.parse('2026-11-15T12:00:00Z')
    expect(dueLabel('2026-11-15T10:00:00Z', 'completed', now)).toBe('Completed')
    expect(dueLabel('2026-11-15T10:00:00Z', 'scheduled', now)).toBe('Overdue')
    expect(dueLabel('2026-11-16T10:00:00Z', 'scheduled', now)).toBe('Upcoming')
    expect(dueLabel('2099-01-01T00:00:00Z', 'scheduled', now, true)).toBe('Due now')
  })
})

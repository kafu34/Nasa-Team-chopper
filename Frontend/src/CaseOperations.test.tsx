import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, type CaseOut } from './api'
import { CaseOperations } from './CaseOperations'

afterEach(() => { cleanup(); vi.restoreAllMocks() })
const caseData = { case_id: 'CASE-1', state: 'monitoring', priority: 'routine', next_action: 'Review follow-up', updated_at: '2026-11-15T00:00:00Z', follow_up_status: 'due', follow_ups: [{ follow_up_id: 'FU-1', title: 'Recheck', due_at: '2026-11-15T00:00:00Z', status: 'due', interrupt: false }], symptoms: [], measurements: [] } as CaseOut

describe('controlled case resolution', () => {
  it('shows every backend blocker and only cancels follow-ups after an explicit choice', async () => {
    const resolve = vi.spyOn(api, 'resolveCase').mockRejectedValueOnce(new ApiError('The case still has open items.', 409, 'CASE_NOT_READY_TO_RESOLVE', { blockers: [{ kind: 'follow_up_outstanding', id: 'FU-1', detail: 'Follow-up FU-1 is due.' }, { kind: 'session_in_progress', id: 'SES-1', detail: 'Session SES-1 is in progress.' }] })).mockResolvedValue({ case: { ...caseData, state: 'resolved', resolved_by: 'DEMO-002', resolved_at: '2026-11-15T12:00:00Z' }, cancelled_follow_up_ids: ['FU-1'], warnings: ['Urgent ground message not yet acknowledged.'] })
    const onUpdated = vi.fn(async () => {})
    render(<CaseOperations caseData={caseData} onUpdated={onUpdated} />)
    fireEvent.change(screen.getByLabelText('Resolution note'), { target: { value: 'Crew review complete' } })
    fireEvent.click(screen.getByRole('button', { name: 'Request case resolution' }))
    expect(await screen.findByText('Follow-up FU-1 is due.')).toBeInTheDocument()
    expect(screen.getByText('Session SES-1 is in progress.')).toBeInTheDocument()
    expect(resolve).toHaveBeenCalledWith('CASE-1', 'DEMO-002', 'Crew review complete', false)
    fireEvent.click(screen.getByLabelText(/Cancel 1 outstanding follow-up/))
    fireEvent.click(screen.getByRole('button', { name: 'Request case resolution' }))
    await waitFor(() => expect(resolve).toHaveBeenLastCalledWith('CASE-1', 'DEMO-002', 'Crew review complete', true))
    expect(onUpdated).toHaveBeenCalledWith(expect.objectContaining({ state: 'resolved' }))
    expect(screen.getByText(/Cancelled follow-ups: FU-1/)).toBeInTheDocument()
    expect(screen.getByText('Urgent ground message not yet acknowledged.')).toBeInTheDocument()
  })
})

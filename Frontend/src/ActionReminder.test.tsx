import { act, cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ActionReminder } from './ActionReminder'

afterEach(() => { cleanup(); vi.useRealTimers() })
describe('next action reminder', () => {
  it('shows for 20 seconds, then returns close to the scheduled test', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-14T10:00:00Z'))
    render(<MemoryRouter><ActionReminder action="Blood pressure check" dueAt="2026-11-14T10:30:00Z" link="/procedure" enabled hidden={false} /></MemoryRouter>)
    expect(screen.getByRole('status', { name: 'Assessment reminder' })).toHaveTextContent('Blood pressure check')
    act(() => vi.advanceTimersByTime(20_000))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    act(() => vi.advanceTimersByTime(19 * 60_000 + 39_000))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    act(() => vi.advanceTimersByTime(1_000))
    expect(screen.getByRole('status')).toHaveTextContent('Blood pressure check')
  })
})

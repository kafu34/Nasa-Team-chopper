import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import { LocalServiceStatus } from './LocalServiceStatus'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('local service recovery', () => {
  it('marks retained information stale and refreshes after reconnection', async () => {
    const health = vi.spyOn(api, 'health').mockRejectedValueOnce(new Error('offline')).mockResolvedValue({ status: 'ok' })
    const recovered = vi.fn(async () => {})
    render(<MemoryRouter><LocalServiceStatus onRecovered={recovered} /></MemoryRouter>)
    expect(await screen.findByRole('alert')).toHaveTextContent('Actions are not queued or saved')
    fireEvent.click(screen.getByRole('button', { name: 'Retry connection' }))
    await waitFor(() => expect(recovered).toHaveBeenCalledTimes(1))
    expect(screen.getByRole('status')).toHaveTextContent('Local medical service restored')
    expect(health).toHaveBeenCalledTimes(2)
  })
})

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, type AccessMatrix, type CommsMessage } from './api'
import { Communications } from './Communications'
import { allowed, DemoAccessContext } from './DemoAccess'

afterEach(() => { cleanup(); vi.restoreAllMocks() })
const message = (direction: CommsMessage['direction'], status: CommsMessage['status']): CommsMessage => ({ message_id: 'MSG-1', client_message_id: 'CLIENT-1', direction, priority: 'urgent', sender_id: direction === 'to_ground' ? 'DEMO-002' : 'GND-FS-01', sender_role: direction === 'to_ground' ? 'crew_medical_officer' : 'flight_surgeon', recipient_role: direction === 'to_ground' ? 'flight_surgeon' : 'crew_medical_officer', case_id: 'CASE-1', subject: 'Medical update', body: 'Fictional status', status, created_at: '2026-11-15T10:00:00Z', transmit_at: null, deliver_at: '2026-11-15T10:05:00Z', delivered_at: status === 'delivered' ? '2026-11-15T10:05:00Z' : null, acknowledged_at: null, acknowledged_by: null, duplicate: false, simulated: true })
const link = { link_id: 'LINK-1', state: 'up' as const, changed_at: '2026-11-15T10:00:00Z', changed_by: 'DEMO-002', reason: 'demo', outage_count: 0, one_way_delay_seconds: 300, transmit_seconds: 5, simulated: true as const }
const matrix = { role_codes: ['crew_medical_officer', 'flight_surgeon'], personnel: [{ person_id: 'DEMO-002', display_name: 'Officer', role_code: 'crew_medical_officer', location: 'habitat', kind: 'crew' }, { person_id: 'GND-FS-01', display_name: 'Surgeon', role_code: 'flight_surgeon', location: 'ground', kind: 'ground' }], permissions: [{ action: 'comms.send_to_ground', allowed_roles: ['crew_medical_officer'], own_record_allowed: false, description: '' }, { action: 'comms.send_to_crew', allowed_roles: ['flight_surgeon'], own_record_allowed: false, description: '' }, { action: 'comms.acknowledge_to_ground', allowed_roles: ['flight_surgeon'], own_record_allowed: false, description: '' }, { action: 'comms.acknowledge_to_crew', allowed_roles: ['crew_medical_officer'], own_record_allowed: false, description: '' }], limitation: 'Demo' } as AccessMatrix
const view = (id: string) => <MemoryRouter><DemoAccessContext.Provider value={{ matrix, viewerId: id, setViewerId: () => {}, can: (action, owner) => allowed(matrix, id, action, owner) }}><Communications caseId="CASE-1" /></DemoAccessContext.Provider></MemoryRouter>

describe('simulated medical communications', () => {
  it('only offers a delivered outbound acknowledgement to the ground viewpoint', async () => {
    vi.spyOn(api, 'commsMessages').mockResolvedValue({ messages: [message('to_ground', 'delivered')], link_state: 'up', one_way_delay_seconds: 300, note: 'Fictional delay' })
    vi.spyOn(api, 'commsLink').mockResolvedValue(link)
    const ack = vi.spyOn(api, 'acknowledgeCommsMessage').mockResolvedValue({ ...message('to_ground', 'acknowledged'), acknowledged_by: 'GND-FS-01' })
    const rendered = render(view('DEMO-002'))
    expect(await screen.findByText('Medical update')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Acknowledge as/ })).not.toBeInTheDocument()
    rendered.rerender(view('GND-FS-01'))
    fireEvent.click(screen.getByRole('button', { name: 'Acknowledge as GND-FS-01' }))
    await waitFor(() => expect(ack).toHaveBeenCalledWith('MSG-1', 'GND-FS-01'))
  })

  it('reuses a client ID when a send response is lost and the same draft is retried', async () => {
    vi.spyOn(api, 'commsMessages').mockResolvedValue({ messages: [message('to_ground', 'queued')], link_state: 'up', one_way_delay_seconds: 300, note: 'Fictional delay' })
    vi.spyOn(api, 'commsLink').mockResolvedValue(link)
    const send = vi.spyOn(api, 'sendCommsMessage').mockRejectedValueOnce(new Error('Response lost')).mockResolvedValue(message('to_ground', 'queued'))
    render(view('DEMO-002'))
    await screen.findByText('Medical update')
    fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'Fictional status' } })
    fireEvent.click(screen.getByRole('button', { name: 'Queue simulated message' }))
    await screen.findByText(/Response lost/)
    fireEvent.click(screen.getByRole('button', { name: 'Queue simulated message' }))
    await waitFor(() => expect(send).toHaveBeenCalledTimes(2))
    expect(send.mock.calls[0][0].client_message_id).toBe(send.mock.calls[1][0].client_message_id)
  })
})

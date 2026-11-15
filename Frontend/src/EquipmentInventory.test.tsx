import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, type EquipmentStatus } from './api'
import { EquipmentInventory } from './EquipmentInventory'

afterEach(() => { cleanup(); vi.restoreAllMocks() })
const device: EquipmentStatus = { equipment_id: 'EQ-BP-01', device_model: 'Demo BP monitor', capability: 'blood_pressure', zone_id: 'medical', readiness: 'ready', readiness_verified_at: '2026-11-14T00:00:00Z', supplies: { cuff: true }, required_supplies: ['cuff'], compatible_procedure_ids: ['PROC-BP-01'], status_updated_at: '2026-11-14T00:00:00Z', usable: false, unusable_reasons: ['readiness_check_stale'], data_category: 'SIMULATED_ENVIRONMENT_OR_DEVICE' }

describe('controlled device inventory', () => {
  it('shows backend stale reasons and clears invalidated routes without silently verifying readiness', async () => {
    vi.spyOn(api, 'equipmentInventory').mockResolvedValue([device])
    const result = { equipment: { ...device, usable: true, unusable_reasons: [] }, changed: true, before: {}, invalidated_recommendation_ids: ['REC-1'], affected_session_ids: ['SES-1'] }
    const update = vi.spyOn(api, 'updateEquipment').mockResolvedValue(result)
    const onUpdated = vi.fn()
    render(<EquipmentInventory zones={[{ zone_id: 'medical', name: 'Medical Bay' }]} onUpdated={onUpdated} />)
    expect(await screen.findByText('Demo BP monitor')).toBeInTheDocument()
    expect(screen.getByText(/readiness check stale/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Update status' }))
    expect(screen.getByLabelText('Readiness')).toHaveValue('')
    fireEvent.change(screen.getByLabelText('Audit note'), { target: { value: 'Supply check only' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save device status' }))
    await waitFor(() => expect(update).toHaveBeenCalledWith('EQ-BP-01', expect.not.objectContaining({ readiness: 'verified_ready' })))
    expect(onUpdated).toHaveBeenCalledWith(result)
    expect(await screen.findByText(/In-progress session\(s\) affected, not cancelled: SES-1/)).toBeInTheDocument()
  })
})

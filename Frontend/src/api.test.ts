import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from './api'

afterEach(() => vi.unstubAllGlobals())
describe('local API errors', () => {
  it('does not substitute mock mission data when backend is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('connection refused')))
    await expect(api.bootstrap()).rejects.toEqual(new ApiError('Local backend unavailable. No data was saved or retrieved.', 0))
  })
  it('uses the committed P0 request shapes', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 201, text: async () => '{}' })
    vi.stubGlobal('fetch', fetchMock)
    await api.symptom({ astronaut_id: 'DEMO-001', region_id: 'head', laterality: 'midline', severity: 3, onset: '2026-11-14T08:45:00Z' })
    await api.completeStep('SES-1', 'S1', 'self')
    await api.measurement({ case_id: 'CASE-1', session_id: 'SES-1', type: 'blood_pressure', unit: 'mmHg', value: { systolic: 118, diastolic: 76, pulse: 70 } })
    await api.emergency()
    const bodies = fetchMock.mock.calls.map(call => JSON.parse(call[1].body))
    expect(bodies[0].onset).toBe('2026-11-14T08:45:00Z')
    expect(bodies[1].completion_source).toBe('self_confirmed')
    expect(bodies[2].value).toEqual({ systolic: 118, diastolic: 76, pulse: 70 })
    expect(bodies[2].source).toBe('SIMULATED_MANUAL_ENTRY')
    expect(bodies[3].trigger).toBe('crew_collapse')
  })
  it('uses the dedicated RadLab timeseries endpoint and detector filter', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, text: async () => '{}' })
    vi.stubGlobal('fetch', fetchMock)
    await api.radiation('REM-Lid')
    const url = new URL(fetchMock.mock.calls[0][0], 'http://localhost')
    expect(url.pathname).toBe('/api/v1/radiation/timeseries')
    expect(url.searchParams.get('dataset_id')).toBe('NASA-RADLAB')
    expect(url.searchParams.get('instrument_id')).toBe('REM-Lid')
  })
  it('sends the structured 3D point in the symptom payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 201, text: async () => '{}' })
    vi.stubGlobal('fetch', fetchMock)
    await api.symptom({ astronaut_id: 'DEMO-001', region_id: 'upper_arm', laterality: 'right', severity: 4, onset: '2026-11-14T08:45:00Z', note: 'Ache when lifting', surface_point: { model_id: 'sentinel-body-v1', site_id: 'right_shoulder', x: -0.468, y: 0.704, z: 0.131 } })
    const body = JSON.parse(fetchMock.mock.calls[0][1].body)
    expect(body.note).toBe('Ache when lifting')
    expect(body.surface_point).toEqual({ model_id: 'sentinel-body-v1', site_id: 'right_shoulder', x: -0.468, y: 0.704, z: 0.131 })
  })
})

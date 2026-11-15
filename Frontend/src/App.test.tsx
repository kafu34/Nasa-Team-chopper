import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'

const roles = { role_codes: ['crew_member', 'crew_medical_officer', 'flight_surgeon', 'ground_support'], permissions: [{ action: 'case.read_sensitive', allowed_roles: ['crew_medical_officer', 'flight_surgeon'], own_record_allowed: true, description: 'Read case' }, { action: 'observations.read_history', allowed_roles: ['crew_medical_officer', 'flight_surgeon'], own_record_allowed: true, description: 'Read observations' }], personnel: [{ person_id: 'DEMO-001', display_name: 'Demo Astronaut One', role_code: 'crew_member', location: 'habitat', kind: 'crew' }, { person_id: 'GND-SUP-01', display_name: 'Ground Support', role_code: 'ground_support', location: 'ground', kind: 'ground' }], limitation: 'No authentication.' }

afterEach(() => { cleanup(); vi.unstubAllGlobals() })
describe('offline-safe screens', () => {
  it('opens emergency assistance even when mission bootstrap fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend offline')))
    render(<MemoryRouter initialEntries={['/emergency']}><App /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'Emergency assistance' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Activate emergency assistance' })).toBeEnabled()
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/v1/demo/bootstrap', expect.anything()))
  })
  it('shows imported OSD-575 measurements and source units from the API', async () => {
    const fetchMock = vi.fn((path: string) => {
      const data = path.includes('/records?') ? { dataset_id: 'OSD-575', source_url: 'https://osdr.nasa.gov/bio/repo/data/studies/OSD-575', source_file: 'CMP.csv', record_schema: 'CMP_ANALYTE_V1', total: 1, available_timepoints: ['L-92'], limitations: [], records: [{ analyte: 'GLUCOSE', value: 5.2, unit: 'mmol/L', subject_id: 'C001', timepoint: 'L-92', timepoint_order: 1, data_category: 'NASA_RESEARCH' }] } : path.endsWith('/OSD-575') ? { dataset_id: 'OSD-575', status: 'IMPORTED', records_available: 1, record_schema: 'CMP_ANALYTE_V1', source_url: 'https://osdr.nasa.gov/bio/repo/data/studies/OSD-575' } : path.endsWith('/datasets') ? { datasets: [{ dataset_id: 'OSD-575', status: 'IMPORTED', records_available: 1 }] } : {}
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(data) })
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter initialEntries={['/research']}><App /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('5.2')).toBeInTheDocument())
    expect(screen.getByText('mmol/L')).toBeInTheDocument()
    expect(screen.getByText('C001')).toBeInTheDocument()
    expect(screen.getByText('L-92')).toBeInTheDocument()
  })
  it('loads RadLab through timeseries and displays a single historical detector', async () => {
    const fetchMock = vi.fn((path: string) => {
      const data = path.includes('/radiation/timeseries?') ? { dataset_id: 'NASA-RADLAB', metric: 'absorbed_dose_rate', unit: 'μGy/hour', total: 2, data_category: 'NASA_RESEARCH', available_instruments: ['DosTel1'], points: [{ timestamp: '2022-04-01T00:00:00Z', value: 9.5, unit: 'μGy/hour', instrument_id: 'DosTel1', module: 'Columbus' }] } : path.endsWith('/NASA-RADLAB') ? { dataset_id: 'NASA-RADLAB', status: 'IMPORTED', record_schema: 'RADIATION_TIMESERIES_V1', records_available: 2847, study_type: 'SPACEFLIGHT_ENVIRONMENT' } : path.endsWith('/datasets') ? { datasets: [{ dataset_id: 'NASA-RADLAB', status: 'IMPORTED' }] } : { dataset_id: 'OSD-575', status: 'NOT_DOWNLOADED' }
      return Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(data) })
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter initialEntries={['/research']}><App /></MemoryRouter>)
    fireEvent.click(screen.getByRole('button', { name: /NASA-RADLAB/ }))
    await waitFor(() => expect(screen.getByText('9.5')).toBeInTheDocument())
    expect(fetchMock.mock.calls.some(call => call[0].includes('/radiation/timeseries?'))).toBe(true)
    expect(fetchMock.mock.calls.some(call => call[0].includes('/NASA-RADLAB/records'))).toBe(false)
    expect(screen.getByText(/not live HAB-01 readings or a crew member’s personal dose/i)).toBeInTheDocument()
  })
  it('places vitals beside the alerting body and expands the selected region for a report', async () => {
    const bootstrap = { astronaut: { astronaut_id: 'DEMO-001', display_name: 'Demo Astronaut One' }, habitat: { habitat_id: 'HAB-01', zones: [] }, observations: [{ type: 'heart_rate', value: 72, unit: 'bpm', observed_at: '2026-11-14T10:00:00Z', source: 'SIMULATED_WEARABLE' }], scheduled_assessments: [], open_cases: [{ case_id: 'CASE-1', state: 'awaiting_assessment', next_action: 'Check symptoms', updated_at: '2026-11-14T10:00:00Z' }], demo_inputs: { ble_observations: [] }, equipment: [] }
    const caseData = { case_id: 'CASE-1', state: 'awaiting_assessment', next_action: 'Check symptoms', follow_ups: [], symptoms: [{ region_id: 'chest', laterality: 'left', severity: 8 }], measurements: [] }
    vi.stubGlobal('fetch', vi.fn((path: string) => Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(path.includes('/access/roles') ? roles : path.includes('/cases/CASE-1') ? caseData : path.includes('/research/datasets/') ? { dataset_id: 'OSD-195', status: 'NOT_DOWNLOADED' } : bootstrap) })))
    render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('Reported 8/10')).toBeInTheDocument())
    expect(screen.getByRole('heading', { name: 'Vitals at a glance' })).toBeInTheDocument()
    expect(screen.getByText('72')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Expand anatomical twin →' }))
    expect(screen.getByRole('heading', { name: 'Point to where it hurts' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Vitals at a glance' })).not.toBeInTheDocument()
    await waitFor(() => expect(screen.getByLabelText('Choose an area by name')).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText('Choose an area by name'), { target: { value: 'left_chest' } })
    expect(screen.getByText('Left chest')).toBeInTheDocument()
  })

  it('lets the astronaut choose a map zone and confirms it with the backend', async () => {
    const bootstrap = { astronaut: { astronaut_id: 'DEMO-001', display_name: 'Demo Astronaut One' }, habitat: { habitat_id: 'HAB-01', zones: [{ zone_id: 'medical', name: 'Medical' }] }, observations: [], scheduled_assessments: [], open_cases: [], demo_inputs: { ble_observations: [] }, equipment: [] }
    const fetchMock = vi.fn((path: string, _init?: RequestInit) => Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(path.includes('/location/confirm') ? { zone_id: 'medical', confidence: 1, source: 'manual_confirmation', observed_at: '2026-11-14T10:00:00Z', explanation: 'Confirmed by astronaut' } : bootstrap) }))
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>)
    fireEvent.click(screen.getByRole('button', { name: 'Open menu' }))
    fireEvent.click(screen.getByRole('link', { name: /Maps · choose my location/ }))
    expect(screen.getByRole('heading', { name: 'Habitat map & equipment' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /medical/i }))
    fireEvent.click(screen.getByRole('button', { name: /Confirm medical/i }))
    await waitFor(() => expect(fetchMock.mock.calls.some(call => call[0].includes('/location/confirm'))).toBe(true))
    const body = JSON.parse(fetchMock.mock.calls.find(call => call[0].includes('/location/confirm'))?.[1]?.body as string)
    expect(body.zone_id).toBe('medical')
  })
})

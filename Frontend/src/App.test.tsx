import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'

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
})

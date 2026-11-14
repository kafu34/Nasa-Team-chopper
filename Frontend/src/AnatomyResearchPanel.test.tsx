import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AnatomyResearchPanel } from './AnatomyResearchPanel'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })
describe('human research context', () => {
  it('shows honest status and no numerical results for an unavailable study', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, text: async () => JSON.stringify({ dataset_id: 'OSD-195', status: 'NOT_DOWNLOADED', status_reason: 'Processed files not present', source_url: 'https://osdr.nasa.gov/bio/repo/data/studies/OSD-195' }) })
    vi.stubGlobal('fetch', fetchMock)
    render(<AnatomyResearchPanel selection={{ regionId: 'upper_arm', laterality: 'left', label: 'Left upper arm' }} />)
    expect(screen.getByText(/Human ground-analogue experiment/)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText(/Processed files not present/)).toBeInTheDocument())
    expect(screen.getByText(/No numerical results shown/)).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
  it('shows only verified imported human-derived cell records', async () => {
    const fetchMock = vi.fn((path: string) => Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(path.includes('/records?gene_symbol=TSPAN6') ? { record_schema: 'GENE_EXPRESSION_V1', total: 13, expression_records: [{ probe_id: 'PROBE-A', gene_symbol: 'TSPAN6', value: 2.4, value_unit: 'RMA log2', sample_id: 'SAMPLE-1', condition_label: 'Space Flight, osteogenic medium', normalization: 'RMA', normalization_verified: true, source_file: 'processed.txt', data_category: 'NASA_RESEARCH' }, { probe_id: 'PROBE-B', gene_symbol: 'TSPAN6', value: null, value_unit: 'RMA log2', sample_id: 'SAMPLE-2', condition_label: 'Ground Control, osteogenic medium', normalization: 'RMA', normalization_verified: true, source_file: 'processed.txt', data_category: 'NASA_RESEARCH' }], comparison_readiness: { ready: false, reasons: ['matched control unavailable'] }, samples: [] } : { dataset_id: 'OSD-546', status: 'IMPORTED', body_systems: ['bone'], source_url: 'https://osdr.nasa.gov/bio/repo/data/studies/OSD-546' }) }))
    vi.stubGlobal('fetch', fetchMock)
    render(<AnatomyResearchPanel selection={null} />)
    fireEvent.click(screen.getByRole('button', { name: 'Bone cells · OSD-546' }))
    await waitFor(() => expect(screen.getByText('2.4')).toBeInTheDocument())
    expect(fetchMock.mock.calls.some(call => call[0].includes('gene_symbol=TSPAN6'))).toBe(true)
    expect(screen.getByText('13 matching research records returned by the backend.')).toBeInTheDocument()
    expect(screen.getByText(/not a direct astronaut bone-density measurement/i)).toBeInTheDocument()
    expect(screen.getByText(/matched control unavailable/)).toBeInTheDocument()
    expect(screen.queryByText('PROBE-B')).not.toBeInTheDocument()
  })
})

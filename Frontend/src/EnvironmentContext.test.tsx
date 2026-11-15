import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import { EnvironmentContext } from './EnvironmentContext'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('environmental attribution', () => {
  it('keeps historical RadLab data separate from habitat, personal dose and health claims', async () => {
    vi.spyOn(api, 'environmentContext').mockResolvedValue({ astronaut_id: 'DEMO-001', radiation: { dataset_id: 'NASA-RADLAB', status: 'IMPORTED', title: 'RadLab', source_url: 'https://example.nasa.gov/radlab', location: 'ISS (historical snapshot)', is_habitat_reading: false, is_personal_dose: false, latest_readings: [{ instrument_id: 'DosTel1', instrument_family: 'DOSIS', spacecraft: 'ISS', module: 'Columbus', metric: 'absorbed_dose_rate', value: 3.2, value_raw: '3.2', unit: 'μGy/hour', timestamp: '2022-04-01T00:00:00Z', source_file: 'radlab.csv', source_row_number: 44 }], limitations: [] }, atmosphere: { dataset_id: 'NASA-EDA', status: 'BLOCKED', note: 'No source file.' }, health_relationship: 'none_inferred', caution: 'Historical ISS readings; no crew health relationship is inferred.', data_category: 'NASA_RESEARCH' })
    render(<EnvironmentContext />)
    expect(await screen.findByText('DosTel1')).toBeInTheDocument()
    expect(screen.getByText('Habitat reading: no')).toBeInTheDocument()
    expect(screen.getByText('Personal dose: no')).toBeInTheDocument()
    expect(screen.getByText('Health relationship: none inferred')).toBeInTheDocument()
    expect(screen.getByText('NASA-EDA · BLOCKED')).toBeInTheDocument()
    expect(screen.getByText('radlab.csv')).toBeInTheDocument()
  })
})

import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { HistologyResults, RadiationResults } from './ResearchSpecialResults'
import type { ResearchRecordsPage, TimeseriesPage } from './api'

describe('new NASA research views', () => {
  it('shows OSD-817 donor counts and notes without assigning group conditions', () => {
    const page = { record_schema: 'HISTOLOGY_COUNTS_V1', available_analytes: ['CTB', 'TUNEL'], available_measures: ['counts', 'normalized_counts'], histology_records: [
      { sample_name: '7346_OD_FN', donor_id: '7346', eye: 'OD', fixation: 'FN', assay: 'TUNEL', measure: 'counts', value: 200, value_raw: '200', unit: 'count', group_number: '6', days_on_system: 14, donor_sex: 'Female', donor_age: 64, notes: 'Image overexposed', source_file: 'TUNEL.csv', source_row_number: 1, annotation_file: 'TUNEL.xlsx', data_category: 'NASA_RESEARCH' },
      { sample_name: '7346_OD_FN', donor_id: '7346', eye: 'OD', fixation: 'FN', assay: 'CTB', measure: 'counts', value: 202, value_raw: '202', unit: 'count', group_number: '6', days_on_system: 14, donor_sex: 'Female', donor_age: 64, notes: 'Repeat image', source_file: 'CTB.csv', source_row_number: 1, annotation_file: 'CTB.xlsx', data_category: 'NASA_RESEARCH' },
    ] } as ResearchRecordsPage
    render(<HistologyResults page={page} />)
    expect(screen.getByText('200')).toBeInTheDocument()
    expect(screen.getByText('Image overexposed')).toBeInTheDocument()
    expect(screen.getByText(/pressure and tilt conditions are unverified/i)).toBeInTheDocument()
    expect(screen.queryByText('202')).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Assay'), { target: { value: 'CTB' } })
    expect(screen.getByText('202')).toBeInTheDocument()
  })

  it('keeps RadLab readings tied to one instrument and historic ISS context', () => {
    const page = { dataset_id: 'NASA-RADLAB', metric: 'absorbed_dose_rate', unit: 'μGy/hour', total: 1192, data_category: 'NASA_RESEARCH', available_instruments: ['DosTel1', 'DosTel2'], points: [
      { timestamp: '2022-04-01T00:00:00Z', value: 9.5, unit: 'μGy/hour', instrument_id: 'DosTel1', module: 'Columbus' },
      { timestamp: '2022-04-01T00:01:00Z', value: 10.25, unit: 'μGy/hour', instrument_id: 'DosTel1', module: 'Columbus' },
      { timestamp: '2022-04-01T00:01:00Z', value: 3, unit: 'μGy/hour', instrument_id: 'DosTel2', module: 'Columbus' },
    ] } as TimeseriesPage
    const onInstrument = vi.fn()
    render(<RadiationResults page={page} instrument="DosTel1" onInstrument={onInstrument} />)
    expect(screen.getByText('9.5')).toBeInTheDocument()
    expect(screen.queryByText('3')).not.toBeInTheDocument()
    expect(screen.getByText(/not live HAB-01 readings or a crew member’s personal dose/i)).toBeInTheDocument()
    expect(screen.getByText(/2 of 1192 readings for DosTel1 shown/)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Detector'), { target: { value: 'DosTel2' } })
    expect(onInstrument).toHaveBeenCalledWith('DosTel2')
  })
})

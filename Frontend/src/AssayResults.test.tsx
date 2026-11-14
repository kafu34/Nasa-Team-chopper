import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AssayResults } from './AssayResults'
import type { ResearchRecordsPage } from './api'

describe('OSD-656 assay display', () => {
  it('shows actual returned units and missing values without clinical interpretation', () => {
    const page = { record_schema: 'BIO_ASSAY_TABLE', total: 2, available_measures: ['concentration_npq'], assay_records: [
      { sample_name: 'C001_urine_L-92', subject_id: 'C001', specimen: 'urine', analyte: 'il6', measure: 'concentration_npq', value: 11.386, unit: 'NPQ as published', timepoint: 'L-92', source_file: 'panel.csv', data_category: 'NASA_RESEARCH' },
      { sample_name: 'C002_urine_L-92', subject_id: 'C002', specimen: 'urine', analyte: 'il6', measure: 'concentration_npq', value: null, unit: 'NPQ as published', timepoint: 'L-92', source_file: 'panel.csv', data_category: 'NASA_RESEARCH' },
    ] } as ResearchRecordsPage
    render(<AssayResults page={page} />)
    expect(screen.getByText('11.386')).toBeInTheDocument()
    expect(screen.getAllByText('NPQ as published')).toHaveLength(2)
    expect(screen.getByText('Missing')).toBeInTheDocument()
    expect(screen.getByText(/not clinical concentrations/i)).toBeInTheDocument()
  })
})

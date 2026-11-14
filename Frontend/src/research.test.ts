import { describe, expect, it } from 'vitest'
import { trendRecords } from './research'

describe('trendRecords', () => {
  it('keeps only comparable real numeric records and never replaces missing values with zero', () => {
    const records = [
      { ANALYTE: 'A', SUBJECT_ID: 'S1', UNITS: 'mg/dL', VALUE: 2, timepoint: 'T1' },
      { ANALYTE: 'B', SUBJECT_ID: 'S1', UNITS: 'mg/dL', VALUE: 90, timepoint: 'T1' },
      { ANALYTE: 'A', SUBJECT_ID: 'S1', UNITS: 'mg/dL', VALUE: null, timepoint: 'T2' },
      { ANALYTE: 'A', SUBJECT_ID: 'S1', UNITS: 'mg/dL', VALUE: 3, timepoint: 'T3' },
      { ANALYTE: 'A', SUBJECT_ID: 'S2', UNITS: 'mg/dL', VALUE: 500, timepoint: 'T3' },
    ]
    expect(trendRecords(records).map(item => item.value)).toEqual([2, 3])
  })
})

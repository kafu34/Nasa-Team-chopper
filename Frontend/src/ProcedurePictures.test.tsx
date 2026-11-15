import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import fixture from '../../shared/fixtures/demo_scenario.json'
import type { ProcedureOut } from './api'
import { ProcedureCoach } from './ProcedureCoach'

afterEach(cleanup)

describe('BP monitor picture guide', () => {
  it('starts with pictures and moves through all six backend actions without acknowledging a step', () => {
    render(<ProcedureCoach caseId={null} equipment={null} procedure={fixture.procedure as unknown as ProcedureOut} session={null} measurement={null} onProcedure={vi.fn()} onSession={vi.fn()} onMeasurement={vi.fn()} onCaseRefresh={vi.fn()} />)
    const pictureNames = [
      /BP monitor and cuff ready/i,
      /Bare left upper arm exposed/i,
      /Cuff wrapped on the left upper arm/i,
      /Cuffed arm supported near heart level/i,
      /Start button pressed while the cuff measures/i,
      /Simulated monitor values copied/i,
    ]
    expect(screen.getByRole('button', { name: 'Picture guide' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '← Previous picture' })).toBeDisabled()
    for (let index = 0; index < pictureNames.length; index++) {
      expect(screen.getByRole('img', { name: pictureNames[index] })).toBeInTheDocument()
      expect(screen.getByText(`Picture ${index + 1} of 6`)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Acknowledge real-world step' })).toBeDisabled()
      if (index < pictureNames.length - 1) fireEvent.click(screen.getByRole('button', { name: 'Next picture →' }))
    }
    expect(screen.getByRole('button', { name: 'Next picture →' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: '← Previous picture' }))
    expect(screen.getByRole('img', { name: pictureNames[4] })).toBeInTheDocument()
  })
})

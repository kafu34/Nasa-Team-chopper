import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { ProcedurePictures } from './ProcedurePictures'
import { visualFor } from './visual-registry'
import type { ProcedureStep } from './api'
import fixture from '../../shared/fixtures/demo_scenario.json'

afterEach(cleanup)
describe('2.8.0 picture guides', () => {
  it('shows distinct pulse-oximeter and thermometer actions from the backend fixture', () => {
    const procedures = fixture.additional_procedures as unknown as { steps: ProcedureStep[] }[]
    const names = [
      /oximeter and restraint ready/i, /index finger prepared/i, /clip placed around/i, /hand held still/i, /oxygen saturation and pulse copied/i,
      /thermometer prepared/i, /forehead cleared/i, /aimed at the forehead/i, /trigger pressed/i, /temperature copied/i,
    ]
    procedures.flatMap(item => item.steps).forEach((step, index) => {
      const scene = visualFor(step)
      expect(scene).not.toBeNull()
      const view = render(<ProcedurePictures scene={scene!} reading={{ systolic: '', diastolic: '', spo2: '97', pulse: '69', temperature: '36.8' }} />)
      expect(screen.getByRole('img', { name: names[index] })).toBeInTheDocument()
      view.unmount()
    })
  })
})

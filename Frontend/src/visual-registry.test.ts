import { describe, expect, it } from 'vitest'
import fixture from '../../shared/fixtures/demo_scenario.json'
import type { ProcedureStep } from './api'
import { visualFor } from './visual-registry'

const steps = fixture.procedure.steps as unknown as ProcedureStep[]

describe('backend visual action contract', () => {
  it('has a working scene for each of the six fixture actions', () => {
    expect(steps.map(step => visualFor(step))).toEqual(['prepare', 'expose', 'wrap', 'support', 'measure', 'record'])
  })

  it('does not silently substitute a scene for a changed action or asset', () => {
    const step = steps[2]
    expect(visualFor({ ...step, visual: { ...step.visual, action_id: 'VA-BP-UNKNOWN' } })).toBeNull()
    expect(visualFor({ ...step, visual: { ...step.visual, asset_id: 'ASSET-WRONG' } })).toBeNull()
  })
})

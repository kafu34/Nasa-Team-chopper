import { describe, expect, it } from 'vitest'
import { humanSelection, humanSiteAt, HUMAN_MODEL_ID } from './human-site'
import { surfacePoint, symptomNote } from './anatomy-sites'

describe('human reference surface mapping', () => {
  it('maps catalog joint anchors to the correct side and existing backend region', () => {
    const shoulder = humanSelection({ x: -0.165, y: 1.394, z: 0.035 }, 'skin', { x: -0.165, y: 0.535, z: 0.035 })
    expect(shoulder).toMatchObject({ siteId: 'right_shoulder', regionId: 'upper_arm', laterality: 'right', modelId: HUMAN_MODEL_ID, modelVersion: 1, meshId: 'skin' })
    expect(humanSiteAt({ x: 0.211, y: 1.124, z: 0.02 })).toBe('left_elbow')
  })

  it('does not send the new mesh coordinates as legacy model points', () => {
    const selection = humanSelection({ x: -0.165, y: 1.394, z: 0.035 }, 'skin', { x: -0.165, y: 0.535, z: 0.035 })
    expect(surfacePoint(selection)).toBeUndefined()
    expect(symptomNote(selection, 'Sore when reaching')).toContain('Exact mesh point not stored')
  })

  it('keeps torso, head, leg and foot areas distinct', () => {
    expect(humanSiteAt({ x: -0.08, y: 1.64, z: 0.04 })).toBe('head')
    expect(humanSiteAt({ x: 0.08, y: 1.26, z: 0.12 })).toBe('left_chest')
    expect(humanSiteAt({ x: -0.08, y: 1.26, z: -0.11 })).toBe('right_upper_back')
    expect(humanSiteAt({ x: 0.1, y: 0.66, z: 0.04 })).toBe('left_upper_leg')
    expect(humanSiteAt({ x: -0.09, y: 0.03, z: 0.09 })).toBe('right_foot')
  })
})

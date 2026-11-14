import { describe, expect, it } from 'vitest'
import { humanSelection, humanSiteAt, HUMAN_MODEL_ID, HUMAN_MODEL_VERSION } from './human-site'
import { reportedSurfaceSelection, surfacePoint, symptomNote } from './anatomy-sites'

describe('human reference surface mapping', () => {
  it('maps catalog joint anchors to the correct side and existing backend region', () => {
    const shoulder = humanSelection({ x: -0.165, y: 1.394, z: 0.035 }, 'skin', { x: -0.165, y: 0.535, z: 0.035 })
    expect(shoulder).toMatchObject({ siteId: 'right_shoulder', regionId: 'upper_arm', laterality: 'right', modelId: HUMAN_MODEL_ID, modelVersion: '1.0.0', meshId: 'skin' })
    expect(humanSiteAt({ x: 0.211, y: 1.124, z: 0.02 })).toBe('left_elbow')
  })

  it('sends model version as text with a mesh attachment and restores only exact compatible markers', () => {
    const selection = humanSelection({ x: -0.165, y: 1.394, z: 0.035 }, 'skin', { x: -0.192, y: 0.622, z: 0.041 }, { triangleIndex: 1204, barycentric: [0.2, 0.3, 0.5] })
    const request = surfacePoint(selection)!
    expect(request).toMatchObject({ model_id: HUMAN_MODEL_ID, model_version: HUMAN_MODEL_VERSION, site_id: 'right_shoulder', mesh_id: 'skin', mesh_local_point: selection.meshLocalPoint, attachment: { triangle_index: 1204, barycentric: [0.2, 0.3, 0.5] } })
    expect(symptomNote(selection, 'Sore when reaching')).toBe('Sore when reaching')
    const output = { ...request, model_version: '1.0.0', site_label: 'Right shoulder', mesh_validation: 'validated' as const, marker_status: 'current' as const, render_hint: 'exact_point' as const }
    expect(reportedSurfaceSelection({ region_id: 'upper_arm', laterality: 'right', note: null, surface_point: output })).toMatchObject({ point: selection.point, meshLocalPoint: selection.meshLocalPoint, attachment: selection.attachment })
    expect(reportedSurfaceSelection({ region_id: 'upper_arm', laterality: 'right', note: null, surface_point: { ...output, render_hint: 'site_only' } })?.point).toBeUndefined()
  })

  it('keeps torso, head, leg and foot areas distinct', () => {
    expect(humanSiteAt({ x: -0.08, y: 1.64, z: 0.04 })).toBe('head')
    expect(humanSiteAt({ x: 0.08, y: 1.26, z: 0.12 })).toBe('left_chest')
    expect(humanSiteAt({ x: -0.08, y: 1.26, z: -0.11 })).toBe('right_upper_back')
    expect(humanSiteAt({ x: 0.1, y: 0.66, z: 0.04 })).toBe('left_upper_leg')
    expect(humanSiteAt({ x: -0.09, y: 0.03, z: 0.09 })).toBe('right_foot')
  })
})

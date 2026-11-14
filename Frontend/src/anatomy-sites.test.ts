import { describe, expect, it } from 'vitest'
import { reportedSurfaceSelection, savedSurfaceSelection, selectAnatomySite, surfacePoint, symptomNote } from './anatomy-sites'

describe('3D surface report compatibility', () => {
  it('sends a shoulder point separately from the user note and restores the structured response', () => {
    const selection = selectAnatomySite('left_shoulder', { x: 0.5124, y: 0.8362, z: 0.1448 })
    expect(selection).toMatchObject({ regionId: 'upper_arm', laterality: 'left', label: 'Left shoulder' })
    expect(surfacePoint(selection)).toEqual({ model_id: 'sentinel-body-v1', site_id: 'left_shoulder', x: 0.5124, y: 0.8362, z: 0.1448 })
    expect(symptomNote(selection, ' Pain when moving arm ')).toBe('Pain when moving arm')
    expect(reportedSurfaceSelection({ region_id: 'upper_arm', laterality: 'left', note: 'Pain when moving arm', surface_point: { ...surfacePoint(selection)!, site_label: 'Left shoulder' } })).toEqual(selection)
  })

  it('reads historical note points and rejects arbitrary notes', () => {
    const legacy = 'Selected surface area: Left shoulder. Backend region: upper arm. Diagram point (model v1): x=0.512, y=0.836, z=0.145.\nPain when moving arm'
    expect(reportedSurfaceSelection({ region_id: 'upper_arm', laterality: 'left', note: legacy, surface_point: null })).toMatchObject({ siteId: 'left_shoulder', point: { x: 0.512, y: 0.836, z: 0.145 } })
    expect(savedSurfaceSelection(legacy)).not.toBeNull()
    expect(savedSurfaceSelection('left shoulder, unknown source')).toBeNull()
    expect(selectAnatomySite('unknown')).toBeNull()
  })

  it('keeps a named-only area in the note without inventing a point', () => {
    const selection = selectAnatomySite('right_elbow')
    expect(surfacePoint(selection)).toBeUndefined()
    expect(symptomNote(selection, 'Ache')).toBe('Selected surface area: Right elbow. Backend region: upper arm.\nAche')
  })
})

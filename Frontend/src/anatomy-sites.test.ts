import { describe, expect, it } from 'vitest'
import { savedSurfaceSelection, selectAnatomySite, symptomNote } from './anatomy-sites'

describe('3D surface report compatibility', () => {
  it('records a shoulder point under a supported API region and restores the point from the note', () => {
    const selection = selectAnatomySite('left_shoulder', { x: 0.5124, y: 0.8362, z: 0.1448 })
    expect(selection).toMatchObject({ regionId: 'upper_arm', laterality: 'left', label: 'Left shoulder' })
    const note = symptomNote(selection, 'Pain when moving arm')
    expect(note).toContain('Backend region: upper arm.')
    expect(note).toContain('Pain when moving arm')
    expect(savedSurfaceSelection(note ?? '')).toMatchObject({ siteId: 'left_shoulder', point: { x: 0.512, y: 0.836, z: 0.145 } })
  })

  it('does not treat arbitrary notes as diagram coordinates', () => {
    expect(savedSurfaceSelection('left shoulder, unknown source')).toBeNull()
    expect(selectAnatomySite('unknown')).toBeNull()
  })
})

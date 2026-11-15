import { describe, expect, it } from 'vitest'
import { mapProjection, routeMatchesMap } from './HabitatMap'
import type { EquipmentRecommendation, HabitatMap } from './api'

const map: HabitatMap = {
  habitat_id: 'HAB-01', name: 'Test habitat', map_version: 'map-1', description: '',
  coordinate_frame: { frame_id: 'D1-LOCAL', origin: 'south-west', x_axis: 'east', y_axis: 'north', units: 'metres' },
  decks: [{ deck_id: 'D1', name: 'Deck 1', bounds: [[0, 0], [11, 9]] }],
  compartments: [{ zone_id: 'crew-quarters', name: 'Crew Quarters', deck_id: 'D1', polygon: [[0, 0], [5, 0], [5, 4], [0, 4]], walkable: true, navigation_reference: [2.5, 2], navigation_node_id: 'NAV-CQ' }],
  passages: [{ passage_id: 'P-1', hatch_id: 'H-1', deck_id: 'D1', from_zone_id: 'crew-quarters', to_zone_id: 'medical', polygon: [[5, 1], [6, 1], [6, 2], [5, 2]], hatch_point: [5.5, 1.5], accessible: true, hatch_state: 'open', note: '' }],
  anchors: [], equipment: [{ equipment_id: 'EQ-BP-01', device_model: 'BP monitor', capability: 'blood_pressure', zone_id: 'medical', readiness: 'verified_ready', point: [8, 2], position_status: 'registered' }],
  route_network: { nodes: [], edges: [] }, note: '',
}
const route: EquipmentRecommendation = {
  equipment_id: 'EQ-BP-01', device_model: 'BP monitor', zone_id: 'medical', readiness: 'verified_ready', route_zone_ids: ['crew-quarters', 'medical'], procedure_id: 'PROC-BP-01', explanation: '', map_version: 'map-1', coordinate_frame_id: 'D1-LOCAL',
  start_reference: { kind: 'zone_navigation_reference', zone_id: 'crew-quarters', node_id: 'NAV-CQ', point: [2.5, 2], note: '' },
  route_hatch_ids: ['H-1'], route_geometry: { frame_id: 'D1-LOCAL', map_version: 'map-1', points: [[2.5, 2], [5.5, 1.5], [8, 2]], node_ids: ['NAV-CQ'], length_m: 5.6, end_equipment_point: [8, 2] },
}

describe('habitat geometry and route safety', () => {
  it('keeps north above south in the SVG view', () => {
    const project = mapProjection(map, 'D1')
    expect(project.point([0, 9])[1]).toBeLessThan(project.point([0, 0])[1])
  })
  it('accepts the registered route and rejects a changed frame, hatch, or endpoint', () => {
    expect(routeMatchesMap(map, route)).toBe(true)
    expect(routeMatchesMap(map, { ...route, coordinate_frame_id: 'OTHER' })).toBe(false)
    expect(routeMatchesMap({ ...map, passages: map.passages.map(p => ({ ...p, accessible: false })) }, route)).toBe(false)
    expect(routeMatchesMap(map, { ...route, route_geometry: { ...route.route_geometry!, end_equipment_point: [7, 2] } })).toBe(false)
    expect(routeMatchesMap({ ...map, state_version: 3 }, { ...route, status: 'active', habitat_state_version: 2 })).toBe(false)
    expect(routeMatchesMap(map, { ...route, status: 'invalidated' })).toBe(false)
  })
})

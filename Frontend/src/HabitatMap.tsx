import { useRef, useState, type PointerEvent } from 'react'
import type { EquipmentRecommendation, HabitatMap as HabitatMapData, LocationLatest, MapPoint } from './api'
import './habitat-map.css'

type Props = { map: HabitatMapData; latest: LocationLatest | null; route: EquipmentRecommendation | null; selectedZone: string; onSelectZone: (zoneId: string) => void }
type View = { zoom: number; panX: number; panY: number }

export function routeMatchesMap(map: HabitatMapData, route: EquipmentRecommendation | null): boolean {
  if (!route?.route_geometry || !route.start_reference || !route.route_hatch_ids) return false
  if (route.map_version !== map.map_version || route.route_geometry.map_version !== map.map_version) return false
  if (route.coordinate_frame_id !== map.coordinate_frame.frame_id || route.route_geometry.frame_id !== map.coordinate_frame.frame_id) return false
  if (!route.route_geometry.points.length || route.start_reference.kind !== 'zone_navigation_reference') return false
  if (route.route_hatch_ids.some(id => !map.passages.some(p => p.hatch_id === id && p.accessible))) return false
  const first = route.route_geometry.points[0], last = route.route_geometry.points.at(-1)
  const start = map.compartments.find(item => item.zone_id === route.start_reference?.zone_id)
  const target = map.equipment.find(item => item.equipment_id === route.equipment_id)
  const samePoint = (a: MapPoint | null | undefined, b: MapPoint | null | undefined) => !!a && !!b && Math.abs(a[0] - b[0]) < 0.001 && Math.abs(a[1] - b[1]) < 0.001
  return !!start && start.navigation_node_id === route.start_reference.node_id && samePoint(start.navigation_reference, route.start_reference.point) && samePoint(first, route.start_reference.point) && !!target && samePoint(target.point, route.route_geometry.end_equipment_point) && samePoint(last, target.point)
}

export function mapProjection(map: HabitatMapData, deckId: string) {
  const bounds = map.decks.find(deck => deck.deck_id === deckId)?.bounds ?? map.decks[0]?.bounds ?? [[0, 0], [11, 9]]
  const [[minX, minY], [maxX, maxY]] = bounds
  const scale = Math.min(760 / Math.max(1, maxX - minX), 580 / Math.max(1, maxY - minY))
  const x0 = 70 + (760 - (maxX - minX) * scale) / 2
  const y0 = 630 - (580 - (maxY - minY) * scale) / 2
  const point = ([x, y]: MapPoint): MapPoint => [x0 + (x - minX) * scale, y0 - (y - minY) * scale]
  const polygon = (points: MapPoint[]) => points.map((p, i) => `${i ? 'L' : 'M'} ${point(p)[0]} ${point(p)[1]}`).join(' ') + ' Z'
  return { point, polygon, scale, bounds }
}

export function HabitatMap({ map, latest, route, selectedZone, onSelectZone }: Props) {
  const [deckId, setDeckId] = useState(map.decks[0]?.deck_id ?? '')
  const [view, setView] = useState<View>({ zoom: 1, panX: 0, panY: 0 })
  const [selectedEquipment, setSelectedEquipment] = useState<string | null>(null)
  const drag = useRef<{ x: number; y: number; panX: number; panY: number; moved: boolean } | null>(null)
  const svg = useRef<SVGSVGElement>(null)
  const { point, polygon, bounds } = mapProjection(map, deckId)
  const [[minX, minY], [maxX, maxY]] = bounds
  const [left, top] = point([minX, maxY]), [right, bottom] = point([maxX, minY])
  const validRoute = routeMatchesMap(map, route) && latest?.display_mode === 'zone_only' && latest.estimate?.zone_id === route?.start_reference?.zone_id
  const routePoints = validRoute ? route!.route_geometry!.points.map(p => point(p).join(',')).join(' ') : ''
  const locatedZone = latest?.estimate?.zone_id
  const locationCurrent = latest?.display_mode === 'zone_only' && latest.estimate?.map_version === map.map_version
  const locationStale = latest?.display_mode === 'stale' && latest.estimate?.map_version === map.map_version
  const showPoint = latest?.display_mode === 'estimated_xy' && latest.estimate?.position && latest.estimate.map_version === map.map_version
  const zone = map.compartments.find(item => item.zone_id === selectedZone)
  const equipment = map.equipment.find(item => item.equipment_id === selectedEquipment)
  const zoom = (factor: number) => setView(current => ({ ...current, zoom: Math.max(1, Math.min(3, current.zoom * factor)) }))
  const pan = (x: number, y: number) => setView(current => ({ ...current, panX: current.panX + x, panY: current.panY + y }))
  const viewW = 900 / view.zoom, viewH = 680 / view.zoom
  const viewBox = `${(900 - viewW) / 2 + view.panX} ${(680 - viewH) / 2 + view.panY} ${viewW} ${viewH}`
  function pointerDown(event: PointerEvent<SVGSVGElement>) {
    if (event.button !== 0) return
    drag.current = { x: event.clientX, y: event.clientY, panX: view.panX, panY: view.panY, moved: false }
  }
  function pointerMove(event: PointerEvent<SVGSVGElement>) {
    if (!drag.current || !svg.current) return
    const dx = event.clientX - drag.current.x, dy = event.clientY - drag.current.y
    if (!drag.current.moved && Math.abs(dx) + Math.abs(dy) > 4) { drag.current.moved = true; event.currentTarget.setPointerCapture(event.pointerId) }
    if (drag.current.moved) setView(current => ({ ...current, panX: drag.current!.panX - dx * viewW / svg.current!.clientWidth, panY: drag.current!.panY - dy * viewH / svg.current!.clientHeight }))
  }
  function pointerUp() { window.setTimeout(() => { drag.current = null }, 0) }
  return <section className="card habitat-map-card" aria-label="Habitat floor plan">
    <div className="habitat-map-head"><div><p className="eyebrow">AUTHORITATIVE HABITAT GEOMETRY</p><h2>{map.name}</h2><p className="muted small">{map.map_version} · {map.coordinate_frame.frame_id} · {map.coordinate_frame.units} · {map.coordinate_frame.origin}</p></div><label className="form-label">Deck<select value={deckId} onChange={event => { setDeckId(event.target.value); setView({ zoom: 1, panX: 0, panY: 0 }) }}>{map.decks.map(deck => <option value={deck.deck_id} key={deck.deck_id}>{deck.name}</option>)}</select></label></div>
    <div className="habitat-map-controls"><button type="button" onClick={() => zoom(1.25)} aria-label="Zoom in on map">+</button><button type="button" onClick={() => zoom(0.8)} aria-label="Zoom out of map">−</button><button type="button" onClick={() => setView({ zoom: 1, panX: 0, panY: 0 })}>Reset view</button><button type="button" onClick={() => pan(-55, 0)} aria-label="Pan map left">←</button><button type="button" onClick={() => pan(55, 0)} aria-label="Pan map right">→</button><button type="button" onClick={() => pan(0, -55)} aria-label="Pan map up">↑</button><button type="button" onClick={() => pan(0, 55)} aria-label="Pan map down">↓</button></div>
    <svg ref={svg} className="habitat-floor" viewBox={viewBox} role="group" aria-label={`Deck ${deckId} floor plan; select a compartment or equipment marker`} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onWheel={event => { event.preventDefault(); zoom(event.deltaY < 0 ? 1.1 : 0.9) }}>
      <rect x="0" y="0" width="900" height="680" fill="#102639" />
      <rect x={left - 12} y={top - 12} width={right - left + 24} height={bottom - top + 24} rx="20" fill="#142e42" stroke="#668ba1" strokeWidth="3" />
      {map.passages.filter(item => item.deck_id === deckId).map(item => <g key={item.passage_id}><path d={polygon(item.polygon)} fill={item.accessible ? '#315f65' : '#64414b'} stroke={item.accessible ? '#85d9c0' : '#ef8e80'} strokeWidth="3" /><circle cx={point(item.hatch_point)[0]} cy={point(item.hatch_point)[1]} r="12" fill={item.accessible ? '#76dcb9' : '#ee8b79'} /><text x={point(item.hatch_point)[0]} y={point(item.hatch_point)[1] + 5} textAnchor="middle" fill="#102639" fontSize="16" fontWeight="900">{item.accessible ? '✓' : '×'}</text></g>)}
      {map.compartments.filter(item => item.deck_id === deckId).map(item => <g key={item.zone_id} role="button" tabIndex={0} aria-label={`Select ${item.name}`} onClick={() => { if (!drag.current?.moved) onSelectZone(item.zone_id) }} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelectZone(item.zone_id) } }} className="habitat-room">
        <path d={polygon(item.polygon)} fill={item.zone_id === locatedZone && locationCurrent ? '#315d70' : item.zone_id === locatedZone && locationStale ? '#454d60' : item.zone_id === selectedZone ? '#254f62' : '#1f4054'} stroke={item.zone_id === selectedZone ? '#f2c477' : '#6b9caf'} strokeWidth={item.zone_id === selectedZone ? 5 : 3} />
        <text x={point(item.navigation_reference)[0]} y={point(item.navigation_reference)[1] - 8} textAnchor="middle" fill="#ecf6f6" fontSize="21" fontWeight="800" pointerEvents="none">{item.name}</text>
        {(item.zone_id === locatedZone && (locationCurrent || locationStale)) && <text x={point(item.navigation_reference)[0]} y={point(item.navigation_reference)[1] + (route?.start_reference?.zone_id === item.zone_id && validRoute ? 70 : 23)} textAnchor="middle" fill={locationCurrent ? '#75d9df' : '#ffc27b'} fontSize="15" fontWeight="800" pointerEvents="none">{locationCurrent ? 'CREW ZONE · NO EXACT POINT' : 'LAST-KNOWN ZONE'}</text>}
      </g>)}
      {routePoints && <g><polyline points={routePoints} fill="none" stroke="#f5c875" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="18 8" pointerEvents="none" /><rect x={point(route!.start_reference!.point)[0] - 11} y={point(route!.start_reference!.point)[1] - 11} width="22" height="22" rx="3" fill="#f5c875" stroke="#102639" strokeWidth="3" /><text x={point(route!.start_reference!.point)[0]} y={point(route!.start_reference!.point)[1] + 37} textAnchor="middle" fill="#f5d89c" fontSize="13" fontWeight="800">ZONE ROUTE START</text></g>}
      {map.anchors.filter(item => map.compartments.some(room => room.zone_id === item.zone_id && room.deck_id === deckId)).map(item => <g key={item.anchor_id} className="habitat-anchor"><path d={`M ${point(item.point)[0]} ${point(item.point)[1] - 9} l 9 9 -9 9 -9 -9 Z`} fill={item.enabled ? '#9da4f2' : '#647281'} stroke="#e1e8fd" strokeWidth="2" /><title>{`${item.anchor_id} · ${item.enabled ? 'enabled' : 'disabled'}`}</title></g>)}
      {map.equipment.filter(item => item.point && map.compartments.some(room => room.zone_id === item.zone_id && room.deck_id === deckId)).map(item => <g key={item.equipment_id} role="button" tabIndex={0} aria-label={`Inspect ${item.equipment_id}, ${item.readiness}`} onClick={() => { if (!drag.current?.moved) setSelectedEquipment(item.equipment_id) }} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelectedEquipment(item.equipment_id) } }} className="habitat-equipment"><circle cx={point(item.point!)[0]} cy={point(item.point!)[1]} r={item.equipment_id === selectedEquipment || item.equipment_id === route?.equipment_id ? 18 : 14} fill={item.readiness === 'verified_ready' ? '#72d9c5' : '#e7aa76'} stroke="#092c3d" strokeWidth="4" /><text x={point(item.point!)[0]} y={point(item.point!)[1] + 5} textAnchor="middle" fill="#0a3340" fontSize="13" fontWeight="900">EQ</text><title>{`${item.equipment_id} · ${item.device_model} · ${item.readiness}`}</title></g>)}
      {showPoint && <circle cx={point(latest!.estimate!.position!)[0]} cy={point(latest!.estimate!.position!)[1]} r="9" fill="#f4d279" stroke="#102639" strokeWidth="3" />}
      <text x="755" y="655" fill="#a8c8d3" fontSize="16">N ↑</text>
    </svg>
    <div className="habitat-map-legend"><span><i className="legend-open" />Open passage</span><span><i className="legend-closed" />Closed hatch</span><span><i className="legend-equipment" />Equipment</span><span><i className="legend-anchor" />Wireless anchor</span><span><i className="legend-route" />Backend route</span></div>
    <p className="muted small">Drag or use arrow buttons to pan; scroll or use +/− to zoom. Room highlights indicate a zone, never a precise crew position. Responder location is unavailable.</p>
    {zone && <p className="status info">Selected compartment: {zone.name}. This selection can be confirmed as the astronaut's zone.</p>}
    {equipment && <p className="status info">{equipment.equipment_id} · {equipment.device_model} · {equipment.readiness} · {equipment.position_status.replaceAll('_', ' ')}</p>}
    {route && !validRoute && <p className="status error">The saved route does not match the current location, map frame, version, open hatches or registered equipment position. Request a new route.</p>}
    {route && validRoute && <p className="status info">Route begins at the {route.start_reference!.zone_id} navigation reference, not the person's position. {route.route_geometry!.length_m} m through {route.route_hatch_ids!.join(' → ') || 'no hatches'}.</p>}
  </section>
}

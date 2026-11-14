import type { BodySelection } from './BodyMap'
import type { SurfacePoint, SymptomOut } from './api'

export const HUMAN_MODEL_ID = 'sentinel-human-male-v1'
export const HUMAN_MODEL_VERSION = '1.0.0'

export type AnatomySite = { id: string; label: string; regionId: string; laterality: 'left' | 'right' | 'midline'; detailed?: boolean }

const centered: AnatomySite[] = [
  { id: 'head', label: 'Head', regionId: 'head', laterality: 'midline' },
  { id: 'neck', label: 'Neck', regionId: 'neck', laterality: 'midline' },
  { id: 'pelvis', label: 'Pelvis', regionId: 'abdomen', laterality: 'midline', detailed: true },
]

const paired = (side: 'left' | 'right'): AnatomySite[] => [
  { id: `${side}_eye`, label: `${side} eye`, regionId: 'eyes', laterality: side },
  { id: `${side}_chest`, label: `${side} chest`, regionId: 'chest', laterality: side },
  { id: `${side}_upper_back`, label: `${side} upper back`, regionId: 'upper_back', laterality: side },
  { id: `${side}_abdomen`, label: `${side} abdomen`, regionId: 'abdomen', laterality: side },
  { id: `${side}_lower_back`, label: `${side} lower back`, regionId: 'lower_back', laterality: side },
  { id: `${side}_shoulder`, label: `${side} shoulder`, regionId: 'upper_arm', laterality: side, detailed: true },
  { id: `${side}_upper_arm`, label: `${side} upper arm`, regionId: 'upper_arm', laterality: side },
  { id: `${side}_elbow`, label: `${side} elbow`, regionId: 'upper_arm', laterality: side, detailed: true },
  { id: `${side}_forearm`, label: `${side} forearm`, regionId: 'forearm_hand', laterality: side, detailed: true },
  { id: `${side}_wrist`, label: `${side} wrist`, regionId: 'forearm_hand', laterality: side, detailed: true },
  { id: `${side}_hand`, label: `${side} hand`, regionId: 'forearm_hand', laterality: side, detailed: true },
  { id: `${side}_upper_leg`, label: `${side} upper leg`, regionId: 'upper_leg', laterality: side },
  { id: `${side}_knee`, label: `${side} knee`, regionId: 'lower_leg_foot', laterality: side, detailed: true },
  { id: `${side}_lower_leg`, label: `${side} lower leg`, regionId: 'lower_leg_foot', laterality: side, detailed: true },
  { id: `${side}_ankle`, label: `${side} ankle`, regionId: 'lower_leg_foot', laterality: side, detailed: true },
  { id: `${side}_foot`, label: `${side} foot`, regionId: 'lower_leg_foot', laterality: side, detailed: true },
]

export const ANATOMY_SITES = [...centered, ...paired('right'), ...paired('left')]
export const ANATOMY_SITE_BY_ID = new Map(ANATOMY_SITES.map(site => [site.id, site]))

export function selectAnatomySite(id: string, point?: { x: number; y: number; z: number }): BodySelection | null {
  const site = ANATOMY_SITE_BY_ID.get(id)
  if (!site) return null
  return { regionId: site.regionId, laterality: site.laterality, label: site.label.replace(/^\w/, letter => letter.toUpperCase()), siteId: id, point }
}

export function surfaceDetail(selection: BodySelection | null): string {
  if (!selection) return ''
  const site = selection.siteId ? ANATOMY_SITE_BY_ID.get(selection.siteId) : null
  const point = selection.point
  if (!point && !site?.detailed) return ''
  if (selection.modelId === HUMAN_MODEL_ID) return `Selected reference surface: ${selection.label}. ${selection.point ? 'The exact mesh point will be sent with this report.' : 'A named area was chosen without an exact mesh point.'}`
  const coordinates = point ? ` Diagram point (model v1): x=${point.x.toFixed(3)}, y=${point.y.toFixed(3)}, z=${point.z.toFixed(3)}.` : ''
  return `Selected surface area: ${selection.label}. Backend region: ${selection.regionId.replaceAll('_', ' ')}.${coordinates}`
}

export function surfacePoint(selection: BodySelection | null): SurfacePoint | undefined {
  if (!selection?.siteId || !selection.point || !ANATOMY_SITE_BY_ID.has(selection.siteId)) return undefined
  const { x, y, z } = selection.point
  if (![x, y, z].every(value => Number.isFinite(value) && Math.abs(value) <= 5)) return undefined
  if (selection.modelId === HUMAN_MODEL_ID) {
    const local = selection.meshLocalPoint
    if (selection.modelVersion !== HUMAN_MODEL_VERSION || selection.meshId !== 'skin' || !local || ![local.x, local.y, local.z].every(Number.isFinite)) return undefined
    return { model_id: HUMAN_MODEL_ID, model_version: HUMAN_MODEL_VERSION, site_id: selection.siteId, x, y, z, mesh_id: 'skin', mesh_local_point: local,
      ...(selection.attachment ? { attachment: { triangle_index: selection.attachment.triangleIndex, barycentric: selection.attachment.barycentric } } : {}) }
  }
  if (selection.modelId && selection.modelId !== 'sentinel-body-v1') return undefined
  return { model_id: 'sentinel-body-v1', site_id: selection.siteId, x, y, z }
}

export function symptomNote(selection: BodySelection | null, userNote: string): string | undefined {
  // Named-list selections have no exact point, so preserve only their site label in the note.
  const detail = selection?.modelId === HUMAN_MODEL_ID ? selection.point ? '' : `Selected reference area: ${selection.label}. No exact mesh point was chosen.` : selection?.point ? '' : surfaceDetail(selection)
  const note = userNote.trim()
  const combined = [detail, note].filter(Boolean).join('\n')
  return combined ? combined.slice(0, 1000) : undefined
}

/** Reads only points written by this frontend's versioned diagram-note format. */
export function savedSurfaceSelection(note: string | null): BodySelection | null {
  if (!note) return null
  const match = /^Selected surface area: (.+?)\. Backend region: [^.]+\. Diagram point \(model v1\): x=(-?\d+\.\d{3}), y=(-?\d+\.\d{3}), z=(-?\d+\.\d{3})\./.exec(note)
  if (!match) return null
  const site = ANATOMY_SITES.find(candidate => candidate.label.toLowerCase() === match[1].toLowerCase())
  const [x, y, z] = match.slice(2).map(Number)
  if (!site || ![x, y, z].every(value => Number.isFinite(value) && Math.abs(value) < 5)) return null
  return selectAnatomySite(site.id, { x, y, z })
}

export function reportedSurfaceSelection(symptom: Pick<SymptomOut, 'region_id' | 'laterality' | 'note' | 'surface_point'>): BodySelection | null {
  const point = symptom.surface_point
  if (point?.model_id === HUMAN_MODEL_ID) {
    const exact = point.render_hint === 'exact_point' && point.model_version === HUMAN_MODEL_VERSION && point.mesh_id === 'skin' && point.mesh_local_point
    const selection = selectAnatomySite(point.site_id, exact ? { x: point.x, y: point.y, z: point.z } : undefined)
    if (selection && selection.regionId === symptom.region_id && selection.laterality === symptom.laterality)
      return { ...selection, modelId: HUMAN_MODEL_ID, modelVersion: point.model_version, meshId: point.mesh_id ?? undefined, meshLocalPoint: exact ? point.mesh_local_point ?? undefined : undefined,
        attachment: exact && point.attachment ? { triangleIndex: point.attachment.triangle_index, barycentric: point.attachment.barycentric } : undefined,
        renderHint: point.render_hint, markerStatus: point.marker_status }
    return null
  }
  if (point?.model_id === 'sentinel-body-v1') {
    const selection = selectAnatomySite(point.site_id, point.render_hint === 'site_only' || point.render_hint === 'not_renderable' ? undefined : { x: point.x, y: point.y, z: point.z })
    if (selection && selection.regionId === symptom.region_id && selection.laterality === symptom.laterality) return { ...selection, modelId: 'sentinel-body-v1', modelVersion: point.model_version, renderHint: point.render_hint, markerStatus: point.marker_status }
    return null
  }
  if (point) return null
  return savedSurfaceSelection(symptom.note)
}

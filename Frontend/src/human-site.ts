import { ANATOMY_BY_KEY, jointAnchor } from 'open-anatomy-3d'
import { HUMAN_MODEL_ID, HUMAN_MODEL_VERSION, selectAnatomySite } from './anatomy-sites'
import type { BodySelection } from './BodyMap'

export { HUMAN_MODEL_ID, HUMAN_MODEL_VERSION } from './anatomy-sites'
export type ModelPoint = { x: number; y: number; z: number }

const jointRadius: Record<string, number> = { shoulder: 0.115, elbow: 0.095, wrist: 0.075, knee: 0.095, ankle: 0.075 }

/** Educational surface zones on the locally bundled male reference mesh. */
export function humanSiteAt(point: ModelPoint): string {
  const side = point.x < 0 ? 'right' : 'left'
  const x = Math.abs(point.x)
  const front = point.z >= 0
  if (point.y >= 1.51) {
    if (front && point.y < 1.68 && point.z > 0.065 && x < 0.085) return `${side}_eye`
    return 'head'
  }
  if (point.y >= 1.39 && x < 0.11) return 'neck'
  for (const joint of Object.keys(jointRadius)) {
    const structure = ANATOMY_BY_KEY[`${joint}_${side === 'right' ? 'r' : 'l'}`]
    const anchor = structure && jointAnchor(structure, 'male')
    if (anchor && Math.hypot(point.x - anchor[0], point.y - anchor[1], point.z - anchor[2]) <= jointRadius[joint]) return `${side}_${joint}`
  }
  if (point.y >= 0.87 && x >= 0.17) {
    if (point.y >= 1.22) return `${side}_upper_arm`
    if (point.y >= 0.91) return `${side}_forearm`
    return `${side}_hand`
  }
  if (point.y >= 1.13) return `${side}_${front ? 'chest' : 'upper_back'}`
  if (point.y >= 0.94) return `${side}_${front ? 'abdomen' : 'lower_back'}`
  if (point.y >= 0.84 && x < 0.16) return 'pelvis'
  if (point.y >= 0.51) return `${side}_upper_leg`
  if (point.y >= 0.13) return `${side}_lower_leg`
  if (point.y >= 0.09) return `${side}_ankle`
  return `${side}_foot`
}

export function humanSelection(point: ModelPoint, meshId: string, meshLocalPoint: ModelPoint, attachment?: BodySelection['attachment']): BodySelection {
  const site = selectAnatomySite(humanSiteAt(point))
  if (!site) throw new Error('Human anatomy point mapped to an unknown site')
  return { ...site, point, modelId: HUMAN_MODEL_ID, modelVersion: HUMAN_MODEL_VERSION, meshId, meshLocalPoint, attachment }
}

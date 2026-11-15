import type { ProcedureStep } from './api'

export const PROCEDURE_ASSETS = {
  'ASSET-BP-MONITOR-A1': '3D monitor with start control and simulated display',
  'ASSET-BP-CUFF-ADULT-STD': '3D adult upper-arm cuff with artery marker and wrap segments',
  'ASSET-CREW-RESTRAINT': '3D torso restraint and arm support reference',
  'ASSET-HUMAN-UPPER-ARM-L': 'Left upper arm of the anatomical reference model',
} as const

export const VISUAL_ACTIONS = {
  'VA-BP-01-PREPARE-EQUIPMENT': { scene: 'prepare', assets: ['ASSET-BP-MONITOR-A1', 'ASSET-BP-CUFF-ADULT-STD', 'ASSET-CREW-RESTRAINT'] },
  'VA-BP-02-EXPOSE-UPPER-ARM': { scene: 'expose', assets: ['ASSET-HUMAN-UPPER-ARM-L'] },
  'VA-BP-03-WRAP-CUFF': { scene: 'wrap', assets: ['ASSET-BP-CUFF-ADULT-STD', 'ASSET-HUMAN-UPPER-ARM-L'] },
  'VA-BP-04-SUPPORT-ARM': { scene: 'support', assets: ['ASSET-CREW-RESTRAINT', 'ASSET-HUMAN-UPPER-ARM-L', 'ASSET-BP-CUFF-ADULT-STD'] },
  'VA-BP-05-START-MEASUREMENT': { scene: 'measure', assets: ['ASSET-BP-MONITOR-A1', 'ASSET-BP-CUFF-ADULT-STD'] },
  'VA-BP-06-RECORD-RESULT': { scene: 'record', assets: ['ASSET-BP-MONITOR-A1', 'ASSET-BP-CUFF-ADULT-STD'] },
} as const

export type VisualScene = typeof VISUAL_ACTIONS[keyof typeof VISUAL_ACTIONS]['scene']

/** A backend action is available only when this frontend has its exact scene and every named asset. */
export function visualFor(step: ProcedureStep): VisualScene | null {
  const visual = step.visual
  const entry = VISUAL_ACTIONS[visual.action_id as keyof typeof VISUAL_ACTIONS]
  if (!entry || !visual.replay_allowed || !visual.pause_allowed) return null
  const requested = [visual.asset_id, ...visual.additional_asset_ids]
  if (entry.assets.length !== requested.length || entry.assets.some((id, index) => id !== requested[index])) return null
  if (requested.some(id => !(id in PROCEDURE_ASSETS))) return null
  return entry.scene
}

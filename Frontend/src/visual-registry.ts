import type { ProcedureStep } from './api'

export const PROCEDURE_ASSETS = {
  'ASSET-BP-MONITOR-A1': '3D monitor with start control and simulated display',
  'ASSET-BP-CUFF-ADULT-STD': '3D adult upper-arm cuff with artery marker and wrap segments',
  'ASSET-CREW-RESTRAINT': '3D torso restraint and arm support reference',
  'ASSET-HUMAN-UPPER-ARM-L': 'Left upper arm of the anatomical reference model',
  'ASSET-PULSE-OXIMETER-P1': '3D fingertip pulse oximeter with probe hinge and simulated display',
  'ASSET-IR-THERMOMETER-T1': '3D non-contact infrared forehead thermometer with simulated display',
} as const

export const VISUAL_ACTIONS = {
  'VA-BP-01-PREPARE-EQUIPMENT': { scene: 'prepare', assets: ['ASSET-BP-MONITOR-A1', 'ASSET-BP-CUFF-ADULT-STD', 'ASSET-CREW-RESTRAINT'] },
  'VA-BP-02-EXPOSE-UPPER-ARM': { scene: 'expose', assets: ['ASSET-HUMAN-UPPER-ARM-L'] },
  'VA-BP-03-WRAP-CUFF': { scene: 'wrap', assets: ['ASSET-BP-CUFF-ADULT-STD', 'ASSET-HUMAN-UPPER-ARM-L'] },
  'VA-BP-04-SUPPORT-ARM': { scene: 'support', assets: ['ASSET-CREW-RESTRAINT', 'ASSET-HUMAN-UPPER-ARM-L', 'ASSET-BP-CUFF-ADULT-STD'] },
  'VA-BP-05-START-MEASUREMENT': { scene: 'measure', assets: ['ASSET-BP-MONITOR-A1', 'ASSET-BP-CUFF-ADULT-STD'] },
  'VA-BP-06-RECORD-RESULT': { scene: 'record', assets: ['ASSET-BP-MONITOR-A1', 'ASSET-BP-CUFF-ADULT-STD'] },
  'VA-PO-01-PREPARE-DEVICE': { scene: 'po-prepare', assets: ['ASSET-PULSE-OXIMETER-P1', 'ASSET-CREW-RESTRAINT'] },
  'VA-PO-02-PREPARE-FINGER': { scene: 'po-finger', assets: ['ASSET-PULSE-OXIMETER-P1'] },
  'VA-PO-03-PLACE-PROBE': { scene: 'po-place', assets: ['ASSET-PULSE-OXIMETER-P1'] },
  'VA-PO-04-HOLD-STILL': { scene: 'po-hold', assets: ['ASSET-PULSE-OXIMETER-P1', 'ASSET-CREW-RESTRAINT'] },
  'VA-PO-05-RECORD-RESULT': { scene: 'po-record', assets: ['ASSET-PULSE-OXIMETER-P1'] },
  'VA-TEMP-01-PREPARE-DEVICE': { scene: 'temp-prepare', assets: ['ASSET-IR-THERMOMETER-T1'] },
  'VA-TEMP-02-PREPARE-FOREHEAD': { scene: 'temp-forehead', assets: ['ASSET-IR-THERMOMETER-T1', 'ASSET-CREW-RESTRAINT'] },
  'VA-TEMP-03-AIM': { scene: 'temp-aim', assets: ['ASSET-IR-THERMOMETER-T1'] },
  'VA-TEMP-04-MEASURE': { scene: 'temp-measure', assets: ['ASSET-IR-THERMOMETER-T1'] },
  'VA-TEMP-05-RECORD-RESULT': { scene: 'temp-record', assets: ['ASSET-IR-THERMOMETER-T1'] },
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

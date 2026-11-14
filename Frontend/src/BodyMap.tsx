import { useState } from 'react'

export type BodySelection = { regionId: string; laterality: 'left' | 'right' | 'midline'; label: string }
type Region = BodySelection & { x: number; y: number; w: number; h: number }

const FRONT: Region[] = [
  { regionId: 'head', laterality: 'midline', label: 'Head', x: 88, y: 16, w: 44, h: 43 },
  { regionId: 'eyes', laterality: 'right', label: 'Right eye', x: 93, y: 31, w: 13, h: 10 },
  { regionId: 'eyes', laterality: 'left', label: 'Left eye', x: 114, y: 31, w: 13, h: 10 },
  { regionId: 'chest', laterality: 'right', label: 'Right chest', x: 73, y: 74, w: 34, h: 48 },
  { regionId: 'chest', laterality: 'left', label: 'Left chest', x: 113, y: 74, w: 34, h: 48 },
  { regionId: 'abdomen', laterality: 'right', label: 'Right abdomen', x: 77, y: 127, w: 30, h: 53 },
  { regionId: 'abdomen', laterality: 'left', label: 'Left abdomen', x: 113, y: 127, w: 30, h: 53 },
  { regionId: 'upper_arm', laterality: 'right', label: 'Right upper arm', x: 43, y: 78, w: 25, h: 60 },
  { regionId: 'upper_arm', laterality: 'left', label: 'Left upper arm', x: 152, y: 78, w: 25, h: 60 },
  { regionId: 'forearm_hand', laterality: 'right', label: 'Right forearm and hand', x: 43, y: 142, w: 25, h: 55 },
  { regionId: 'forearm_hand', laterality: 'left', label: 'Left forearm and hand', x: 152, y: 142, w: 25, h: 55 },
  { regionId: 'upper_leg', laterality: 'right', label: 'Right upper leg', x: 79, y: 191, w: 28, h: 65 },
  { regionId: 'upper_leg', laterality: 'left', label: 'Left upper leg', x: 113, y: 191, w: 28, h: 65 },
  { regionId: 'lower_leg_foot', laterality: 'right', label: 'Right lower leg and foot', x: 79, y: 259, w: 28, h: 75 },
  { regionId: 'lower_leg_foot', laterality: 'left', label: 'Left lower leg and foot', x: 113, y: 259, w: 28, h: 75 },
]
const BACK: Region[] = FRONT.filter(region => region.regionId !== 'eyes').map(region => ({ ...region, regionId: region.regionId === 'chest' ? 'upper_back' : region.regionId === 'abdomen' ? 'lower_back' : region.regionId, label: region.label.replace('chest', 'upper back').replace('abdomen', 'lower back') }))

export function BodyMap({ value, onChange }: { value: BodySelection | null; onChange: (selection: BodySelection) => void }) {
  const [side, setSide] = useState<'front' | 'back'>('front')
  const regions = side === 'front' ? FRONT : BACK
  return <div className="body-panel">
    <div className="segmented" aria-label="Body view">
      <button type="button" aria-pressed={side === 'front'} onClick={() => setSide('front')}>Front</button>
      <button type="button" aria-pressed={side === 'back'} onClick={() => setSide('back')}>Back</button>
    </div>
    <div className="body-map-wrap">
      <svg className="body-map" viewBox="0 0 220 355" role="img" aria-label={`${side} body regions; select a labelled area`}>
        <path className="body-outline" d="M95 12 Q110 2 125 12 L134 28 L130 54 L124 65 L132 71 L152 75 L170 89 L180 185 L170 204 L152 202 L147 155 L147 187 L140 200 L143 325 L133 344 L115 344 L110 220 L105 344 L87 344 L77 325 L80 200 L73 187 L73 155 L68 202 L50 204 L40 185 L50 89 L68 75 L88 71 L96 65 L90 54 L86 28 Z" />
        {regions.map(region => {
          const selected = value?.regionId === region.regionId && value.laterality === region.laterality
          return <rect key={`${region.regionId}-${region.laterality}`} x={region.x} y={region.y} width={region.w} height={region.h} rx="11"
            className={`body-region ${selected ? 'selected' : ''}`} role="button" tabIndex={0} aria-label={region.label} aria-pressed={selected}
            onClick={() => onChange(region)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onChange(region) } }} />
        })}
      </svg>
    </div>
    <p className="muted small">Surface regions only. This map does not locate internal organs or provide a diagnosis.</p>
  </div>
}

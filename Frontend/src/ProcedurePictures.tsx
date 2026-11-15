import type { VisualScene } from './visual-registry'
import { AdditionalProcedurePictures } from './AdditionalProcedurePictures'

type Reading = { systolic: string; diastolic: string; pulse: string; spo2?: string; temperature?: string }
type Props = { scene: VisualScene; reading: Reading }

const titles: Partial<Record<VisualScene, string>> = {
  prepare: 'BP monitor and cuff ready; crew member rests quietly',
  expose: 'Bare left upper arm exposed for the cuff',
  wrap: 'Cuff wrapped on the left upper arm above the elbow',
  support: 'Cuffed arm supported near heart level in a restrained posture',
  measure: 'Start button pressed while the cuff measures and deflates',
  record: 'Simulated monitor values copied into matching entry fields',
}

function Monitor({ x, y, mode = 'ready', reading }: { x: number; y: number; mode?: 'ready' | 'measuring' | 'result'; reading?: Reading }) {
  return <g transform={`translate(${x} ${y})`}>
    <rect x="0" y="0" width="235" height="206" rx="20" fill="#071e31" stroke="#77d6df" strokeWidth="4" />
    <rect x="17" y="18" width="201" height="137" rx="8" fill="#e3f4f0" />
    <text x="30" y="45" fill="#16384b" fontSize="15" fontWeight="800">DEMO BP MONITOR A1</text>
    {mode === 'result' ? <>
      <text x="30" y="73" fill="#a24949" fontSize="15" fontWeight="800">SIMULATED</text>
      <text x="30" y="112" fill="#16384b" fontSize="34" fontWeight="800">{reading?.systolic || '118'}/{reading?.diastolic || '76'}</text>
      <text x="30" y="138" fill="#385d6a" fontSize="15">mmHg · pulse {reading?.pulse || '70'} bpm</text>
    </> : mode === 'measuring' ? <>
      <text x="30" y="88" fill="#16384b" fontSize="22" fontWeight="800">MEASURING</text>
      <rect x="30" y="110" width="175" height="13" rx="6" fill="#a9cbd0" />
      <rect x="30" y="110" width="112" height="13" rx="6" fill="#218ba5" />
    </> : <text x="30" y="95" fill="#16384b" fontSize="25" fontWeight="800">READY</text>}
    <circle cx="185" cy="180" r="16" fill="#78d9df" />
    <text x="113" y="185" fill="#d8edf1" fontSize="14" fontWeight="700">START</text>
  </g>
}

function Cuff({ x, y, width = 145, height = 92 }: { x: number; y: number; width?: number; height?: number }) {
  return <g transform={`translate(${x} ${y})`}>
    <rect width={width} height={height} rx="14" fill="#14617a" stroke="#76d8e1" strokeWidth="5" />
    <path d={`M 10 14 H ${width - 10} M 10 ${height - 14} H ${width - 10}`} stroke="#3998aa" strokeWidth="4" />
    <rect x={width * .67} y="14" width="8" height={height - 28} rx="3" fill="#f28a75" />
    <text x="15" y={height / 2 + 5} fill="#e9f8f7" fontSize="17" fontWeight="800">BP CUFF</text>
  </g>
}

function Arm({ x, y, cuff = false, elbowLabel = true }: { x: number; y: number; cuff?: boolean; elbowLabel?: boolean }) {
  return <g transform={`translate(${x} ${y})`}>
    <rect x="28" y="0" width="112" height="310" rx="52" fill="#c9997e" stroke="#edc6ab" strokeWidth="5" />
    <path d="M 42 246 Q 84 261 126 246" fill="none" stroke="#a36d61" strokeWidth="5" />
    {elbowLabel && <text x="156" y="258" fill="#dfebef" fontSize="17">elbow crease</text>}
    {cuff && <Cuff x={13} y={106} width={142} height={100} />}
  </g>
}

function Picture({ scene, reading }: Props) {
  switch (scene) {
    case 'prepare': return <>
      <Monitor x={72} y={128} />
      <circle cx="384" cy="129" r="24" fill="#c9997e" stroke="#edc6ab" strokeWidth="4" />
      <ellipse cx="384" cy="230" rx="52" ry="76" fill="#c9997e" stroke="#edc6ab" strokeWidth="4" />
      <rect x="339" y="202" width="91" height="25" rx="7" fill="#14617a" stroke="#76d8e1" strokeWidth="3" />
      <rect x="420" y="191" width="148" height="55" rx="26" fill="#c9997e" stroke="#edc6ab" strokeWidth="4" />
      <Cuff x={490} y={184} width={136} height={73} />
      <path d="M 307 235 C 369 279 408 257 490 226" fill="none" stroke="#7ba4b4" strokeWidth="6" />
      <circle cx="650" cy="112" r="38" fill="#254e64" stroke="#78d9df" strokeWidth="3" />
      <path d="M 650 89 V 112 L 668 123" fill="none" stroke="#e8f8f5" strokeWidth="5" strokeLinecap="round" />
      <text x="602" y="169" fill="#eff8f7" fontSize="20" fontWeight="800">REST 5 MIN</text>
      <text x="89" y="376" fill="#bcd9e1" fontSize="18">BP monitor + cuff · restrained, supported quiet rest</text>
    </>
    case 'expose': return <>
      <path d="M 184 92 Q 255 57 330 94 L 354 323 L 173 323 Z" fill="#c9997e" stroke="#edc6ab" strokeWidth="5" />
      <Arm x={334} y={82} />
      <path d="M 355 93 H 488 L 476 146 H 361 Z" fill="#14617a" stroke="#76d8e1" strokeWidth="5" />
      <path d="M 492 162 L 576 162 L 535 209" fill="none" stroke="#f1bb64" strokeWidth="5" />
      <circle cx="410" cy="206" r="51" fill="none" stroke="#f1bb64" strokeWidth="5" strokeDasharray="10 8" />
      <text x="520" y="144" fill="#f7d49a" fontSize="22" fontWeight="800">BARE SKIN</text>
      <text x="520" y="286" fill="#dcebef" fontSize="18">Left upper arm</text>
    </>
    case 'wrap': return <>
      <Arm x={248} y={62} cuff elbowLabel={false} />
      <path d="M 364 198 L 468 91 H 642" fill="none" stroke="#f28a75" strokeWidth="5" />
      <text x="477" y="79" fill="#ffd0bf" fontSize="19" fontWeight="800">ARTERY MARKER</text>
      <path d="M 470 273 H 548 M 470 287 H 548" stroke="#f1bb64" strokeWidth="5" strokeLinecap="round" />
      <text x="496" y="322" fill="#f7d49a" fontSize="18">Two-finger fit</text>
      <path d="M 240 277 H 390" stroke="#f1bb64" strokeWidth="3" strokeDasharray="8 6" />
      <text x="72" y="265" fill="#f7d49a" fontSize="18" fontWeight="800">2–3 cm above</text>
      <text x="113" y="288" fill="#f7d49a" fontSize="18">elbow crease</text>
    </>
    case 'support': return <>
      <ellipse cx="197" cy="213" rx="100" ry="145" fill="#c9997e" stroke="#edc6ab" strokeWidth="5" />
      <rect x="111" y="142" width="171" height="49" rx="10" fill="#14617a" stroke="#76d8e1" strokeWidth="4" />
      <text x="133" y="174" fill="#e8f8f5" fontSize="19" fontWeight="800">RESTRAINT</text>
      <rect x="279" y="169" width="343" height="84" rx="40" fill="#c9997e" stroke="#edc6ab" strokeWidth="5" />
      <Cuff x={297} y={163} width={112} height={94} />
      <rect x="438" y="263" width="217" height="22" rx="8" fill="#3e7288" />
      <rect x="525" y="285" width="23" height="52" rx="6" fill="#3e7288" />
      <path d="M 157 208 H 682" stroke="#f28a75" strokeWidth="3" strokeDasharray="10 8" />
      <text x="468" y="140" fill="#ffd0bf" fontSize="20" fontWeight="800">ABOUT HEART LEVEL</text>
      <text x="66" y="375" fill="#bcd9e1" fontSize="17">Positioning schematic · actual microgravity method requires review</text>
    </>
    case 'measure': return <>
      <Monitor x={72} y={106} mode="measuring" />
      <path d="M 307 249 C 386 343 455 245 511 237" fill="none" stroke="#7ba4b4" strokeWidth="6" />
      <rect x="535" y="106" width="112" height="268" rx="52" fill="#c9997e" stroke="#edc6ab" strokeWidth="5" />
      <Cuff x={518} y={172} width={145} height={99} />
      <circle cx="257" cy="286" r="29" fill="none" stroke="#f1bb64" strokeWidth="5" />
      <path d="M 245 327 L 200 367" stroke="#f1bb64" strokeWidth="8" strokeLinecap="round" />
      <text x="87" y="392" fill="#f7d49a" fontSize="18" fontWeight="800">Press START; keep still until the cuff deflates</text>
    </>
    case 'record': return <>
      <Monitor x={54} y={100} mode="result" reading={reading} />
      <path d="M 303 202 H 429" stroke="#f1bb64" strokeWidth="5" markerEnd="url(#picture-arrow)" />
      <text x="465" y="110" fill="#d5e8ec" fontSize="18" fontWeight="800">COPY THE DISPLAY</text>
      <rect x="454" y="134" width="246" height="70" rx="12" fill="#23445a" stroke="#78d9df" strokeWidth="3" />
      <text x="473" y="160" fill="#b7d3da" fontSize="16">Systolic / Diastolic</text>
      <text x="473" y="189" fill="#f1f8f6" fontSize="26" fontWeight="800">{reading.systolic || '—'} / {reading.diastolic || '—'}</text>
      <rect x="454" y="221" width="246" height="70" rx="12" fill="#23445a" stroke="#78d9df" strokeWidth="3" />
      <text x="473" y="247" fill="#b7d3da" fontSize="16">Pulse · bpm</text>
      <text x="473" y="277" fill="#f1f8f6" fontSize="26" fontWeight="800">{reading.pulse || '—'}</text>
      <text x="458" y="342" fill="#ffd0bf" fontSize="18" fontWeight="800">SIMULATED VALUES ONLY</text>
      <Cuff x={72} y={370} width={138} height={43} />
      <text x="237" y="398" fill="#bcd9e1" fontSize="18" fontWeight="800">Remove cuff, then record the display</text>
    </>
  }
}

export function ProcedurePictures({ scene, reading }: Props) {
  if (scene.startsWith('po-') || scene.startsWith('temp-')) return <AdditionalProcedurePictures scene={scene as Parameters<typeof AdditionalProcedurePictures>[0]['scene']} reading={{ spo2: reading.spo2 ?? '', pulse: reading.pulse, temperature: reading.temperature ?? '' }} />
  return <div className="procedure-picture-frame">
    <svg viewBox="0 0 760 430" role="img" aria-label={titles[scene]} preserveAspectRatio="xMidYMid meet">
      <title>{titles[scene]}</title>
      <defs><marker id="picture-arrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M 0 0 L 10 5 L 0 10 Z" fill="#f1bb64" /></marker></defs>
      <rect width="760" height="430" rx="18" fill="#102b40" />
      <path d="M 0 80 H 760 M 0 350 H 760" stroke="#204259" strokeWidth="2" />
      <text x="32" y="49" fill="#69d4df" fontSize="17" fontWeight="800" letterSpacing="2">BP MONITOR · PICTURE GUIDE</text>
      <Picture scene={scene} reading={reading} />
    </svg>
  </div>
}

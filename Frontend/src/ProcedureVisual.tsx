import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js'
import { ATTRIBUTION } from 'open-anatomy-3d'
import type { ProcedureStep } from './api'
import { visualFor, type VisualScene } from './visual-registry'
import { buildAdditionalStage, type ProcedureReading } from './AdditionalProcedureStage'

type Reading = ProcedureReading
type Props = { step: ProcedureStep; reading: Reading; onViewed: (stepId: string) => void; viewed: boolean }
type Stage = { draw: (progress: number, reading: Reading) => void; dispose: () => void }

const cloth = new THREE.MeshStandardMaterial({ color: 0x245e78, roughness: 0.86, side: THREE.DoubleSide })
const trim = new THREE.MeshStandardMaterial({ color: 0x72d6df, roughness: 0.45 })
const skin = new THREE.MeshStandardMaterial({ color: 0xb8917f, roughness: 0.9 })
const dark = new THREE.MeshStandardMaterial({ color: 0x263b52, roughness: 0.7 })
const red = new THREE.MeshBasicMaterial({ color: 0xe57c75 })

function box(w: number, h: number, d: number, material: THREE.Material) { return new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material) }
function cylinder(radius: number, height: number, material: THREE.Material) { return new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, height, 40), material) }
function line(points: THREE.Vector3[], radius: number, material: THREE.Material) { return new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points), 40, radius, 8, false), material) }
function add(parent: THREE.Object3D, child: THREE.Object3D, x: number, y: number, z: number) { child.position.set(x, y, z); parent.add(child); return child }

function cuffGeometry() {
  const group = new THREE.Group()
  const parts: THREE.Mesh[] = []
  for (let i = 0; i < 16; i++) {
    const segment = new THREE.Mesh(new THREE.CylinderGeometry(0.079, 0.079, 0.155, 5, 1, true, i * Math.PI / 8, Math.PI / 8 + 0.006), cloth)
    group.add(segment); parts.push(segment)
  }
  const edgeTop = new THREE.Mesh(new THREE.TorusGeometry(0.08, 0.004, 7, 48), trim)
  edgeTop.rotation.x = Math.PI / 2
  add(group, edgeTop, 0, 0.078, 0)
  const edgeBottom = edgeTop.clone()
  add(group, edgeBottom, 0, -0.078, 0)
  const marker = box(0.014, 0.11, 0.009, red)
  add(group, marker, 0, 0, 0.084)
  return { group, parts, marker }
}

function monitorGeometry() {
  const group = new THREE.Group()
  group.add(box(0.39, 0.31, 0.13, dark))
  add(group, box(0.32, 0.19, 0.006, trim), 0, 0.035, 0.07)
  const screen = document.createElement('canvas')
  screen.width = 512; screen.height = 300
  const texture = new THREE.CanvasTexture(screen)
  texture.colorSpace = THREE.SRGBColorSpace
  const display = new THREE.Mesh(new THREE.PlaneGeometry(0.3, 0.175), new THREE.MeshBasicMaterial({ map: texture }))
  add(group, display, 0, 0.035, 0.076)
  const button = cylinder(0.033, 0.018, trim)
  button.rotation.x = Math.PI / 2
  add(group, button, 0.12, -0.116, 0.075)
  return { group, button, screen, texture }
}

function drawDisplay(canvas: HTMLCanvasElement, texture: THREE.CanvasTexture, kind: VisualScene, progress: number, reading: Reading) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.fillStyle = '#d9f2ed'; ctx.fillRect(0, 0, 512, 300)
  ctx.fillStyle = '#19394a'; ctx.font = 'bold 26px Arial'; ctx.fillText('DEMO BP MONITOR A1', 20, 37)
  ctx.font = 'bold 24px Arial'
  if (kind === 'measure') {
    ctx.fillText(progress < 0.2 ? 'PRESS START' : progress < 0.82 ? 'MEASURING…' : 'CUFF DEFLATED', 20, 115)
    ctx.fillStyle = '#56a8b8'; ctx.fillRect(20, 145, Math.max(0, Math.min(1, (progress - 0.2) / 0.62)) * 465, 20)
    ctx.font = '20px Arial'; ctx.fillStyle = '#19394a'; ctx.fillText('No reading until the demo finishes', 20, 224)
  } else if (kind === 'record') {
    ctx.fillStyle = '#9f3c42'; ctx.fillText('SIMULATED VALUES', 20, 91)
    ctx.fillStyle = '#19394a'; ctx.font = 'bold 48px Arial'; ctx.fillText(`${reading.systolic || '—'} / ${reading.diastolic || '—'}`, 20, 167)
    ctx.font = '24px Arial'; ctx.fillText(`mmHg     Pulse ${reading.pulse || '—'} bpm`, 20, 219)
    ctx.fillStyle = '#bd883b'; ctx.fillRect(18 + Math.min(2, Math.floor(progress * 3)) * 152, 242, 135, 8)
  } else {
    ctx.fillText('READY · EDUCATIONAL DEMO', 20, 128)
    ctx.font = '20px Arial'; ctx.fillText('No live measurement', 20, 196)
  }
  texture.needsUpdate = true
}

function makeSupportSchematic(): { group: THREE.Group; cuff: THREE.Group } {
  const group = new THREE.Group()
  const torso = new THREE.Mesh(new THREE.SphereGeometry(0.34, 24, 18), skin)
  torso.scale.set(0.75, 1.28, 0.52); add(group, torso, -0.68, 1.22, 0)
  const upper = cylinder(0.075, 0.48, skin)
  upper.rotation.z = Math.PI / 2; add(group, upper, -0.27, 1.3, 0)
  const elbow = new THREE.Mesh(new THREE.SphereGeometry(0.072, 20, 16), skin)
  add(group, elbow, -0.02, 1.3, 0)
  const forearm = cylinder(0.058, 0.55, skin)
  forearm.rotation.z = Math.PI / 2; add(group, forearm, 0.26, 1.3, 0)
  add(group, new THREE.Mesh(new THREE.SphereGeometry(0.055, 20, 16), skin), 0.56, 1.3, 0)
  const cuff = cuffGeometry().group
  cuff.rotation.z = Math.PI / 2; add(group, cuff, -0.26, 1.3, 0)
  const band = box(0.12, 0.63, 0.4, cloth)
  add(group, band, -0.75, 1.22, 0)
  return { group, cuff }
}

async function buildStage(host: HTMLDivElement, kind: VisualScene): Promise<Stage> {
  if (kind.startsWith('po-') || kind.startsWith('temp-')) return buildAdditionalStage(host, kind)
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5))
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.18
  renderer.domElement.className = 'procedure-canvas'
  renderer.domElement.setAttribute('role', 'img')
  renderer.domElement.setAttribute('aria-label', `3D educational ${kind} demonstration`)
  host.appendChild(renderer.domElement)
  const scene = new THREE.Scene()
  scene.add(new THREE.HemisphereLight(0xe8f5ff, 0x1d364c, 1.6))
  const key = new THREE.DirectionalLight(0xffffff, 2); key.position.set(2, 3, 4); scene.add(key)
  const camera = new THREE.PerspectiveCamera(32, 1, 0.02, 20)
  let gltf
  try { gltf = await new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).loadAsync('/models/anatomy-male.glb') }
  catch (error) { renderer.dispose(); renderer.domElement.remove(); throw error }
  const body = gltf.scene
  for (const name of ['skeleton', 'muscles', 'organs', 'vessels', 'nerves']) { const item = body.getObjectByName(name); if (item) item.visible = false }
  body.getObjectByName('skin')?.traverse(item => { if ((item as THREE.Mesh).isMesh) (item as THREE.Mesh).material = skin })
  scene.add(body)
  const monitorParts = monitorGeometry()
  const monitor = monitorParts.group
  add(scene, monitor, -0.66, 1.06, 0.5)
  const cuffParts = cuffGeometry()
  const cuff = cuffParts.group
  add(scene, cuff, 0.21, 1.23, 0)
  const fingers = new THREE.Group()
  for (let i = 0; i < 2; i++) add(fingers, cylinder(0.009, 0.1, skin), 0.035 + i * 0.018, -0.07, 0.075)
  add(cuff, fingers, 0, 0, 0)
  const sleeve = cylinder(0.064, 0.22, cloth)
  add(scene, sleeve, 0.22, 1.25, 0)
  const highlight = new THREE.Mesh(new THREE.TorusGeometry(0.102, 0.008, 8, 40), new THREE.MeshBasicMaterial({ color: 0xf3bd61, transparent: true, opacity: 0.9 }))
  highlight.rotation.x = Math.PI / 2
  add(scene, highlight, 0.21, 1.24, 0)
  const restraint = new THREE.Group()
  for (const y of [1.13, 1.32]) add(restraint, box(0.62, 0.045, 0.025, cloth), 0, y, 0.19)
  scene.add(restraint)
  const support = new THREE.Group()
  add(support, box(0.74, 0.055, 0.26, dark), 0.25, 1.28, 0)
  add(support, box(0.09, 0.25, 0.09, trim), 0, 1.14, 0)
  scene.add(support)
  const schematic = makeSupportSchematic()
  scene.add(schematic.group)
  const closeArm = cylinder(0.062, 0.64, skin)
  add(scene, closeArm, 0.21, 1.23, 0)
  const tubing = line([new THREE.Vector3(0.25, 1.2, 0.03), new THREE.Vector3(0.52, 1.03, 0.3), new THREE.Vector3(-0.25, 0.85, 0.55), new THREE.Vector3(-0.49, 1.02, 0.55)], 0.006, dark)
  scene.add(tubing)
  const draw = (progress: number, reading: Reading) => {
    const p = Math.max(0, Math.min(1, progress))
    body.visible = kind !== 'support' && kind !== 'measure' && kind !== 'record'
    monitor.visible = kind === 'prepare' || kind === 'measure' || kind === 'record'
    cuff.visible = kind === 'wrap' || kind === 'expose' || kind === 'measure' || kind === 'record'
    cuff.position.set(kind === 'prepare' ? 0.56 : 0.21, kind === 'prepare' ? 0.94 : 1.23, kind === 'prepare' ? 0.5 : 0)
    if (kind === 'prepare') cuff.visible = true
    cuffParts.parts.forEach((part, index) => { part.visible = kind === 'wrap' ? index < Math.ceil(p * 16) : kind !== 'expose' })
    cuffParts.marker.visible = kind !== 'expose' && (kind !== 'wrap' || p > 0.6)
    fingers.visible = kind === 'wrap' && p > 0.75
    sleeve.visible = kind === 'expose'
    sleeve.scale.y = Math.max(0.23, 1 - p * 0.77)
    sleeve.position.y = 1.25 + p * 0.11
    highlight.visible = kind === 'expose' && p > 0.45
    restraint.visible = kind === 'prepare'
    restraint.scale.setScalar(kind === 'prepare' ? 0.8 + p * 0.2 : 1)
    support.visible = kind === 'support'
    support.position.y = kind === 'support' ? -0.25 + p * 0.25 : 0
    schematic.group.visible = kind === 'support'
    closeArm.visible = kind === 'measure' || kind === 'record'
    tubing.visible = kind === 'measure' || kind === 'record'
    if (kind === 'measure') cuff.scale.setScalar(p < 0.18 ? 1 : p < 0.62 ? 1 + (p - 0.18) * 0.16 : 1 + (1 - p) * 0.19)
    else cuff.scale.setScalar(1)
    if (kind === 'record') cuff.position.x = 0.21 + Math.max(0, p - 0.55) * 0.75
    monitorParts.button.position.z = 0.075 - (kind === 'measure' && p > 0.12 && p < 0.26 ? 0.018 : 0)
    if (kind === 'prepare') { monitor.position.x = -0.82 + p * 0.16; cuff.position.x = 0.74 - p * 0.18 }
    drawDisplay(monitorParts.screen, monitorParts.texture, kind, p, reading)
    if (kind === 'expose' || kind === 'wrap') { camera.position.set(1.1, 1.36, 1.05); camera.lookAt(0.23, 1.27, 0) }
    else if (kind === 'support') { camera.position.set(0.15, 1.5, 2.4); camera.lookAt(-0.1, 1.2, 0) }
    else if (kind === 'measure') { camera.position.set(-0.15, 1.25, 2.6); camera.lookAt(-0.15, 1.09, 0.22) }
    else if (kind === 'record') {
      const focus = Math.max(0, Math.min(1, (p - 0.53) / 0.25))
      camera.position.set(-0.15 - focus * 0.48, 1.25 - focus * 0.07, 2.6 - focus * 1.1)
      camera.lookAt(-0.15 - focus * 0.48, 1.09 - focus * 0.01, 0.22 + focus * 0.08)
    }
    else { camera.position.set(0, 1.15, 3.7); camera.lookAt(0, 0.99, 0) }
    const width = Math.max(1, host.clientWidth), height = Math.max(1, host.clientHeight)
    renderer.setSize(width, height, false); camera.aspect = width / height; camera.updateProjectionMatrix(); renderer.render(scene, camera)
  }
  const dispose = () => {
    scene.traverse(item => { if ((item as THREE.Mesh).isMesh) (item as THREE.Mesh).geometry.dispose() })
    monitorParts.texture.dispose(); renderer.dispose(); renderer.domElement.remove()
  }
  return { draw, dispose }
}

export function ProcedureVisual({ step, reading, onViewed, viewed }: Props) {
  const kind = visualFor(step)
  const host = useRef<HTMLDivElement>(null)
  const stage = useRef<Stage | null>(null)
  const onViewedRef = useRef(onViewed); onViewedRef.current = onViewed
  const readingRef = useRef(reading); readingRef.current = reading
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  const progressRef = useRef(0)
  const playingRef = useRef(false)
  const lastTime = useRef(0)
  useEffect(() => { progressRef.current = 0; playingRef.current = false; setProgress(0); setPlaying(false); setStatus('loading') }, [step.step_id])
  useEffect(() => {
    const mount = host.current
    if (!kind || !mount || typeof WebGL2RenderingContext === 'undefined') { setStatus('error'); return }
    let disposed = false
    let frame = 0
    void buildStage(mount, kind).then(value => {
      if (disposed) { value.dispose(); return }
      stage.current = value; setStatus('ready'); value.draw(progressRef.current, readingRef.current)
      const tick = (time: number) => {
        const delta = lastTime.current ? Math.min(100, time - lastTime.current) : 0
        lastTime.current = time
        if (playingRef.current) {
          progressRef.current = Math.min(1, progressRef.current + delta / 6000)
          if (progressRef.current >= 1) { playingRef.current = false; setPlaying(false); onViewedRef.current(step.step_id) }
          setProgress(progressRef.current)
        }
        value.draw(progressRef.current, readingRef.current)
        frame = window.requestAnimationFrame(tick)
      }
      frame = window.requestAnimationFrame(tick)
    }).catch(() => { if (!disposed) setStatus('error') })
    return () => { disposed = true; if (frame) window.cancelAnimationFrame(frame); stage.current?.dispose(); stage.current = null }
  }, [kind, step.step_id])
  if (!kind) return <div className="status error">Visual demonstration unavailable: this backend action or asset is not implemented in the frontend. The written instruction remains available.</div>
  const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  const toggle = () => {
    if (reducedMotion()) { progressRef.current = 1; setProgress(1); stage.current?.draw(1, readingRef.current); onViewed(step.step_id); return }
    playingRef.current = !playingRef.current; setPlaying(playingRef.current); lastTime.current = 0
  }
  const replay = () => {
    if (reducedMotion()) { progressRef.current = 1; setProgress(1); stage.current?.draw(1, readingRef.current); onViewed(step.step_id); return }
    progressRef.current = 0; setProgress(0); playingRef.current = true; setPlaying(true); lastTime.current = 0; stage.current?.draw(0, readingRef.current)
  }
  return <section className="procedure-visual" aria-label={`${step.title} visual demonstration`}>
    <div className="procedure-visual-head"><div><span className="eyebrow">3D EDUCATIONAL DEMONSTRATION</span><h3>{step.title}</h3></div><span className="tag simulated">{viewed ? 'Viewed on this device' : 'Not viewed yet'}</span></div>
    <div className="procedure-stage" ref={host}>{status === 'loading' && <p role="status">Loading 3D procedure scene…</p>}{status === 'error' && <p role="status">3D demonstration unavailable on this device. Follow the backend instruction and its limitations.</p>}</div>
    <div className="procedure-playback"><button type="button" disabled={status !== 'ready'} onClick={toggle}>{playing ? 'Pause' : progress > 0 && progress < 1 ? 'Resume' : 'Play demonstration'}</button><button type="button" disabled={status !== 'ready'} onClick={replay}>Replay</button><label>Demonstration progress <progress value={progress} max={1} /></label></div>
    <p className="muted small">{step.visual.expected_visible_action}</p>
    {kind === 'support' && <p className="status info">Positioning schematic: the static reference body cannot depict an articulated arm. Earth-based positioning is not automatically valid in microgravity.</p>}
    {(kind.startsWith('po-') || kind.startsWith('temp-')) && <p className="status info">The 3D device and body-part scene is a schematic educational animation. It is not a live sensor or a validated microgravity technique.</p>}
    <p className="muted small">Animation viewing is recorded only on this device. Step acknowledgement is sent separately to the backend; neither proves clinical execution.</p>
    {!kind.startsWith('po-') && !kind.startsWith('temp-') && <p className="muted small human-body-credit">{ATTRIBUTION}</p>}
  </section>
}

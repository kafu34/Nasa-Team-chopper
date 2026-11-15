import * as THREE from 'three'
import type { VisualScene } from './visual-registry'

export type ProcedureReading = { systolic: string; diastolic: string; pulse: string; spo2?: string; temperature?: string }
type Stage = { draw: (progress: number, reading: ProcedureReading) => void; dispose: () => void }
const box = (w: number, h: number, d: number, material: THREE.Material) => new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material)
const sphere = (r: number, material: THREE.Material) => new THREE.Mesh(new THREE.SphereGeometry(r, 32, 22), material)
const place = <T extends THREE.Object3D>(group: THREE.Group, child: T, x: number, y: number, z: number) => { child.position.set(x, y, z); group.add(child); return child }

export function buildAdditionalStage(host: HTMLDivElement, kind: VisualScene): Stage {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5))
  renderer.domElement.className = 'procedure-canvas'
  renderer.domElement.setAttribute('role', 'img')
  renderer.domElement.setAttribute('aria-label', `3D schematic educational ${kind} device action`)
  host.appendChild(renderer.domElement)
  const scene = new THREE.Scene()
  scene.add(new THREE.HemisphereLight(0xf1f8ff, 0x172c42, 2))
  const light = new THREE.DirectionalLight(0xffffff, 2.4); light.position.set(2, 4, 5); scene.add(light)
  const camera = new THREE.PerspectiveCamera(34, 1, 0.01, 20)
  const materials = {
    body: new THREE.MeshStandardMaterial({ color: 0xc9957d, roughness: 0.88 }),
    device: new THREE.MeshStandardMaterial({ color: 0x214a60, roughness: 0.48 }),
    trim: new THREE.MeshStandardMaterial({ color: 0x74d7df, metalness: 0.2, roughness: 0.38 }),
    dark: new THREE.MeshStandardMaterial({ color: 0x102838, roughness: 0.75 }),
    amber: new THREE.MeshBasicMaterial({ color: 0xf3bd61 }),
  }
  const displayCanvas = document.createElement('canvas'); displayCanvas.width = 512; displayCanvas.height = 256
  const texture = new THREE.CanvasTexture(displayCanvas); texture.colorSpace = THREE.SRGBColorSpace
  const displayMaterial = new THREE.MeshBasicMaterial({ map: texture })
  const pulse = kind.startsWith('po-')

  const finger = new THREE.Group()
  const fingerCore = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.13, 0.92, 36), materials.body)
  fingerCore.rotation.z = Math.PI / 2; finger.add(fingerCore)
  place(finger, sphere(0.12, materials.body), 0.46, 0, 0)
  const restraint = place(finger, box(0.16, 0.48, 0.27, materials.device), -0.38, -0.05, -0.02)
  scene.add(finger)
  const probe = new THREE.Group()
  const lower = place(probe, box(0.52, 0.10, 0.32, materials.device), 0, -0.115, 0)
  place(probe, box(0.53, 0.025, 0.34, materials.trim), 0, -0.17, 0)
  const lid = new THREE.Group()
  place(lid, box(0.53, 0.12, 0.34, materials.device), 0, 0.12, 0)
  place(lid, box(0.43, 0.015, 0.28, materials.trim), 0, 0.19, 0)
  const poDisplay = place(lid, new THREE.Mesh(new THREE.PlaneGeometry(0.40, 0.17), displayMaterial), 0, 0.2, 0)
  poDisplay.rotation.x = -Math.PI / 2
  probe.add(lid); scene.add(probe)

  const head = new THREE.Group()
  const face = place(head, sphere(0.39, materials.body), 0, 0.05, 0)
  face.scale.set(0.78, 1.12, 0.6)
  const hair = place(head, sphere(0.40, materials.dark), 0, 0.28, -0.02)
  hair.scale.set(0.8, 0.3, 0.65)
  scene.add(head)
  const thermometer = new THREE.Group()
  place(thermometer, box(0.45, 0.23, 0.22, materials.device), 0, 0, 0)
  place(thermometer, box(0.18, 0.41, 0.20, materials.device), -0.10, -0.31, 0)
  place(thermometer, box(0.17, 0.13, 0.17, materials.trim), 0.31, 0, 0)
  place(thermometer, new THREE.Mesh(new THREE.PlaneGeometry(0.30, 0.14), displayMaterial), -0.07, 0.045, 0.116)
  const trigger = place(thermometer, box(0.095, 0.08, 0.06, materials.amber), 0.045, -0.19, 0.12)
  const beam = place(thermometer, new THREE.Mesh(new THREE.CylinderGeometry(0.006, 0.006, 0.64, 12), new THREE.MeshBasicMaterial({ color: 0xf3bd61, transparent: true, opacity: 0.7 })), 0.67, 0, 0)
  beam.rotation.z = Math.PI / 2
  scene.add(thermometer)
  const target = place(head, new THREE.Mesh(new THREE.TorusGeometry(0.07, 0.008, 8, 32), materials.amber), -0.05, 0.22, 0.24)

  const draw = (progress: number, reading: ProcedureReading) => {
    const p = Math.max(0, Math.min(1, progress))
    const ctx = displayCanvas.getContext('2d')
    if (ctx) {
      ctx.fillStyle = '#e5f5f0'; ctx.fillRect(0, 0, 512, 256)
      ctx.fillStyle = '#17394b'; ctx.font = 'bold 32px Arial'; ctx.fillText(pulse ? 'DEMO OXIMETER P1' : 'DEMO IR THERMOMETER T1', 20, 45)
      ctx.fillStyle = '#23536b'; ctx.font = 'bold 45px Arial'
      if (pulse) ctx.fillText(kind === 'po-record' || kind === 'po-hold' && p > 0.72 ? `${reading.spo2 || '98'}%  ${reading.pulse || '68'} bpm` : 'WAIT FOR STABLE', 20, 137)
      else ctx.fillText(kind === 'temp-record' || kind === 'temp-measure' && p > 0.58 ? `${reading.temperature || '36.7'} °C` : 'READY', 20, 137)
      ctx.font = '26px Arial'; ctx.fillStyle = '#a34e4c'; ctx.fillText('SIMULATED · NO LIVE SENSOR', 20, 207)
      texture.needsUpdate = true
    }
    finger.visible = pulse; probe.visible = pulse; head.visible = !pulse; thermometer.visible = !pulse
    if (pulse) {
      restraint.visible = kind === 'po-prepare' || kind === 'po-hold'
      finger.position.set(kind === 'po-prepare' ? -0.7 : -0.22, 0, 0)
      probe.position.set(kind === 'po-prepare' || kind === 'po-finger' ? 0.72 : kind === 'po-place' ? 0.7 - p * 0.7 : 0, 0, 0)
      lid.rotation.z = kind === 'po-place' ? 0.36 * (1 - p) : kind === 'po-finger' ? 0.36 : 0
      lower.visible = true
      probe.rotation.y = kind === 'po-record' ? -0.15 - p * 0.2 : 0
      camera.position.set(0, 0.35, 2.25); camera.lookAt(0, 0, 0)
    } else {
      hair.position.y = kind === 'temp-forehead' ? 0.28 + 0.16 * p : 0.28
      thermometer.position.set(kind === 'temp-prepare' ? 0 : kind === 'temp-aim' ? -1.05 + p * 0.32 : -0.73, kind === 'temp-prepare' ? 0 : -0.02, 0.28)
      head.position.x = kind === 'temp-prepare' ? 1.2 : 0.48
      target.visible = kind === 'temp-aim' || kind === 'temp-measure'
      beam.visible = kind === 'temp-aim' && p > 0.45 || kind === 'temp-measure' && p > 0.24 && p < 0.65
      trigger.position.z = kind === 'temp-measure' && p > 0.22 && p < 0.42 ? 0.08 : 0.12
      camera.position.set(0, 0.25, 2.7); camera.lookAt(0, 0, 0)
    }
    const width = Math.max(1, host.clientWidth), height = Math.max(1, host.clientHeight)
    renderer.setSize(width, height, false); camera.aspect = width / height; camera.updateProjectionMatrix(); renderer.render(scene, camera)
  }
  const dispose = () => { scene.traverse(item => { if ((item as THREE.Mesh).isMesh) (item as THREE.Mesh).geometry.dispose() }); Object.values(materials).forEach(item => item.dispose()); displayMaterial.dispose(); (beam.material as THREE.Material).dispose(); texture.dispose(); renderer.dispose(); renderer.domElement.remove() }
  return { draw, dispose }
}

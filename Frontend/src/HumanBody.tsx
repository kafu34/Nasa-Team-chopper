import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js'
import { TrackballControls } from 'three/addons/controls/TrackballControls.js'
import { ATTRIBUTION } from 'open-anatomy-3d'
import type { BodySelection } from './BodyMap'
import { ANATOMY_SITES, selectAnatomySite } from './anatomy-sites'
import { ThreeBody } from './ThreeBody'
import { HUMAN_MODEL_ID, humanSelection } from './human-site'
import { strongestAlert, type BodyAlerts } from './mission-ui'

type Layer = 'skin' | 'muscles' | 'skeleton'
type Props = {
  value: BodySelection | null
  onChange: (selection: BodySelection) => void
  alerts?: BodyAlerts
  savedPoints?: { selection: BodySelection; severity: number }[]
  compact?: boolean
  animateAlerts?: boolean
}
type Viewer = {
  scene: THREE.Scene
  camera: THREE.PerspectiveCamera
  controls: TrackballControls
  groups: Partial<Record<Layer, THREE.Object3D>>
  marker: THREE.Mesh
  skinMesh?: THREE.Mesh
  savedMarkers: THREE.Mesh[]
  skinMaterial?: THREE.MeshStandardMaterial
  render: () => void
}

const front: [number, number, number] = [0, 0.87, 3.35]
const center: [number, number, number] = [0, 0.87, 0]

export function HumanBody({ value, onChange, alerts, savedPoints = [], compact = false, animateAlerts = true }: Props) {
  const [mode, setMode] = useState<'human' | 'legacy'>('human')
  const [layer, setLayer] = useState<Layer>('skin')
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const host = useRef<HTMLDivElement>(null)
  const viewer = useRef<Viewer | null>(null)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  useEffect(() => {
    const mount = host.current
    if (mode !== 'human' || !mount) return
    if (typeof WebGL2RenderingContext === 'undefined') { setMode('legacy'); return }
    let renderer: THREE.WebGLRenderer
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' }) }
    catch { setMode('legacy'); return }
    let cancelled = false
    let loaded: THREE.Object3D | null = null
    const createdMaterials = new Set<THREE.Material>()
    let frame = 0
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(34, 1, 0.02, 20)
    camera.position.set(...front)
    const controls = new TrackballControls(camera, renderer.domElement)
    controls.target.set(...center)
    controls.noRotate = compact
    controls.noZoom = compact
    controls.noPan = compact
    controls.staticMoving = true
    controls.minDistance = 1.15
    controls.maxDistance = 7
    controls.rotateSpeed = 2
    controls.zoomSpeed = 1.15
    controls.panSpeed = 0.7
    controls.multiTouchRoll = true
    controls.update()
    scene.add(new THREE.HemisphereLight(0xe5f4ff, 0x233950, 1.25))
    const key = new THREE.DirectionalLight(0xffffff, 1.65)
    key.position.set(-3, 4, 5)
    scene.add(key)
    const rim = new THREE.DirectionalLight(0x7bd8e8, 0.8)
    rim.position.set(3, 2, -3)
    scene.add(rim)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5))
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.1
    renderer.domElement.className = 'three-body-canvas'
    renderer.domElement.setAttribute('role', 'img')
    renderer.domElement.setAttribute('aria-label', compact ? 'Human anatomy reference model; tap to expand' : 'Human anatomy reference model; drag to rotate, right drag to pan, scroll or pinch to zoom, tap the exterior to select')
    mount.appendChild(renderer.domElement)
    const marker = new THREE.Mesh(new THREE.SphereGeometry(0.025, 12, 8), new THREE.MeshBasicMaterial({ color: 0xffdb8a, depthTest: false }))
    marker.renderOrder = 10
    marker.visible = false
    scene.add(marker)
    const render = () => {
      frame = 0
      const width = Math.max(1, mount.clientWidth)
      const height = Math.max(1, mount.clientHeight)
      renderer.setSize(width, height, false)
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      controls.handleResize()
      controls.update()
      renderer.render(scene, camera)
    }
    const requestRender = () => { if (!frame) frame = window.requestAnimationFrame(render) }
    const resize = new ResizeObserver(requestRender)
    resize.observe(mount)
    controls.addEventListener('change', requestRender)
    const groups: Viewer['groups'] = {}
    viewer.current = { scene, camera, controls, groups, marker, savedMarkers: [], render: requestRender }
    const skinMeshes: THREE.Object3D[] = []
    const raycaster = new THREE.Raycaster()
    let pointerStart: { x: number; y: number; button: number } | null = null
    const onPointerDown = (event: PointerEvent) => { pointerStart = { x: event.clientX, y: event.clientY, button: event.button } }
    const onPointerUp = (event: PointerEvent) => {
      if (!pointerStart || pointerStart.button !== 0 || Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) > 7) { pointerStart = null; return }
      pointerStart = null
      if (!groups.skin?.visible) return
      const bounds = renderer.domElement.getBoundingClientRect()
      raycaster.setFromCamera(new THREE.Vector2(((event.clientX - bounds.left) / bounds.width) * 2 - 1, -((event.clientY - bounds.top) / bounds.height) * 2 + 1), camera)
      const hit = raycaster.intersectObjects(skinMeshes, false)[0]
      if (!hit) return
      const mesh = hit.object
      const local = mesh.worldToLocal(hit.point.clone())
      let attachment: BodySelection['attachment']
      if (hit.face && hit.faceIndex != null && hit.faceIndex >= 0) {
        const position = (mesh as THREE.Mesh).geometry.attributes.position
        const a = new THREE.Vector3().fromBufferAttribute(position, hit.face.a)
        const b = new THREE.Vector3().fromBufferAttribute(position, hit.face.b)
        const c = new THREE.Vector3().fromBufferAttribute(position, hit.face.c)
        const weights = THREE.Triangle.getBarycoord(local, a, b, c, new THREE.Vector3())
        if (weights) {
          const values = [Math.max(0, weights.x), Math.max(0, weights.y), Math.max(0, weights.z)]
          const total = values.reduce((sum, weight) => sum + weight, 0)
          if (total > 0) attachment = { triangleIndex: hit.faceIndex, barycentric: values.map(weight => weight / total) as [number, number, number] }
        }
      }
      onChangeRef.current(humanSelection(hit.point, 'skin', local, attachment))
    }
    renderer.domElement.addEventListener('pointerdown', onPointerDown)
    renderer.domElement.addEventListener('pointerup', onPointerUp)
    renderer.domElement.addEventListener('pointermove', requestRender)
    renderer.domElement.addEventListener('wheel', requestRender, { passive: true })
    const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder)
    void loader.loadAsync('/models/anatomy-male.glb').then(gltf => {
      if (cancelled) return
      loaded = gltf.scene
      for (const name of ['skin', 'muscles', 'skeleton'] as Layer[]) groups[name] = gltf.scene.getObjectByName(name)
      const palette: Record<Layer, number> = { skin: 0xb8917f, muscles: 0xb9434a, skeleton: 0xdcd8c9 }
      for (const name of ['skin', 'muscles', 'skeleton'] as Layer[]) {
        const material = new THREE.MeshStandardMaterial({ color: palette[name], roughness: 0.88, metalness: 0, side: THREE.DoubleSide })
        createdMaterials.add(material)
        if (name === 'skin' && viewer.current) viewer.current.skinMaterial = material
        groups[name]?.traverse(object => { const mesh = object as THREE.Mesh; if (mesh.isMesh) mesh.material = material })
      }
      groups.skin?.traverse(object => { if ((object as THREE.Mesh).isMesh) skinMeshes.push(object) })
      if (viewer.current) viewer.current.skinMesh = skinMeshes[0] as THREE.Mesh | undefined
      for (const name of ['organs', 'vessels', 'nerves']) { const group = gltf.scene.getObjectByName(name); if (group) group.visible = false }
      if (!groups.skin || !groups.muscles || !groups.skeleton || !skinMeshes.length) { setStatus('error'); return }
      groups.skin.visible = true
      groups.muscles.visible = false
      groups.skeleton.visible = false
      scene.add(gltf.scene)
      setStatus('ready')
      requestRender()
    }).catch(() => { if (!cancelled) setStatus('error') })
    requestRender()
    return () => {
      cancelled = true
      resize.disconnect()
      controls.removeEventListener('change', requestRender)
      controls.dispose()
      renderer.domElement.removeEventListener('pointerdown', onPointerDown)
      renderer.domElement.removeEventListener('pointerup', onPointerUp)
      renderer.domElement.removeEventListener('pointermove', requestRender)
      renderer.domElement.removeEventListener('wheel', requestRender)
      if (frame) window.cancelAnimationFrame(frame)
      for (const saved of viewer.current?.savedMarkers ?? []) { saved.removeFromParent(); saved.geometry.dispose(); (saved.material as THREE.Material).dispose() }
      loaded?.traverse(object => {
        const mesh = object as THREE.Mesh
        if (!mesh.isMesh) return
        mesh.geometry.dispose()
      })
      for (const material of createdMaterials) material.dispose()
      marker.geometry.dispose()
      ;(marker.material as THREE.Material).dispose()
      renderer.dispose()
      renderer.domElement.remove()
      viewer.current = null
    }
  }, [mode, compact])

  useEffect(() => {
    const current = viewer.current
    if (!current) return
    for (const name of ['skin', 'muscles', 'skeleton'] as Layer[]) if (current.groups[name]) current.groups[name].visible = name === layer
    current.render()
  }, [layer, status])

  useEffect(() => {
    const current = viewer.current
    if (!current) return
    current.marker.visible = value?.modelId === HUMAN_MODEL_ID && Boolean(value.point) && layer === 'skin'
    if (current.marker.visible && value?.point) current.marker.position.set(value.point.x, value.point.y, value.point.z)
    current.render()
  }, [value, layer, status])

  useEffect(() => {
    const current = viewer.current
    const skin = current?.skinMesh
    if (!current || !skin) return
    for (const marker of current.savedMarkers) { marker.removeFromParent(); marker.geometry.dispose(); (marker.material as THREE.Material).dispose() }
    current.savedMarkers = []
    for (const saved of savedPoints) {
      const selection = saved.selection
      if (selection.modelId !== HUMAN_MODEL_ID || selection.renderHint !== 'exact_point' || selection.meshId !== 'skin' || !selection.point) continue
      const marker = new THREE.Mesh(new THREE.SphereGeometry(0.025, 12, 8), new THREE.MeshBasicMaterial({ color: saved.severity >= 7 ? 0xff777a : 0xffbe6b, depthTest: false }))
      const local = selection.meshLocalPoint ?? skin.worldToLocal(new THREE.Vector3(selection.point.x, selection.point.y, selection.point.z))
      marker.position.set(local.x, local.y, local.z)
      marker.renderOrder = 9
      skin.add(marker)
      current.savedMarkers.push(marker)
    }
    current.render()
  }, [savedPoints, status])

  useEffect(() => {
    const current = viewer.current
    const skin = current?.skinMaterial
    if (!current || !skin) return
    const alert = strongestAlert(alerts ?? {})
    skin.emissive.set(alert?.tone === 'red' ? 0xc43746 : alert ? 0xc98738 : 0x000000)
    if (!alert || layer !== 'skin') { skin.emissiveIntensity = 0; current.render(); return }
    if (!animateAlerts || window.matchMedia('(prefers-reduced-motion: reduce)').matches) { skin.emissiveIntensity = 0.2; current.render(); return }
    let frame = 0
    let active = true
    const pulse = (time: number) => {
      if (!active) return
      skin.emissiveIntensity = 0.12 + 0.2 * (0.5 + 0.5 * Math.sin(time / 340))
      current.render()
      frame = window.requestAnimationFrame(pulse)
    }
    frame = window.requestAnimationFrame(pulse)
    return () => { active = false; window.cancelAnimationFrame(frame); skin.emissiveIntensity = 0 }
  }, [alerts, animateAlerts, layer, status])

  const cameraView = (position: [number, number, number]) => {
    const current = viewer.current
    if (!current) return
    current.camera.up.set(0, 1, 0)
    current.controls.target.set(...center)
    current.camera.position.set(...position)
    current.controls.update()
    current.render()
  }
  const zoom = (factor: number) => {
    const current = viewer.current
    if (!current) return
    const offset = current.camera.position.clone().sub(current.controls.target).multiplyScalar(factor)
    offset.clampLength(1.15, 7)
    current.camera.position.copy(current.controls.target).add(offset)
    current.controls.update()
    current.render()
  }

  if (mode === 'legacy') return <div className="human-body"><div className="human-body-mode"><button type="button" onClick={() => { setMode('human'); setStatus('loading') }}>Human reference</button><button type="button" aria-pressed="true">Legacy diagram</button></div><p className="muted small">Saved v1 markers belong to this diagram. They are not projected onto the new reference mesh.</p><ThreeBody value={value?.modelId === HUMAN_MODEL_ID ? null : value} onChange={onChange} alerts={alerts} savedPoints={savedPoints.filter(saved => saved.selection.modelId !== HUMAN_MODEL_ID)} compact={compact} animateAlerts={animateAlerts} /></div>
  return <div className={`three-body human-body ${compact ? 'three-body--compact' : ''}`}>
    {!compact && <><div className="human-body-mode"><button type="button" aria-pressed="true">Human reference</button><button type="button" onClick={() => setMode('legacy')}>Legacy diagram{savedPoints.filter(saved => saved.selection.modelId !== HUMAN_MODEL_ID).length ? ` (${savedPoints.filter(saved => saved.selection.modelId !== HUMAN_MODEL_ID).length} saved)` : ''}</button></div><div className="human-body-layers" aria-label="Anatomical layers">{(['skin', 'muscles', 'skeleton'] as Layer[]).map(name => <button type="button" key={name} aria-pressed={layer === name} onClick={() => setLayer(name)}>{name === 'skin' ? 'Exterior' : name === 'muscles' ? 'Muscles' : 'Skeleton'}</button>)}</div><div className="three-body-toolbar" aria-label="3D body controls"><button type="button" onClick={() => cameraView(front)}>Front</button><button type="button" onClick={() => cameraView([0, 0.87, -3.35])}>Back</button><button type="button" onClick={() => cameraView([3.35, 0.87, 0])}>Left side</button><button type="button" onClick={() => cameraView([-3.35, 0.87, 0])}>Right side</button><button type="button" onClick={() => zoom(0.8)} aria-label="Zoom in">＋</button><button type="button" onClick={() => zoom(1.25)} aria-label="Zoom out">−</button><button type="button" onClick={() => cameraView(front)}>Reset view</button></div><p className="muted small three-body-help">Drag to rotate on any axis. Right drag to pan. Scroll or pinch to zoom. Tap the exterior to select a reference surface.</p></>}
    <div ref={host} className="three-body-stage" />
    {!compact && savedPoints.some(saved => saved.selection.modelId === HUMAN_MODEL_ID) && <div className="human-body-saved" aria-label="Saved human reference reports"><strong>Saved reports on this reference</strong><ul>{savedPoints.filter(saved => saved.selection.modelId === HUMAN_MODEL_ID).map((saved, index) => <li key={`${saved.selection.siteId}-${index}`}>{saved.selection.label}: {saved.selection.renderHint === 'exact_point' ? 'exact marker restored' : saved.selection.renderHint === 'site_only' ? 'area only; model version changed' : 'marker unavailable'} · reported {saved.severity}/10</li>)}</ul></div>}
    {compact && <p className="muted human-body-compact-credit">Reference anatomy: BodyParts3D / open-anatomy-3d · CC BY 4.0</p>}
    {status === 'loading' && <p className="muted small" role="status">Loading local anatomical model…</p>}
    {status === 'error' && <div className="status error">The human model could not load on this device. <button type="button" onClick={() => setMode('legacy')}>Open legacy diagram</button></div>}
    {!compact && <><label className="form-label human-body-site-list">Choose an area by name for keyboard access<select value={value?.modelId === HUMAN_MODEL_ID ? value.siteId ?? '' : ''} onChange={event => { const site = selectAnatomySite(event.target.value); if (site) onChange({ ...site, modelId: HUMAN_MODEL_ID, modelVersion: '1.0.0' }) }}><option value="">Select a surface area</option>{ANATOMY_SITES.map(site => <option key={site.id} value={site.id}>{site.label}</option>)}</select></label><p className="muted small">Educational reference anatomy, not a scan or finding for this astronaut. Tapped skin points are stored by the local backend with the model version and mesh attachment. A named-area choice has no exact point. Use Legacy diagram for saved v1 points.</p><p className="muted small human-body-credit">{ATTRIBUTION} <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">Licence</a></p><p className="muted small">{layer === 'skin' ? 'Exterior surface: tap to select a region.' : `${layer === 'muscles' ? 'Muscle' : 'Skeletal'} geometry is shown for education; return to Exterior to report a surface concern.`}</p></>}
  </div>
}

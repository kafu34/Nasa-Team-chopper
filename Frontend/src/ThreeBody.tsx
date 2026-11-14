import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { TrackballControls } from 'three/addons/controls/TrackballControls.js'
import { ANATOMY_SITES, ANATOMY_SITE_BY_ID, selectAnatomySite } from './anatomy-sites'
import { BodyMap, type BodySelection } from './BodyMap'
import type { BodyAlerts } from './mission-ui'

type Viewer = {
  camera: THREE.PerspectiveCamera
  controls: TrackballControls
  meshes: THREE.Mesh<THREE.BufferGeometry, THREE.MeshStandardMaterial>[]
  marker: THREE.Mesh
  savedMarkers: THREE.Group
  render: () => void
}

type Props = {
  value: BodySelection | null
  onChange: (selection: BodySelection) => void
  alerts?: BodyAlerts
  savedPoints?: { selection: BodySelection; severity: number }[]
  compact?: boolean
  animateAlerts?: boolean
}

export function ThreeBody({ value, onChange, alerts = {}, savedPoints = [], compact = false, animateAlerts = true }: Props) {
  const host = useRef<HTMLDivElement>(null)
  const viewer = useRef<Viewer | null>(null)
  const onChangeRef = useRef(onChange)
  const [available, setAvailable] = useState(true)
  onChangeRef.current = onChange

  useEffect(() => {
    const mount = host.current
    if (!mount || typeof WebGL2RenderingContext === 'undefined') { setAvailable(false); return }
    let renderer: THREE.WebGLRenderer
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' }) }
    catch { setAvailable(false); return }

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 30)
    camera.position.set(0, -0.25, 7.3)
    const controls = new TrackballControls(camera, renderer.domElement)
    controls.target.set(0, -0.25, 0)
    controls.noPan = true
    controls.noRotate = compact
    controls.noZoom = compact
    controls.staticMoving = true
    controls.minDistance = 3
    controls.maxDistance = 11
    controls.rotateSpeed = 2.3
    controls.zoomSpeed = 1.2
    controls.multiTouchRoll = true
    controls.update()
    scene.add(new THREE.AmbientLight(0xc8e4f2, 2.1))
    const keyLight = new THREE.DirectionalLight(0xffffff, 2.6)
    keyLight.position.set(-3, 5, 5)
    scene.add(keyLight)
    const rimLight = new THREE.DirectionalLight(0x4fc5d7, 1.5)
    rimLight.position.set(3, 2, -4)
    scene.add(rimLight)

    const meshes: Viewer['meshes'] = []
    const geometries = new Set<THREE.BufferGeometry>()
    const materials = new Set<THREE.Material>()
    const add = (siteId: string, geometry: THREE.BufferGeometry, position: [number, number, number], scale: [number, number, number]) => {
      const material = new THREE.MeshStandardMaterial({ color: 0x49738a, roughness: 0.67, metalness: 0.08, side: THREE.DoubleSide })
      const mesh = new THREE.Mesh(geometry, material)
      mesh.position.set(...position)
      mesh.scale.set(...scale)
      mesh.userData.siteId = siteId
      scene.add(mesh)
      meshes.push(mesh)
      geometries.add(geometry)
      materials.add(material)
      return mesh
    }
    const sphere = (id: string, position: [number, number, number], scale: [number, number, number]) => add(id, new THREE.SphereGeometry(1, 20, 16), position, scale)
    const limb = (id: string, a: THREE.Vector3, b: THREE.Vector3, radiusA: number, radiusB: number) => {
      const midpoint = a.clone().add(b).multiplyScalar(0.5)
      const direction = b.clone().sub(a)
      const mesh = add(id, new THREE.CylinderGeometry(radiusA, radiusB, direction.length(), 16, 1), [midpoint.x, midpoint.y, midpoint.z], [1, 1, 1])
      mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize())
    }
    sphere('head', [0, 1.42, 0], [0.29, 0.38, 0.26])
    sphere('neck', [0, 0.99, 0], [0.13, 0.19, 0.14])
    sphere('right_eye', [-0.105, 1.48, 0.238], [0.055, 0.043, 0.032])
    sphere('left_eye', [0.105, 1.48, 0.238], [0.055, 0.043, 0.032])
    for (const side of ['right', 'left'] as const) {
      const sign = side === 'right' ? -1 : 1
      const half = (id: string, y: number, height: number, front: boolean) => add(id,
        new THREE.SphereGeometry(1, 20, 16, front ? 0 : Math.PI, Math.PI),
        [sign * 0.18, y, 0], [0.235, height, 0.265])
      half(`${side}_chest`, 0.61, 0.38, true)
      half(`${side}_upper_back`, 0.61, 0.38, false)
      half(`${side}_abdomen`, 0.02, 0.28, true)
      half(`${side}_lower_back`, 0.02, 0.28, false)
      sphere(`${side}_shoulder`, [sign * 0.51, 0.84, 0], [0.19, 0.19, 0.2])
      limb(`${side}_upper_arm`, new THREE.Vector3(sign * 0.55, 0.73, 0), new THREE.Vector3(sign * 0.69, 0.26, 0), 0.14, 0.12)
      sphere(`${side}_elbow`, [sign * 0.7, 0.19, 0], [0.13, 0.14, 0.14])
      limb(`${side}_forearm`, new THREE.Vector3(sign * 0.72, 0.1, 0), new THREE.Vector3(sign * 0.82, -0.45, 0), 0.105, 0.09)
      sphere(`${side}_wrist`, [sign * 0.83, -0.52, 0], [0.105, 0.105, 0.11])
      sphere(`${side}_hand`, [sign * 0.84, -0.7, 0.02], [0.115, 0.2, 0.085])
      limb(`${side}_upper_leg`, new THREE.Vector3(sign * 0.22, -0.43, 0), new THREE.Vector3(sign * 0.28, -1.24, 0), 0.2, 0.17)
      sphere(`${side}_knee`, [sign * 0.28, -1.34, 0], [0.175, 0.17, 0.18])
      limb(`${side}_lower_leg`, new THREE.Vector3(sign * 0.28, -1.45, 0), new THREE.Vector3(sign * 0.29, -2.08, 0), 0.15, 0.115)
      sphere(`${side}_ankle`, [sign * 0.29, -2.14, 0], [0.12, 0.13, 0.125])
      sphere(`${side}_foot`, [sign * 0.29, -2.29, 0.16], [0.18, 0.105, 0.36])
    }
    sphere('pelvis', [0, -0.38, 0], [0.39, 0.22, 0.23])

    const markerGeometry = new THREE.SphereGeometry(0.07, 16, 12)
    const markerMaterial = new THREE.MeshBasicMaterial({ color: 0xffe0a3, depthTest: false })
    const marker = new THREE.Mesh(markerGeometry, markerMaterial)
    marker.renderOrder = 10
    marker.visible = false
    scene.add(marker)
    geometries.add(markerGeometry)
    materials.add(markerMaterial)
    const savedMarkers = new THREE.Group()
    scene.add(savedMarkers)

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5))
    renderer.domElement.className = 'three-body-canvas'
    renderer.domElement.setAttribute('aria-label', compact ? '3D anatomical body preview; tap an area to expand' : '3D anatomical body; drag to rotate, pinch or scroll to zoom, tap to mark a surface point')
    renderer.domElement.setAttribute('role', 'img')
    mount.appendChild(renderer.domElement)
    let frame = 0
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
    const raycaster = new THREE.Raycaster()
    let pointerStart: { x: number; y: number } | null = null
    const onPointerDown = (event: PointerEvent) => { pointerStart = { x: event.clientX, y: event.clientY } }
    const onPointerUp = (event: PointerEvent) => {
      if (!pointerStart || Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) > 7) { pointerStart = null; return }
      pointerStart = null
      const bounds = renderer.domElement.getBoundingClientRect()
      raycaster.setFromCamera(new THREE.Vector2(((event.clientX - bounds.left) / bounds.width) * 2 - 1, -((event.clientY - bounds.top) / bounds.height) * 2 + 1), camera)
      const hit = raycaster.intersectObjects(meshes)[0]
      if (!hit) return
      const selection = selectAnatomySite(hit.object.userData.siteId as string, { x: hit.point.x, y: hit.point.y, z: hit.point.z })
      if (selection) onChangeRef.current(selection)
    }
    renderer.domElement.addEventListener('pointerdown', onPointerDown)
    renderer.domElement.addEventListener('pointerup', onPointerUp)
    renderer.domElement.addEventListener('pointermove', requestRender)
    renderer.domElement.addEventListener('wheel', requestRender, { passive: true })
    viewer.current = { camera, controls, meshes, marker, savedMarkers, render: requestRender }
    requestRender()
    return () => {
      resize.disconnect()
      controls.removeEventListener('change', requestRender)
      controls.dispose()
      renderer.domElement.removeEventListener('pointerdown', onPointerDown)
      renderer.domElement.removeEventListener('pointerup', onPointerUp)
      renderer.domElement.removeEventListener('pointermove', requestRender)
      renderer.domElement.removeEventListener('wheel', requestRender)
      if (frame) window.cancelAnimationFrame(frame)
      for (const child of savedMarkers.children) {
        const point = child as THREE.Mesh<THREE.BufferGeometry, THREE.MeshBasicMaterial>
        point.geometry.dispose()
        point.material.dispose()
      }
      for (const geometry of geometries) geometry.dispose()
      for (const material of materials) material.dispose()
      renderer.dispose()
      renderer.domElement.remove()
      viewer.current = null
    }
  }, [compact])

  useEffect(() => {
    const current = viewer.current
    if (!current) return
    for (const child of [...current.savedMarkers.children]) {
      const marker = child as THREE.Mesh<THREE.BufferGeometry, THREE.MeshBasicMaterial>
      current.savedMarkers.remove(marker)
      marker.geometry.dispose()
      marker.material.dispose()
    }
    for (const saved of savedPoints) {
      if (!saved.selection.point) continue
      const marker = new THREE.Mesh(new THREE.SphereGeometry(0.055, 12, 8), new THREE.MeshBasicMaterial({ color: saved.severity >= 7 ? 0xff777a : 0xffbe6b, depthTest: false }))
      marker.position.set(saved.selection.point.x, saved.selection.point.y, saved.selection.point.z)
      marker.renderOrder = 9
      current.savedMarkers.add(marker)
    }
    current.render()
  }, [savedPoints, available])

  useEffect(() => {
    const current = viewer.current
    if (!current) return
    current.marker.visible = Boolean(value?.point)
    if (value?.point) current.marker.position.set(value.point.x, value.point.y, value.point.z)
    for (const mesh of current.meshes) {
      const site = ANATOMY_SITE_BY_ID.get(mesh.userData.siteId as string)
      if (!site) continue
      const alert = alerts[`${site.regionId}:${site.laterality}`]
      const selected = value?.siteId === site.id || (!value?.siteId && value?.regionId === site.regionId && value.laterality === site.laterality)
      mesh.material.color.set(selected ? 0x70dce8 : alert?.tone === 'red' ? 0xd85e69 : alert ? 0xd49a52 : 0x49738a)
      mesh.material.emissive.set(alert?.tone === 'red' ? 0x8a2334 : alert ? 0x80501a : 0x000000)
      mesh.material.emissiveIntensity = alert ? 0.28 : 0
    }
    current.render()
    if (!animateAlerts || !Object.keys(alerts).length || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    let frame = 0
    const pulse = (time: number) => {
      for (const mesh of current.meshes) if (mesh.material.emissive.getHex() !== 0) mesh.material.emissiveIntensity = 0.18 + 0.25 * (1 + Math.sin(time / 280)) / 2
      current.render()
      frame = window.requestAnimationFrame(pulse)
    }
    frame = window.requestAnimationFrame(pulse)
    return () => window.cancelAnimationFrame(frame)
  }, [value, alerts, animateAlerts, available])

  const moveCamera = (position: [number, number, number]) => {
    const current = viewer.current
    if (!current) return
    current.camera.up.set(0, 1, 0)
    current.camera.position.set(...position)
    current.controls.update()
    current.render()
  }
  const zoom = (factor: number) => {
    const current = viewer.current
    if (!current) return
    const offset = current.camera.position.clone().sub(current.controls.target).multiplyScalar(factor)
    offset.clampLength(3, 11)
    current.camera.position.copy(current.controls.target).add(offset)
    current.controls.update()
    current.render()
  }

  if (!available) return <div className="three-body-fallback"><p className="muted small">3D graphics are unavailable on this device. Use the surface map or the named-area list below.</p><BodyMap value={value} onChange={onChange} alerts={alerts} compact={compact} animateAlerts={animateAlerts} />{!compact && <label className="form-label">Choose an area by name<select value={value?.siteId ?? ''} onChange={event => { const site = selectAnatomySite(event.target.value); if (site) onChange(site) }}><option value="">Select a surface area</option>{ANATOMY_SITES.map(site => <option key={site.id} value={site.id}>{site.label}</option>)}</select></label>}</div>
  return <div className={`three-body ${compact ? 'three-body--compact' : ''}`}>
    {!compact && <><div className="three-body-toolbar" aria-label="3D body controls"><button type="button" onClick={() => moveCamera([0, -0.25, 7.3])}>Front</button><button type="button" onClick={() => moveCamera([0, -0.25, -7.3])}>Back</button><button type="button" onClick={() => moveCamera([7.3, -0.25, 0])}>Left side</button><button type="button" onClick={() => moveCamera([-7.3, -0.25, 0])}>Right side</button><button type="button" onClick={() => zoom(0.8)} aria-label="Zoom in">＋</button><button type="button" onClick={() => zoom(1.25)} aria-label="Zoom out">−</button><button type="button" onClick={() => moveCamera([0, -0.25, 7.3])}>Reset view</button></div><p className="muted small three-body-help">Drag to rotate on any axis. Scroll or pinch to zoom. Tap once to mark the exact point; the marker does not diagnose an internal structure.</p></>}
    <div ref={host} className="three-body-stage" />
    {!compact && <label className="form-label three-body-list">Choose an area by name for keyboard access<select value={value?.siteId ?? ''} onChange={event => { const site = selectAnatomySite(event.target.value); if (site) onChange(site) }}><option value="">Select a surface area</option>{ANATOMY_SITES.map(site => <option key={site.id} value={site.id}>{site.label}</option>)}</select></label>}
  </div>
}

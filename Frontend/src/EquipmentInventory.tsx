import { useEffect, useState } from 'react'
import { api, DEMO, type EquipmentStatus, type EquipmentUpdateOut } from './api'
import './equipment-inventory.css'

const words = (value: string) => value.replaceAll('_', ' ')
const problem = (cause: unknown) => cause instanceof Error ? cause.message : 'The local service could not update this device.'

export function EquipmentInventory({ zones, onUpdated }: { zones: { zone_id: string; name: string }[]; onUpdated: (result: EquipmentUpdateOut) => void }) {
  const [items, setItems] = useState<EquipmentStatus[] | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [readiness, setReadiness] = useState<'' | 'verified_ready' | 'unknown' | 'needs_service' | 'in_use'>('')
  const [supplies, setSupplies] = useState<Record<string, boolean>>({})
  const [zone, setZone] = useState('')
  const [actorId, setActorId] = useState<string>(DEMO.responderId)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<EquipmentUpdateOut | null>(null)

  async function refresh() {
    try { const response = await api.equipmentInventory(); if (!Array.isArray(response)) throw new Error('Backend returned an invalid equipment list.'); setItems(response); setError(null) }
    catch (cause) { setError(`${problem(cause)} ${items ? 'The last loaded inventory may be stale.' : ''}`) }
  }
  useEffect(() => { void refresh() }, []) // eslint-disable-line react-hooks/exhaustive-deps
  function edit(item: EquipmentStatus) { setSelected(item.equipment_id); setReadiness(['verified_ready', 'unknown', 'needs_service', 'in_use'].includes(item.readiness) ? item.readiness as typeof readiness : ''); setSupplies({ ...item.supplies }); setZone(item.zone_id); setNote(''); setResult(null); setError(null) }
  async function save() {
    if (!selected || note.trim().length < 3) { setError('Enter an audit note of at least three characters.'); return }
    setBusy(true); setError(null); setResult(null)
    try { const out = await api.updateEquipment(selected, { actor_id: actorId, ...(readiness ? { readiness } : {}), supplies, zone_id: zone, note: note.trim() }); setResult(out); setSelected(null); onUpdated(out); await refresh() }
    catch (cause) { setError(problem(cause)) }
    finally { setBusy(false) }
  }

  return <section className="card equipment-inventory" aria-labelledby="inventory-title"><div className="inventory-head"><div><p className="eyebrow">Controlled inventory / 2.11.0</p><h2 id="inventory-title">Device readiness</h2><p className="muted small">Fictional device status from the local backend. A stale readiness check or missing supply makes a device unusable for a new recommendation.</p></div><button type="button" className="button secondary" onClick={() => void refresh()}>Refresh devices</button></div>
    {error && <p className="status error" role="alert">{error}</p>}{result && <p className="status info" role="status">{result.equipment.equipment_id} {result.changed ? 'updated' : 'verified without a state change'}. {result.invalidated_recommendation_ids.length ? `Invalidated route(s): ${result.invalidated_recommendation_ids.join(', ')}.` : 'No route was invalidated.'} {result.affected_session_ids.length ? `In-progress session(s) affected, not cancelled: ${result.affected_session_ids.join(', ')}.` : 'No in-progress session was affected.'}</p>}
    {items ? <div className="inventory-list">{items.map(item => <article key={item.equipment_id} className={`inventory-item ${item.usable ? 'usable' : 'unusable'}`}><div><div className="inventory-id"><strong>{item.device_model}</strong><span>{item.usable ? 'Usable' : 'Unavailable'}</span></div><p className="muted small">{item.equipment_id} · {words(item.capability)} · {zones.find(zoneItem => zoneItem.zone_id === item.zone_id)?.name ?? item.zone_id}</p><p className="small">Readiness: {words(item.readiness)} · checked {item.readiness_verified_at ? new Date(item.readiness_verified_at).toLocaleString() : 'never'}</p><p className="small">Supplies: {item.required_supplies.map(supply => `${words(supply)} ${item.supplies[supply] ? 'ready' : 'missing'}`).join(', ') || 'none required'}</p>{item.unusable_reasons.length > 0 && <p className="inventory-reasons">Backend reasons: {item.unusable_reasons.map(words).join('; ')}</p>}</div><button type="button" className="button secondary" onClick={() => edit(item)}>Update status</button></article>)}</div> : <p className="muted">Loading authoritative device status…</p>}
    {selected && <div className="inventory-editor"><h3>Update {selected}</h3><p className="muted small">Crew-role action. The actor is self-declared in this demonstration; the backend records the change.</p><div className="inventory-form-grid"><label className="form-label">Crew actor<select value={actorId} onChange={event => setActorId(event.target.value)}><option value={DEMO.responderId}>Crew medical officer · {DEMO.responderId}</option><option value={DEMO.astronautId}>Crew member · {DEMO.astronautId}</option></select></label><label className="form-label">Readiness<select value={readiness} onChange={event => setReadiness(event.target.value as typeof readiness)}><option value="">Leave readiness unchanged</option><option value="verified_ready">Verified ready (fresh check)</option><option value="unknown">Unknown</option><option value="needs_service">Needs service</option><option value="in_use">In use</option></select></label><label className="form-label">Device zone<select value={zone} onChange={event => setZone(event.target.value)}>{zones.map(item => <option key={item.zone_id} value={item.zone_id}>{item.name}</option>)}</select></label></div><fieldset className="inventory-supplies"><legend>Required supplies</legend>{Object.entries(supplies).map(([name, available]) => <label key={name}><input type="checkbox" checked={available} onChange={event => setSupplies(value => ({ ...value, [name]: event.target.checked }))} /> {words(name)}</label>)}</fieldset><label className="form-label">Audit note<textarea value={note} maxLength={500} rows={2} onChange={event => setNote(event.target.value)} placeholder="Why is this device status changing?" /></label><div className="button-row"><button type="button" className="button" disabled={busy} onClick={() => void save()}>Save device status</button><button type="button" className="button secondary" disabled={busy} onClick={() => setSelected(null)}>Cancel</button></div></div>}
  </section>
}

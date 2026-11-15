import { type AccessMatrix } from './api'
import { useDemoAccess } from './DemoAccess'
import './access-matrix.css'

const label = (value: string) => value.replaceAll('_', ' ').replaceAll('.', ' · ')

export function AccessMatrixPanel({ matrix, error }: { matrix: AccessMatrix | null; error: string | null }) {
  const { viewerId, setViewerId, can } = useDemoAccess()
  return <div className="access-page"><header className="page-title"><p className="eyebrow">Role-aware demonstration</p><h1>Roles & access</h1><p className="intro">The local backend publishes these fictional personnel and permissions. Select an identity to see which actions it permits.</p></header>
    {error && <p className="status error" role="alert">{error}</p>}
    {!matrix && !error && <p className="status info">Loading the backend role matrix…</p>}
    {matrix && <><p className="status info">{matrix.limitation}</p><section className="card"><h2>Demo identity</h2><label className="form-label">Acting as<select value={viewerId} onChange={event => setViewerId(event.target.value)}>{matrix.personnel.map(person => <option key={person.person_id} value={person.person_id}>{person.display_name} · {label(person.role_code)} · {person.person_id}</option>)}</select></label><p className="muted small">Changing identity updates sensitive case and monitoring reads and the role-checked controls. It does not authenticate the operator.</p></section>
      <section className="card"><h2>Published permission matrix</h2><div className="table-scroll"><table className="access-table"><thead><tr><th>Action</th><th>Allowed roles</th><th>Selected identity</th></tr></thead><tbody>{matrix.permissions.map(permission => <tr key={permission.action}><td><strong>{label(permission.action)}</strong><small>{permission.description}</small></td><td>{permission.allowed_roles.map(label).join(', ')}{permission.own_record_allowed ? '; crew member on own record' : ''}</td><td><span className={`access-state ${can(permission.action, 'DEMO-001') ? 'allowed' : 'denied'}`}>{can(permission.action, 'DEMO-001') ? 'Allowed' : 'Restricted'}</span></td></tr>)}</tbody></table></div></section></>}
  </div>
}

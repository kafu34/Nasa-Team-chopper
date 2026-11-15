import { createContext, useContext } from 'react'
import { DEMO, type AccessMatrix } from './api'

export type DemoAccessValue = {
  matrix: AccessMatrix | null
  viewerId: string
  setViewerId: (id: string) => void
  can: (action: string, recordOwnerId?: string) => boolean
}

// Standalone component tests use the default; the app always supplies a matrix-backed value.
const fallback: DemoAccessValue = { matrix: null, viewerId: DEMO.responderId, setViewerId: () => {}, can: () => true }
export const DemoAccessContext = createContext<DemoAccessValue>(fallback)
export const useDemoAccess = () => useContext(DemoAccessContext)

export function allowed(matrix: AccessMatrix | null, viewerId: string, action: string, recordOwnerId?: string) {
  const role = matrix?.personnel.find(person => person.person_id === viewerId)?.role_code
  const permission = matrix?.permissions.find(item => item.action === action)
  return Boolean(role && permission && (permission.allowed_roles.includes(role) || permission.own_record_allowed && role === 'crew_member' && recordOwnerId === viewerId))
}

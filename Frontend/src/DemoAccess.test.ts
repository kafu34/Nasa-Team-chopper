import { describe, expect, it } from 'vitest'
import { allowed } from './DemoAccess'
import type { AccessMatrix } from './api'

const matrix: AccessMatrix = { role_codes: ['crew_member', 'crew_medical_officer', 'flight_surgeon', 'ground_support'], personnel: [{ person_id: 'DEMO-001', display_name: 'Crew', role_code: 'crew_member', kind: 'crew', location: 'habitat' }, { person_id: 'DEMO-002', display_name: 'Officer', role_code: 'crew_medical_officer', kind: 'crew', location: 'habitat' }, { person_id: 'GND-FS-01', display_name: 'Surgeon', role_code: 'flight_surgeon', kind: 'ground', location: 'ground' }, { person_id: 'GND-SUP-01', display_name: 'Support', role_code: 'ground_support', kind: 'ground', location: 'ground' }], permissions: [{ action: 'case.read_sensitive', allowed_roles: ['crew_medical_officer', 'flight_surgeon'], own_record_allowed: true, description: 'Read a case' }, { action: 'case.resolve', allowed_roles: ['crew_medical_officer', 'flight_surgeon'], own_record_allowed: false, description: 'Resolve a case' }, { action: 'inventory.update', allowed_roles: ['crew_member', 'crew_medical_officer'], own_record_allowed: false, description: 'Update equipment' }], limitation: 'Self-declared identities.' }

describe('published role matrix', () => {
  it('allows own-record reads but does not extend them to closure or ground support', () => {
    expect(allowed(matrix, 'DEMO-001', 'case.read_sensitive', 'DEMO-001')).toBe(true)
    expect(allowed(matrix, 'DEMO-001', 'case.read_sensitive', 'DEMO-002')).toBe(false)
    expect(allowed(matrix, 'DEMO-001', 'case.resolve')).toBe(false)
    expect(allowed(matrix, 'DEMO-002', 'case.resolve')).toBe(true)
    expect(allowed(matrix, 'GND-FS-01', 'case.resolve')).toBe(true)
    expect(allowed(matrix, 'GND-SUP-01', 'case.read_sensitive', 'DEMO-001')).toBe(false)
    expect(allowed(matrix, 'GND-SUP-01', 'inventory.update')).toBe(false)
    expect(allowed(null, 'DEMO-001', 'case.read_sensitive', 'DEMO-001')).toBe(false)
  })
})

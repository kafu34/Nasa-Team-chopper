import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Monitoring } from './Monitoring'
import { syntheticBatch } from './MonitoringActions'
import { ProcedureCoach } from './ProcedureCoach'
import type { SessionOut } from './api'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('proactive monitoring presentation', () => {
  it('keeps data-quality exclusions separate from concerns and shows the backend disclaimer', async () => {
    const disclaimer = 'Configured demonstration rule. A deviation is not a diagnosis.'
    const monitoring = {
      astronaut_id: 'DEMO-001', ruleset_version: 'DET-1.0', baseline_method_id: 'BASELINE-1.0', generated_at: '2026-11-15T08:00:00Z', disclaimer,
      types: [{ type: 'heart_rate', unit: 'bpm', freshness: 'stale', rule_id: 'DET-HR-01', baseline: null, latest_value: null, latest_observed_at: null, latest_quality: null, difference_from_baseline: null, latest_detection: { gate: 'excluded_poor_quality', outcome: 'excluded_poor_quality', explanation: 'Poor source quality; not used for detection.', disclaimer, rule_id: 'DET-HR-01', deviating_count: 0, required_count: 3, alert_raised: false, alert_suppressed: false }, trend: { readings: 0, window_minutes: 180, description: 'insufficient_readings' }, open_concern_id: null }],
      concerns: [], data_quality: [{ type: 'heart_rate', issue: 'recent_poor_quality', note: 'Take a new reading.' }],
    }
    const fetchMock = vi.fn((path: string) => Promise.resolve({ ok: true, status: 200, text: async () => JSON.stringify(path.includes('/monitoring?') ? monitoring : path.endsWith('/baselines') ? { baselines: [] } : { rules: [] }) }))
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter><Monitoring onCaseOpened={() => {}} onCaseDetected={() => {}} /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('Take a new reading.')).toBeInTheDocument())
    expect(screen.getAllByText(disclaimer).length).toBeGreaterThan(0)
    expect(screen.getByText(/No monitoring concern has been opened/)).toBeInTheDocument()
    expect(screen.getByText('Not recorded')).toBeInTheDocument()
    expect(screen.queryByText('Not recorded bpm')).not.toBeInTheDocument()
  })
  it('makes synthetic scenarios explicit inputs without assigning a detection outcome', () => {
    const now = Date.parse('2026-11-15T08:00:00Z')
    const sustained = syntheticBatch('sustained', now)
    expect(sustained.map(item => item.value)).toEqual([84, 86, 88])
    expect(sustained.map(item => item.observed_at)).toEqual(['2026-11-15T07:40:00.000Z', '2026-11-15T07:50:00.000Z', '2026-11-15T08:00:00.000Z'])
    const quality = syntheticBatch('quality', now)
    expect(quality.map(item => item.quality)).toEqual(['good', 'poor', 'poor'])
    expect(quality[0].observed_at).toBe('2026-11-15T03:00:00.000Z')
    expect(syntheticBatch('repeat', now)[0]).toEqual(syntheticBatch('repeat', now)[1])
  })
  it('interrupts a routine procedure when the backend reports another urgent case', () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    const session = { session_id: 'SES-1', case_id: 'CASE-ROUTINE', procedure_id: 'PROC-BP-01', procedure_version: '1', mode: 'self', status: 'in_progress', current_step_id: null, current_step: null, completed_steps: [], case_state: 'awaiting_results', case_priority: 'routine', urgent_events: [{ case_id: 'CASE-URGENT', kind: 'emergency', state: 'escalated', priority: 'urgent', next_action: 'Follow urgent emergency instructions.', reason: 'Emergency reported' }] } as SessionOut
    render(<MemoryRouter><ProcedureCoach caseId="CASE-ROUTINE" equipment={null} procedure={null} session={session} measurement={null} onProcedure={() => {}} onSession={() => {}} onMeasurement={() => {}} onCaseRefresh={async () => null} /></MemoryRouter>)
    expect(screen.getByRole('alert')).toHaveTextContent('Urgent case interruption.')
    expect(screen.getByRole('alert')).toHaveTextContent('Follow urgent emergency instructions.')
    expect(screen.getByRole('link', { name: 'Open emergency assistance' })).toHaveAttribute('href', '/emergency')
  })
})

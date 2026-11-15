import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, type ProcedureStep, type SessionOut, type StepEventOut } from './api'
import { useStepEvents } from './step-events'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

const step = (id: string, action: string) => ({ step_id: id, order: Number(id.slice(1)), title: id, instruction: 'Fictional instruction', responder_note: '', target_region_id: 'upper_arm', target_laterality: 'left', target_site_id: null, equipment: { required_capability: 'blood_pressure', compatible_device_models: ['Demo'], components: ['cuff'] }, instruction_source_ids: [], warnings: [], requires_confirmation: true, visual: { action_id: action } }) as unknown as ProcedureStep
const session = (views = 0): SessionOut => ({ session_id: 'SES-1', case_id: 'CASE-1', procedure_id: 'PROC-BP-01', procedure_version: '1.1.0-demo', actor_id: 'DEMO-001', mode: 'self', status: 'in_progress', current_step_id: 'S1', current_step: null, completed_steps: [], case_state: 'awaiting_results', step_states: [{ step_id: 'S1', visual_action_id: 'VA-BP-01', displayed_at: null, view_count: views, replay_count: Math.max(0, views - 1), last_viewed_at: null, visual_unavailable: false, acknowledged_at: null, completion_source: null }] })
const ok = { event_id: 'EVT-1', session_id: 'SES-1', recorded_at: '', duplicate: false } as unknown as StepEventOut

function Probe({ s, target, available }: { s: SessionOut | null; target: ProcedureStep; available: boolean }) {
  const { recordViewed, recordError } = useStepEvents(s, target, available)
  return <div><button type="button" onClick={() => recordViewed(target)}>played</button>{recordError && <p>{recordError}</p>}</div>
}

describe('procedure step events (contract 2.4.0)', () => {
  it('records the instruction once per step, with a stable client ID and the step action', async () => {
    const rec = vi.spyOn(api, 'recordStepEvent').mockResolvedValue(ok)
    const target = step('S1', 'VA-BP-01')
    const view = render(<Probe s={session()} target={target} available />)
    view.rerender(<Probe s={session()} target={target} available />)
    await waitFor(() => expect(rec).toHaveBeenCalledTimes(1))
    expect(rec).toHaveBeenCalledWith('SES-1', expect.objectContaining({ step_id: 'S1', event_type: 'instruction_displayed', visual_action_id: 'VA-BP-01', actor_id: 'DEMO-001', client_event_id: 'SES-1:S1:instruction_displayed' }))
  })

  it('records an unavailable scene instead of a display', async () => {
    const rec = vi.spyOn(api, 'recordStepEvent').mockResolvedValue(ok)
    render(<Probe s={session()} target={step('S1', 'VA-BP-01')} available={false} />)
    await waitFor(() => expect(rec).toHaveBeenCalledWith('SES-1', expect.objectContaining({ event_type: 'visual_unavailable' })))
  })

  it('sends a first play as viewed and a later play as replayed, from the backend count', async () => {
    const rec = vi.spyOn(api, 'recordStepEvent').mockResolvedValue(ok)
    const target = step('S1', 'VA-BP-01')
    const view = render(<Probe s={session(0)} target={target} available />)
    fireEvent.click(screen.getByRole('button', { name: 'played' }))
    await waitFor(() => expect(rec).toHaveBeenCalledWith('SES-1', expect.objectContaining({ event_type: 'animation_viewed' })))
    view.rerender(<Probe s={session(1)} target={target} available />)
    fireEvent.click(screen.getByRole('button', { name: 'played' }))
    await waitFor(() => expect(rec).toHaveBeenCalledWith('SES-1', expect.objectContaining({ event_type: 'animation_replayed' })))
  })

  it('sends nothing without a session and never blocks on a failed record', async () => {
    const rec = vi.spyOn(api, 'recordStepEvent').mockRejectedValue(new Error('Local backend unreachable'))
    const target = step('S1', 'VA-BP-01')
    const view = render(<Probe s={null} target={target} available />)
    expect(rec).not.toHaveBeenCalled()
    view.rerender(<Probe s={session()} target={target} available />)
    expect(await screen.findByText('Local backend unreachable')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'played' })).toBeEnabled()
  })
})

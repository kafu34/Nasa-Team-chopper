import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type ProcedureStep, type SessionOut, type StepEventType, type StepState } from './api'

// Records what the coach actually showed in the backend's session record (contract 2.4.0,
// POST /procedure-sessions/{id}/events), so display and viewing survive reloads and other devices.
// These are visual records only: they never acknowledge, reorder or complete a real-world step.
// A failed record never blocks the procedure; the coach shows a quiet note instead.

export function stepStateFor(session: SessionOut | null, stepId: string | undefined): StepState | undefined {
  return stepId ? session?.step_states?.find(item => item.step_id === stepId) : undefined
}

export function useStepEvents(session: SessionOut | null, step: ProcedureStep | undefined, sceneAvailable: boolean, onRecorded?: () => void) {
  const [recordError, setRecordError] = useState<string | null>(null)
  const sent = useRef(new Set<string>())
  const onRecordedRef = useRef(onRecorded); onRecordedRef.current = onRecorded
  const sessionId = session?.session_id
  const actorId = session?.actor_id

  const record = useCallback(async (eventType: StepEventType, target: ProcedureStep, clientEventId: string) => {
    if (!sessionId || !actorId) return
    try {
      await api.recordStepEvent(sessionId, { step_id: target.step_id, event_type: eventType, visual_action_id: target.visual.action_id, actor_id: actorId, client_event_id: clientEventId, occurred_at: new Date().toISOString() })
      setRecordError(null)
      onRecordedRef.current?.()
    } catch (cause) {
      sent.current.delete(clientEventId) // allow a later retry of the same once-per-step record
      setRecordError(cause instanceof Error ? cause.message : 'The visual record could not be saved.')
    }
  }, [sessionId, actorId])

  // Once per step per session: the instruction was shown, or its visual scene is unavailable.
  useEffect(() => {
    if (!sessionId || !step) return
    const kind: StepEventType = sceneAvailable ? 'instruction_displayed' : 'visual_unavailable'
    const id = `${sessionId}:${step.step_id}:${kind}`
    if (sent.current.has(id)) return
    sent.current.add(id)
    void record(kind, step, id)
  }, [sessionId, step, sceneAvailable, record])

  // Every completed play: the first is a view, later ones are replays (judged from the backend's own count).
  const recordViewed = useCallback((target: ProcedureStep) => {
    if (!sessionId) return
    const views = stepStateFor(session, target.step_id)?.view_count ?? 0
    const kind: StepEventType = views > 0 ? 'animation_replayed' : 'animation_viewed'
    void record(kind, target, `${sessionId}:${target.step_id}:${kind}:${Date.now()}`)
  }, [sessionId, session, record])

  return { recordViewed, recordError }
}

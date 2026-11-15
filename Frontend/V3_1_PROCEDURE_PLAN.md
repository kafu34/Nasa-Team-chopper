# Milestone 3: visual BP procedure build plan

## Contract and current-state audit

The current `ProcedureCoach` loads `PROC-BP-01`, starts a backend session, lists six text instructions, acknowledges steps in order, and submits a simulated reading. It has no 3D equipment, animation, visual-action registry, pause/replay controls or session restoration after refresh. Contract 2.3.0 provides `visual_requirements`, six distinct `step.visual.action_id` values, asset IDs, camera targets, warnings and `GET /procedure-sessions/{id}`. It does not expose a durable animation-view event; an animation cannot be claimed as backend-verified clinical execution.

The existing human GLB is a static anatomical reference, not a rigged procedure patient. The visual coach will use it for full-body context and a separately labelled 3D closeup for equipment-to-arm interactions. The arm closeup is educational geometry, not a scan or mission-approved device fitting. If the supported posture cannot be convincingly shown with this static body, the affected acceptance item remains PARTIAL rather than being silently counted complete.

## Build sequence

1. Read the six backend visual contracts and inventory identity.
2. Inspect existing procedure/session UI and relevant API types.
3. Write this plan and identify limitations before code changes.
4. Extend TypeScript procedure and session models from contract 2.3.0.
5. Add a visual-action and asset registry with exactly the six required actions.
6. Build reusable 3D monitor, adult cuff, restraint, anatomical body and arm closeup assets.
7. Build scene 1: monitor/cuff preparation, supported restraint and rest cue.
8. Build scenes 2 and 3: bare left upper arm focus and cuff wrapping on the arm with orientation/finger-fit cues.
9. Build scene 4: visibly supported cuffed arm at approximate heart level with explicit microgravity limitation.
10. **Review steps 1–9:** inspect actual geometry, source alignment, equipment identity and any misleading posture; revise remaining work and record reflection.

### Step 10 review and reflection

The shared scene renderer was built in one pass, including the geometry later used by steps 11–12. Browser inspection showed the preparation monitor and measurement monitor clipped by the initial camera, and the sleeve too large relative to the arm. I widened those views, resized the sleeve, and added a visible arm under the measurement cuff. The supported-arm scene uses its own labelled 3D schematic; the static anatomical body cannot demonstrate a bent, supported arm. The contract's microgravity limitation remains visible. The efficient remainder is to finish framing the simulated reading, then validate the six actions and session workflow against the live isolated backend before any completion claim.
11. Build scene 5: press monitor start, then cuff inflation/deflation and progress display.
12. Build scene 6: labelled simulated readings, cuff removal and matching entry fields.
13. Add pause/replay, progress indication, scene selection and reduced-motion behaviour.
14. Bind scenes to backend `action_id`/asset IDs; show unavailable state for unknown actions or assets.
15. Keep animation viewed, step acknowledged and measurement recorded as distinct UI states.
16. Restore procedure and session state via backend GET using a locally retained session ID; clear stale IDs.
17. Test each action/asset mapping, session restoration and disabled/unavailable states.
18. Run the app against an isolated backend and capture all six running scenes.
19. Run build, frontend and real HTTP regression checks; review ownership and commit/push/merge the verified frontend work.
20. **Review steps 11–19 and reflect:** classify every acceptance item, report limits and identify the next milestone.

### Step 20 review and reflection

The final browser pass ran all six backend-defined scenes, paused and resumed a scene, replayed a scene, created a fictional case and backend session, acknowledged six steps, refreshed at step 2, and submitted a 118/76 mmHg simulated reading. The backend restored the session and accepted the reading with technical checks passed. The frontend build and 28 unit tests pass, including a fixture-to-registry test. The live browser pass is the integration evidence; the backend pytest suite was not run in this worktree because its Python environment has no `pytest` installed.

**Milestone 3 status: PARTIAL. Validation level: EDUCATIONAL_DEMONSTRATION.** The six scenes and measurement path function, but the backend contract has no animation-view/replay persistence endpoint. The frontend records that state only in browser storage, separate from backend acknowledgement. Also, this isolated backend did not supply an equipment registry, so the live run could not demonstrate matching the model to a selected inventory item. The supported-arm view uses a labelled schematic because the available anatomical body is static, and the scene assets are educational geometry rather than hardware-tested device models. These items must remain visible in the acceptance record; they cannot be counted as complete clinical or mission approval.

The next efficient handoff is for the backend to expose a durable visual-event field or endpoint tied to session and step, plus a selectable compatible inventory item in the test state. The frontend can then bind viewed/replayed events to that contract and verify identity against the selected item. An articulated body asset would allow the supported posture to be shown on the anatomical figure itself.

## Design brief

Keep the mission-console palette and current workflow. The main procedure view should prioritize one large scene, step title, instruction, playback controls and acknowledgement. Show the selected backend device identity and educational validation level next to the scene. Use distinct camera framing and equipment motion per step. All playback controls need keyboard access and at least 44 px targets. The simulation must not generate a clinical reading or complete a backend step by animation alone.

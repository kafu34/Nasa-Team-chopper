# Milestones 6 and 7 — communications and environment plan

Contract 2.10.0 is current on the backend branch and main. This software-only part uses its simulated communications queue and attributed RadLab context. It changes frontend-authored files only. Ground communication remains delayed and can fail; onboard response never waits for it. RadLab is NASA research data, not a habitat measurement or personal dose. No health relationship is inferred. The original 20-step planning and review rhythm applies.

1. Confirm the clean worktree, latest remote contract and frontend ownership.
2. Read §11 of the handoff, schemas, emergency response and acceptance limits.
3. Locate existing navigation, emergency, monitoring and research UI entry points.
4. Define typed frontend models and API calls for the link, messages, acknowledgement and environment.
5. Build a communications view that first shows simulated link state, delay and queue status.
6. Show message priority, direction, status, case, timestamps and receiving role from backend records.
7. Add a crew-to-ground compose action with actor, subject, body, priority and optional current case.
8. Give each send attempt a stable client message ID so retry after a lost response does not duplicate a message.
9. Add receiving-side acknowledgement only for delivered messages, using the demo ground or crew actor as appropriate.
10. **Review and reflect:** compare roles, status transitions, retry and outage language against backend ownership; simplify any unsupported control.
11. Add a clearly labelled simulated link control for demonstration, with actor and reason recorded by the backend.
12. Connect emergency escalation's backend message ID to its queue record without delaying onboard instructions.
13. Build environmental context display with RadLab provenance, instrument, value, unit and source row.
14. Show the backend caution and explicit non-habitat, non-personal-dose, no-inferred-relationship flags; show NASA-EDA as blocked.
15. Add focused UI tests for queue states, role-sensitive acknowledgement and environment cautions.
16. Run the full frontend test suite and production build.
17. Test real send, queued/in-transit state, simulated outage and emergency link in an isolated 2.10.0 backend browser run.
18. Test environment in desktop and narrow viewports, capture screenshots, and check the diff for frontend-only authorship.
19. Commit and push this part; fast-forward main only if its remote history remains an ancestor.
20. **Review and reflect:** record verified Milestone 6 and 7 progress, remaining role/follow-up UI work and software limits.

## Step 10 review gate

The link control must say it is simulation. A sender cannot acknowledge their own outbound message; the receiving-side demo actor is required, and the button appears only after backend delivery. The UI must use `deliver_at` rather than computing a promised arrival. A retry must reuse the original `client_message_id` after uncertainty, while a new authored message needs a new ID. An emergency queue record cannot be presented as delivered until the backend says so. Environmental readings stay in NASA research context and must never drive a medical alert.

## Step 10 reflection

The communications view uses the backend queue and link state, shows the 300-second configured delay and only offers acknowledgement for a delivered message when the selected demo viewpoint is its receiver. The role selector explicitly says identities are self-declared. A send retry preserves its client message ID for the same draft; editing the draft makes a new ID. Simulated link changes use the backend with a stated reason. The emergency screen now links the backend escalation message ID to the queue and says onboard response does not wait for delivery. Environmental context is a separate research-labelled view and never feeds alert logic. The next checks are TypeScript, focused tests and real backend/browser transitions; those can reveal schema or layout errors before this part is accepted.

## Step 20 review and reflection

The isolated 2.10.0 browser scenario queued a crew message while the simulated link was down, then showed it in transit after restoration with the backend's expected arrival time. A fictional emergency queued urgent message `MSG-6D8D8B435A`, and its response link opened that same queue record. The environment page showed imported historical ISS RadLab readings, units, instrument and source rows with the backend caution, and NASA-EDA's `NOT_DOWNLOADED` status plus `BLOCKED` note. Desktop and narrow-screen screenshots are indexed in `evidence/README.md`. A review of the longer navigation found that emergency assistance could leave the desktop viewport on long pages, so the sidebar was made sticky and visually rechecked. The shutdown log contained one transient communications-list 500 during the run; the two state-advancing reads had been issued concurrently. They are now sequential, and a direct list read on the same disposable database returned 200. This is a likely concurrency explanation, not a proven backend root cause. All 43 frontend tests pass and the production build succeeds after the change. The remaining frontend work is role/access presentation and case/follow-up operations; an interactive delivered-message acknowledgement still needs its own timed browser check, while the backend tests already cover that transition. This part changes frontend files only and uses no hardware.

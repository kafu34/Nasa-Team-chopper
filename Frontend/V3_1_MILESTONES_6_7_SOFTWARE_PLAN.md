# v3.1 Milestones 6 and 7 — software-only build plan

## Contract and scope audit

At the start of this first slice, the shared contract was 2.8.0. It supports three educational assessment procedures, case requested assessments, equipment recommendations, a habitat inventory, scheduled assessments in demo bootstrap, follow-up records, monitoring investigations and role-gated concern review. It has no screening schedule management, diagnostic coordination decision record, communication queue, environmental health-correlation service or broad medical authorisation contract. Those require Claude's versioned backend work; the frontend must show current data honestly and must not create local substitutes. Hardware adapters, positioning hardware and calibrated AR are deferred at the user's request. This plan covers a first vertical slice of both milestones, followed by contract-driven slices as backend work lands.

## Part-by-part sequence

1. Confirm Git state, the latest pushed Claude contract, and frontend ownership.
2. Compare v3.1 Milestones 6 and 7 acceptance text with current screens and the 2.8.0 OpenAPI paths.
3. Identify the next independent frontend slice: case assessment coordination plus explicit local-backend loss and recovery.
4. Record current case, equipment, schedule and follow-up data shapes; do not infer missing backend decisions.
5. Add a case assessment panel that shows the backend's requested procedure, capability, status and reason.
6. Connect that panel to existing equipment and procedure screens, while clearly showing when no recommendation has been requested.
7. Show recommended device readiness, location, excluded alternatives and route status from the backend response.
8. Present scheduled assessments and follow-ups with due/overdue state calculated from backend timestamps; do not create or acknowledge schedules locally.
9. Add a visible local-service status and retry control that never labels a failed write as saved.
10. **Review and reflect:** check stale-data wording, case/device matching, urgent priority, time calculations and backend ownership. Simplify the remaining slice if a field is unavailable.
11. Refresh bootstrap and active case after service recovery without discarding the last known view during a transient outage.
12. Make the emergency path available when the service is down and state clearly that activation still requires the backend.
13. Add focused tests for case coordination, schedule states and service-loss/recovery behaviour.
14. Run the frontend build and tests; fix any type or accessibility issues.
15. Start an isolated 2.8.0 backend and test a real case-to-device-to-procedure route in the browser.
16. Stop the backend briefly, verify the loss banner and failed-write honesty, then restart and verify recovery.
17. Inspect desktop and narrow-screen layouts; capture screenshots for visual acceptance.
18. Recheck the diff for backend-owned edits, accidental local database files and unsupported claims.
19. Commit and push the frontend slice; fast-forward the shared branch only if its remote history remains an ancestor.
20. **Review and reflect:** classify exactly which Milestone 6 and 7 acceptance items advanced, and hand Claude a precise list of missing contracts for later slices.

## Step 10 review gate

Before implementing the second half, compare the rendered panel and service state against the backend contract. If a displayed recommendation belongs to another case or capability, suppress it. Treat scheduled and follow-up timestamps as backend facts and due labels as display calculations. Keep urgent instructions visible independently of service status. No medical decision or durable acknowledgement is invented in the browser.

## Step 10 reflection

The first build passes. Case-bound equipment state now prevents a recommendation from a previous case appearing in the new case or procedure coach. The panel only calls a device suitable when its procedure ID matches the backend's requested assessment; otherwise it directs the crew to request a recommendation. A review found that `scheduled_assessments.is_due` must override wall-clock calculation because the backend can advance fictional scenario time, so this was corrected before browser checks. Urgent priority remains above the coordination panel and the emergency route remains independent of backend data loading. The service banner describes retained information as potentially stale and does not claim failed writes are queued. The next verification is live outage/recovery, where the current screen must remain navigable without a false saved state.

## Step 20 review and reflection

This first software slice advances Milestone 6 assessment coordination and schedule/follow-up presentation, and Milestone 7 local-service failure disclosure and recovery. The isolated 2.8.0 browser scenario opened a temperature concern, requested `PROC-TEMP-01`, selected ready `EQ-THERM-01` after a zone confirmation, returned a route, and showed the linked case state. Stopping the backend left the open browser view available with a sticky stale-data banner; a case refresh and emergency activation attempt failed without a saved-result claim. Restarting the backend refreshed bootstrap and the active case. Desktop and narrow-screen screenshots are indexed in `evidence/README.md`. The test suite has 39 passing tests and the production build succeeds; the existing large chunk warning remains. At this first-slice checkpoint, the full milestone outcomes remained PARTIAL: 2.8.0 lacked durable diagnostic decisions, screening management, inventory operations, general follow-up actions, broad role enforcement, environmental health context, communications queues and an offline write/reconciliation policy. `V3_1_MILESTONES_6_7_BACKEND_HANDOFF.md` states the needed contracts. Hardware and calibrated AR remain deferred by the user. The next efficient frontend build should follow the next versioned backend contract and a shared scenario, while keeping the current software workflow intact.

## Subsequent contract update

Claude then pushed 2.9.0 and 2.10.0, adding screening, roles, communications, environmental context and recovery. The next part follows the separate 20-step plan in V3_1_CONTRACT_2_10_PLAN.md. The earlier gaps above describe the 2.8.0 checkpoint, not the current backend.

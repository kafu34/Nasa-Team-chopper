# Contract 2.11.0 frontend plan — inventory and case resolution

Claude's 2.11.0 backend commit is merged into this worktree. This part remains software-only and edits frontend-authored files. Inventory changes and case resolution are controlled backend operations; a UI action does not imply success until the backend returns the new state. Follow-up cancellation is an explicit choice. The user's 20-step planning cadence applies.

1. Confirm the 2.11.0 merge, clean tree, exact inventory and resolution schemas.
2. Inspect current map/equipment and case/follow-up views for the right entry points.
3. Add typed equipment list/update and case-resolution API operations, including structured error details.
4. Load authoritative inventory on the location/equipment screen instead of relying on bootstrap's older summary.
5. Show usability, readiness-check age, supplies, zone and every backend unusable reason.
6. Add crew-role device status editing with readiness, supplies, zone and an audit note.
7. Make the update result show invalidated recommendation IDs and affected sessions without claiming sessions were cancelled.
8. Clear any active frontend recommendation invalidated by a successful device update and require a new backend route.
9. Show backend case resolution fields and acknowledgement state in the case view.
10. **Review and reflect:** verify the inventory UI never treats stale checks as ready and the case UI does not bypass blockers.
11. Add manual case acknowledgement with actor role and distinguish it from resolution.
12. Add controlled resolution form for crew medical officer or flight surgeon, note and explicit follow-up cancellation choice.
13. Show all returned 409 blockers and backend warnings; only display resolved after a successful response.
14. Refresh case and bootstrap after resolution so attention and open-case counts come from the backend.
15. Add focused tests for inventory invalidation, blocker handling and follow-up cancellation choice.
16. Run full frontend tests and production build.
17. Test readiness update and recommendation invalidation against isolated 2.11.0 backend in a browser.
18. Test a blocked case resolution and a successful resolvable case, then inspect desktop/narrow layouts and capture screenshots.
19. Check frontend-only authorship and remote ancestry, then commit and push the verified part.
20. **Review and reflect:** record which Milestones 6 and 7 outcomes advanced and the remaining role-access and timed-communications validation.

## Step 10 review gate

The backend owns `usable`, `unusable_reasons`, readiness timestamps and route invalidation. A changed device can invalidate other capability routes, so the frontend must suppress a cached recommendation when its ID is in the backend invalidation list. Sessions listed as affected remain in progress. A 409 blocker is not a success state. Case resolution is manual, role-restricted, audited and cannot silently cancel follow-ups. The emergency path must remain visible.

## Step 10 reflection

The typed client builds with the new inventory and case operations. The device panel uses `usable` and backend reason codes, and clears an active recommendation when the update reports its ID as invalidated or changes the selected device. An editor review found that mapping a legacy `ready` value to `verified_ready` would silently create a fresh check, so the default now leaves readiness unchanged until a crew actor explicitly selects verification. The case form defaults follow-up cancellation to off and surfaces structured 409 blockers. A resolved urgent case keeps its priority in the backend, but the frontend no longer displays the active urgent interruption banner after `state=resolved`. The next gate is focused tests and live 2.11.0 browser flows.

## Step 20 review and reflection

The isolated 2.11.0 browser run opened a routine BP case, confirmed Medical Bay, and received BP device `EQ-BP-01` with route `REC-30FE377697`. Changing the device to `needs_service` returned that recommendation ID as invalidated, and the selected device/route disappeared from the frontend. A resolution attempt on the in-progress BP case showed all three backend blockers and kept the case open. After a demo reset, a fictional emergency case was acknowledged without resolving, then manually resolved by `DEMO-002`. The backend kept urgent priority, set interrupt false and returned an unacknowledged-ground-message warning; the UI displayed the warning and stopped treating the case as an active urgent interruption. Its URL now carries the case ID so the resolved record survives reload. Desktop and narrow screenshots are indexed in `evidence/README.md`. The full frontend suite has 45 passing tests with no unhandled errors, and the production build succeeds. An early full run exposed an unexpected-payload crash in the inventory panel; response-shape validation fixed it before this review. Remaining work is role/access presentation and two timed or follow-up browser scenarios listed in the handoff. No hardware was added.

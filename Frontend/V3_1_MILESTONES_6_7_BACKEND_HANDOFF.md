# Milestones 6 and 7 — contract 2.11.0 handoff

Claude's 2.9.0 and 2.10.0 commits arrived during the first frontend slice; 2.11.0 arrived while the communications/environment slice was being finished. The backend now supplies durable screening, a role matrix, a simulated medical communications queue, RadLab context, recovery, controlled inventory status updates and manual case resolution. The frontend consumes screening, reminders, assessment start, recovery, communications, environment, inventory, case-resolution and role-matrix endpoints. The earlier 2.8.0 list of missing contracts is superseded.

## Remaining frontend work

1. **Controlled closure follow-up scenario:** inventory invalidation and blocked/successful case resolution have live browser evidence. Follow-up cancellation is supported and unit-tested in the frontend, and backend-tested, but still needs one interactive browser scenario with an actual outstanding follow-up. A request to create a disposable BP assessment fixture for that check was rejected, so no alternative setup was attempted.

## Verified frontend work

The header selects one fictional backend person for viewer-checked case, monitoring and observation-history reads and for role-checked concern review, baseline recomputation, case acknowledgement/resolution, inventory updates, hatch changes and ground messages. `/access` displays the published permission matrix and the no-authentication limit. A local browser check showed crew member `DEMO-001` reading their own monitoring record, ground support `GND-SUP-01` receiving backend 403 `ROLE_NOT_PERMITTED` for that read, and ground support seeing no hatch/device update controls. Desktop and narrow role-screen screenshots were captured during the browser check. The full frontend suite passed 46 tests and the production build passed.

For communications, a fictional `DEMO-001` message `MSG-C258849B75` moved from `in_transit` to `delivered` after the real 300-second simulated one-way delay. Ground support `GND-SUP-01`, an allowed receiving-side role, acknowledged it in the browser; the queue showed `acknowledged`, the actor and timestamp. No real Earth link was involved.

## Backend limits to retain in the UI

The local server cannot accept writes while unavailable, and the frontend does not queue medical actions. `/system/recovery` supplies work to restore after the server returns; it does not reconcile offline writes. The communications link is simulated and has no real ground system. There is no authenticated identity. The 2.11.0 backend's resolved emergency response retains an obsolete `URGENT: crew response in progress` prefix in `next_action` while setting `attention.interrupt` to false; the frontend removes that prefix in the resolved-case display and does not schedule it as an urgent reminder. Hardware adapters, positioning hardware and calibrated AR are outside the user's software-only scope.

The backend acceptance level is recorded in `docs/ACCEPTANCE_RECORD.md`; frontend completion still requires interactive browser and visual checks for each new screen.

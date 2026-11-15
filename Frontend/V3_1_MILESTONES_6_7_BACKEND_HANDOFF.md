# Milestones 6 and 7 — contract 2.11.0 handoff

Claude's 2.9.0 and 2.10.0 commits arrived during the first frontend slice; 2.11.0 arrived while the communications/environment slice was being finished. The backend now supplies durable screening, a role matrix, a simulated medical communications queue, RadLab context, recovery, controlled inventory status updates and manual case resolution. The frontend consumes screening, reminders, assessment start, recovery, communications and environment endpoints. The earlier 2.8.0 list of missing contracts is superseded.

## Remaining frontend work

1. **Roles and access:** present the published role matrix and apply a consistent demo viewer identity to sensitive reads/actions. Backend identities are self-declared; no authentication exists.
2. **Inventory and case resolution:** wire 2.11.0 `/equipment` and controlled status updates, including recommendation invalidations and affected sessions. Present resolution blockers, warnings, actor restrictions and audited follow-up cancellation from `/cases/{id}/resolve`. Do not label a case resolved until the backend returns it.
3. **Communications final validation:** the new queue, send, simulated link and emergency reference have live browser evidence; a delivered message and receiving-side acknowledgement still need an interactive browser check after the configured five-minute simulated delay or a supported clock scenario. The backend has automated coverage, and frontend role/status controls have focused tests.

## Backend limits to retain in the UI

The 2.11.0 backend can update fictional device readiness, but the frontend has not wired that operation yet. The local server cannot accept writes while unavailable, and the frontend does not queue medical actions. `/system/recovery` supplies work to restore after the server returns; it does not reconcile offline writes. The communications link is simulated and has no real ground system. There is no authenticated identity. Hardware adapters, positioning hardware and calibrated AR are outside the user's software-only scope.

The backend acceptance level is recorded in `docs/ACCEPTANCE_RECORD.md`; frontend completion still requires interactive browser and visual checks for each new screen.

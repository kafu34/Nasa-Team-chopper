# Milestones 6 and 7 — contract 2.11.0 handoff

Claude's 2.9.0 and 2.10.0 commits arrived during the first frontend slice; 2.11.0 arrived while the communications/environment slice was being finished. The backend now supplies durable screening, a role matrix, a simulated medical communications queue, RadLab context, recovery, controlled inventory status updates and manual case resolution. The frontend consumes screening, reminders, assessment start, recovery, communications, environment, inventory and case-resolution endpoints. The earlier 2.8.0 list of missing contracts is superseded.

## Remaining frontend work

1. **Roles and access:** present the published role matrix and apply a consistent demo viewer identity to sensitive reads/actions. Backend identities are self-declared; no authentication exists.
2. **Communications final validation:** the new queue, send, simulated link and emergency reference have live browser evidence; a delivered message and receiving-side acknowledgement still need an interactive browser check after the configured five-minute simulated delay or a supported clock scenario. The backend has automated coverage, and frontend role/status controls have focused tests.
3. **Controlled closure follow-up scenario:** inventory invalidation and blocked/successful case resolution have live browser evidence. Follow-up cancellation is supported and unit-tested in the frontend, and backend-tested, but still needs one interactive browser scenario with an actual outstanding follow-up.

## Backend limits to retain in the UI

The local server cannot accept writes while unavailable, and the frontend does not queue medical actions. `/system/recovery` supplies work to restore after the server returns; it does not reconcile offline writes. The communications link is simulated and has no real ground system. There is no authenticated identity. The 2.11.0 backend's resolved emergency response retains an obsolete `URGENT: crew response in progress` prefix in `next_action` while setting `attention.interrupt` to false; the frontend removes that prefix in the resolved-case display and does not schedule it as an urgent reminder. Hardware adapters, positioning hardware and calibrated AR are outside the user's software-only scope.

The backend acceptance level is recorded in `docs/ACCEPTANCE_RECORD.md`; frontend completion still requires interactive browser and visual checks for each new screen.

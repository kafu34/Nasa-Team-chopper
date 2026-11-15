# Milestones 6 and 7 — contract 2.10.0 handoff

Claude's 2.9.0 and 2.10.0 commits arrived during the first frontend slice. The current backend now supplies three durable screening schedules, reminder acknowledgement, routine assessment start, a published role matrix, a simulated medical communications queue, RadLab environmental context and a recovery snapshot. The frontend consumes screening, reminder, start and recovery endpoints in this part. The earlier 2.8.0 list of missing contracts is superseded.

## Remaining frontend work

1. **Medical communications:** show queue status, priorities, delivery delay and ground-link state; integrate emergency escalation's `message_id`. A receiving actor must acknowledge only after delivery. Keep the simulated nature of the link visible.
2. **Environmental context:** show returned RadLab source, unit, instrument and caution. Preserve `is_habitat_reading: false`, `is_personal_dose: false` and `health_relationship: none_inferred`; do not imply a causal health link. NASA-EDA remains blocked.
3. **Roles and access:** present the published role matrix and apply a consistent demo viewer identity to sensitive reads/actions. Backend identities are self-declared; no authentication exists.
4. **Case and follow-up operations:** wire any supported case acknowledgement/review actions with their actor restrictions and audit state. Keep absent operations visibly unavailable instead of inventing client-side completion.

## Backend limits to retain in the UI

Inventory readiness is read-only in the current operational UI. The local server cannot accept writes while unavailable, and the frontend does not queue medical actions. `/system/recovery` supplies work to restore after the server returns; it does not reconcile offline writes. The communications link is simulated and has no real ground system. There is no authenticated identity. Hardware adapters, positioning hardware and calibrated AR are outside the user's software-only scope.

The backend acceptance level is recorded in `docs/ACCEPTANCE_RECORD.md`; frontend completion still requires interactive browser and visual checks for each new screen.

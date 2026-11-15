# SENTINEL AI — Backend acceptance record (v3.1 §8 and §12)

Owner: Claude (backend). Contract **2.11.1**. Recorded 2026-11-15 after plan step 43 (Review 4 followed step 40).
The tests were run, and their results are in `docs/TEST_REPORT.md` (356 passed, 0 failed; HTTP smoke 47/47).

**Status** uses the v3.1 words: COMPLETE, PARTIAL, BLOCKED, NOT STARTED. It covers **only the backend part**.

**Validation level:**
- **Simulated and tested:** automated tests against simulated data.
- **Real data:** imported NASA files.
- **Hardware tested** and **clinically validated:** nothing has reached either level.

A subsystem is complete for the whole product only when Codex's visual and integration criteria also pass.

| v3.1 §8 subsystem | Backend status | Validation level | Evidence (tests) | Not done / limits |
|---|---|---|---|---|
| Health collection | COMPLETE | Simulated and tested | ingestion, batch, validation, source label, freshness, duplicate resubmission, persistence (`test_u`, `test_w`) | Simulated sources only; no device adapters (Milestone 8) |
| Personal baselines | COMPLETE | Simulated and tested | versioned, never automatic, frozen during concerns, concern readings excluded (`test_u`, `test_v`) | Fictional history; method not clinically reviewed |
| Deterioration detection | COMPLETE | Simulated and tested | DET-1.1 sustained-change rule, data-quality gate, scenarios A–C (`test_u`) | Configured demonstration rules, not clinical criteria |
| Autonomous investigation | COMPLETE | Simulated and tested | automatic case, evidence, state machine, review before closure, controlled resolution (`test_u`, `test_v`, `test_za`) | Resolution is manual by design; nothing resolves automatically |
| Diagnostics coordination | COMPLETE | Simulated and tested | compatible ready devices, unavailable and unready devices, routes, hatch invalidation, inventory updates invalidating routes (`test_c`, `test_s`, `test_x`, `test_za`) | Device records are fictional; no hardware is queried |
| Preventive screening | COMPLETE | Simulated and tested | 3 screening types, due/overdue, durable reminders, start without a symptom, recurrence (`test_y`) | Fictional schedule; reminders are created when read (no background worker) |
| Medical action guidance | COMPLETE (backend) | Simulated and tested | 3 versioned, sourced procedures with visual contracts and limitations (`test_p`, `test_x`) | Educational demonstration only; not flight-surgeon reviewed; visuals are Codex's |
| Follow-up | COMPLETE | Simulated and tested | scheduling, due, reassessment with evidence, acknowledgement, controlled closure with blockers and audited cancellation (`test_d`, `test_v`, `test_za`) | — |
| Environmental intelligence | PARTIAL | Real data (RadLab) | attributed RadLab context, no health inference (`test_z`) | NASA-EDA BLOCKED (no source file or importer) |
| Offline operation | COMPLETE (backend) | Simulated and tested | local SQLite only, restart mid-session, mid-outage and mid-transmission, idempotent resend, `/system/recovery` (`test_z`) | Client-side offline behaviour is Codex's |
| Medical communications | COMPLETE | Simulated and tested | durable queue, simulated delay and outage, urgent first, addressee-only acknowledgement (flight surgeon for ground messages, 2.11.1), emergency escalation (`test_z`) | Simulated link; no real ground system |
| Safety and privacy | PARTIAL | Simulated and tested | role matrix, audited denials, viewer-checked sensitive reads, audit trail, protocol versions (`test_w`, `test_y`) | **No authentication**: identities are self-declared. Reads without `viewer_id` stay open for the demo |
| Anatomical Twin (backend) | COMPLETE (backend) | Simulated and tested | model registry, mesh attachment validation, marker migration status (`test_m`, `test_n`, `test_q`) | Exact surface contact cannot be proven by the backend |
| Procedure Coach (backend) | COMPLETE (backend) | Simulated and tested | session state, visual events, device binding, measurement integration (`test_r`, `test_x`) | The registry check covers only PROC-BP-01 until Codex adds the PO and TEMP actions |
| Habitat Intelligence (backend) | PARTIAL | Simulated and tested | geometry, map, hatches, routes, movement simulator (`test_o`, `test_s`, `test_t`) | Zone-only positioning; cannot place a person in a zone with no working anchor |
| Astronaut Attention Manager (backend) | COMPLETE (backend) | Simulated and tested | priority, interrupt flags, deduplication and suppression, urgent protection, `urgent_events` (`test_u`, `test_v`) | Presentation is Codex's |
| NASA research integrity (§9) | COMPLETE for imported data | Real data | 5 datasets imported and kept through every migration and reset (`test_e`, `test_j`, `test_k`, `test_l`) | OSD-195 BLOCKED (processed files not supplied) |
| Milestone 8: hardware and AR | NOT STARTED | — | — | Out of scope by owner decision (2026-11-15) |

Nothing in this record is labelled hardware tested or clinically validated.

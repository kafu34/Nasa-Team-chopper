# Contract 2.10.0 frontend plan — Milestones 6 and 7, next software slice

Claude pushed `6209f80` (screening/access, 2.9.0) and `2abefee` (communications/environment/recovery, 2.10.0) while the first frontend slice was being tested. The merge is in this worktree. The first slice's case coordination and service banner remain useful. This part integrates the newly available durable screening and recovery contracts. Communications, environmental context and access presentation follow as separate parts, all software-only. Backend files are read but not edited.

1. Read the 2.9.0 and 2.10.0 handoff, schemas and fixture for exact endpoint and state names.
2. Compare the existing case panel and service banner with new screening and recovery data.
3. Add typed assessments, reminders and recovery responses to the frontend API.
4. Load the three authoritative assessments and durable reminders for the fictional astronaut.
5. Replace schedule display calculations with backend `due_state`; show due, overdue, upcoming and completed distinctly.
6. Let the crew acknowledge a durable reminder and refresh it from the backend; explain that acknowledgement does not complete an assessment.
7. Let the crew start a due or overdue routine assessment through `/assessments/{id}/start`, using the appropriate actor and mode.
8. Carry the returned case and session into the existing procedure coach without creating a symptom.
9. Load `/system/recovery` after reconnecting and show its open work counts and link state without claiming writes were queued.
10. **Review and reflect:** verify each state comes from the backend, case/session restoration uses returned IDs, and the visual labels remain educational.
11. Add focused tests for screening state, acknowledgement, and routine session handoff.
12. Test recovery counts and stale-data wording with controlled service failure.
13. Run the full frontend test suite and production build.
14. Start isolated backend 2.10.0 and test all three schedule states in a browser.
15. Browser-test one routine assessment start without a symptom and continue to its coach.
16. Browser-test reminder acknowledgement and reloading its durable status.
17. Browser-test service restart and recovery response; capture desktop and narrow-screen evidence.
18. Review diff for frontend-only authorship and update the backend handoff with remaining UI work.
19. Commit and push this part after checking remote ancestry; merge only if the shared branch can fast-forward.
20. **Review and reflect:** classify Milestones 6 and 7 progress and list the remaining 2.10.0 integrations separately.

## Step 10 review gate

The backend owns `due_state` and reminder status; no local date logic should override them. Starting a routine assessment returns both case and session and may join an existing one, so the UI must use the returned IDs and avoid claiming a new session when `session_created` is false. Acknowledging a reminder must leave the assessment itself due. The loss-of-service view must remain visibly stale until recovery data is fetched.

## Step 10 reflection

The typed 2.10.0 client builds, and focused screening/recovery tests pass. The new screening panel loads the authoritative `due_state` and durable reminder records, while the earlier case summary now also prefers `due_state` when it is present. Reminder acknowledgement only changes the reminder; the panel explicitly says that the assessment remains due. Starting a scheduled assessment passes the returned case and session to the existing procedure route, and the expanded coach can accept that session without inventing a symptom or silently creating a second one. The local-service banner requests `/system/recovery` after a failed health period and shows open work counts from that response. The remaining risk is integration behavior under the real 2.10.0 backend, especially a routine start that joins an existing session; browser checks are the next gate. Communications and environmental context are separate parts after this screening/recovery slice.

## Step 20 review and reflection

The isolated 2.10.0 browser run showed all three backend states: overdue temperature, due BP and upcoming pulse oximetry. It acknowledged the overdue temperature reminder, reloaded and found the acknowledgement still recorded while the assessment stayed overdue. Starting that routine assessment returned `CASE-65BDC7D388` and `SES-9134831E5D`; the temperature coach used those IDs and reload retained the in-progress session. At a narrow viewport the schedule and action controls remained usable. On local backend loss the sticky status said data could be stale and writes were not queued. On restart the frontend called `/system/recovery` and displayed one open case, one session, two reminders, zero undelivered messages and link state `up`. The first slice's live device route and emergency guidance checks remain documented separately. The final build and test gate and Git history check follow this review. Milestone 6 screening and assessment handoff advanced; Milestone 7 recovery advanced. Communications, environmental context, role presentation and case/follow-up operations remain frontend work, and the backend limits are recorded in the handoff. No hardware work is included.

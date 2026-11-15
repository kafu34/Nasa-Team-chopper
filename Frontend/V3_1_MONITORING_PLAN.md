# Milestone 5: proactive health intelligence frontend plan

## Gap and contract audit

The current frontend shows bootstrap vitals and case status but has no monitoring history, individual baseline comparison, detection evidence, data-quality view or concern review. Backend contract 2.6.0 on `backend/p0-v2.1` supplies these via `/astronauts/{id}/monitoring`, `/baselines`, `/monitoring/ruleset`, observation ingestion, and concern endpoints. Detection is a configured fictional rule, never a diagnosis. The frontend must render returned values, units, freshness, rule IDs and disclaimers. Baseline recompute and concern review require deliberate user action and backend state.

## Build sequence

1. Inspect the v3.1 Milestone 5 acceptance criteria and existing overview, case, reminder and procedure screens.
2. Read the committed 2.6.0 OpenAPI and handoff schemas and inspect synthetic scenario fixtures.
3. Record the gaps, ownership, validation limits and this implementation plan before code changes.
4. Merge the backend branch into this worktree without editing backend-owned files.
5. Add TypeScript models and API methods for monitoring, baseline versions, rules, observation batch, concern and review.
6. Build a monitoring page with latest readings, freshness, units and individual baseline comparisons.
7. Show detection outcomes, configured rule explanations and the backend disclaimer next to every finding.
8. Show quality problems separately from concerns, with missing/stale/poor-quality distinctions.
9. Show investigation progress, reassessment due state, alert suppression and requested assessment.
10. **Review and reflect:** inspect contract mapping, truthfulness, mobile hierarchy and uncertainty; adjust remaining steps.

   Reflection: the first page uses the backend's six monitoring types, versioned baseline list, ruleset, quality notices and concerns. Quality is visually separated from findings, with the disclaimer adjacent to each detection. The contract has no full observation-history endpoint, so the page labels baseline version history rather than inventing a time-series plot. Keep steps 11–20, and prioritize a clear pending/failed state for synthetic ingestion and review actions.
11. Add a clearly labelled fictional wearable-sync demonstration using backend ingestion and visible result summaries.
12. Add deliberate baseline recompute and concern-review controls, respecting frozen or not-ready state.
13. Connect newly opened cases to the existing case, equipment and BP procedure flow.
14. Surface urgent-priority protection and urgent interruptions in case and procedure views.
15. Cover sustained change, poor-quality/missing, duplicate, urgent and reassessment scenarios without fabricating backend transitions.
16. Add focused tests for detection presentation, quality separation and urgent priority.
17. Exercise the real browser against the running backend using fictional data; inspect desktop and phone layouts.
18. Run frontend tests and build; inspect the merged backend contract and ownership in the diff.
19. Commit only frontend-authored changes, push the worktree branch and fast-forward merge when safe.
20. **Review and reflect:** record functional and visual evidence, remaining PARTIAL/BLOCKED criteria, medical limits and next work.

## Step 20 review and reflection

Backend contract 2.6.0 was merged into this worktree. The frontend reads the live monitoring summary, baseline versions and ruleset. A browser test submitted the fictional sustained heart-rate batch: three readings produced `deviation_not_sustained`, `deviation_not_sustained`, then `concern_opened`. The open concern appeared with a frozen baseline, evidence IDs, case link and reassessment. A repeated-reading batch returned one updated concern, one exact upload duplicate and a suppressed repeat alert. A stale/poor-quality batch returned only quality exclusions. The linked case retained its urgent priority and showed monitoring evidence. Desktop and 390 px phone layouts were inspected; the phone had no horizontal page overflow. The production build and all 34 frontend tests pass.

Milestone 5 is **PARTIAL** as a full v3.1 acceptance item. The backend exposes baseline versions and latest readings but no full individual observation-history endpoint, so a true health-history time series cannot be drawn. Recovery after a 240-minute reassessment and the urgent-during-procedure scenario are covered by backend tests and frontend state handling, but were not exercised end to end in the live browser during this pass. Role-based concern-review authorisation remains backend work. All demonstrations are simulated and tested; none is a diagnosis or clinically approved detection rule. Next work: a history endpoint, an isolated repeatable browser scenario for due reassessment and urgent interruption, and role enforcement before classifying the full milestone COMPLETE.

# Contract 2.7.0 frontend follow-up and visual evidence

## Reconciliation

The procedure coach and BP picture guide are committed on `main` (`a073f3e`, `d03287e`); the current worktree is clean. Contract 2.5.0 habitat and 2.6.0 monitoring screens are implemented and previously browser checked. Their screenshots are in local visualizations, not the repository evidence folder. Backend branch `backend/p0-v2.1` now supplies contract 2.7.0: observation history, isolated demo scenarios that reset synthetic state, and role-aware review enforcement. Frontend must consume these responses and capture reproducible screen evidence without treating synthetic data as clinical findings.

## Build sequence

1. Verify git and screenshot status against the actual worktree.
2. Read the 2.7.0 handoff, OpenAPI models and affected frontend components.
3. Check whether an isolated backend runtime can host reset-first scenario tests without touching the existing demo database.
4. Merge the backend branch into this worktree without editing backend-owned files.
5. Model observation history, scenario results and crew roles in TypeScript.
6. Add paged history retrieval with type filtering and backend source/quality labels.
7. Draw a baseline-versus-reading chart from returned values and times, with no invented measurements.
8. Add scenario loading controls with a review step that states the reset effect.
9. Make concern Close and baseline recompute depend on the selected crew role and backend state.
10. **Review and reflect:** inspect data provenance, role checks, visual hierarchy and the scenario reset boundary; adjust the remaining steps.
11. Verify the history API in the live frontend and chart/row correspondence.
12. Verify scenario results against an isolated backend if available; otherwise mark live scenario browser acceptance PARTIAL.
13. Verify role-aware Close display for crew member and medical officer.
14. Capture habitat map, hatch, route and location screens for contract 2.5.0.
15. Capture monitoring, concern, quality and review screens for contract 2.6.0.
16. Capture history, scenario and role screens for contract 2.7.0.
17. Save representative screenshots in a frontend evidence folder with an index and exact test context.
18. Run focused tests, full frontend tests and build; inspect the rendered desktop and phone layouts.
19. Stage only frontend-authored files plus the backend merge; commit, push and fast-forward merge when safe.
20. **Review and reflect:** classify visual and integration acceptance, record remaining gaps and confirm GitHub state.

## Step 10 review and reflection

History values and dates come from the observation endpoint; source, quality, detection and active-baseline membership stay visible in the table. The chart is a visual connection of returned points and its baseline is the returned active personal baseline. Scenario controls expose the reset before calling the endpoint. A crew member can continue monitoring; Close and recompute are gated on the returned role and still checked by the backend. The build passed after correcting the actor-state type. Next, use an isolated demo database to verify that a reset cannot erase another demonstration, and inspect the app's case/session state immediately after scenario loading. Browser evidence takes priority over extra cosmetic changes.

## Step 20 review and reflection

The isolated backend identified itself as contract 2.7.0 and served role-coded bootstrap plus observation history. Browser checks exposed two navigation and alert issues that were corrected during the build: a hard reload discarded the active session, and an emergency alert initially showed a routine message and duplicated the urgent text. The route now preserves session state and the alert uses the urgent event. Browser evidence for 2.5.0, 2.6.0 and 2.7.0 is indexed in `evidence/README.md`. The remaining practical limit is that role selection is a fictional demo control, not authentication; backend authorization checks the submitted actor ID, and the frontend does not claim a production identity system. Synthetic scenario reset was exercised only against the disposable database. Final test and Git status are recorded in the handoff response.

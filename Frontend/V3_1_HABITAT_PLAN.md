# Milestone 4: habitat digital twin build plan

## Contract audit

The initial contract 2.3.0 supplies a versioned single-deck map via `GET /habitats/HAB-01/map`, zone-only or stale crew location via `GET /location/DEMO-001/latest`, and a versioned equipment route polyline from `POST /equipment/recommend`. The map has room and passage polygons, live hatch access, anchor and equipment points, and a route network. The existing frontend had separate room buttons and a text route. It must not turn a zone estimate or navigation reference into a precise person dot. Contract 2.5.0 arrived during this task and is covered in steps 21–30.

At the initial audit the merged backend did not expose a movement simulator, hatch controls, responder location or multi-crew routes. The subsequent backend branch adds these endpoints; its role-based hatch authorisation remains pending.

## Build sequence

1. Read the map, latest-location and equipment-route contracts.
2. Inspect the current spatial UI and its state flow.
3. Write this plan and record backend limits before code changes.
4. Add map, location freshness and route geometry TypeScript models and API calls.
5. Load the map and latest location independently of the rest of the page.
6. Build one SVG floor plan from backend compartment and passage polygons.
7. Render open and closed hatches, anchors and registered equipment points.
8. Highlight a reported zone without placing a fabricated astronaut position dot.
9. Add compartment selection, deck selection, keyboard controls, zoom and pan.
10. **Review and reflect:** inspect geometry, coordinate inversion, label placement, controls and location honesty; adjust the remaining plan.

   Reflection: the SVG consumes backend polygons in metre coordinates and inverts the vertical axis consistently. Room labels use backend navigation references, while the crew zone is rendered as an area highlight. The controls fit without a separate map library. Keep steps 11–20; strengthen route validation before display and retain text controls for keyboard and small screens.
11. Draw the backend route polyline only when frame and map version match.
12. Mark the route start as a zone navigation reference, not a person position.
13. Show selected equipment, readiness, rejected alternatives and route details.
14. Refresh map and latest location after manual confirmation or simulated estimate.
15. Handle stale, unavailable and mismatched map/route states explicitly.
16. Link the recommended BP device to its visual procedure.
17. Add focused tests for geometry, route validity and location display.
18. Inspect desktop and mobile layouts in a real browser against the live backend.
19. Run build and tests, check ownership and stage only frontend files.
20. **Review and reflect:** classify acceptance items, document backend gaps, commit, push and merge verified work.

## Step 20 review and reflection

The live backend returned `HAB-01-map-1.1` and a zone-only manual location. A real browser tap selected Crew Quarters, confirmation persisted it, and a BP recommendation drew the backend polyline through `H-CQ-EX` and `H-EX-MED`, avoiding the closed `H-LAB-MED` hatch. Desktop and 390 px mobile layouts were inspected. The route starts at the compartment navigation reference and is never displayed as a precise crew point. Build and all 31 frontend tests pass.

At this review point the first map slice was **PARTIAL**. A subsequent fetch revealed backend contract 2.5.0 on `backend/p0-v2.1`, supplying hatch control, stored route status, crew-based route starts, and movement scenarios. Extend the plan below before final acceptance. A version or frame mismatch suppresses the route and prompts a fresh request.

21. Inspect 2.5.0 route, hatch, location, and simulation schemas and merge the backend branch without editing backend files.
22. Add frontend models and API calls for live hatch state, recommendation status, crew route starts, and simulator runs.
23. Add a hatch operations panel with explicit reason and state action; refetch map and recommendation after a change.
24. Add patient/responder route start choice with latest estimate status and uncertainty shown honestly.
25. Add a clearly labelled fictional movement scenario control and show estimator results, never simulator ground truth as crew position.
26. Refresh the map and latest location after simulation; invalidate outdated route visuals.
27. Test route invalidation, hatch change, and simulator display against the live local backend.
28. Inspect the updated desktop and phone layouts.
29. Run build/tests and confirm only frontend-authored edits plus the backend merge are staged.
30. **Review and reflect:** confirm the final contract alignment and document any backend gap before push/merge.

## Step 30 review and reflection

Contract 2.5.0 was merged into this worktree. The frontend now offers a reasoned hatch state action, reads the new map state, suppresses invalidated route geometry, can route from a patient or responder latest estimate, and runs named fictional movement scenarios through the estimator. A live browser check closed `H-CQ-EX`, observed stored-route invalidation and no drawn polyline, reopened it, and requested a fresh route. A responder route started from the confirmed Exercise Bay zone. `SIM-WALK-CQ-MED` returned nine zone estimates; the page displayed those estimates and the latest location, never the evaluation ground truth. Desktop and phone layouts were inspected.

The remaining backend limit is role-based hatch authorisation: contract 2.5.0 permits any registered habitat crew member to change a hatch. The frontend labels this as a fictional crew action. It does not infer precise crew coordinates. The current fixture still has one deck; deck selection follows the API and needs another live acceptance pass when a multi-deck fixture exists.

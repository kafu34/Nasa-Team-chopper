# v3.1 milestone report — frontend, 14 November 2026

## Scope and changed files

Milestone 1 audit and the independent part of Milestone 2 Anatomical Twin were addressed. `src/HumanBody.tsx`, `src/human-site.ts`, `src/BodyMap.tsx`, `src/anatomy-sites.ts`, `src/App.tsx`, and `src/dashboard.css` add the anatomical viewer and compatible report flow. `public/models/` contains the offline model with licence and attribution. `src/human-site.test.ts` and `src/App.test.tsx` verify region mapping, legacy isolation and the dashboard flow. `V3_1_PLAN_AND_GAPS.md` records the required build plan and tenth-step review; `V3_1_BACKEND_HANDOFF.md` records the contract prerequisite.

## Actual behaviour and status

| Requirement | Status | Evidence / remaining gap |
| --- | --- | --- |
| Human exterior geometry | COMPLETE | Real recognisable head, torso, limbs, hands and feet render from the local glTF on desktop and tablet. |
| Front/back/side, free rotation, zoom, pan, reset | COMPLETE | Camera presets and trackball controls observed in the running browser. |
| Exterior, skeletal, muscle geometry | COMPLETE | Distinct loaded mesh groups and working layer visibility controls; screenshots in `evidence/`. |
| Detailed surface selection and laterality | PARTIAL | Browser click and named-site keyboard control work for the 35 existing sites. The mapping is an educational coordinate-zone approximation; mesh-boundary and laterality validation requires the backend contract. |
| Durable new-model symptom marker | BLOCKED | Backend only accepts `sentinel-body-v1` points. New model point, mesh and local attachment are session-only. A compatible broad region and truthful note can be reported. |
| Existing v1 marker compatibility | COMPLETE | Saved v1 marker remains on the legacy diagram and is never projected onto the unrelated mesh. |
| Procedure-specific visual coach | PARTIAL | Existing text/session workflow preserved; six visual scenes and shared action IDs are still required. |
| Habitat digital twin | PARTIAL | Existing zone/equipment workflow preserved; authoritative geometry and routes are absent. |
| Proactive health intelligence | PARTIAL | Existing observations and cases remain; automatic baseline and investigation API are absent. |
| NASA research and emergency regression | COMPLETE for existing integration | Real HTTP test passed for research and independent emergency route. OSD-546 is human-derived cell expression; OSD-195 remains unavailable, and neither is astronaut bone density. |

Validation level: **simulated and tested** for the existing demo backend. The human model is an educational reference, not a scan or clinical finding. No hardware, mission protocol or clinical validation is claimed.

## Visual evidence

- `evidence/v3.1-exterior-selection.jpg` — running human exterior and right-chest selection.
- `evidence/v3.1-back.jpg`, `evidence/v3.1-side.jpg` — back and side camera presets.
- `evidence/v3.1-muscles.jpg`, `evidence/v3.1-skeleton.jpg` — actual anatomy layers.
- `evidence/v3.1-legacy-marker.jpg` — saved v1 marker on its original diagram.
- `evidence/v3.1-tablet.jpg` — 768 × 1024 layout inspection.
- `evidence/v3.1-dashboard-alert.jpg` — vitals beside the human model, with a red self-reported severity alert.

## Verification

- `npm.cmd test -- --run`: 26/26 passed.
- `npm.cmd run build`: passed; the lazy 3D viewer is a separate bundle.
- `SENTINEL_API_BASE=http://127.0.0.1:8001 npm.cmd run test:integration`: passed against an isolated real uvicorn server and temporary SQLite database. Verified symptom and v1 point persistence, case/session/measurement flow, research values and unavailable status, emergency, and preservation of research records across demo reset.
- Browser inspection: exterior click selected right chest; front/back/side, layers and legacy marker worked; tablet layout was usable. The dashboard showed the human model beside vitals with red alert colour for a persisted severity-10 report. No browser console errors were observed.

## Next required implementation tasks

1. Claude commits the additive mesh-marker schema, persistence and validation described in `V3_1_BACKEND_HANDOFF.md`.
2. Codex integrates that exact schema and verifies new-model markers survive refresh, navigation and case reopening.
3. Claude supplies the structured procedure visual actions and equipment identities; Codex builds the six distinct BP scenes and verifies session restoration.
4. Continue with habitat geometry and proactive monitoring in the specification's milestone order.

## Step 20 review and reflection

Steps 11–19 were checked against the v3.1 acceptance criteria. The test suite and real HTTP regression passed, and the visual evidence shows the anatomical model in the actual app. The old API is the critical dependency: treating it as a new-model marker store would corrupt anatomical meaning, so that acceptance item remains BLOCKED. Keeping the old diagram for existing points preserves data while Claude extends the contract. The next smooth build step is schema agreement, then persistence wiring and reload tests; visual procedure work can follow without changing the anatomy contract.

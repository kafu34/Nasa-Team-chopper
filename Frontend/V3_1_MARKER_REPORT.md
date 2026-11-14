# v3.1 marker integration report — 15 November 2026

## Scope and status

Claude's backend/shared branch was merged into this worktree. The frontend now consumes contract 2.3.0 for real skin taps and restores compatible saved markers. The **tested durable new-model marker workflow is COMPLETE for the fictional local demo**: a real browser tap was submitted, read from the backend after refresh, shown in the same place, rotated with the model, and shown again after navigating through the case. The full Anatomical Twin remains **PARTIAL** because the educational site-zone mapping and backend surface validation are not exact geometric/clinical validation. Procedure, habitat and proactive milestones remain separate.

## Files and contract

`src/api.ts`, `src/BodyMap.tsx`, `src/human-site.ts`, `src/anatomy-sites.ts`, `src/HumanBody.tsx`, `src/App.tsx`, `src/dashboard.css`, and focused tests were updated. `V3_1_MARKER_PLAN.md` contains the 20-step plan and tenth-step review. No independent backend or shared schema was invented; `shared/openapi.yaml` 2.3.0 and `shared/anatomy/sentinel-human-male-v1.json` came from Claude's branch.

The request uses `model_id: "sentinel-human-male-v1"`, **string** `model_version: "1.0.0"`, `site_id`, `mesh_id: "skin"`, world x/y/z, mesh-local x/y/z and optional triangle/barycentric attachment. The response's `render_hint` controls restoration. `site_only` and `not_renderable` do not place an exact marker. V1 points are shown only on the legacy diagram.

## Real browser and backend evidence

On the isolated 2.3.0 server, a browser click on the actual chest skin mesh selected `right_chest`. The UI submitted the report to `POST /api/v1/symptoms`. `GET /api/v1/cases/CASE-CD35D91F95` returned:

| Field | Returned value |
| --- | --- |
| Region / side / site | `chest` / `right` / `right_chest` |
| Model / version / mesh | `sentinel-human-male-v1` / `1.0.0` / `skin` |
| World point | `(-0.140549, 1.310977, 0.074806)` metres |
| Mesh-local point | `(-0.163476, 0.524896, 0.087025)` |
| Attachment | triangle `2961`, barycentric `(0.131412, 0.811681, 0.056907)` |
| Server status | `mesh_validation: validated`, `marker_status: current`, `render_hint: exact_point` |

The marker reappeared after browser refresh, stayed on the chest in the side view, and reappeared after visiting Case & Follow-Up and returning to Anatomical Twin. Evidence: `evidence/v3.1-real-tap-saved.jpg`, `v3.1-real-tap-reloaded.jpg`, `v3.1-real-tap-side.jpg`, and `v3.1-real-tap-case-reopen.jpg`.

## Tests and limits

`npm.cmd test -- --run`: **26/26 passed**. `npm.cmd run build`: **passed**. The prior real HTTP integration scenario also passed; this follow-up separately verified a genuine browser ray cast against the 2.3.0 backend. The backend's three fixture points are synthetic and were not used as the browser tap.

The backend has no triangle geometry. Its `mesh_validation: validated` confirms bounds and local-to-world consistency, not exact skin contact. The model is educational and not a scan, finding, diagnosis or hardware-validated procedure. The next work is the six distinct BP visual scenes using Claude's committed visual-action contract, followed by the habitat plan and proactive monitoring milestones.

## Step 20 review and reflection

The real tap, backend response, refresh, rotation and case navigation met the marker persistence gate. The string version avoided a 422 mismatch. The mesh-local point and triangle attachment came from the browser ray cast, and old v1 points retained their original surface. The verification boundary is now clear: this frontend workflow demonstrates contact on its loaded skin mesh, while the backend cannot independently establish that contact from its stored bounds and transform. The next milestone should consume the committed procedure visual IDs rather than add a generic animation.

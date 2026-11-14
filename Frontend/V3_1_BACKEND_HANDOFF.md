# v3.1 backend handoff: anatomical surface points

The frontend now uses the locally bundled `anatomy-male.glb` reference model as `sentinel-human-male-v1`. It has distinct skin, muscle and skeleton geometry. A skin click produces the existing 35-site classification plus a model-space point, the hit mesh name and a mesh-local point. The latter three values are retained in the browser session only.

## Existing contract constraint

`shared/openapi.yaml` and `docs/INTEGRATION_HANDOFF.md` currently accept `surface_point` only for `sentinel-body-v1`. It is a point on the old primitive diagram. New-model coordinates cannot be sent under that ID. The frontend therefore sends the existing `region_id`, `laterality`, severity, onset and a note identifying the selected reference area; the response does not claim an exact saved point. Saved v1 points stay on the legacy diagram.

## Contract decisions needed from Claude

1. Define an additive, versioned symptom marker reference for `sentinel-human-male-v1` in `shared/openapi.yaml` and the handoff. It must identify asset/model version, canonical anatomical site or region, side, source surface mesh and stable mesh-relative attachment. A mesh-local coordinate is available now; triangle ID plus barycentric coordinates is preferable if the model's transforms or geometry may change.
2. Validate that the selected point belongs to the declared mesh, site and laterality. Keep detailed selection separate from broad medical classification, patient report, monitoring concern and verified finding.
3. Persist and return the marker in `POST /api/v1/symptoms`, `GET /api/v1/cases/{case_id}` and the bootstrap/case surfaces used on reopen. Preserve existing `sentinel-body-v1` records with their original model ID.
4. Document compatibility or explicit migration for any later asset revision. Do not reinterpret old coordinates on the new asset.
5. Add a shared fixture and backend test that report a right-shoulder point, rotate/refresh/reopen the case, and retrieve the same model, mesh, site, side and attachment. Include a left-side counterpart and a rejected mismatched region.

Codex can then derive the frontend request/response types from the committed schema, submit the exact attachment, render restored new-model markers and run the full persistence gate. The current UI labels that gate as incomplete.

The later milestones also need Claude's versioned visual-action IDs and equipment references for `PROC-BP-01`, authoritative habitat polygons/passages/route coordinates, and baseline/investigation events. The frontend will consume those contracts when committed; this document does not define an alternate API.

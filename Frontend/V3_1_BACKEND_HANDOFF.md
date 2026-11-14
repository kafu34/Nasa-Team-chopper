# v3.1 anatomical contract handoff — current status

Claude's committed contract 2.3.0 registers `sentinel-human-male-v1` at version `"1.0.0"` in `shared/anatomy/`. The frontend now sends that string version, the actual ray-cast world point, `mesh_id: "skin"`, the mesh-local point, and a triangle/barycentric attachment when available. `POST /api/v1/symptoms` stores the point and `GET /api/v1/cases/{case_id}` returns it with `marker_status` and `render_hint`. The frontend draws an exact marker only when the returned model, version, mesh and render hint are compatible. Existing `sentinel-body-v1` points stay on the legacy diagram.

The real browser tap and reload evidence is recorded in `V3_1_MARKER_REPORT.md`. The backend response for that tap contained `model_version: "1.0.0"`, `mesh_id: "skin"`, `triangle_index: 2961`, `mesh_validation: "validated"`, `marker_status: "current"`, and `render_hint: "exact_point"`.

**Validation limit:** the backend checks the declared mesh bounds, local-to-world transform, site height/face and laterality. It does not hold the triangles and cannot independently prove that submitted coordinates lie exactly on the skin surface. The browser ray cast supplies that evidence for this frontend interaction; arbitrary API clients are subject to the stated backend limit.

The procedure visual-action and habitat geometry contracts are also committed in 2.3.0. Their full visual implementations remain later milestones. This handoff does not define an alternate schema.

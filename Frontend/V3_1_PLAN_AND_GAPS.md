# SENTINEL AI v3.1 frontend plan and gap audit

## Repository and contract audit (14 November 2026)

| Area | Current evidence | v3.1 status |
| --- | --- | --- |
| Shared API | `shared/openapi.yaml` and `docs/INTEGRATION_HANDOFF.md` define 35 `sentinel-body-v1` sites and structured symptom points. No mesh-relative marker reference or new model version is defined. | PARTIAL |
| Anatomical Twin | `ThreeBody.tsx` renders primitive spheres and cylinders, provides rotation and zoom, and restores `sentinel-body-v1` points. It has no anatomical layers or pan. | PARTIAL |
| Procedure Coach | The backend drives six `PROC-BP-01` instructions and persists steps and measurements; the frontend presents text and forms. No visual-action identifiers or equipment scene assets exist. | PARTIAL |
| Habitat Twin | The API returns zones, estimates and route zone IDs. The frontend shows zone cards; the shared contract has no compartment polygons, passage geometry or route coordinates. | PARTIAL |
| Proactive monitoring | Current UI displays observations and case state. The API does not expose versioned personal baselines, automatic findings or investigation history. | PARTIAL |
| NASA research | Existing imported data panels use actual backend values and unavailable statuses. Preserve them through visual work. | COMPLETE for the currently integrated datasets; future scope remains separate |
| Emergency access | Independent route and backend action exist. Keep them usable when WebGL or research is unavailable. | COMPLETE for the fictional simulation |

The `open-anatomy-3d@0.1.0` male model is selected for the next exterior milestone. Its locally hosted glTF includes named skin, skeleton and muscle meshes. The model package identifies BodyParts3D © DBCLS, CC BY 4.0, as its anatomical source; attribution must remain visible. The model is an educational reference body, not a scan of `DEMO-001`.

## Design brief

- **Audience and job:** a fictional crew member identifies a reported surface concern and explores reference anatomy without confusing research or illustration with a patient finding.
- **Tokens:** retain the mission console's navy canvas (`#14243a`), slate panels (`#263b52`), cyan interaction (`#56c7d8`), amber self-report (`#f3bd61`), and red high-severity (`#e57c75`). Retain its sans-serif type and existing two-column desktop layout.
- **Signature:** a real full-body mesh with a concise Exterior / Muscles / Skeleton control, camera presets and a marker legend next to the report.
- **Accessibility:** labelled controls of at least 44 px, keyboard-selectable named sites, visible focus, reduced-motion support and an honest 2D fallback.
- **Self-critique:** this is a mission medical console; layer controls and source attribution should clarify evidence, not make the viewer look like a generic model showcase.

## Build sequence

1. Audit current frontend screens and tests against v3.1.
2. Read the committed OpenAPI contract and integration handoff.
3. Verify an anatomically credible licensed asset and its offline packaging.
4. Identify model-version and marker schema changes that belong to Claude.
5. Add the local human asset and attribution inside `Frontend/`.
6. Build a human-mesh viewer while keeping the existing fallback.
7. Add pan, free rotation, zoom, reset and four camera presets.
8. Show actual skin, skeleton and muscle geometry through visible controls.
9. Add mesh picking, side-aware site selection and clearly versioned marker behavior.
10. **Review steps 1–9:** inspect visual coherence, API compatibility, licensing and whether any shortcut misstates persistence; revise the remaining build if needed. Record a reflection.
11. Test region mapping, model identity and marker compatibility.
12. Inspect desktop and tablet browser behavior, including keyboard controls.
13. Test a symptom report against the actual backend, without claiming new-model point persistence until the contract supports it.
14. Capture front, back, side, layer and restored-marker evidence where implemented.
15. Classify each acceptance item as COMPLETE, PARTIAL, BLOCKED or NOT STARTED.
16. Run frontend build, tests and relevant API regression checks.
17. Document the exact backend contract needed for durable mesh-relative points and later milestones.
18. Review the diff for ownership boundaries, stale claims and accidental data changes.
19. Commit the frontend milestone in this worktree.
20. **Review steps 11–19 and reflect:** compare the running app with v3.1, record remaining prerequisites and the next implementation stage.

## Step 10 review and reflection

Steps 1–9 were checked against the running application and the committed API. The bundled human asset renders coherent exterior, muscle and skeletal geometry; front and side views, layer switches and exterior picking were observed in the browser. A single glTF keeps the layers aligned and avoids separate model registration. The source model has no usable material colours, so the frontend assigns distinct educational colours per layer. The right chest click mapped to the right chest backend region.

The existing API cannot store a `sentinel-human-male-v1` mesh attachment. Sending its world coordinates as a `sentinel-body-v1` point would create a false durable marker. The viewer therefore keeps new-model points in the current session and submits the compatible broad region and an explicitly limited note. Saved v1 points stay on the legacy diagram. This makes the complete marker requirement PARTIAL until Claude publishes and implements an additive marker schema. Remaining work is focused on tests, responsive inspection, backend verification and a precise handoff; it does not introduce a competing API schema.

## Contract handoff required from backend owner

The current `surface_point` schema accepts only `model_id: sentinel-body-v1` and world coordinates on the old primitive diagram. A new human mesh must have a distinct immutable model ID and version. The backend owner needs to define and persist an additive mesh reference (asset/model version, mesh ID and mesh-local attachment, such as triangle plus barycentric coordinates or local position) and return it in case records. Existing v1 points must remain on the legacy diagram or have an explicit, verified migration. Do not project them onto the new model by guesswork.

Procedure visual-action identifiers, habitat geometry and route coordinates, and proactive-monitoring evidence APIs are also absent from the current shared contract. Their frontend implementations can start only at the independent visual or UI level until Claude publishes compatible schemas.

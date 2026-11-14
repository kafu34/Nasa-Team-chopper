# v3.1 anatomical marker integration plan

This follow-up uses Claude's committed 2.3.0 contract. It continues the existing viewer; it does not change backend medical rules or reinterpret v1 markers.

1. Fetch and inspect Claude's latest branch and handoff.
2. Merge the committed backend/shared contract into this worktree.
3. Compare the registered model manifest against the bundled GLB and existing 35 sites.
4. Extend frontend request and response types with version, mesh-local point, attachment, marker status and render hint.
5. Make the human model version the exact string `"1.0.0"`.
6. Capture the ray-cast point and mesh-local coordinate from a real skin tap.
7. Capture triangle and barycentric attachment when the ray cast supplies a valid face.
8. Submit the structured new-model point through the existing symptom API.
9. Restore saved points only when the backend says `render_hint: exact_point` for the matching model/version.
10. **Review steps 1–9 and reflect:** check contract shape, geometric consistency, legacy isolation and the backend's surface-validation limit.
11. Render the restored marker attached to the skin mesh and retain v1 markers on the legacy diagram.
12. Explain named-site-only reports and incompatible markers accurately in the UI.
13. Add focused request, response and compatibility tests.
14. Start an isolated 2.3.0 backend with a disposable demo database.
15. Run a real browser tap, submit it and inspect the backend response.
16. Refresh and reopen the case; verify marker location, model, version and attachment are restored.
17. Check rotation and zoom after restoration and capture visual evidence.
18. Run frontend build, unit tests and real HTTP regression; update the acceptance report.
19. Review ownership boundaries, commit in this worktree, push and merge if regression gates pass.
20. **Review steps 11–19 and reflect:** state what the browser proved and what the backend cannot prove without triangles.

The backend can validate model bounds, laterality, site plausibility and the mesh-local transform. It cannot prove exact contact with the skin surface because it does not hold triangle geometry. The three shared fixture points are synthetic; browser ray-cast evidence is a separate required gate.

## Step 10 review and reflection

The merged contract has one selectable skin mesh and the same 35 site mappings as the frontend. A real ray cast supplies world and mesh-local points; the triangle index and normalized barycentric weights are added when Three.js exposes the face. The frontend uses the exact string version `"1.0.0"` and never sends a human-mesh point under the v1 diagram ID. Saved exact points attach to the skin mesh; `site_only` and `not_renderable` hints do not place an approximate point. This avoids accidental migration. The remaining gate is not another schema change: it is a browser tap sent to the running 2.3.0 backend, followed by reload and case reopening. Unit tests and build pass, but those cannot substitute for that gate.

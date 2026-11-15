# Contract 2.8.0 frontend build plan — Milestone 6, part 1

## Scope and starting evidence

Claude pushed `a907a4b` on `backend/p0-v2.1`: two educational procedures (pulse oximetry and non-contact forehead temperature), a `GET /procedures` catalogue, procedure-specific measurements, and ruleset DET-1.1. The frontend at `27f9b46` is BP-specific in its visual registry, coach state, and measurement form. Build only frontend-authored files in this worktree; merge the backend commit for integrated verification. Do not present educational scenes as flight-surgeon-approved or hardware-tested.

## Part-by-part build sequence

1. Confirm current Git state and the pushed backend commit.
2. Compare 2.8.0 handoff and fixture action/asset IDs with current frontend assumptions.
3. Record the current procedure and case-entry path, including session restoration and device matching.
4. Merge the backend commit without modifying backend-owned files.
5. Add typed procedure catalogue and type-specific measurement contracts to the frontend API.
6. Let crew select BP, pulse oximetry, or temperature from the backend catalogue and preserve a session's procedure ID.
7. Replace fixed BP measurement fields with the selected procedure's actual technical input shape and unit.
8. Register the ten exact new action/asset combinations; keep failure explicit for unknown actions.
9. Draw distinct picture-guide scenes for all five pulse-oximeter and all five thermometer steps.
10. **Review and reflect:** check contract IDs, medical wording, session isolation, and visual differences; simplify remaining work where possible.
11. Add separate 3D device interactions for the new action IDs with pause/replay and accurate target framing.
12. Connect picture and 3D scenes to the existing backend step acknowledgement without treating viewing as completion.
13. Check the new catalogue, procedure definitions and measurement validation against an isolated 2.8.0 backend.
14. Browser-test all five steps of pulse oximetry, including a completed session and SpO2 submission.
15. Browser-test all five thermometer steps, including a completed session and temperature submission.
16. Browser-check the existing six-step BP flow, urgent interruption and current map/monitoring navigation for regressions.
17. Capture desktop and narrow-screen visual evidence for both new procedures and their measurement forms.
18. Run focused and full frontend tests, build, and inspect Git diff for backend ownership and accidental artifacts.
19. Commit frontend files and evidence, push the worktree branch, then fast-forward merge when the remote is still an ancestor.
20. **Review and reflect:** classify Milestone 6 progress, scientific limits, integration status and next backend/frontend tasks.

Steps 1–3 are complete from the initial audit. The handoff's device names and fixture action IDs are the source of truth for steps 5–12.

## Step 10 review and reflection

The backend action registry contains five distinct pulse-oximeter scenes and five distinct infrared-thermometer scenes, with exact ordered asset lists; unknown or changed IDs still return an unavailable state. The new picture guides depict different device interactions, and the new coach keeps session keys separate by case and procedure. The BP coach remains intact. The first type build found three expected migration issues in the old BP API test, a literal default parameter and a scene cast; these were corrected before visual work continued. The next work is to render the ten 3D states, add a device-capability choice to habitat routing, and verify that DET-1.1 opens the intended assessment case. Medical text stays labelled educational and simulated. The efficient path is to reuse the existing playback controls while giving the new devices their own geometries, avoiding a second animation control implementation.

## Step 20 review and reflection

The 2.8.0 backend handoff is integrated for this frontend slice. Browser runs against an isolated backend confirmed both DET-1.1 scenario-to-procedure paths, five ordered acknowledgements in each session, technically accepted simulated readings, session restoration, and the temperature device route. Desktop and narrow-screen evidence covers both guides and their result forms. The BP picture guide still renders, and a case requesting temperature cannot start a pulse-oximeter session from a catalogue preview. All 36 frontend tests and the production build pass. The build reports an existing large JavaScript chunk warning; it is not a failed gate. The visual content remains an educational schematic with fictional devices and no flight-surgeon review or real hardware validation. Milestone 6 as a whole is partial: the next backend steps 35–40 and corresponding frontend features are still outstanding. Keeping the two new procedures in one data-driven coach reduced duplicate session and form logic; a separate device scene module kept the existing BP animation stable. No backend-authored files were edited in this frontend part.

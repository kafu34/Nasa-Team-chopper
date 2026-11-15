# Milestones 6–7 completion plan (software only)

1. Confirm clean worktree and backend contract 2.11.0.
2. Read the published role matrix and existing frontend actor controls.
3. Type the role matrix and add `viewer_id` to the three sensitive API reads.
4. Load fictional personnel from `/access/roles` at app startup.
5. Provide one visible demo identity switch and explain its self-declared limit.
6. Use that identity on sensitive case and monitoring reads.
7. Clear stale sensitive data when identity changes or a read is denied.
8. Apply matrix permissions to concern review, baseline changes, case operations, inventory, and communications.
9. Expose the backend permission matrix in a readable, responsive panel.
10. Review every wired action against the published matrix; reflect on safety and simpler shared state.
11. Run focused tests and build; repair concrete failures.
12. Start a disposable backend and frontend without editing backend files.
13. Browser-check allowed and denied viewers and actor buttons.
14. Capture role UI desktop and narrow-screen screenshots.
15. Browser-check a delayed message through delivered and receiver acknowledgement.
16. Browser-check explicit follow-up cancellation during valid case resolution.
17. Run full tests and production build.
18. Update evidence and handoff only for observed outcomes.
19. Remove disposable files, check frontend-only diff, commit, and push.
20. Review completion against the software-only scope and reflect on any remaining backend limits.

**Step 10 review and reflection:** Use the backend matrix as the source for permission display and button visibility. Keep a single selected identity so displayed viewer and submitted actor cannot quietly diverge. Preserve emergency access and explicit warnings that this demo has no authentication.

**Step 20 review and reflection:** The role matrix, own-record read, denied ground-support monitoring read, hidden hatch/device controls, and delayed receiver acknowledgement were observed in the browser. The five-minute delay was allowed to elapse; no clock shortcut was used. The disposable follow-up setup request was rejected, so live cancellation remains PARTIAL even though its frontend/backend tests pass. Keep that distinction in the handoff. The local backend's self-declared identities and lack of authentication remain explicit product limits.

# BP monitor picture guide plan

## Scope and evidence

Keep `PROC-BP-01` and its six backend action/asset IDs. The guide uses one medical instrument: the configured automatic upper-arm BP monitor and its cuff. The crew restraint and arm support are positioning context, not extra medical instruments. The backend's instruction, warning, source and session state remain authoritative. Official [AHA home-monitoring guidance](https://www.heart.org/en/health-topics/high-blood-pressure/understanding-blood-pressure-readings/monitoring-your-blood-pressure-at-home) and [CDC measuring guidance](https://www.cdc.gov/high-blood-pressure/measure/) informed the bare-arm, quiet-rest, cuff-fit and support illustrations. Their Earth-seated images are not copied into the spaceflight interface; the original drawings preserve the backend's microgravity limitation.

## Build sequence

1. Re-read the six backend BP monitor steps and current visual registry.
2. Review the existing procedure layout, playback and acknowledgement states.
3. Check official BP measurement guidance and image reuse constraints.
4. Define one accessible picture per backend visual action.
5. Draw the preparation picture with the monitor, cuff and rest cue.
6. Draw the bare left upper-arm picture.
7. Draw the cuff wrap with artery marker, fit and elbow spacing cues.
8. Draw the restrained supported-arm schematic without Earth seated posture.
9. Draw start/measurement and simulated result pictures using the same monitor.
10. **Review and reflect:** verify all six pictures against backend text, equipment identity and safety limits; correct visual ambiguity.

### Step 10 review and reflection

The six original SVG panels map one-to-one to the existing visual-action registry. The only medical instrument depicted is the automatic upper-arm BP monitor with its cuff. Step 2 labels the left bare upper arm; step 3 shows the cuff on the arm, its artery marker, finger fit and spacing above the elbow; step 4 shows a restraint and supported arm without a chair or Earth gravity cues. Step 5 points to the monitor's start control, and step 6 labels the readings as simulated. The pictures are original drawings informed by AHA/CDC guidance, not copied web images; this avoids uncertain image reuse rights and prevents Earth-seated imagery from implying a validated microgravity method. The illustrations stay tied to backend action IDs, and their viewing will not acknowledge a real-world step.
11. Make the picture guide the default procedure view.
12. Add previous/next picture controls and retain direct six-step navigation.
13. Keep the existing 3D replay as an optional view.
14. Keep picture navigation separate from backend step acknowledgement and simulated reading.
15. Make images responsive, keyboard accessible and legible without color alone.
16. Add a meaningful component test covering all six action-to-picture mappings and navigation.
17. Build and run the frontend tests.
18. Inspect the guide at desktop and mobile sizes in a real browser.
19. Check a live backend procedure response, review diff and stage only frontend files.
20. **Review and reflect:** report acceptance status and limitations, then commit, push and fast-forward merge if verified.

### Step 20 review and reflection

The default picture guide now presents all six backend-defined BP monitor actions in sequence. Browser inspection against a live backend procedure response checked every drawing, the optional 3D replay and a 390 px mobile viewport. The mobile image fits without horizontal page scrolling, with the full backend instruction and readable picture caption beside it. Overlapping callouts were corrected; the preparation picture now includes restrained setup, and the result picture shows cuff removal. Frontend build and 29 tests pass, including a test that advances through all six pictures without changing backend acknowledgement.

**Picture-guide result: COMPLETE for the six educational BP monitor pictures and navigation. Overall Milestone 3: PARTIAL; validation level: EDUCATIONAL_DEMONSTRATION.** The backend still has no durable picture/animation viewed event, no hardware-tested procedure is implied, and this demonstration did not establish a selected inventory item. The supported posture is explicitly a schematic with a microgravity limitation. Future backend event and inventory contracts can close those acceptance gaps without changing the picture sequence.

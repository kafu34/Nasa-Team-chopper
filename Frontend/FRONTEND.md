# SENTINEL AI frontend

## Scope and status

This React, TypeScript, and Vite frontend is the mission medical console for the fictional `DEMO-001` astronaut in `HAB-01`. It contains the dashboard, interactive front/back surface body map, simulated habitat location and equipment screen, backend-driven `PROC-BP-01` coach, NASA research catalogue and measurements view, case follow-up, and an independent emergency screen.

The client now follows the committed `shared/openapi.yaml` v2.1.0 and `shared/fixtures/demo_scenario.json` for the P0 workflow. Requests use the contract's ISO symptom onset, 0–10 severity, simulated BLE observations, ordered step-confirmation sources, structured blood-pressure values, and error envelope. No research values, case transitions, or medical procedures are fabricated as fallbacks. The live browser-to-backend flow has been verified.

The overview places fictional mission vitals beside an Anatomical Twin. Selecting a surface region opens the larger body view and pain report. Persisted, unresolved self-reported symptoms highlight regions orange for severity 1–6 and red for 7–10; these colors do not diagnose a condition. The three-bar menu contains Maps and Settings. On the map, choosing a habitat zone requires explicit confirmation with the backend. The next-action reminder is visible for 20 seconds, then appears once more near a scheduled assessment time or later if already overdue. Settings can disable animation and reminders on this device. The emergency action remains visible on small screens.

Version 2.2 adds OSD-195 muscle and OSD-546 skeletal/bone-cell research panels to the Anatomical Twin. The checked-in OpenAPI contract includes both IDs and the additive `GENE_EXPRESSION_V1` response fields while retaining contract version `2.1.0`. The OSD-546 bone-cell panel requests `gene_symbol=TSPAN6` and displays imported processed expression values with sample, condition, published scale, normalization, and comparison-readiness context. These are cell measurements, never astronaut bone-density results. OSD-195 remains `NOT_DOWNLOADED` and shows its status message without values.

The next backend update adds OSD-817 ex vivo donor-eye TUNEL/CTB counts and a historical NASA RadLab ISS snapshot. The eye selection and optic-nerve panel show `HISTOLOGY_COUNTS_V1` values, source notes, and published group numbers without assigning unverified pressure/tilt conditions. NASA Research requests RadLab through `/api/v1/radiation/timeseries`, shows one detector at a time in the backend unit, and identifies the readings as historical ISS area dosimetry rather than live habitat or personal exposure.

## Run

```powershell
cd Frontend
npm.cmd install
npm.cmd run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` and `/healthz` to `http://127.0.0.1:8000`. The local backend is required for persisted medical workflows and NASA records; Earth internet is not required during operation when both processes and locally stored data are available.

```powershell
npm.cmd run build
npm.cmd run test
```

With the local backend running, run `npm.cmd run test:integration` from `Frontend/`. It resets synthetic demo state, tests the P0 API scenario, checks imported OSD-575, OSD-656, OSD-546, OSD-817 and NASA-RADLAB records plus unavailable OSD-195, then resets synthetic state again. NASA research records are not reset.

## Integration handoff

1. Run the full scenario against the real server, including `POST /api/v1/demo/reset`, symptom, location, equipment, procedure session and steps, measurement, actual OSD-575 records, missing datasets, and emergency activation.
2. Verify the OSD-575 chart uses only actual numeric records for one analyte, subject, and unit, ordered by the backend timepoint key. Keep NASA research subjects separate from `DEMO-001`.
3. When processed OSD-195 files are available and the backend imports them, verify sample conditions, published scale, normalization, and source metadata against the returned records. The frontend displays OSD-546 sample values but does not compute flight/control or before/after comparisons or medical findings.
4. Preserve `/api/v1/research/osd-575` compatibility in the backend while consuming the generic dataset APIs in this frontend.

Catalogue identifiers displayed: `OSD-575`, `OSD-656`, `NASA-EDA`, `NASA-RADLAB`, `OSD-195`, `OSD-546`, `OSD-654`, `OSD-684`, `OSD-573`, `OSD-817`. OSD-654 is identified as animal research and excluded from primary human-health analysis. Numerical views appear only for `IMPORTED` datasets. Other availability states are `NOT_DOWNLOADED`, `READY_TO_IMPORT`, `IMPORT_FAILED`, and `UNSUPPORTED_FORMAT`.

## Safety boundaries

SENTINEL AI is a research prototype, not a clinically validated medical device. The body map represents surface regions only. The interface does not diagnose, prescribe medication, invent emergency treatment steps, claim live Bluetooth detection, or equate measurement quality with medical significance. Emergency activation is directly reachable without the research or location workflow. Frontend route assets are bundled locally; backend outage is shown as an error and no save is claimed.

## Verification record

- Production build: passed on 14 November 2026 (`npm.cmd run build`).
- Frontend tests: 19 passed on 14 November 2026 (`npm.cmd run test`), including API request shapes, body selection and severity highlights, map confirmation, reminder timing, emergency access without bootstrap, OSD-575 record display, OSD-656 assay units and missing values, unavailable OSD-195 handling, and imported OSD-546 numeric-display rules using test fixtures.
- Live P0 HTTP integration: passed on 14 November 2026 (`npm.cmd run test:integration`) against local FastAPI. The backend returned 531 actual OSD-575 records, 22 filtered IL6 assay records from OSD-656, 13 filtered TSPAN6 expression records from OSD-546, and `NOT_DOWNLOADED` for OSD-195. The synthetic scenario was reset afterward.
- Vite `/api` proxy smoke check: passed against the same local backend. Bootstrap returned HTTP 200; OSD-546 TSPAN6 returned 13 `GENE_EXPRESSION_V1` records. A sandboxed dev server was unreachable from outside the sandbox, so this check started Vite outside that network boundary and stopped it afterward.
- OSD-656: backend now reports `IMPORTED` with 8,888 urine inflammation assay values. The research screen uses `assay_records[]` and labels NPQ as relative assay units, not clinical concentrations.
- OSD-546: backend reports `IMPORTED` with 432,861 processed expression values. The `gene_symbol=TSPAN6` query returned 13 records, one per cell sample, with published scale and condition labels. The frontend displays these as human-derived cell research only.
- OSD-195: backend reports `NOT_DOWNLOADED` and zero records. The backend handoff says only raw CEL files were supplied; no processed numerical import or comparison is claimed. The raw `.CEL.gz` file is not used as a ready-to-display table.
- OSD-817: backend reports `IMPORTED` with 72 TUNEL and CTB count values in `histology_records[]`. The frontend shows donor-eye samples, group numbers, units, and image notes without attributing measurements to astronauts or mapping groups to unverified pressure/tilt conditions.
- NASA-RADLAB: backend reports `IMPORTED` with 2,847 historical ISS readings. The frontend queries `instrument_id=DosTel1` initially, then allows selection from the backend instrument list. It charts one detector at a time and shows the published μGy/hour unit.
- Follow-up verification: production build, 14 frontend tests, and the live HTTP integration test passed on 14 November 2026 against the updated local backend. The integration test confirmed 72 OSD-817 values and RadLab's dedicated timeseries endpoint.
- Browser visual QA: passed on 14 November 2026 against the live local Vite proxy and backend at desktop and 390 px mobile widths. The dashboard, compact menu, enlarged body view, and saved severity-10 red alert were observed. The synthetic report was left in the demo backend for inspection; `npm.cmd run test:integration` resets it when rerun.

## 30-second demonstration storyboard

| Time | Screen | Action |
| --- | --- | --- |
| 0–4 s | Overview | Show fictional crew member, scheduled assessment, and next action from the backend. |
| 4–8 s | Anatomical Twin | Select region and laterality; confirm symptom and show persisted case ID. |
| 8–12 s | Location & Equipment | Submit simulated anchor observation; show estimated zone, confidence, ready device, and backend route. |
| 12–20 s | Procedure Coach | Open `PROC-BP-01`, acknowledge backend steps, submit a simulated measurement, and show backend quality/case response. |
| 20–25 s | NASA Research | Show actual imported OSD-575 measurements, subject, units, timepoint, and provenance. |
| 25–30 s | Emergency | Open independent responder screen and activate the fictional collapse scenario. |

Record this only after the live integrated flow is verified. Show limitations and simulated labels in the capture.

## Seven-slide alternative outline

1. Long-duration mission health challenge and five NASA hazards.
2. SENTINEL AI purpose, audience, and research-prototype boundary.
3. Connected routine assessment journey.
4. Anatomical Twin, simulated habitat navigation, and Procedure Coach.
5. Actual OSD-575 data, source attribution, and research limitations.
6. Independent fictional emergency responder scenario.
7. Architecture, test evidence, present limitations, and next steps.

## Plan review and reflection

Steps 1–10 were reviewed against the master prompt and v2.1 amendment. The research chart was adjusted to group only comparable analyte, subject, and unit records; mixed-measurement lines could mislead viewers.

Steps 11–20 were reviewed against the same requirements. The independent emergency route is verified under bootstrap failure. Source files and documentation remain inside `Frontend/`. The browser preview timed out, so visual capture is still pending.

Version 2.2 delta steps 1–10 were reviewed on 14 November 2026. The frontend follows the P0 schemas and additive expression and assay record fields; the complete local P0 HTTP scenario passed. Nine frontend tests and the production build pass. The research screen renders imported OSD-656 assay values in their published relative units. The bone-cell panel uses imported OSD-546 TSPAN6 sample values, while the muscle panel withholds OSD-195 numbers. OSD-654 is identified as animal research. Reflection: the remaining P1 data dependency is verified processed OSD-195 source files and sample metadata. The UI exposes import status and comparison-readiness reasons; raw microarray interpretation remains outside the frontend scope.

Follow-up steps 1–10 were reviewed on 14 November 2026 against the new backend branch's handoff and live responses. The dedicated RadLab endpoint and OSD-817 `histology_records[]` were adopted within `Frontend/`; OSD-195 and OSD-546 behavior stayed intact. Reflection: reusing the existing research catalogue and body-system panel kept this update small. Checking one real record before finalizing caught the precise published units and the optic-nerve body-system key. The backend branch currently deletes `Frontend/` in its diff against `main`, so it should not be merged wholesale without resolving that deletion.

Dashboard redesign steps 1–10 were reviewed on 14 November 2026 against the requested vitals/body layout, pain focus, severity colors, three-bar menu, manual map selection, and timed reminder. Reflection: reusing the existing body map, location API, and case data avoided a second reporting flow. The mobile review exposed an oversized navigation row, so its links were moved into the menu at narrow widths. A live report exposed an incorrect scheduled-reminder link, which was corrected to the procedure guide. The production build, 19 tests, live HTTP scenario, and browser flow passed; only `Frontend/` was edited.

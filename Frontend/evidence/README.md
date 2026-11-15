# Frontend visual acceptance evidence

Browser checks used the local Vite app against an isolated backend reporting contract `2.7.0`, with a disposable SQLite demo database. All patient readings and scenarios shown here are fictional. The 2.5.0 and 2.6.0 images were captured in the earlier browser acceptance runs and copied here so the evidence stays with the frontend change.

| Contract | Screen / check | Screenshot |
|---|---|---|
| 2.5.0 | Habitat map, zone choice, equipment route | [habitat-route-2.5.png](habitat-route-2.5.png) |
| 2.5.0 | Hatch state and route invalidation | [habitat-hatches-2.5.png](habitat-hatches-2.5.png) |
| 2.6.0 | Individual baselines and quality notices | [monitoring-overview-2.6.png](monitoring-overview-2.6.png) |
| 2.6.0 | Monitoring concern and investigation | [monitoring-investigation-2.6.png](monitoring-investigation-2.6.png) |
| 2.7.0 | Reset-first reassessment scenario and actor | [scenario-reassessment-2.7.png](scenario-reassessment-2.7.png) |
| 2.7.0 | History chart from returned timestamps and values | [history-chart-2.7.png](history-chart-2.7.png) |
| 2.7.0 | Observation provenance, quality, detection and baseline membership | [history-rows-2.7.png](history-rows-2.7.png) |
| 2.7.0 | Crew member role, Close absent | [role-crew-2.7.png](role-crew-2.7.png) |
| 2.7.0 | Officer role, Close choice for awaiting-review concern | [role-close-2.7.png](role-close-2.7.png) |
| 2.7.0 | Urgent interruption at BP procedure step 3 | [procedure-urgent-2.7.png](procedure-urgent-2.7.png) |
| 2.7.0 | Emergency interruption at BP procedure step 3 | [procedure-emergency-2.7.png](procedure-emergency-2.7.png) |

Browser interactions confirmed the scenario reset disclosure, all three scenario IDs, reassessment completion after three good-quality fictional readings, backend transition to `awaiting_review`, crew Close exclusion, officer Close success, and persisted session step 3 on both interruption routes. The chart plotted 15 returned heart-rate records and the table showed the same backend rows. An isolated backend was necessary because every live scenario intentionally resets fictional demo state. Screenshots are browser viewport captures; the 2.7.0 screen is represented by several captures at different scroll positions.

## Contract 2.8.0 / Milestone 6, part 1

This run used Vite at `127.0.0.1:5177` against an isolated local backend at `127.0.0.1:8001` reporting contract `2.8.0`, ruleset `DET-1.1`, and a disposable SQLite demo database. The backend returned three procedure summaries. Its fictional SpO₂ decline scenario requested `PROC-PO-01`; its fictional temperature deviation scenario requested `PROC-TEMP-01`. In each case the frontend selected the requested procedure, started a separate backend session, acknowledged five steps in order, and submitted a technically accepted simulated reading. Reload restored the session. The map recommended `EQ-THERM-01` and returned a route to its crew-quarters zone. A mismatched preview remained visible but its session start was disabled. The existing six-step BP picture guide still rendered. Neither guide or result has been validated with real hardware or reviewed by a flight surgeon.

| Screen / check | Screenshot |
|---|---|
| Pulse oximeter desktop picture guide | [pulse-oximeter-guide-2.8.png](pulse-oximeter-guide-2.8.png) |
| Pulse oximeter 3D replay | [pulse-oximeter-3d-2.8.png](pulse-oximeter-3d-2.8.png) |
| Pulse oximeter accepted simulated result | [pulse-oximeter-result-2.8.png](pulse-oximeter-result-2.8.png) |
| Pulse oximeter narrow-screen picture guide | [pulse-oximeter-mobile-guide-2.8.png](pulse-oximeter-mobile-guide-2.8.png) |
| Thermometer desktop picture guide | [thermometer-guide-2.8.png](thermometer-guide-2.8.png) |
| Thermometer 3D replay | [thermometer-3d-2.8.png](thermometer-3d-2.8.png) |
| Thermometer accepted simulated result | [thermometer-result-2.8.png](thermometer-result-2.8.png) |
| Thermometer narrow-screen result | [thermometer-mobile-2.8.png](thermometer-mobile-2.8.png) |
| Thermometer narrow-screen picture guide | [thermometer-mobile-guide-2.8.png](thermometer-mobile-guide-2.8.png) |
| Thermometer equipment and backend route | [thermometer-route-2.8.png](thermometer-route-2.8.png) |

## Milestones 6 and 7 software slice — coordination and local-service recovery

The same isolated 2.8.0 backend and a Vite page at `127.0.0.1:5178` were used for this run. A fictional sustained temperature scenario opened `CASE-952C84A0FA` with `PROC-TEMP-01`; the case view displayed that backend request, the scheduled BP screening and the pending reassessment. After a manual Medical Bay zone confirmation, the backend recommended ready `EQ-THERM-01` and a route through Exercise Bay to Crew Quarters. The case panel then displayed the matching device. When the backend was stopped, a case refresh failed, the local-service banner identified retained data as potentially stale, and the emergency guidance page remained accessible. A fictional activation attempt did not show a saved response. Restarting the backend restored health checks and refreshed bootstrap and the active case. This verifies loss-of-service disclosure and recovery for a running browser session, not durable offline write queuing or a full onboard offline deployment.

| Screen / check | Screenshot |
|---|---|
| Requested assessment and backend schedule | [care-coordination-case-2.8.png](care-coordination-case-2.8.png) |
| Matching thermometer device and route | [care-coordination-device-2.8.png](care-coordination-device-2.8.png) |
| Narrow-screen case and device cards | [care-coordination-mobile-2.8.png](care-coordination-mobile-2.8.png) |
| Service loss with retained case state | [local-service-unavailable-2.8.png](local-service-unavailable-2.8.png) |
| Service restoration with case reload | [local-service-recovered-2.8.png](local-service-recovered-2.8.png) |

## Contract 2.10.0 — screening and recovery

This browser run used Vite at `127.0.0.1:5178` against an isolated local 2.10.0 backend at `127.0.0.1:8001`, with a disposable SQLite database. The three returned assessment states were overdue temperature, due blood pressure and upcoming pulse oximetry. An overdue reminder acknowledgement survived reload while its assessment stayed overdue. Starting temperature screening without a symptom returned case `CASE-65BDC7D388` and session `SES-9134831E5D`; the procedure coach opened that in-progress session and retained it after reload. The narrow viewport showed the schedule and controls. During a deliberate server outage the banner marked retained information as potentially stale. After restart, `/system/recovery` reported one open case, one session, two open reminders, no undelivered messages and simulated link `up`. These IDs and counts belong to the disposable demonstration only.

| Screen / check | Screenshot |
|---|---|
| Three backend screening states and reminder controls | [screening-schedule-2.10.png](screening-schedule-2.10.png) |
| Durable reminder acknowledgement with assessment still overdue | [screening-reminder-ack-2.10.png](screening-reminder-ack-2.10.png) |
| Routine assessment in the temperature procedure coach | [screening-start-session-2.10.png](screening-start-session-2.10.png) |
| Narrow-screen schedule and controls | [screening-mobile-2.10.png](screening-mobile-2.10.png) |
| Local server recovery snapshot | [recovery-snapshot-2.10.png](recovery-snapshot-2.10.png) |

## Contract 2.10.0 — simulated communications and environmental context

The next software-only browser run used Vite at `127.0.0.1:5178` against an isolated 2.10.0 backend and disposable SQLite database. NASA-RadLab was imported into that database from the repository's source file. The communications view displayed the backend's 300-second one-way delay. A crew-authored fictional message stayed `queued` during a simulated link outage and became `in_transit` after restoration, with `deliver_at` supplied by the backend. An emergency activation queued urgent message `MSG-6D8D8B435A`; the emergency screen linked to that exact queue record and explicitly kept onboard action independent of delivery. This run did not wait five minutes for delivery or exercise a live ground acknowledgement; backend tests cover those transitions, while the frontend acknowledgement control has a focused role and status test. The environment view showed historical ISS RadLab readings with source file, row, units and NASA link, plus the backend's caution. NASA-EDA returned `NOT_DOWNLOADED` with a `BLOCKED` note because no source file or importer exists. The narrow-screen caution remained readable. The sidebar was made viewport-sticky so emergency assistance remains visible on long desktop pages.

| Screen / check | Screenshot |
|---|---|
| Crew message queued during simulated ground-link outage | [comms-queued-outage-2.10.png](comms-queued-outage-2.10.png) |
| Message in transit after simulated link restoration | [comms-in-transit-2.10.png](comms-in-transit-2.10.png) |
| Emergency response with queued ground message ID | [emergency-comms-link-2.10.png](emergency-comms-link-2.10.png) |
| Attributed RadLab context and visible emergency entry | [environment-context-2.10.png](environment-context-2.10.png) |
| Narrow-screen environmental caution | [environment-mobile-2.10.png](environment-mobile-2.10.png) |

## Contract 2.11.0 — device status and controlled case closure

An isolated 2.11.0 backend and disposable database supplied the device inventory. The browser displayed authoritative `usable` values and reasons, including an unknown BP monitor and another missing its cuff. A routine BP screening opened case `CASE-A9340887E1`; after Medical Bay confirmation, the backend recommended `EQ-BP-01` with route `REC-30FE377697`. Marking that device `needs_service` returned the recommendation ID as invalidated. The frontend removed the cached selected device and route; the active procedure session was not claimed cancelled. A resolution request on that in-progress case returned all three backend blockers: session in progress, assessment requested and state not resolvable. The case remained open.

After a demo reset, a separate fictional emergency opened `CASE-6778E1C1BE`. A crew acknowledgement left it escalated. The crew medical officer then resolved it; the backend kept urgent priority but set `attention.interrupt` to false and returned a warning about unacknowledged ground message `MSG-E6A6DBC538`. The frontend displayed that warning, removed the active urgent treatment of the resolved case, and retained the resolved case ID in the page URL. Reloading that URL restored the resolved record. The narrow-screen result remained readable. These IDs refer only to the disposable scenario. Follow-up cancellation was verified in a focused frontend test and backend tests; this browser run had no outstanding follow-up to cancel.

| Screen / check | Screenshot |
|---|---|
| Authoritative device usability and unavailable reasons | [inventory-overview-2.11.png](inventory-overview-2.11.png) |
| BP device and backend route before status change | [inventory-route-before-2.11.png](inventory-route-before-2.11.png) |
| Cached route removed after device invalidation | [inventory-invalidation-2.11.png](inventory-invalidation-2.11.png) |
| All backend case-resolution blockers | [case-resolution-blockers-2.11.png](case-resolution-blockers-2.11.png) |
| Resolved case and unacknowledged urgent message warning | [case-resolution-success-2.11.png](case-resolution-success-2.11.png) |
| Narrow-screen resolved case | [case-resolution-mobile-2.11.png](case-resolution-mobile-2.11.png) |

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

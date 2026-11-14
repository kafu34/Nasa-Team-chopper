# 3D Anatomical Twin backend handoff

## Current behavior

The frontend allows free-axis rotation, zoom, and an exact tap on its local 3D surface model. It reports the detailed site to the user while sending only an existing fixture `region_id` and `laterality` to `POST /api/v1/symptoms`. For example, a right shoulder or right elbow tap is sent under `upper_arm`/`right`. The exact model point and detailed site are placed at the beginning of `note` as a versioned diagram string and restored from the case response. This works with the current backend but the point is not a first-class API value. It is a point on a stylized diagram, not a measured physical location or a diagnosis.

## Additive contract proposal for backend owner

1. Add stable detailed site identifiers for shoulder and elbow, and ideally all named surface parts in `src/anatomy-sites.ts`. Keep existing broad region IDs accepted for older clients and for rule grouping. Do not silently reinterpret historical `upper_arm` records as shoulder or elbow.
2. Add an optional structured `surface_point` to symptom create and symptom output, for example `{ "model_id": "sentinel-body-v1", "site_id": "right_shoulder", "x": -0.468, "y": 0.704, "z": 0.131 }`. Preserve it in case retrieval. Validate `model_id`, known `site_id`, finite bounded coordinates, and matching side. Keep the field optional so existing clients still work.
3. Return both the broad rule region and detailed surface site. The rule engine may continue using the broad region until clinical or mission requirements justify a separate rule; a diagram point alone should not drive clinical conclusions.
4. Once the structured field is deployed and documented in OpenAPI, the frontend can send it directly and stop encoding it into `note`. Read historical versioned notes for compatibility. Keep user-entered note text distinct from machine-readable location data.

The frontend currently has no need for backend changes to rotate, zoom, or mark a point. These backend changes are needed for interoperable, queryable precision beyond this UI.

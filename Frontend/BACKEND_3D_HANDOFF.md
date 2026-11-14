# 3D Anatomical Twin backend handoff — integrated

## Current behavior

The frontend allows free-axis rotation, zoom, and an exact tap on its local 3D surface model. It reports the detailed site to the user while sending an existing fixture `region_id`, `laterality`, and a structured `surface_point` to `POST /api/v1/symptoms`. For example, a right shoulder or right elbow tap is sent under `upper_arm`/`right` with its own `site_id` and model coordinates. The merged backend stores the structured field and returns it through case retrieval. Old versioned note points remain readable for historical reports. It is a point on a stylized diagram, not a measured physical location or a diagnosis.

## Implemented additive contract

1. The backend defines the same 35 detailed sites in `Backend/app/services/surface_sites.py`. Existing broad region IDs remain accepted, and historical `upper_arm` records are not reinterpreted as shoulder or elbow.
2. `POST /api/v1/symptoms` optionally accepts `{ "model_id": "sentinel-body-v1", "site_id": "right_shoulder", "x": -0.468, "y": 0.704, "z": 0.131 }` as `surface_point`. Create and case responses return it with `site_label`. The backend validates the model, site, side, and coordinate bounds.
3. The rule engine continues using broad regions. The duplicate rule compares detailed site IDs so shoulder and elbow reports do not hide each other.
4. New point reports send the structured field and leave user-entered note text separate. The frontend still reads historical versioned notes for compatibility.

The backend `surface_model` catalogue is included in the bootstrap response. A keyboard named-area choice does not invent a coordinate; its site name is retained in the note until a point is tapped.

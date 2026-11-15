"""Role-based access (plan step 36; 36.1 in 2.7.0, the full matrix in 2.9.0).

Role codes come from the fixture: `role_code` on each crew member, plus fictional `ground_personnel` (flight
surgeon, ground support). Ground personnel are valid actors for role checks, but they are not habitat crew.

LIMITATION: there is no authentication. Actor and viewer IDs are self-declared, so this is role enforcement in a
simulation, not security. A request without `viewer_id` keeps the open demonstration behaviour.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from .. import models as m
from ..errors import ApiError, not_found
from .audit import audit

ROLE_CODES = ("crew_member", "crew_medical_officer", "flight_surgeon", "ground_support")
CLINICAL = {"crew_medical_officer", "flight_surgeon"}
CREW = {"crew_member", "crew_medical_officer"}
GROUND = {"flight_surgeon", "ground_support"}

# action -> (allowed roles, own-record exception for crew_member, description)
PERMISSIONS: dict[str, tuple[set[str], bool, str]] = {
    "monitoring_concern.close": (CLINICAL, False, "Close a monitoring concern after review."),
    "monitoring_concern.continue": (CREW | {"flight_surgeon"}, False, "Record a continue-monitoring review."),
    "baseline.recompute": (CLINICAL, False, "Create a new baseline version."),
    "hatch.change": (CREW, False, "Open or close a hatch (habitat crew only)."),
    "case.acknowledge": (CREW | {"flight_surgeon"}, False, "Acknowledge a case alert."),
    "case.read_sensitive": (CLINICAL, True, "Read a case with symptoms, measurements and audit (viewer_id)."),
    "observations.read_history": (CLINICAL, True, "Read observation history and monitoring (viewer_id)."),
    "comms.send_to_ground": (CREW, False, "Queue a medical message to the ground."),
    "comms.send_to_crew": (GROUND, False, "Queue a message to the crew."),
    "comms.acknowledge_to_ground": ({"flight_surgeon"}, False, "Acknowledge a delivered medical message sent to "
                                   "the ground; only its addressee, the flight surgeon (2.11.1)."),
    "comms.acknowledge_to_crew": (CREW, False, "Acknowledge a delivered message sent to the crew."),
    "comms.link": (CREW | GROUND, False, "Simulate loss or restoration of the communication link."),
    "inventory.update": (CREW, False, "Update a device's readiness, supplies or location (2.11.0)."),
    "case.resolve": (CLINICAL, False, "Resolve a case after its open items are closed (2.11.0)."),
}


def personnel(fx: dict) -> list[dict]:
    crew = [{"person_id": fx[k]["astronaut_id"], "display_name": fx[k]["display_name"],
             "role_code": fx[k].get("role_code", "crew_member"), "location": "habitat", "kind": "crew"}
            for k in ("astronaut", "responder") if k in fx]
    ground = [{**{k: g[k] for k in ("person_id", "display_name", "role_code", "location")}, "kind": "ground"}
              for g in fx.get("ground_personnel", [])]
    return crew + ground


def role_code(fx: dict, person_id: str) -> str:
    return next((p["role_code"] for p in personnel(fx) if p["person_id"] == person_id), "crew_member")


def resolve(db: Session, fx: dict, person_id: str) -> tuple[str, str]:
    """(kind, role_code) for a crew member in the database or a fictional ground person; 404 otherwise."""
    if db.get(m.Astronaut, person_id) is not None:
        return "crew", role_code(fx, person_id)
    g = next((p for p in fx.get("ground_personnel", []) if p["person_id"] == person_id), None)
    if g is None:
        raise not_found("Person", person_id)
    return "ground", g["role_code"]


def require(db: Session, fx: dict, actor_id: str, action: str, entity_type: str, entity_id: str,
            case_id: str | None = None, record_owner_id: str | None = None) -> str:
    """404 for an unknown person; 403 ROLE_NOT_PERMITTED (audited) when the role may not perform the action."""
    _, role = resolve(db, fx, actor_id)
    allowed, own_ok, _ = PERMISSIONS[action]
    if role in allowed or (own_ok and role == "crew_member" and record_owner_id == actor_id):
        return role
    audit(db, actor_id, "access.denied", entity_type, entity_id, case_id, attempted_action=action,
          role_code=role, allowed_roles=sorted(allowed))
    db.commit()
    raise ApiError(403, "ROLE_NOT_PERMITTED", f"Role '{role}' may not perform '{action}'.",
                   {"actor_id": actor_id, "role_code": role, "allowed_roles": sorted(allowed), "action": action,
                    "own_record_allowed": own_ok})


def check_viewer(db: Session, fx: dict, viewer_id: str | None, action: str, entity_type: str, entity_id: str,
                 record_owner_id: str) -> None:
    """Sensitive reads: no viewer keeps the demo behaviour; a declared viewer is role-checked and audited."""
    if viewer_id is None:
        return
    role = require(db, fx, viewer_id, action, entity_type, entity_id, record_owner_id=record_owner_id)
    audit(db, viewer_id, "record.viewed", entity_type, entity_id, None, read_action=action, role_code=role)
    db.commit()


def matrix(fx: dict) -> dict:
    return {"role_codes": list(ROLE_CODES),
            "permissions": [{"action": a, "allowed_roles": sorted(r), "own_record_allowed": own, "description": d}
                            for a, (r, own, d) in PERMISSIONS.items()],
            "personnel": personnel(fx),
            "limitation": ("No authentication: actor and viewer IDs are self-declared. This is role enforcement in a "
                           "simulation, not security. Requests without viewer_id keep the open demonstration "
                           "behaviour.")}

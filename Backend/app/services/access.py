"""Role-based access, first part of plan step 36 (contract 2.7.0).

Role codes come from the fixture (`role_code` on each crew member); anyone without one is `crew_member`.
Only the actions listed in PERMISSIONS are role-checked so far. The other sensitive endpoints are still open to any
registered crew member; step 36 adds them.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from .. import models as m
from ..errors import ApiError, not_found
from .audit import audit

ROLE_CODES = ("crew_member", "crew_medical_officer", "flight_surgeon", "ground_support")
PERMISSIONS = {
    "monitoring_concern.close": {"crew_medical_officer", "flight_surgeon"},
    "baseline.recompute": {"crew_medical_officer", "flight_surgeon"},
}


def role_code(fx: dict, astronaut_id: str) -> str:
    for key in ("astronaut", "responder"):
        person = fx.get(key) or {}
        if person.get("astronaut_id") == astronaut_id:
            return person.get("role_code", "crew_member")
    return "crew_member"


def require(db: Session, fx: dict, actor_id: str, action: str, entity_type: str, entity_id: str,
            case_id: str | None = None) -> str:
    """404 for an unknown actor; 403 ROLE_NOT_PERMITTED (audited) when the role may not perform the action."""
    if db.get(m.Astronaut, actor_id) is None:
        raise not_found("Astronaut", actor_id)
    role = role_code(fx, actor_id)
    allowed = PERMISSIONS[action]
    if role not in allowed:
        audit(db, actor_id, "access.denied", entity_type, entity_id, case_id, attempted_action=action,
              role_code=role, allowed_roles=sorted(allowed))
        db.commit()
        raise ApiError(403, "ROLE_NOT_PERMITTED", f"Role '{role}' may not perform '{action}'.",
                       {"actor_id": actor_id, "role_code": role, "allowed_roles": sorted(allowed),
                        "action": action})
    return role

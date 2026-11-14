from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from .. import models as m
from ..db import utcnow


def audit(db: Session, actor: str, action: str, entity_type: str, entity_id: str,
          case_id: Optional[str] = None, **details: Any) -> m.AuditEvent:
    ev = m.AuditEvent(timestamp=utcnow(), actor=actor, action=action, entity_type=entity_type,
                      entity_id=entity_id, case_id=case_id, details=details)
    db.add(ev)
    return ev

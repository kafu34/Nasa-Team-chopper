"""Seeds the fictional demonstration world from shared/fixtures/demo_scenario.json.

Reset deletes and re-creates only synthetic tables. NASA research tables are never touched.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import models as m
from .db import utcnow


@lru_cache(maxsize=4)
def _load(path: str, mtime: float) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_fixture(path: Path) -> dict:
    return _load(str(path), path.stat().st_mtime)


def _ago(now: datetime, minutes: float | None) -> datetime | None:
    return None if minutes is None else now - timedelta(minutes=minutes)


def is_seeded(db: Session) -> bool:
    return db.scalar(select(m.Astronaut.astronaut_id).limit(1)) is not None


def seed_demo(db: Session, fx: dict, now: datetime | None = None) -> None:
    now = now or utcnow()
    hab = fx["habitat"]
    db.add(m.Habitat(habitat_id=hab["habitat_id"], name=hab["name"], map_version=hab["map_version"]))
    db.flush()
    for z in hab["zones"]:
        db.add(m.Zone(zone_id=z["zone_id"], habitat_id=hab["habitat_id"], name=z["name"]))
    db.flush()
    for c in hab["connections"]:
        db.add(m.ZoneConnection(habitat_id=hab["habitat_id"], **c))
    for person in (fx["astronaut"], fx["responder"]):
        mis = person["mission"]
        db.add(
            m.Astronaut(
                astronaut_id=person["astronaut_id"],
                display_name=person["display_name"],
                role=person["role"],
                fictional=person["fictional"],
                mission_id=mis["mission_id"],
                mission_name=mis["mission_name"],
                habitat_id=mis["habitat_id"],
                mission_day=mis["mission_day"],
            )
        )
    for a in fx["anchors"]:
        db.add(
            m.WirelessAnchor(
                anchor_id=a["anchor_id"],
                zone_id=a["zone_id"],
                enabled=a["enabled"],
                verified_at=_ago(now, a["verified_minutes_ago"]),
                verified_by=a["verified_by"],
            )
        )
    proc = fx["procedure"]
    db.add(
        m.ProcedureDefinition(
            procedure_id=proc["procedure_id"],
            version=proc["version"],
            title=proc["title"],
            required_capability=proc["required_capability"],
            definition=proc,
        )
    )
    db.flush()
    for e in fx["equipment"]:
        db.add(
            m.Equipment(
                equipment_id=e["equipment_id"],
                device_model=e["device_model"],
                capability=e["capability"],
                zone_id=e["zone_id"],
                readiness=e["readiness"],
                readiness_verified_at=_ago(now, e["readiness_verified_minutes_ago"]),
                supplies=e["supplies"],
                required_supplies=e["required_supplies"],
                compatible_procedure_ids=e["compatible_procedure_ids"],
                status_updated_at=now,
            )
        )
    astro_id = fx["astronaut"]["astronaut_id"]
    for o in fx["observations"]:
        db.add(
            m.HealthObservation(
                observation_id=o["observation_id"],
                astronaut_id=astro_id,
                type=o["type"],
                value=o["value"],
                unit=o["unit"],
                observed_at=_ago(now, o["minutes_ago"]),
                recorded_at=_ago(now, o["minutes_ago"]),
                source=o["source"],
                quality=o["quality"],
                simulated=True,
            )
        )
    sa = fx["scheduled_assessment"]
    db.add(
        m.ScheduledAssessment(
            assessment_id=sa["assessment_id"],
            astronaut_id=sa["astronaut_id"],
            title=sa["title"],
            capability=sa["capability"],
            procedure_id=sa["procedure_id"],
            due_at=_ago(now, sa["due_minutes_ago"]),
            status="scheduled",
            reason=sa["reason"],
        )
    )
    db.add(
        m.AuditEvent(
            timestamp=now,
            actor="system",
            action="demo.seeded",
            entity_type="fixture",
            entity_id=fx["fixture_version"],
            details={"fixture_version": fx["fixture_version"]},
        )
    )
    db.commit()


def reset_demo(db: Session, fx: dict) -> dict:
    """Delete every synthetic record and re-seed. Research tables are not touched."""
    research_before = db.query(m.ResearchMeasurement).count()
    for table in m.SYNTHETIC_TABLES:
        db.execute(delete(table))
    db.commit()
    seed_demo(db, fx)
    research_after = db.query(m.ResearchMeasurement).count()
    return {"research_records_before": research_before, "research_records_after": research_after}

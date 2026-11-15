"""Deterministic, versioned rules for symptom intake (RULESET-P0-1.0).

Rules
-----
R-SYM-00  Validate region/laterality/onset against the fixture.
R-SYM-01  An identical report (same region, laterality, severity and surface site) within 10 minutes is a
          duplicate. Two different detailed sites in one broad region (e.g. shoulder and elbow) are kept apart.
R-SYM-02  A symptom opens (or joins) the astronaut's open routine case and moves it to 'investigating'.
R-SYM-03  If a configured symptom-linked scheduled assessment exists (2.9.0: daily screenings are not), link it and move the case to 'awaiting_assessment'.
          This is a fictional demonstration configuration. It does NOT claim the symptom is a clinical
          indication for blood-pressure testing.
R-SYM-04  Severity >= 8 raises the case priority to 'urgent' and advises notifying the crew medical officer.
          The priority is never lowered automatically (cases.raise_priority, 2.6.0).
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import RULESET_VERSION
from ..db import utcnow
from ..errors import ApiError, not_found
from ..schemas.cases import SymptomCreate
from . import cases as case_svc
from . import surface_sites
from .audit import audit

DUPLICATE_WINDOW = timedelta(minutes=10)
HIGH_SEVERITY = 8

NEXT_ACTION_ASSESSMENT = (
    "Complete the scheduled non-invasive blood-pressure assessment (PROC-BP-01). This is a configured "
    "demonstration assessment; the reported symptom has not been clinically evaluated."
)
NEXT_ACTION_MONITOR = (
    "Symptom recorded. Continue routine activities and report any change. Contact the crew medical officer "
    "if you are concerned."
)
HIGH_SEVERITY_PREFIX = "High severity reported: notify the crew medical officer now. "


def report_symptom(db: Session, fx: dict, body: SymptomCreate) -> tuple[m.SymptomReport, m.MedicalCase, bool]:
    astro = db.get(m.Astronaut, body.astronaut_id)
    if astro is None:
        raise not_found("Astronaut", body.astronaut_id)
    regions = {r["region_id"]: r for r in fx["anatomical_regions"]}
    region = regions.get(body.region_id)
    if region is None:
        raise ApiError(422, "UNKNOWN_REGION", f"Region '{body.region_id}' is not defined.",
                       {"allowed_region_ids": sorted(regions)})
    if not region["lateral"] and body.laterality in ("left", "right", "bilateral"):
        raise ApiError(422, "INVALID_LATERALITY", f"Region '{body.region_id}' does not take a side.",
                       {"allowed_laterality": ["midline", "not_applicable"]})
    surface = surface_sites.validate(body.surface_point, body.region_id, body.laterality)         if body.surface_point is not None else None
    site_id = surface["site_id"] if surface else None
    now = utcnow()
    if body.onset > now + timedelta(minutes=5):
        raise ApiError(422, "TIMESTAMP_IN_FUTURE", "onset is in the future.", {"onset": body.onset.isoformat()})

    # R-SYM-01 duplicate detection
    dup = db.scalars(
        select(m.SymptomReport).join(m.MedicalCase, m.MedicalCase.case_id == m.SymptomReport.case_id)
        .where(m.SymptomReport.astronaut_id == body.astronaut_id, m.SymptomReport.region_id == body.region_id,
               m.SymptomReport.laterality == body.laterality, m.SymptomReport.severity == body.severity,
               m.SymptomReport.reported_at >= now - DUPLICATE_WINDOW,
               m.MedicalCase.state.in_(case_svc.OPEN_STATES))
        .order_by(m.SymptomReport.reported_at.desc())
    ).all()
    dup = next((s for s in dup if (s.surface_point or {}).get("site_id") == site_id), None)
    if dup is not None:
        case = db.get(m.MedicalCase, dup.case_id)
        audit(db, body.astronaut_id, "symptom.duplicate_ignored", "symptom_report", dup.symptom_id, case.case_id,
              rule="R-SYM-01", ruleset_version=RULESET_VERSION)
        db.commit()
        return dup, case, True

    # R-SYM-02 open or join a case
    case = case_svc.open_case(db, body.astronaut_id, "routine")
    if case is None:
        case = m.MedicalCase(case_id=m.new_id("CASE"), astronaut_id=body.astronaut_id, kind="routine",
                             state="detected", priority="routine", evidence=[], next_action=NEXT_ACTION_MONITOR,
                             follow_up_status="none", ruleset_version=RULESET_VERSION, created_at=now, updated_at=now)
        db.add(case)
        db.flush()
        audit(db, "rules-engine", "case.created", "medical_case", case.case_id, case.case_id,
              rule="R-SYM-02", ruleset_version=RULESET_VERSION, state="detected")

    sym = m.SymptomReport(symptom_id=m.new_id("SYM"), astronaut_id=body.astronaut_id, region_id=body.region_id,
                          laterality=body.laterality, severity=body.severity, onset=body.onset, note=body.note,
                          surface_point=surface,
                          reported_at=now, case_id=case.case_id)
    db.add(sym)
    case_svc.add_evidence(case, "symptom", sym.symptom_id,
                          f"Self-reported {body.region_id} ({body.laterality})"
                          + (f", surface site {site_id}" if site_id else "") + f", severity {body.severity}/10")
    audit(db, body.astronaut_id, "symptom.reported", "symptom_report", sym.symptom_id, case.case_id,
          rule="R-SYM-02", region_id=body.region_id, laterality=body.laterality, severity=body.severity,
          surface_site_id=site_id)
    if case.state == "detected":
        case_svc.transition(db, case, "investigating", "rules-engine", "R-SYM-02: symptom report opens investigation")

    # R-SYM-03 link configured assessment
    if case.state == "investigating":
        sa = db.scalars(select(m.ScheduledAssessment)
                        .where(m.ScheduledAssessment.astronaut_id == body.astronaut_id,
                               m.ScheduledAssessment.status == "scheduled",
                               m.ScheduledAssessment.symptom_linked.is_(True))
                        .order_by(m.ScheduledAssessment.due_at)).first()
        if sa is not None:
            sa.case_id = case.case_id
            case.requested_assessment = {"assessment_id": sa.assessment_id, "capability": sa.capability,
                                         "procedure_id": sa.procedure_id, "status": "requested",
                                         "configured_reason": sa.reason}
            case_svc.add_evidence(case, "scheduled_assessment", sa.assessment_id, sa.title)
            case_svc.transition(db, case, "awaiting_assessment", "rules-engine",
                                "R-SYM-03: configured scheduled assessment linked (demonstration configuration)")
            case_svc.set_next_action(case, NEXT_ACTION_ASSESSMENT)
        else:
            case_svc.set_next_action(case, NEXT_ACTION_MONITOR)

    # R-SYM-04 high severity
    if body.severity >= HIGH_SEVERITY:
        case_svc.raise_priority(db, case, "rules-engine", "R-SYM-04",
                                f"Self-reported severity {body.severity}/10 (R-SYM-04)",
                                HIGH_SEVERITY_PREFIX.strip(), severity=body.severity, symptom_id=sym.symptom_id)
    case.updated_at = now
    db.commit()
    return sym, case, False

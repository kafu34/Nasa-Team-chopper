"""Isolated live-demonstration scenarios (contract 2.7.0).

Each scenario resets the synthetic demo, then builds its state through the normal services, so what the browser
sees is what those services produce. The one shortcut, moving a reassessment's due time to the past, is a
simulated clock change and is audited as one. Fictional demonstration data only.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import utcnow
from ..errors import ApiError
from ..schemas.cases import ObservationCreate, SymptomCreate
from ..schemas.procedures import SessionCreate
from ..seed import reset_demo
from . import detection, procedures, rules
from .audit import audit

SCENARIOS = {
    "SCN-REASSESSMENT-DUE": "A heart-rate monitoring concern is open and its reassessment is due now. Submit a good-"
                            "quality heart-rate reading near 66 bpm to complete it.",
    "SCN-URGENT-DURING-PROCEDURE": "A routine blood-pressure session is in progress (2 of 6 steps confirmed) when a "
                                   "severity-9 chest symptom makes the same case urgent.",
    "SCN-EMERGENCY-DURING-PROCEDURE": "A routine blood-pressure session is in progress (2 of 6 steps confirmed) when "
                                      "an emergency is activated for the same astronaut.",
}
ASTRO = "DEMO-001"


def _hr(value: float, minutes_ago: float) -> ObservationCreate:
    return ObservationCreate(astronaut_id=ASTRO, type="heart_rate", value=value, unit="bpm",
                             source="SIMULATED_WEARABLE", quality="good",
                             observed_at=utcnow() - timedelta(minutes=minutes_ago))


def _routine_session(db: Session, fx: dict) -> tuple[str, str]:
    s = fx["demo_symptom"]
    _, case, _ = rules.report_symptom(db, fx, SymptomCreate(
        astronaut_id=ASTRO, region_id=s["region_id"], laterality=s["laterality"], severity=s["severity"],
        onset=utcnow() - timedelta(minutes=s["onset_minutes_ago"]), note=s["note"]))
    session, _ = procedures.create_session(db, SessionCreate(case_id=case.case_id, procedure_id="PROC-BP-01",
                                                             actor_id=ASTRO, mode="self"))
    for step in ("S1", "S2"):
        procedures.confirm_step(db, session.session_id, step, "self_confirmed")
    return case.case_id, session.session_id


def load(db: Session, fx: dict, scenario_id: str) -> dict:
    if scenario_id not in SCENARIOS:
        raise ApiError(404, "NOT_FOUND", f"Scenario '{scenario_id}' was not found.",
                       {"available_scenarios": sorted(SCENARIOS)})
    reset_demo(db, fx)  # also re-creates the version-1 baselines
    out = {"scenario_id": scenario_id, "description": SCENARIOS[scenario_id], "reset_first": True,
           "case_id": None, "session_id": None, "concern_id": None, "emergency_case_id": None,
           "simulated_clock_changes": []}
    if scenario_id == "SCN-REASSESSMENT-DUE":
        for value, ago in ((84, 30), (86, 20), (88, 10)):
            obs, _ = detection.ingest(db, fx, _hr(value, ago))
        out["concern_id"], out["case_id"] = obs.detection["concern_id"], obs.detection["case_id"]
        fu = db.scalars(select(m.FollowUpTask).where(m.FollowUpTask.concern_id == out["concern_id"])).first()
        old = fu.due_at
        fu.due_at = utcnow() - timedelta(minutes=1)
        out["simulated_clock_changes"].append(
            f"Reassessment {fu.follow_up_id} due time moved from {old.isoformat()} to {fu.due_at.isoformat()}.")
    else:
        out["case_id"], out["session_id"] = _routine_session(db, fx)
        if scenario_id == "SCN-URGENT-DURING-PROCEDURE":
            rules.report_symptom(db, fx, SymptomCreate(
                astronaut_id=ASTRO, region_id="chest", laterality="midline", severity=9,
                onset=utcnow() - timedelta(minutes=5), note="Fictional demonstration report: sudden chest pain."))
        else:
            from ..schemas.emergency import EmergencyCreate
            from . import emergency

            emg, _ = emergency.activate(db, EmergencyCreate(astronaut_id=ASTRO, responder_id="DEMO-002",
                                                            trigger="crew_collapse"), fx)
            out["emergency_case_id"] = emg.case_id
    audit(db, "demo", "demo.scenario_loaded", "scenario", scenario_id, out["case_id"],
          simulated_clock_changes=out["simulated_clock_changes"])
    db.commit()
    return out

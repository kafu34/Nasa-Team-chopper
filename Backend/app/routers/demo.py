from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .. import models as m
from ..config import CONTRACT_VERSION, RULESET_VERSION
from ..db import get_db, utcnow
from ..schemas.common import error_responses
from ..schemas.cases import ObservationOut
from ..schemas.demo import (AnchorOut, AstronautOut, BootstrapOut, ConnectionOut, DemoInputs, EquipmentOut, HabitatOut,
                            HealthOut, Mission, ProcedureSummary, RegionOut, ResetOut, ScheduledAssessmentOut, ZoneOut)
from ..seed import reset_demo
from ..services import cases as case_svc
from ..services import datasets as ds
from ..services import observations as obs_svc
from ..services import access, surface_sites
from ..services import demo_scenarios
from ..schemas.monitoring import ScenarioLoaded
from ..services.monitoring import detection_ruleset_out

router = APIRouter()


def astronaut_out(a: m.Astronaut, fx: dict | None = None) -> AstronautOut:
    return AstronautOut(astronaut_id=a.astronaut_id, display_name=a.display_name, role=a.role,
                        role_code=access.role_code(fx or {}, a.astronaut_id), fictional=a.fictional,
                        mission=Mission(mission_id=a.mission_id, mission_name=a.mission_name,
                                        habitat_id=a.habitat_id, mission_day=a.mission_day))


@router.get("/healthz", response_model=HealthOut, tags=["system"], summary="Liveness and database check")
def healthz(db: Session = Depends(get_db)) -> HealthOut:
    try:
        db.execute(text("SELECT 1"))
        db_state = "ok"
    except Exception:  # pragma: no cover - defensive
        db_state = "error"
    return HealthOut(status="ok", service="sentinel-ai-backend", contract_version=CONTRACT_VERSION,
                     database=db_state, offline_capable=True, server_time=utcnow())


@router.get("/api/v1/demo/bootstrap", response_model=BootstrapOut, tags=["demo"],
            summary="Load the fictional DEMO-001 / HAB-01 demonstration state")
def bootstrap(request: Request, db: Session = Depends(get_db)) -> BootstrapOut:
    fx = request.app.state.fixture
    settings = request.app.state.settings
    now = utcnow()
    astro = db.get(m.Astronaut, fx["astronaut"]["astronaut_id"])
    responder = db.get(m.Astronaut, fx["responder"]["astronaut_id"])
    hab = db.get(m.Habitat, astro.habitat_id)
    zones = db.scalars(select(m.Zone).where(m.Zone.habitat_id == hab.habitat_id).order_by(m.Zone.zone_id)).all()
    conns = db.scalars(select(m.ZoneConnection).where(m.ZoneConnection.habitat_id == hab.habitat_id)
                       .order_by(m.ZoneConnection.id)).all()
    assessments = db.scalars(select(m.ScheduledAssessment)
                             .where(m.ScheduledAssessment.astronaut_id == astro.astronaut_id)
                             .order_by(m.ScheduledAssessment.due_at)).all()
    observations = db.scalars(select(m.HealthObservation)
                              .where(m.HealthObservation.astronaut_id == astro.astronaut_id)
                              .order_by(m.HealthObservation.observed_at.desc())).all()
    open_cases = db.scalars(select(m.MedicalCase).where(m.MedicalCase.state.in_(case_svc.OPEN_STATES))
                            .order_by(m.MedicalCase.created_at)).all()
    return BootstrapOut(
        contract_version=CONTRACT_VERSION,
        fixture_version=fx["fixture_version"],
        ruleset_version=RULESET_VERSION,
        server_time=now,
        disclaimer=fx["disclaimer"],
        astronaut=astronaut_out(astro, fx),
        responder=astronaut_out(responder, fx),
        habitat=HabitatOut(habitat_id=hab.habitat_id, name=hab.name, map_version=hab.map_version,
                           zones=[ZoneOut.model_validate(z) for z in zones],
                           connections=[ConnectionOut.model_validate(c) for c in conns]),
        anchors=[AnchorOut.model_validate(a) for a in db.scalars(select(m.WirelessAnchor)
                                                                 .order_by(m.WirelessAnchor.anchor_id))],
        equipment=[EquipmentOut.model_validate(e) for e in db.scalars(select(m.Equipment)
                                                                      .order_by(m.Equipment.equipment_id))],
        procedures=[ProcedureSummary.model_validate(p) for p in db.scalars(select(m.ProcedureDefinition))],
        scheduled_assessments=[
            ScheduledAssessmentOut(assessment_id=a.assessment_id, astronaut_id=a.astronaut_id, title=a.title,
                                   capability=a.capability, procedure_id=a.procedure_id, due_at=a.due_at,
                                   status=a.status, is_due=a.status == "scheduled" and a.due_at <= now,
                                   reason=a.reason, case_id=a.case_id, completed_at=a.completed_at)
            for a in assessments
        ],
        observations=[ObservationOut.model_validate(o) for o in observations],
        observation_status=obs_svc.statuses(db, fx, astro.astronaut_id),
        open_cases=[case_svc.summary(c) for c in open_cases],
        anatomical_regions=[RegionOut(**r) for r in fx["anatomical_regions"]],
        laterality_values=fx["laterality_values"],
        surface_model=surface_sites.catalogue(),
        surface_models=surface_sites.models_catalogue(),
        anatomical_annotation_kinds=surface_sites.ANNOTATION_KINDS,
        detection_ruleset=detection_ruleset_out(fx),
        demo_inputs=DemoInputs(
            ble_observations=fx["ble_observations"]["observations"],
            expected_zone_id=fx["ble_observations"]["expected_zone_id"],
            symptom=fx["demo_symptom"],
            measurement=fx["demo_measurement"],
            emergency={k: fx["emergency_scenario"][k] for k in ("astronaut_id", "responder_id", "trigger")},
            expected_recommendation=fx["expected_recommendation"],
        ),
        research_datasets=[ds.summary(db, settings, d) for d in ds.CANONICAL_IDS],
    )


@router.post("/api/v1/demo/scenarios/{scenario_id}", response_model=ScenarioLoaded, tags=["demo"],
             responses=error_responses(404),
             summary="Reset, then load an isolated live-demonstration scenario (2.7.0)",
             description="SCN-REASSESSMENT-DUE, SCN-URGENT-DURING-PROCEDURE, SCN-EMERGENCY-DURING-PROCEDURE. The state "
                         "is built through the normal services; any simulated clock change is listed and audited.")
def load_scenario(scenario_id: str, request: Request, db: Session = Depends(get_db)) -> ScenarioLoaded:
    return ScenarioLoaded(**demo_scenarios.load(db, request.app.state.fixture, scenario_id))


@router.post("/api/v1/demo/reset", response_model=ResetOut, tags=["demo"],
             summary="Restore synthetic demo state; NASA research records are not altered")
def reset(request: Request, db: Session = Depends(get_db)) -> ResetOut:
    counts = reset_demo(db, request.app.state.fixture)
    return ResetOut(reset=True, fixture_version=request.app.state.fixture["fixture_version"], reset_at=utcnow(),
                    message="Synthetic demonstration state restored. NASA research records unchanged.", **counts)

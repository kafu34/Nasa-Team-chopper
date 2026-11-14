"""SENTINEL AI backend: FastAPI modular monolith.

Run:  cd Backend && .venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import CONTRACT_VERSION, Settings
from .db import Base, make_engine, make_session_factory
from .errors import install_error_handlers
from .seed import is_seeded, load_fixture, seed_demo

log = logging.getLogger("sentinel")

DESCRIPTION = (
    "SENTINEL AI research demonstration backend (NASA Space Apps Challenge 2026). "
    "Not a clinically validated medical device. All astronaut, habitat and device data are fictional "
    "(SIMULATED_ASTRONAUT / SIMULATED_ENVIRONMENT_OR_DEVICE). NASA research records (NASA_RESEARCH) are kept "
    "separate and are never presented as live astronaut observations. "
    "Errors use the envelope {\"error\": {\"code\", \"message\", \"details\"}}."
)


def _routers():
    from .routers import cases, demo, emergency, procedures, research, spatial

    return [demo.router, cases.router, spatial.router, procedures.router, research.router, emergency.router]


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        startup(app)
        yield
        app.state.engine.dispose()

    app = FastAPI(title="SENTINEL AI Backend API", version=CONTRACT_VERSION, description=DESCRIPTION,
                  lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False,
                       allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type"])
    install_error_handlers(app)
    for r in _routers():
        app.include_router(r)
    return app


def startup(app: FastAPI) -> None:
    settings: Settings = app.state.settings
    engine = make_engine(settings.db_url)
    Base.metadata.create_all(engine)
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.fixture = load_fixture(settings.fixture_path)
    with app.state.session_factory() as db:
        if not is_seeded(db):
            seed_demo(db, app.state.fixture)
            log.info("Seeded demo fixture %s", app.state.fixture["fixture_version"])
        if settings.auto_import_nasa:
            from .importers.osd575 import import_if_available

            result = import_if_available(db, settings)
            log.info("OSD-575 auto-import: %s", result.outcome)
            from .importers import osd656
            from .importers.expression import import_all_available

            log.info("OSD-656 auto-import: %s", osd656.import_if_available(db, settings).outcome)

            for dataset_id, results in import_all_available(db, settings).items():
                log.info("%s auto-import: %s", dataset_id, [r.outcome for r in results])


app = create_app()

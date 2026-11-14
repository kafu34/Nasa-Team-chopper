from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import REPO_DIR, Settings
from app.main import create_app

(Path(__file__).resolve().parent.parent / "var").mkdir(exist_ok=True)  # holds pytest --basetemp

REAL_CSV =REPO_DIR / "data" / "nasa" / "raw" / "LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv"


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def now_iso(seconds_ago: float = 0) -> str:
    return iso(datetime.now(timezone.utc) - timedelta(seconds=seconds_ago))


class Harness:
    """Builds isolated apps on a temporary SQLite file; restart() reopens the same database."""

    def __init__(self, tmp_path: Path):
        self.tmp = tmp_path
        self.raw = tmp_path / "raw"
        self.raw.mkdir()
        self.db_url = f"sqlite:///{(tmp_path / 'sentinel.db').as_posix()}"
        self._client: TestClient | None = None

    def settings(self, auto_import: bool) -> Settings:
        return Settings(db_url=self.db_url, nasa_raw_dir=self.raw, var_dir=self.tmp / "var",
                        auto_import_nasa=auto_import)

    def add_real_csv(self) -> Path:
        dst = self.raw / REAL_CSV.name
        shutil.copyfile(REAL_CSV, dst)
        return dst

    def start(self, auto_import: bool = False) -> TestClient:
        self.stop()
        self._client = TestClient(create_app(self.settings(auto_import)))
        self._client.__enter__()
        return self._client

    def restart(self, auto_import: bool = False) -> TestClient:
        return self.start(auto_import)

    def stop(self) -> None:
        if self._client is not None:
            self._client.__exit__(None, None, None)
            self._client = None


@pytest.fixture
def harness(tmp_path):
    h = Harness(tmp_path)
    yield h
    h.stop()


@pytest.fixture
def client(harness) -> TestClient:
    return harness.start()


@pytest.fixture
def fixture_data(client):
    return client.app.state.fixture


@pytest.fixture
def symptom_payload(fixture_data):
    s = fixture_data["demo_symptom"]
    return {"astronaut_id": s["astronaut_id"], "region_id": s["region_id"], "laterality": s["laterality"],
            "severity": s["severity"], "onset": now_iso(s["onset_minutes_ago"] * 60), "note": s["note"]}


@pytest.fixture
def ble_payload(fixture_data):
    b = fixture_data["ble_observations"]
    return {"astronaut_id": b["astronaut_id"],
            "observations": [{"anchor_id": o["anchor_id"], "rssi_dbm": o["rssi_dbm"],
                              "observed_at": now_iso(o["age_seconds"])} for o in b["observations"]]}

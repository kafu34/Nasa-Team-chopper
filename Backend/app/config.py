"""Runtime settings. All paths default to locations inside the repository."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent

CONTRACT_VERSION = "2.1.0"
RULESET_VERSION = "RULESET-P0-1.0"


def _default_db_url() -> str:
    return os.environ.get("SENTINEL_DB_URL", f"sqlite:///{(BACKEND_DIR / 'var' / 'sentinel.db').as_posix()}")


@dataclass
class Settings:
    db_url: str = field(default_factory=_default_db_url)
    nasa_raw_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("SENTINEL_NASA_RAW_DIR", REPO_DIR / "data" / "nasa" / "raw"))
    )
    fixture_path: Path = field(
        default_factory=lambda: Path(
            os.environ.get("SENTINEL_FIXTURE_PATH", REPO_DIR / "shared" / "fixtures" / "demo_scenario.json")
        )
    )
    var_dir: Path = field(default_factory=lambda: Path(os.environ.get("SENTINEL_VAR_DIR", BACKEND_DIR / "var")))
    auto_import_nasa: bool = field(default_factory=lambda: os.environ.get("SENTINEL_AUTO_IMPORT", "1") != "0")
    cors_origins: tuple[str, ...] = ("http://127.0.0.1:5173", "http://localhost:5173")

    @property
    def import_log_dir(self) -> Path:
        return self.var_dir / "import_logs"

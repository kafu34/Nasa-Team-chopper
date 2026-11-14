"""Write the authoritative API contract generated from the FastAPI app to shared/openapi.yaml.

Usage (from Backend/):  .venv/Scripts/python scripts/export_openapi.py [--check]
--check exits 1 if the committed file differs from the app (contract drift).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import REPO_DIR  # noqa: E402
from app.main import create_app  # noqa: E402

OUT = REPO_DIR / "shared" / "openapi.yaml"
HEADER = ("# SENTINEL AI API contract v2.1 - GENERATED from Backend/app by Backend/scripts/export_openapi.py.\n"
          "# Do not edit by hand. Owner: backend (Claude). Consumer: frontend (Codex).\n")


def generated() -> dict:
    return json.loads(json.dumps(create_app().openapi()))


def render(spec: dict) -> str:
    return HEADER + yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=120)


def main() -> int:
    spec = generated()
    if "--check" in sys.argv:
        current = yaml.safe_load(OUT.read_text(encoding="utf-8")) if OUT.exists() else None
        if current != spec:
            print("shared/openapi.yaml is out of date. Run scripts/export_openapi.py")
            return 1
        print("shared/openapi.yaml matches the app.")
        return 0
    OUT.write_text(render(spec), encoding="utf-8")
    print(f"Wrote {OUT} ({len(spec['paths'])} paths, version {spec['info']['version']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

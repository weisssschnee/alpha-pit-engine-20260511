from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PHASE2_SCHEMA_VERSION = "phase2-v2_1-prototype-v1"
PHASE2_GENERATION_SCHEMA_VERSION = "phase2-v2_1-generation-v1"


def with_schema(payload: dict[str, Any], *, schema_version: str = PHASE2_SCHEMA_VERSION) -> dict[str, Any]:
    versioned = dict(payload)
    versioned["schema_version"] = schema_version
    return versioned


def write_json_artifact(
    path: Path,
    payload: dict[str, Any],
    *,
    schema_version: str = PHASE2_SCHEMA_VERSION,
) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    versioned = with_schema(payload, schema_version=schema_version)
    path.write_text(json.dumps(versioned, ensure_ascii=False, indent=2), encoding="utf-8")
    return versioned


def read_json_artifact(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

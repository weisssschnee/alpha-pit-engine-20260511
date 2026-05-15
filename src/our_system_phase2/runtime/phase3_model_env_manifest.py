"""Write model/environment manifest for replay-aware selector artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _versions() -> dict[str, Any]:
    import sys

    mods = ["sklearn", "numpy", "pandas", "scipy", "joblib"]
    out: dict[str, Any] = {
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
    }
    for name in mods:
        try:
            mod = __import__(name)
            out[name] = getattr(mod, "__version__", "unknown")
        except Exception as exc:
            out[name] = f"ERR:{type(exc).__name__}:{exc}"
    return out


def _inspect_joblib(path: Path) -> dict[str, Any]:
    import joblib

    row: dict[str, Any] = {
        "path": str(path),
        "name": path.name,
        "exists": path.exists(),
        "size": path.stat().st_size if path.exists() else None,
        "mtime": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")
        if path.exists()
        else None,
        "sha256": _sha256(path) if path.exists() else None,
        "load_status": "not_loaded",
        "warnings": [],
    }
    if not path.exists():
        row["load_status"] = "missing"
        return row
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            payload = joblib.load(path)
        row["load_status"] = "loaded"
        row["warnings"] = [
            {
                "category": warning.category.__name__,
                "message": str(warning.message),
            }
            for warning in caught
        ]
        if isinstance(payload, dict):
            row["payload_keys"] = sorted(str(key) for key in payload.keys())
            row["artifact_version"] = payload.get("version")
            row["target"] = payload.get("target")
            row["feature_count"] = len(payload.get("feature_columns") or [])
            model = payload.get("model")
            if model is not None:
                row["model_class"] = f"{type(model).__module__}.{type(model).__name__}"
                row["model_params"] = getattr(model, "get_params", lambda: {})()
        else:
            row["payload_type"] = f"{type(payload).__module__}.{type(payload).__name__}"
    except Exception as exc:
        row["load_status"] = "load_failed"
        row["load_error"] = f"{type(exc).__name__}: {exc}"
    return row


def build_manifest(model_dir: Path) -> dict[str, Any]:
    model_files = sorted(model_dir.glob("*.joblib")) if model_dir.exists() else []
    models = [_inspect_joblib(path) for path in model_files]
    warning_count = sum(len(row.get("warnings") or []) for row in models)
    return {
        "created_at": _now(),
        "experiment_id": "20260515_phase3_model_env_manifest",
        "objective": "Record replay-ranker model artifacts and runtime library versions before Phase3H.",
        "model_dir": str(model_dir),
        "environment": _versions(),
        "model_count": len(models),
        "models": models,
        "warning_count": warning_count,
        "decision": "HOLD_REPRODUCIBILITY" if warning_count else "PASS_MANIFEST_ONLY",
        "next_action": (
            "If warning_count > 0, re-save or retrain replay rankers under the runtime sklearn version "
            "before using them for a promotion-grade Phase3H run."
        ),
    }


def _write_markdown(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# Phase3 Model Environment Manifest",
        "",
        f"- created_at: `{manifest['created_at']}`",
        f"- decision: `{manifest['decision']}`",
        f"- model_dir: `{manifest['model_dir']}`",
        f"- model_count: `{manifest['model_count']}`",
        f"- warning_count: `{manifest['warning_count']}`",
        "",
        "## Environment",
        "",
    ]
    for key, value in manifest["environment"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Models", "", "| name | load_status | warnings | artifact_version | target | feature_count |", "| --- | --- | ---: | --- | --- | ---: |"])
    for row in manifest["models"]:
        lines.append(
            "| {name} | {status} | {warnings} | {version} | {target} | {features} |".format(
                name=row.get("name"),
                status=row.get("load_status"),
                warnings=len(row.get("warnings") or []),
                version=row.get("artifact_version"),
                target=row.get("target"),
                features=row.get("feature_count"),
            )
        )
    lines.extend(["", "## Next Action", "", manifest["next_action"]])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, default=Path("data/models"))
    parser.add_argument("--output-root", type=Path, default=Path("reports/phase3_model_env_manifest_20260515"))
    args = parser.parse_args()

    manifest = build_manifest(args.model_dir)
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "phase3_model_env_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write_markdown(args.output_root / "PHASE3_MODEL_ENV_MANIFEST_2026-05-15.md", manifest)
    print(json.dumps({"decision": manifest["decision"], "model_count": manifest["model_count"], "warning_count": manifest["warning_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

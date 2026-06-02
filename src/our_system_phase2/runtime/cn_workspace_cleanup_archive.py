from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST = Path("runtime/manifests/cn_data_feature_workspace_key_artifacts_20260601.json")
DEFAULT_ARCHIVE_ROOT = Path("archive/workspace_cleanup_20260601")
DEFAULT_REPORT_JSON = Path("reports/CN_WORKSPACE_CLEANUP_ARCHIVE_2026-06-01.json")
DEFAULT_REPORT_MD = Path("reports/CN_WORKSPACE_CLEANUP_ARCHIVE_2026-06-01.md")

STALE_RUNTIME_DIRS = [
    "runtime/cn_factor_pack_phase3aa_micro_selector_20260531",
    "runtime/cn_factor_pack_phase3aa_micro_selector_augmented_20260531",
    "runtime/cn_factor_pack_phase3aa_micro_selector_augmented_fast_20260531",
    "runtime/cn_factor_pack_phase3aa_preflight_light_20260531",
    "runtime/cn_flow_liquidity_factor_pack_v1_micro_selector_20260601",
    "runtime/cn_flow_liquidity_factor_pack_v1_tiny_selector_20260601",
    "runtime/cn_flow_liquidity_factor_pack_v1_selector_gate_20260601",
    "runtime/cn_underutilized_field_factor_pack_v1_selector256_20260601",
    "runtime/cn_research_factor_pack_v2_micro_selector_20260531",
    "runtime/cn_research_factor_pack_v2_micro_selector_fast_20260531",
    "runtime/cn_research_factor_pack_v2_replay_smoke_20260531",
]

CACHE_DIR_NAMES = {"__pycache__", ".pytest_cache"}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _workspace_root() -> Path:
    return Path.cwd().resolve()


def _safe_resolve(root: Path, raw: str) -> Path:
    path = (root / raw).resolve()
    if not _is_relative_to(path, root):
        raise ValueError(f"path escapes workspace: {raw}")
    return path


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return int(path.stat().st_size)
    return int(sum(item.stat().st_size for item in path.rglob("*") if item.is_file()))


def _load_protected_paths(root: Path, manifest_path: Path) -> set[Path]:
    protected: set[Path] = set()
    if not manifest_path.exists():
        return protected
    manifest = _read_json(manifest_path)
    for row in manifest.get("key_artifacts") or []:
        raw = str(row.get("path") or "")
        if not raw:
            continue
        protected.add(_safe_resolve(root, raw))
    return protected


def _contains_protected(path: Path, protected: set[Path]) -> bool:
    resolved = path.resolve()
    for protected_path in protected:
        if protected_path == resolved or _is_relative_to(protected_path, resolved):
            return True
    return False


def _archive_target(root: Path, archive_root: Path, source: Path) -> Path:
    relative = source.resolve().relative_to(root)
    return (archive_root / "stale_runtime" / relative).resolve()


def _collect_cache_dirs(root: Path, archive_root: Path) -> list[Path]:
    dirs: list[Path] = []
    for name in CACHE_DIR_NAMES:
        dirs.extend(path for path in root.rglob(name) if path.is_dir())
    return [
        path.resolve()
        for path in dirs
        if _is_relative_to(path.resolve(), root)
        and not _is_relative_to(path.resolve(), archive_root.resolve())
        and ".git" not in path.parts
    ]


def build_cleanup_plan(*, manifest_path: Path, archive_root: Path) -> dict[str, Any]:
    root = _workspace_root()
    manifest_path = _safe_resolve(root, str(manifest_path))
    archive_root = _safe_resolve(root, str(archive_root))
    protected = _load_protected_paths(root, manifest_path)
    archive_actions: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for raw in STALE_RUNTIME_DIRS:
        source = _safe_resolve(root, raw)
        if not source.exists():
            skipped.append({"path": raw, "reason": "missing"})
            continue
        if _contains_protected(source, protected):
            skipped.append({"path": raw, "reason": "contains_protected_key_artifact"})
            continue
        target = _archive_target(root, archive_root, source)
        if not _is_relative_to(target, archive_root):
            raise ValueError(f"archive target escapes archive root: {target}")
        archive_actions.append(
            {
                "source": str(source.relative_to(root)),
                "target": str(target.relative_to(root)),
                "bytes": _dir_size(source),
            }
        )
    cache_dirs = []
    for path in _collect_cache_dirs(root, archive_root):
        if _contains_protected(path, protected):
            skipped.append({"path": str(path.relative_to(root)), "reason": "cache_dir_contains_protected_key_artifact"})
            continue
        cache_dirs.append({"path": str(path.relative_to(root)), "bytes": _dir_size(path)})
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "dry_run",
        "workspace_root": str(root),
        "manifest_path": str(manifest_path.relative_to(root)),
        "archive_root": str(archive_root.relative_to(root)),
        "archive_actions": archive_actions,
        "cache_remove_actions": cache_dirs,
        "skipped": skipped,
        "totals": {
            "archive_count": len(archive_actions),
            "archive_bytes": int(sum(row["bytes"] for row in archive_actions)),
            "cache_remove_count": len(cache_dirs),
            "cache_remove_bytes": int(sum(row["bytes"] for row in cache_dirs)),
        },
    }


def execute_plan(plan: dict[str, Any]) -> dict[str, Any]:
    root = Path(plan["workspace_root"]).resolve()
    archive_root = (root / plan["archive_root"]).resolve()
    moved: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for action in plan["archive_actions"]:
        source = (root / action["source"]).resolve()
        target = (root / action["target"]).resolve()
        if not source.exists():
            moved.append({**action, "status": "missing_at_execute"})
            continue
        if not _is_relative_to(target, archive_root):
            raise ValueError(f"unsafe target: {target}")
        if target.exists():
            suffix = datetime.now(timezone.utc).strftime("%H%M%S")
            target = target.with_name(f"{target.name}__{suffix}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        moved.append({**action, "target": str(target.relative_to(root)), "status": "moved"})
    for action in plan["cache_remove_actions"]:
        path = (root / action["path"]).resolve()
        if not path.exists():
            removed.append({**action, "status": "missing_at_execute"})
            continue
        if not _is_relative_to(path, root) or _is_relative_to(path, archive_root):
            raise ValueError(f"unsafe cache path: {path}")
        shutil.rmtree(path)
        removed.append({**action, "status": "removed"})
    out = dict(plan)
    out["mode"] = "executed"
    out["executed_at"] = datetime.now(timezone.utc).isoformat()
    out["moved"] = moved
    out["removed"] = removed
    return out


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# CN Workspace Cleanup Archive",
        "",
        f"mode: `{payload['mode']}`",
        "",
        "## Totals",
        "",
    ]
    for key, value in payload["totals"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Archived Runtime Directories", ""])
    for row in payload.get("moved") or payload.get("archive_actions") or []:
        lines.append(f"- `{row['source']}` -> `{row['target']}` ({row.get('status', 'planned')}, {row['bytes']} bytes)")
    lines.extend(["", "## Removed Cache Directories", ""])
    for row in payload.get("removed") or payload.get("cache_remove_actions") or []:
        lines.append(f"- `{row['path']}` ({row.get('status', 'planned')}, {row['bytes']} bytes)")
    lines.extend(["", "## Skipped", ""])
    for row in payload.get("skipped") or []:
        lines.append(f"- `{row['path']}`: {row['reason']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_REPORT_MD)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    plan = build_cleanup_plan(manifest_path=args.manifest, archive_root=args.archive_root)
    payload = execute_plan(plan) if args.execute else plan
    output_json = _safe_resolve(_workspace_root(), str(args.output_json))
    output_md = _safe_resolve(_workspace_root(), str(args.output_md))
    _write_json(output_json, payload)
    _write_markdown(output_md, payload)
    print(json.dumps({"mode": payload["mode"], "totals": payload["totals"], "skipped": payload["skipped"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

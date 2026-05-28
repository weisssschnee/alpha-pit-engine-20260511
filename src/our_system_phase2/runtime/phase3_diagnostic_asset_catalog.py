from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso


CATALOG_VERSION = "phase3-diagnostic-asset-catalog-v1-2026-05-25"


def _safe_read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _safe_text_head(path: Path, limit: int = 2000) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="ignore")[:limit]
    except Exception:
        return ""


def _classify_path(path: Path) -> str:
    name = path.name.lower()
    text = str(path).lower()
    if "decision" in name or "freeze" in name or "locked" in name:
        return "decision_or_locked_candidate"
    if "aggregate" in name or "global" in name:
        return "aggregate_or_global_report"
    if "validation" in name or "strict" in name or "replay" in name:
        return "validation_or_replay_report"
    if "forward" in name or "shadow" in name:
        return "forward_or_shadow"
    if "smoke" in name:
        return "smoke_or_probe"
    if "runtime" in text or "jobs" in text:
        return "runtime_or_job_artifact"
    return "diagnostic_report_or_source"


def _promotion_status(path: Path, *, git_tracked: set[str]) -> str:
    rel = path.as_posix()
    lower = rel.lower()
    if rel in git_tracked:
        return "git_tracked"
    if "phase3z" in lower or "phase3t" in lower or "phase3u" in lower or "phase3v" in lower or "phase3w" in lower or "phase3x" in lower or "phase3y" in lower:
        return "local_diagnostic_unpromoted"
    return "local_untracked_or_modified"


def _git_tracked_paths(repo_root: Path) -> set[str]:
    import subprocess

    try:
        proc = subprocess.run(
            ["git", "ls-files"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return set()
    return {line.strip().replace("\\", "/") for line in proc.stdout.splitlines() if line.strip()}


def _path_record(path: Path, repo_root: Path, *, git_tracked: set[str], category: str) -> dict[str, Any]:
    rel = path.relative_to(repo_root).as_posix()
    stat = path.stat()
    payload = _safe_read_json(path) if path.is_file() and path.suffix.lower() == ".json" else None
    text_head = _safe_text_head(path) if path.is_file() and path.suffix.lower() in {".md", ".txt"} else ""
    decision = ""
    if payload:
        decision = str(payload.get("decision") or payload.get("status") or "")
    if not decision and text_head:
        for marker in ("decision:", "- decision:", "Decision:"):
            if marker in text_head:
                decision = text_head[text_head.find(marker) : text_head.find(marker) + 160].splitlines()[0]
                break
    return {
        "path": rel,
        "category": category,
        "kind": "directory" if path.is_dir() else "file",
        "classification": _classify_path(path),
        "promotion_status": _promotion_status(Path(rel), git_tracked=git_tracked),
        "size_bytes": "" if path.is_dir() else stat.st_size,
        "modified_time": utc_now_iso_from_timestamp(stat.st_mtime),
        "decision_or_status": decision,
        "has_json_decision": bool(payload and payload.get("decision")),
    }


def utc_now_iso_from_timestamp(timestamp: float) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _collect(repo_root: Path, *, local_helper_root: Path | None = None) -> list[dict[str, Any]]:
    git_tracked = _git_tracked_paths(repo_root)
    rows: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    patterns = [
        ("reports", "phase3[tuvwxyz]*"),
        ("reports", "PHASE3Z*"),
        ("runtime", "phase3[tuvwxyz]*"),
        ("runtime/baselines", "phase3z*"),
        ("scripts", "*phase3z*"),
        ("src/our_system_phase2/runtime", "phase3[tuvwxyz]*.py"),
        ("src/our_system_phase2/services", "*limit_event*.py"),
    ]
    for base, pattern in patterns:
        root = repo_root / base
        if not root.exists():
            continue
        for path in sorted(root.glob(pattern)):
            key = str(path.resolve()).lower()
            if key in seen_paths:
                continue
            seen_paths.add(key)
            rows.append(_path_record(path, repo_root, git_tracked=git_tracked, category=base))

    if local_helper_root and local_helper_root.exists():
        for path in sorted(local_helper_root.glob("*phase3z*")):
            key = str(path.resolve()).lower()
            if key in seen_paths:
                continue
            seen_paths.add(key)
            try:
                stat = path.stat()
            except OSError:
                continue
            rows.append(
                {
                    "path": str(path),
                    "category": "external_local_helper",
                    "kind": "directory" if path.is_dir() else "file",
                    "classification": _classify_path(path),
                    "promotion_status": "external_local_helper_untracked",
                    "size_bytes": "" if path.is_dir() else stat.st_size,
                    "modified_time": utc_now_iso_from_timestamp(stat.st_mtime),
                    "decision_or_status": "",
                    "has_json_decision": False,
                }
            )
    return rows


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def counts(key: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for row in rows:
            value = str(row.get(key) or "")
            out[value] = out.get(value, 0) + 1
        return dict(sorted(out.items()))

    return {
        "catalog_version": CATALOG_VERSION,
        "created_at": utc_now_iso(),
        "asset_count": len(rows),
        "by_category": counts("category"),
        "by_classification": counts("classification"),
        "by_promotion_status": counts("promotion_status"),
        "promotion_policy": "local/company diagnostics remain unpromoted until strict replay, global clustering, leakage/OOS audit, decision record, and chain lock update.",
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_report(path: Path, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Phase3 Local Diagnostic Asset Catalog",
        "",
        f"- catalog_version: `{summary['catalog_version']}`",
        f"- created_at: `{summary['created_at']}`",
        f"- asset_count: `{summary['asset_count']}`",
        "- decision: `CATALOG_ONLY_NO_PROMOTION`",
        "",
        "## Promotion Status Counts",
        "",
        "```json",
        json.dumps(summary["by_promotion_status"], ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## Classification Counts",
        "",
        "```json",
        json.dumps(summary["by_classification"], ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## Interpretation",
        "",
        "- Git-tracked Phase3G/H/J/O/P/R/S assets remain the official chain.",
        "- Phase3T-Z and company helper artifacts are diagnostic unless explicitly promoted.",
        "- This catalog starts asset recovery; it does not validate alpha quality.",
        "",
        "## Candidate Promotion Queue Seeds",
        "",
    ]
    candidates = [
        row
        for row in rows
        if row["classification"] in {"decision_or_locked_candidate", "aggregate_or_global_report", "validation_or_replay_report"}
        and row["promotion_status"] != "git_tracked"
    ][:40]
    if not candidates:
        lines.append("- none")
    else:
        for row in candidates:
            lines.append(f"- `{row['path']}` | {row['classification']} | {row['promotion_status']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Catalog local Phase3 diagnostic assets without promoting them.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--local-helper-root", type=Path, default=Path("G:/Chengbo/scripts"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase3_diagnostic_asset_catalog_20260525"))
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    rows = _collect(repo_root, local_helper_root=args.local_helper_root)
    summary = _summary(rows)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "phase3_diagnostic_asset_catalog_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    _write_csv(output_dir / "phase3_diagnostic_asset_catalog.csv", rows)
    _write_report(output_dir / "PHASE3_DIAGNOSTIC_ASSET_CATALOG_2026-05-25.md", summary, rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

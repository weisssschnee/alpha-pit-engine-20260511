"""Preflight gate for Phase3AA mature-chain launches."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import subprocess
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.runtime.phase3aa_enrich_shared_candidate_pool import _event_rows
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.phase3g_signal_vector_store import (
    DEFAULT_PHASE3G_VECTOR_METADATA,
    DEFAULT_PHASE3G_VECTOR_NPZ,
    Phase3GSignalVectorStore,
)
from our_system_phase2.services.phase3g_vector_selector import is_signal_vector_selector


REPORT_FILENAME = "PHASE3AA_ASSET_PREFLIGHT_2026-05-29.md"
DEFAULT_OUTPUT_ROOT = Path("reports/phase3aa_asset_preflight_20260529")


REQUIRED_PACKAGES = [
    "numpy",
    "pandas",
    "pyarrow",
    "numba",
    "bottleneck",
    "numexpr",
    "polars",
    "joblib",
    "scikit-learn",
]


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _package_matrix() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in REQUIRED_PACKAGES:
        try:
            out[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            out[name] = "MISSING"
    return out


def _git_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    try:
        proc = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=str(path),
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception as exc:
        return {"exists": True, "error": f"{type(exc).__name__}:{exc}"}
    return {
        "exists": True,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip().splitlines(),
        "stderr": proc.stderr.strip().splitlines(),
    }


def _local_phase3aa_processes() -> list[dict[str, Any]]:
    script = (
        "Get-CimInstance Win32_Process -Filter \"name = 'python.exe'\" | "
        "Where-Object { $_.CommandLine -like '*phase3aa*' -or $_.CommandLine -like '*stock_pit_unreached*' } | "
        "Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Depth 3"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    text = proc.stdout.strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return [{"parse_error": text[:500]}]
    if isinstance(payload, list):
        rows = payload
    else:
        rows = [payload]
    filtered = []
    for row in rows:
        cmd = str(row.get("CommandLine") or "")
        if "phase3aa-asset-preflight" in cmd or "phase3aa_asset_preflight" in cmd:
            continue
        filtered.append(row)
    return filtered


def _check_file(path: Path, *, sha: bool = False) -> dict[str, Any]:
    out = {
        "path": str(path),
        "exists": path.exists(),
        "length": path.stat().st_size if path.exists() and path.is_file() else None,
    }
    if sha:
        out["sha256"] = _sha256(path)
    return out


def run_preflight(*, repo_root: Path, output_root: Path, old_worktree: Path | None) -> dict[str, Any]:
    runtime_baselines = repo_root / "runtime" / "baselines"
    src_baselines = repo_root / "src" / "our_system_phase2" / "runtime" / "baselines"
    required_files = {
        "chain_lock": runtime_baselines / "phase3_algorithm_chain_lock_v1.json",
        "mature_workspace_profile": runtime_baselines / "phase3_mature_feature_workspace_v1.json",
        "x0_shadow": runtime_baselines / "phase3o_x0_official_shadow_v1.json",
        "x0_shadow_sha": runtime_baselines / "phase3o_x0_official_shadow_v1.sha256",
        "phase3h_149_baseline": src_baselines / "phase3H_cumulative_deployable_clusters_20260515.json",
        "phase3aa_run_plan": repo_root / "runtime" / "run_plans" / "phase3aa_mature_chain_event_g2_run_plan.json",
        "phase3g_vector_npz": repo_root / DEFAULT_PHASE3G_VECTOR_NPZ,
        "phase3g_vector_metadata": repo_root / DEFAULT_PHASE3G_VECTOR_METADATA,
    }
    files = {name: _check_file(path, sha=name in {"x0_shadow", "phase3g_vector_npz", "phase3g_vector_metadata"}) for name, path in required_files.items()}

    chain_lock = _read_json(required_files["chain_lock"]) if required_files["chain_lock"].exists() else {}
    mature_profile = _read_json(required_files["mature_workspace_profile"]) if required_files["mature_workspace_profile"].exists() else {}
    x0 = _read_json(required_files["x0_shadow"]) if required_files["x0_shadow"].exists() else {}

    try:
        vector_store = Phase3GSignalVectorStore()
        vector_store_ready = vector_store.coverage_ready()
    except Exception as exc:
        vector_store_ready = False
        vector_error = f"{type(exc).__name__}:{exc}"
    else:
        vector_error = ""

    event_rows = _event_rows(max_per_role=32, include_gate_candidates=False)
    event_fields = sorted({field for row in event_rows for field in str(row.get("event_fields") or "").split("|") if field})
    selector_profile = "signal_vector_diversified_source_priority_proxy"
    package_matrix = _package_matrix()
    local_phase3aa_processes = _local_phase3aa_processes()

    checks = {
        "required_files_exist": all(item["exists"] for item in files.values()),
        "phase3g_signal_vector_store_ready": bool(vector_store_ready),
        "event_derived_factor_rows_available": len(event_rows) > 0,
        "event_field_breadth_count": len(event_fields),
        "source_priority_selector_registered": is_signal_vector_selector(selector_profile),
        "x0_shadow_read_only_declared": x0.get("status") == "official_daily_shadow",
        "chain_lock_names_g2": (chain_lock.get("official_algorithm_chain") or {}).get("discovery_primary", {}).get("name") == "G2_signal_vector_diversified_selector",
        "mature_profile_requires_shared_pool": "shared_candidate_pool" in list(mature_profile.get("required_chain") or []),
        "no_local_phase3aa_processes": len(local_phase3aa_processes) == 0,
        "old_worktree_status": _git_status(old_worktree) if old_worktree else {"provided": False},
    }
    missing_packages = [name for name, version in package_matrix.items() if version == "MISSING"]
    required_pass = (
        checks["required_files_exist"]
        and checks["phase3g_signal_vector_store_ready"]
        and checks["event_derived_factor_rows_available"]
        and checks["source_priority_selector_registered"]
        and checks["x0_shadow_read_only_declared"]
        and checks["chain_lock_names_g2"]
        and checks["mature_profile_requires_shared_pool"]
        and checks["no_local_phase3aa_processes"]
    )
    decision = "PASS_PHASE3AA_ASSET_PREFLIGHT" if required_pass else "HOLD_PHASE3AA_ASSET_PREFLIGHT"
    if missing_packages:
        acceleration_decision = "PASS_WITH_UNUSED_OR_MISSING_ACCEL_LIBS"
    else:
        acceleration_decision = "PASS_ACCEL_PACKAGE_MATRIX"

    report = {
        "created_at": utc_now_iso(),
        "decision": decision,
        "acceleration_decision": acceleration_decision,
        "repo_root": str(repo_root),
        "files": files,
        "checks": checks,
        "vector_store_error": vector_error,
        "event_candidate_count": len(event_rows),
        "event_field_breadth_count": len(event_fields),
        "event_field_sample": event_fields[:40],
        "selector_profile": selector_profile,
        "package_matrix": package_matrix,
        "missing_packages": missing_packages,
        "local_phase3aa_processes": local_phase3aa_processes,
        "launch_contract": {
            "entrypoint": "app.py phase3aa-mature-chain",
            "requires_shared_pool": True,
            "requires_event_injection": True,
            "requires_source_priority_selector": True,
            "requires_frozen_selection": True,
            "requires_signal_vector_artifacts": True,
            "unreached_supervisor_primary_allowed": False,
            "x0_r3_shadow_mutation_allowed": False,
        },
    }
    output_root.mkdir(parents=True, exist_ok=True)
    write_json_artifact(output_root / "phase3aa_asset_preflight.json", report)
    _write_markdown(output_root / REPORT_FILENAME, report)
    return report


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Phase3AA Asset Preflight",
        "",
        f"- decision: `{report['decision']}`",
        f"- acceleration_decision: `{report['acceleration_decision']}`",
        f"- event_candidate_count: `{report['event_candidate_count']}`",
        f"- event_field_breadth_count: `{report['event_field_breadth_count']}`",
        f"- selector_profile: `{report['selector_profile']}`",
        "",
        "## Checks",
    ]
    for key, value in report["checks"].items():
        if key == "old_worktree_status":
            continue
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Files"])
    for key, item in report["files"].items():
        lines.append(f"- {key}: exists=`{item['exists']}` length=`{item['length']}`")
    lines.extend(["", "## Package Matrix"])
    for key, value in report["package_matrix"].items():
        lines.append(f"- {key}: `{value}`")
    if report["local_phase3aa_processes"]:
        lines.extend(["", "## Blocking Processes"])
        for proc in report["local_phase3aa_processes"]:
            lines.append(f"- pid={proc.get('ProcessId')} cmd=`{str(proc.get('CommandLine') or '')[:180]}`")
    lines.extend(["", "## Launch Contract"])
    for key, value in report["launch_contract"].items():
        lines.append(f"- {key}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--old-worktree", type=Path, default=Path("G:/Project_V7_Rotation/.worktrees/our_system_phase1_repo"))
    args = parser.parse_args()

    report = run_preflight(repo_root=args.repo_root, output_root=args.output_root, old_worktree=args.old_worktree)
    print(json.dumps({"decision": report["decision"], "acceleration_decision": report["acceleration_decision"]}, ensure_ascii=False, indent=2))
    return 0 if str(report["decision"]).startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())

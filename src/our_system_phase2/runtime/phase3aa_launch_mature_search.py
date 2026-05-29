from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH
from our_system_phase2.services.runtime_state_registry import finish_job, register_job


PHASE3AA_VERSION = "phase3aa-mature-chain-heavy-search-v1-2026-05-29"
DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OLD_REPORTS_ROOT = Path(r"G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo\reports")
DEFAULT_CURRENT_REPORTS_ROOT = DEFAULT_REPO_ROOT / "reports"


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _discover_roots(
    bases: list[Path],
    *,
    marker_names: tuple[str, ...],
    limit: int,
) -> list[Path]:
    roots: dict[str, Path] = {}
    for base in bases:
        if not base.exists():
            continue
        for marker_name in marker_names:
            for path in base.rglob(marker_name):
                parent = path.parent.resolve()
                roots[str(parent)] = parent
    return sorted(roots.values(), key=_mtime, reverse=True)[: max(0, int(limit))]


def _build_supervisor_command(
    *,
    launch_root: Path,
    shard_count: int,
    max_active: int,
    dataset_path: Path,
    target_window_count: int,
    max_window: int,
    top_bottom_quantile: float,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
    parallel_workers: int,
    previous_roots: list[Path],
    reward_roots: list[Path],
    max_family_share: float,
    reward_exploration_share: float,
    policy_state_path: Path,
    poll_seconds: float,
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "our_system_phase2.runtime.stock_pit_unreached_search_supervisor",
        "--launch-root",
        str(launch_root),
        "--shard-count",
        str(shard_count),
        "--max-active",
        str(max_active),
        "--dataset-path",
        str(dataset_path),
        "--target-window-count",
        str(target_window_count),
        "--max-window",
        str(max_window),
        "--top-bottom-quantile",
        str(top_bottom_quantile),
        "--recent-quarter-window-count",
        str(recent_quarter_window_count),
        "--recent-warmup-days",
        str(recent_warmup_days),
        "--parallel-workers",
        str(parallel_workers),
        "--use-fast-context",
        "--max-family-share",
        str(max_family_share),
        "--reward-exploration-share",
        str(reward_exploration_share),
        "--policy-state-path",
        str(policy_state_path),
        "--poll-seconds",
        str(poll_seconds),
    ]
    for root in previous_roots:
        command.extend(["--previous-search-root", str(root)])
    for root in reward_roots:
        command.extend(["--reward-control-root", str(root)])
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch Phase3AA through mature stock-PIT supervisor.")
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--launch-root", type=Path, required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--machine", choices=["local", "company", "cloud", "unknown"], default="local")
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--shard-count", type=int, default=4)
    parser.add_argument("--max-active", type=int, default=2)
    parser.add_argument("--target-window-count", type=int, default=12)
    parser.add_argument("--max-window", type=int, default=126)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--recent-quarter-window-count", type=int, default=2)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    parser.add_argument("--parallel-workers", type=int, default=2)
    parser.add_argument("--previous-root-limit", type=int, default=80)
    parser.add_argument("--reward-root-limit", type=int, default=40)
    parser.add_argument(
        "--memory-base",
        type=Path,
        action="append",
        default=[],
        help="Additional reports/runtime roots to scan for candidate_ledgers and validation summaries.",
    )
    parser.add_argument("--max-family-share", type=float, default=0.18)
    parser.add_argument("--reward-exploration-share", type=float, default=0.35)
    parser.add_argument("--poll-seconds", type=float, default=30.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    launch_root = args.launch_root.resolve()
    launch_root.mkdir(parents=True, exist_ok=True)
    search_bases = list(dict.fromkeys([DEFAULT_CURRENT_REPORTS_ROOT, DEFAULT_OLD_REPORTS_ROOT, *args.memory_base]))
    previous_roots = _discover_roots(
        search_bases,
        marker_names=("candidate_ledger.json",),
        limit=args.previous_root_limit,
    )
    reward_roots = _discover_roots(
        search_bases,
        marker_names=("stage1_validation_report.json", "stage1_summary.json"),
        limit=args.reward_root_limit,
    )
    policy_state_path = launch_root / "phase3aa_policy_state.json"
    command = _build_supervisor_command(
        launch_root=launch_root / "supervisor",
        shard_count=args.shard_count,
        max_active=args.max_active,
        dataset_path=args.dataset_path,
        target_window_count=args.target_window_count,
        max_window=args.max_window,
        top_bottom_quantile=args.top_bottom_quantile,
        recent_quarter_window_count=args.recent_quarter_window_count,
        recent_warmup_days=args.recent_warmup_days,
        parallel_workers=args.parallel_workers,
        previous_roots=previous_roots,
        reward_roots=reward_roots,
        max_family_share=args.max_family_share,
        reward_exploration_share=args.reward_exploration_share,
        policy_state_path=policy_state_path,
        poll_seconds=args.poll_seconds,
    )
    manifest = {
        "created_at": utc_now_iso(),
        "phase": "Phase3AA",
        "version": PHASE3AA_VERSION,
        "job_id": args.job_id,
        "machine": args.machine,
        "repo_root": str(repo_root),
        "launch_root": str(launch_root),
        "dataset_path": str(args.dataset_path),
        "previous_root_count": len(previous_roots),
        "reward_root_count": len(reward_roots),
        "previous_roots": [str(path) for path in previous_roots],
        "reward_roots": [str(path) for path in reward_roots],
        "policy_state_path": str(policy_state_path),
        "supervisor_command": command,
        "dry_run": bool(args.dry_run),
    }
    write_json_artifact(launch_root / "phase3aa_launch_manifest.json", manifest)
    (launch_root / "phase3aa_supervisor_command.txt").write_text(" ".join(command), encoding="utf-8")

    if args.dry_run:
        print(_json_dump({"status": "dry_run", "manifest": str(launch_root / "phase3aa_launch_manifest.json")}))
        return 0

    register_job(
        job_id=args.job_id,
        machine=args.machine,
        command=" ".join(command),
        output_root=str(launch_root),
        scope="diagnostic",
        metadata={
            "phase": "Phase3AA",
            "version": PHASE3AA_VERSION,
            "previous_root_count": len(previous_roots),
            "reward_root_count": len(reward_roots),
        },
    )
    status = "completed"
    result: dict[str, Any] = {"manifest": str(launch_root / "phase3aa_launch_manifest.json")}
    try:
        log_path = launch_root / "phase3aa_supervisor.log"
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{utc_now_iso()}] BEGIN {' '.join(command)}\n")
            handle.flush()
            subprocess.run(command, cwd=str(repo_root), stdout=handle, stderr=subprocess.STDOUT, check=True)
            handle.write(f"[{utc_now_iso()}] END {' '.join(command)}\n")
        result["log_path"] = str(log_path)
    except Exception as exc:
        status = "failed"
        result["error"] = repr(exc)
        raise
    finally:
        finish_job(job_id=args.job_id, status=status, result=result)
    print(_json_dump({"status": status, "manifest": str(launch_root / "phase3aa_launch_manifest.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

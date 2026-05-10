from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH, dataset_role_for_path
from our_system_phase2.services.stock_pit_ledger_policy import build_stock_pit_search_control_policy


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_status(
    *,
    launch_root: Path,
    queued: list[int],
    running: dict[int, dict[str, Any]],
    completed: dict[int, dict[str, Any]],
    failed: dict[int, dict[str, Any]],
    max_active: int,
    status: str,
) -> None:
    write_json_artifact(
        launch_root / "supervisor_status.json",
        {
            "created_at": utc_now_iso(),
            "status": status,
            "max_active_workers": max_active,
            "queued_shards": queued,
            "running": {str(key): value for key, value in running.items()},
            "completed": {str(key): value for key, value in completed.items()},
            "failed": {str(key): value for key, value in failed.items()},
            "running_count": len(running),
            "completed_count": len(completed),
            "failed_count": len(failed),
        },
    )


def _args(
    *,
    output_root: Path,
    shard_index: int,
    shard_count: int,
    dataset_path: Path,
    target_window_count: int,
    max_window: int,
    top_bottom_quantile: float,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
    parallel_workers: int,
    use_fast_context: bool = False,
    previous_search_roots: list[Path] | None = None,
    max_family_share: float = 0.0,
    reward_control_roots: list[Path] | None = None,
    reward_exploration_share: float = 0.25,
    policy_state_path: Path | None = None,
) -> list[str]:
    args = [
        sys.executable,
        "-m",
        "our_system_phase2.runtime.stock_pit_unreached_search_worker",
        "--output-root",
        str(output_root),
        "--shard-index",
        str(shard_index),
        "--shard-count",
        str(shard_count),
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
    ]
    if use_fast_context:
        args.append("--use-fast-context")
    for root in previous_search_roots or []:
        args.extend(["--previous-search-root", str(root)])
    if max_family_share > 0:
        args.extend(["--max-family-share", str(max_family_share)])
    for root in reward_control_roots or []:
        args.extend(["--reward-control-root", str(root)])
    args.extend(["--reward-exploration-share", str(reward_exploration_share)])
    if policy_state_path is not None:
        args.extend(["--policy-state-path", str(policy_state_path)])
    return args


def run_supervisor(
    *,
    launch_root: Path,
    shard_count: int,
    start_shard: int,
    end_shard: int | None,
    max_active: int,
    dataset_path: Path,
    target_window_count: int,
    max_window: int,
    top_bottom_quantile: float,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
    parallel_workers: int,
    use_fast_context: bool = False,
    previous_search_roots: list[Path] | None = None,
    max_family_share: float = 0.0,
    reward_control_roots: list[Path] | None = None,
    reward_exploration_share: float = 0.25,
    policy_state_path: Path | None = None,
    poll_seconds: float = 30.0,
) -> dict[str, Any]:
    launch_root.mkdir(parents=True, exist_ok=True)
    previous_search_roots = list(previous_search_roots or [])
    reward_control_roots = list(reward_control_roots or [])
    last_shard = shard_count - 1 if end_shard is None else min(shard_count - 1, int(end_shard))
    first_shard = max(0, int(start_shard))
    queued = list(range(first_shard, last_shard + 1))
    active: dict[int, subprocess.Popen[Any]] = {}
    running: dict[int, dict[str, Any]] = {}
    completed: dict[int, dict[str, Any]] = {}
    failed: dict[int, dict[str, Any]] = {}
    manifest = {
        "created_at": utc_now_iso(),
        "search_name": "phase2-stock-pit-unreached-shape-liquidity-20260504",
        "dataset_path": str(dataset_path),
        "dataset_role": dataset_role_for_path(dataset_path),
        "shard_count": shard_count,
        "start_shard": first_shard,
        "end_shard": last_shard,
        "max_active_workers": max_active,
        "target_window_count": target_window_count,
        "max_window": max_window,
        "top_bottom_quantile": top_bottom_quantile,
        "recent_quarter_window_count": recent_quarter_window_count,
        "recent_warmup_days": recent_warmup_days,
        "parallel_workers_per_shard": parallel_workers,
        "use_fast_context": bool(use_fast_context),
        "previous_search_roots": [str(root) for root in previous_search_roots],
        "max_family_share": float(max_family_share),
        "reward_control_roots": [str(root) for root in reward_control_roots],
        "reward_exploration_share": float(reward_exploration_share),
        "policy_state_path": str(policy_state_path) if policy_state_path is not None else None,
        "policy_state_precomputed_for_workers": bool(policy_state_path is not None and reward_control_roots),
        "formula_space": "shape_location_gap_liquidity_volatility_second_order_interactions",
        "workers": [],
    }
    worker_reward_control_roots = reward_control_roots
    if policy_state_path is not None and reward_control_roots:
        build_stock_pit_search_control_policy(
            reward_control_roots,
            expected_dataset_role=dataset_role_for_path(dataset_path),
            exploration_share=reward_exploration_share,
            policy_state_path=policy_state_path,
        )
        worker_reward_control_roots = []
    write_json_artifact(launch_root / "launch_manifest.json", manifest)

    while queued or active:
        while queued and len(active) < max_active:
            shard_index = queued.pop(0)
            output_root = launch_root.parent / f"{launch_root.name}-shard_{shard_index:02d}_of_{shard_count:02d}"
            stdout_path = launch_root / f"shard_{shard_index:02d}.stdout.log"
            stderr_path = launch_root / f"shard_{shard_index:02d}.stderr.log"
            process = subprocess.Popen(
                _args(
                    output_root=output_root,
                    shard_index=shard_index,
                    shard_count=shard_count,
                    dataset_path=dataset_path,
                    target_window_count=target_window_count,
                    max_window=max_window,
                    top_bottom_quantile=top_bottom_quantile,
                    recent_quarter_window_count=recent_quarter_window_count,
                    recent_warmup_days=recent_warmup_days,
                    parallel_workers=parallel_workers,
                    use_fast_context=use_fast_context,
                    previous_search_roots=previous_search_roots,
                    max_family_share=max_family_share,
                    reward_control_roots=worker_reward_control_roots,
                    reward_exploration_share=reward_exploration_share,
                    policy_state_path=policy_state_path,
                ),
                stdout=stdout_path.open("w", encoding="utf-8"),
                stderr=stderr_path.open("w", encoding="utf-8"),
                cwd=str(Path.cwd()),
            )
            item = {
                "shard_index": shard_index,
                "pid": process.pid,
                "output_root": str(output_root),
                "stdout": str(stdout_path),
                "stderr": str(stderr_path),
                "started_at": utc_now_iso(),
            }
            active[shard_index] = process
            running[shard_index] = item
            manifest["workers"].append(item)
            write_json_artifact(launch_root / "launch_manifest.json", manifest)

        for shard_index, process in list(active.items()):
            return_code = process.poll()
            if return_code is None:
                continue
            item = dict(running.pop(shard_index))
            item["finished_at"] = utc_now_iso()
            item["return_code"] = return_code
            summary = _read_json(Path(str(item["output_root"])) / "stage1_summary.json")
            if summary:
                top = (summary.get("top_long_only_candidates") or [{}])[0]
                item["summary"] = {
                    "validation_evaluated_count": summary.get("validation_evaluated_count"),
                    "validation_unsupported_count": summary.get("validation_unsupported_count"),
                    "top_candidate_id": top.get("candidate_id"),
                    "top_long_sortino": top.get("mean_window_long_sortino"),
                    "top_long_return": top.get("mean_window_long_return"),
                }
            if return_code == 0:
                completed[shard_index] = item
            else:
                failed[shard_index] = item
            del active[shard_index]

        _write_status(
            launch_root=launch_root,
            queued=queued,
            running=running,
            completed=completed,
            failed=failed,
            max_active=max_active,
            status="running" if queued or active else "completed",
        )
        if queued or active:
            time.sleep(max(1.0, poll_seconds))
    return _read_json(launch_root / "supervisor_status.json") or {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Rolling launcher for stock-PIT unreached-space search.")
    parser.add_argument("--launch-root", type=Path, required=True)
    parser.add_argument("--shard-count", type=int, default=8)
    parser.add_argument("--start-shard", type=int, default=0)
    parser.add_argument("--end-shard", type=int, default=None)
    parser.add_argument("--max-active", type=int, default=1)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--target-window-count", type=int, default=24)
    parser.add_argument("--max-window", type=int, default=126)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--recent-quarter-window-count", type=int, default=2)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    parser.add_argument("--parallel-workers", type=int, default=1)
    parser.add_argument("--use-fast-context", action="store_true")
    parser.add_argument("--previous-search-root", type=Path, action="append", default=[])
    parser.add_argument("--max-family-share", type=float, default=0.0)
    parser.add_argument("--reward-control-root", type=Path, action="append", default=[])
    parser.add_argument("--reward-exploration-share", type=float, default=0.25)
    parser.add_argument("--policy-state-path", type=Path, default=None)
    parser.add_argument("--poll-seconds", type=float, default=30.0)
    args = parser.parse_args()
    result = run_supervisor(
        launch_root=args.launch_root,
        shard_count=args.shard_count,
        start_shard=args.start_shard,
        end_shard=args.end_shard,
        max_active=max(1, int(args.max_active)),
        dataset_path=args.dataset_path,
        target_window_count=args.target_window_count,
        max_window=args.max_window,
        top_bottom_quantile=args.top_bottom_quantile,
        recent_quarter_window_count=args.recent_quarter_window_count,
        recent_warmup_days=args.recent_warmup_days,
        parallel_workers=max(1, int(args.parallel_workers)),
        use_fast_context=bool(args.use_fast_context),
        previous_search_roots=list(args.previous_search_root or []),
        max_family_share=max(0.0, float(args.max_family_share)),
        reward_control_roots=list(args.reward_control_root or []),
        reward_exploration_share=max(0.0, float(args.reward_exploration_share)),
        policy_state_path=args.policy_state_path,
        poll_seconds=args.poll_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

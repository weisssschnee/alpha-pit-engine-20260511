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


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _worker_args(
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
) -> list[str]:
    args = [
        sys.executable,
        "-m",
        "our_system_phase2.runtime.stock_pit_ashare_state_search_worker",
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
    return args


def _write_status(
    *,
    launch_root: Path,
    started: dict[int, dict[str, Any]],
    completed: dict[int, dict[str, Any]],
    failed: dict[int, dict[str, Any]],
    queued: list[int],
    max_active: int,
    status: str,
) -> None:
    running = {
        str(shard): item
        for shard, item in started.items()
        if shard not in completed and shard not in failed
    }
    write_json_artifact(
        launch_root / "supervisor_status.json",
        {
            "created_at": utc_now_iso(),
            "status": status,
            "max_active_workers": max_active,
            "queued_shards": queued,
            "running": running,
            "completed": completed,
            "failed": failed,
            "running_count": len(running),
            "completed_count": len(completed),
            "failed_count": len(failed),
        },
    )


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
    use_fast_context: bool,
    poll_seconds: float,
) -> dict[str, Any]:
    launch_root.mkdir(parents=True, exist_ok=True)
    stop_shard = shard_count if end_shard is None else min(shard_count, int(end_shard))
    queued = list(range(max(0, int(start_shard)), stop_shard))
    active: dict[int, subprocess.Popen[Any]] = {}
    started: dict[int, dict[str, Any]] = {}
    completed: dict[int, dict[str, Any]] = {}
    failed: dict[int, dict[str, Any]] = {}
    manifest = {
        "created_at": utc_now_iso(),
        "search_name": "phase2-stock-pit-ashare-state-fresh-20260506",
        "dataset_path": str(dataset_path),
        "dataset_role": dataset_role_for_path(dataset_path),
        "shard_count": shard_count,
        "start_shard": max(0, int(start_shard)),
        "end_shard": stop_shard,
        "max_active_workers": max_active,
        "target_window_count": target_window_count,
        "max_window": max_window,
        "top_bottom_quantile": top_bottom_quantile,
        "recent_quarter_window_count": recent_quarter_window_count,
        "recent_warmup_days": recent_warmup_days,
        "parallel_workers_per_shard": parallel_workers,
        "use_fast_context": bool(use_fast_context),
        "search_memory_dataset_role": "stock_pit_panel",
        "fresh_space": "ashare_limit_state_proxy_open_confirmation_liquidity_interactions",
        "workers": [],
    }
    write_json_artifact(launch_root / "launch_manifest.json", manifest)

    while queued or active:
        while queued and len(active) < max_active:
            shard_index = queued.pop(0)
            worker_root = launch_root.parent / f"{launch_root.name}-shard_{shard_index:02d}_of_{shard_count:02d}"
            worker_root.mkdir(parents=True, exist_ok=True)
            stdout_path = launch_root / f"shard_{shard_index:02d}.stdout.log"
            stderr_path = launch_root / f"shard_{shard_index:02d}.stderr.log"
            stdout = stdout_path.open("w", encoding="utf-8")
            stderr = stderr_path.open("w", encoding="utf-8")
            process = subprocess.Popen(
                _worker_args(
                    output_root=worker_root,
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
                ),
                stdout=stdout,
                stderr=stderr,
                cwd=str(Path.cwd()),
            )
            item = {
                "shard_index": shard_index,
                "pid": process.pid,
                "output_root": str(worker_root),
                "stdout": str(stdout_path),
                "stderr": str(stderr_path),
                "started_at": utc_now_iso(),
            }
            active[shard_index] = process
            started[shard_index] = item
            manifest["workers"].append(item)
            write_json_artifact(launch_root / "launch_manifest.json", manifest)

        for shard_index, process in list(active.items()):
            return_code = process.poll()
            if return_code is None:
                continue
            item = dict(started[shard_index])
            item["finished_at"] = utc_now_iso()
            item["return_code"] = return_code
            summary = _read_json(Path(str(item["output_root"])) / "stage1_summary.json")
            if summary is not None:
                top = (summary.get("top_long_only_candidates") or [{}])[0]
                item["summary"] = {
                    "validation_evaluated_count": summary.get("validation_evaluated_count"),
                    "validation_unsupported_count": summary.get("validation_unsupported_count"),
                    "top_candidate_id": top.get("candidate_id"),
                    "top_long_sortino": top.get("mean_window_long_sortino"),
                    "top_long_return": top.get("mean_window_long_return"),
                    "top_rank_ic": top.get("mean_window_rank_ic"),
                }
            if return_code == 0:
                completed[shard_index] = item
            else:
                failed[shard_index] = item
            del active[shard_index]

        _write_status(
            launch_root=launch_root,
            started=started,
            completed=completed,
            failed=failed,
            queued=queued,
            max_active=max_active,
            status="running" if queued or active else "completed",
        )
        if queued or active:
            time.sleep(max(1.0, poll_seconds))

    final_status = _read_json(launch_root / "supervisor_status.json") or {}
    final_status["finished_at"] = utc_now_iso()
    write_json_artifact(launch_root / "supervisor_status.json", final_status)
    return final_status


def main() -> None:
    parser = argparse.ArgumentParser(description="Rolling launcher for stock-PIT A-share state fresh-search shards.")
    parser.add_argument("--launch-root", type=Path, required=True)
    parser.add_argument("--shard-count", type=int, default=16)
    parser.add_argument("--start-shard", type=int, default=0)
    parser.add_argument("--end-shard", type=int, default=None)
    parser.add_argument("--max-active", type=int, default=4)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--target-window-count", type=int, default=24)
    parser.add_argument("--max-window", type=int, default=126)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--recent-quarter-window-count", type=int, default=2)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    parser.add_argument("--parallel-workers", type=int, default=1)
    parser.add_argument("--use-fast-context", action="store_true")
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
        poll_seconds=args.poll_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

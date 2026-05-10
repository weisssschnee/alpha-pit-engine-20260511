from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH, dataset_role_for_path
from our_system_phase2.services.real_market_validation import batch_validate_candidate_ledger
from our_system_phase2.services.stock_pit_ashare_state_search import (
    ASHARE_STATE_SEARCH_VERSION,
    build_stock_pit_ashare_state_ledger,
)


def _float_value(value: Any, default: float = -999.0) -> float:
    try:
        return default if value is None else float(value)
    except (TypeError, ValueError):
        return default


def _rank_key(item: dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        _float_value(item.get("mean_window_long_sortino")),
        _float_value(item.get("mean_window_long_return")),
        _float_value(item.get("mean_window_rank_ic")),
        -_float_value(item.get("tradability_ic_excluded_row_count"), default=0.0),
    )


def run_worker(
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
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    write_json_artifact(
        output_root / "worker_status.json",
        {
            "created_at": utc_now_iso(),
            "status": "started",
            "shard_index": shard_index,
            "shard_count": shard_count,
            "dataset_path": str(dataset_path),
            "dataset_role": dataset_role_for_path(dataset_path),
            "search_version": ASHARE_STATE_SEARCH_VERSION,
            "use_fast_context": bool(use_fast_context),
        },
    )
    ledger = build_stock_pit_ashare_state_ledger(
        path=dataset_path,
        shard_index=shard_index,
        shard_count=shard_count,
        target_window_count=target_window_count,
        max_window=max_window,
    )
    ledger_path = output_root / "candidate_ledger.json"
    write_json_artifact(ledger_path, ledger)
    validation = batch_validate_candidate_ledger(
        ledger_path,
        path=dataset_path,
        retained_only=True,
        top_bottom_quantile=top_bottom_quantile,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
        parallel_workers=parallel_workers,
        use_fast_context=use_fast_context,
    )
    validation_path = output_root / "stage1_validation_report.json"
    write_json_artifact(validation_path, validation)
    ranked = sorted(list(validation.get("evaluations", []) or []), key=_rank_key, reverse=True)
    summary = {
        "created_at": utc_now_iso(),
        "status": "completed",
        "shard_index": shard_index,
        "shard_count": shard_count,
        "dataset_path": str(dataset_path),
        "dataset_role": dataset_role_for_path(dataset_path),
        "search_version": ASHARE_STATE_SEARCH_VERSION,
        "ledger_record_count": ledger.get("record_count"),
        "full_space_candidate_count": ledger.get("full_space_candidate_count"),
        "validation_evaluated_count": validation.get("evaluated_count"),
        "validation_unsupported_count": validation.get("unsupported_count"),
        "validation_signal_clock": validation.get("signal_clock"),
        "validation_feature_lag_days": validation.get("feature_lag_days"),
        "validation_execution_lag_days": validation.get("execution_lag_days"),
        "validation_top_bottom_quantile": validation.get("top_bottom_quantile"),
        "validation_acceleration_mode": validation.get("validation_acceleration_mode"),
        "validation_period": {
            "start": validation.get("evaluation_start_date"),
            "end": validation.get("evaluation_end_date"),
        },
        "top_long_only_candidates": [
            {
                "candidate_id": item.get("candidate_id"),
                "mean_window_long_sortino": item.get("mean_window_long_sortino"),
                "mean_window_long_return": item.get("mean_window_long_return"),
                "mean_window_rank_ic": item.get("mean_window_rank_ic"),
                "recent_positive_rank_ic_ratio": item.get("recent_positive_rank_ic_ratio"),
                "tradability_filter_available": item.get("tradability_filter_available"),
                "tradability_ic_excluded_row_count": item.get("tradability_ic_excluded_row_count"),
                "primitive_family": item.get("primitive_family"),
                "proposal_kind": item.get("proposal_kind"),
                "direction": item.get("direction"),
                "expression": item.get("expression"),
            }
            for item in ranked[:20]
        ],
        "candidate_ledger": str(ledger_path),
        "stage1_validation_report": str(validation_path),
    }
    write_json_artifact(output_root / "stage1_summary.json", summary)
    write_json_artifact(output_root / "worker_status.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one stock-PIT A-share state fresh-search shard.")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, default=16)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--target-window-count", type=int, default=24)
    parser.add_argument("--max-window", type=int, default=126)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--recent-quarter-window-count", type=int, default=2)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    parser.add_argument("--parallel-workers", type=int, default=1)
    parser.add_argument("--use-fast-context", action="store_true")
    args = parser.parse_args()
    summary = run_worker(
        output_root=args.output_root,
        shard_index=args.shard_index,
        shard_count=args.shard_count,
        dataset_path=args.dataset_path,
        target_window_count=args.target_window_count,
        max_window=args.max_window,
        top_bottom_quantile=args.top_bottom_quantile,
        recent_quarter_window_count=args.recent_quarter_window_count,
        recent_warmup_days=args.recent_warmup_days,
        parallel_workers=max(1, int(args.parallel_workers)),
        use_fast_context=bool(args.use_fast_context),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

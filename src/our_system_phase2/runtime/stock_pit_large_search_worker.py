from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH, dataset_role_for_path
from our_system_phase2.services.real_market_validation import SIGNAL_CLOCK_AFTER_OPEN, batch_validate_candidate_ledger
from our_system_phase2.services.stock_pit_ledger_policy import (
    apply_stock_pit_ledger_selection_policy,
    build_stock_pit_search_control_policy,
    diversified_top_candidates,
    family_diversity_report,
)
from our_system_phase2.services.stock_pit_forward_first_search import (
    build_stock_pit_forward_first_large_search_ledger,
    build_stock_pit_rx_typed_beam_search_ledger,
)
from our_system_phase2.services.stock_pit_successive_halving import run_stock_pit_successive_halving_validation


def _float_value(value: Any, default: float = -999.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _rank_key(item: dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        _float_value(item.get("mean_window_long_sortino")),
        _float_value(item.get("mean_window_long_return")),
        _float_value(item.get("mean_window_rank_ic")),
        -_float_value(item.get("tradability_ic_excluded_row_count"), default=0.0),
    )


def _candidate_summary_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
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


def _summary(validation: dict[str, Any], *, shard_index: int, shard_count: int, ledger: dict[str, Any], dataset_path: Path) -> dict[str, Any]:
    evaluations = list(validation.get("evaluations", []) or [])
    ranked = sorted(evaluations, key=_rank_key, reverse=True)
    diversified = diversified_top_candidates(ranked, limit=20, max_per_family=2)
    return {
        "created_at": utc_now_iso(),
        "status": "completed",
        "shard_index": shard_index,
        "shard_count": shard_count,
        "dataset_path": str(dataset_path),
        "dataset_role": dataset_role_for_path(dataset_path),
        "search_version": ledger.get("search_version"),
        "ledger_record_count": ledger.get("record_count"),
        "full_parameter_slice_candidate_count": ledger.get("full_space_candidate_count_for_current_parameter_slice"),
        "validation_evaluated_count": validation.get("evaluated_count"),
        "validation_unsupported_count": validation.get("unsupported_count"),
        "validation_signal_clock": validation.get("signal_clock"),
        "validation_feature_lag_days": validation.get("feature_lag_days"),
        "validation_execution_lag_days": validation.get("execution_lag_days"),
        "validation_top_bottom_quantile": validation.get("top_bottom_quantile"),
        "validation_acceleration_mode": validation.get("validation_acceleration_mode"),
        "successive_halving": validation.get("successive_halving"),
        "validation_period": {
            "start": validation.get("evaluation_start_date"),
            "end": validation.get("evaluation_end_date"),
        },
        "ledger_selection_policy": ledger.get("ledger_selection_policy"),
        "search_control_policy": ledger.get("search_control_policy"),
        "search_control_schedule_audit": ledger.get("search_control_schedule_audit"),
        "evaluation_family_diversity": family_diversity_report(evaluations),
        "top_long_only_candidates": [_candidate_summary_item(item) for item in ranked[:20]],
        "diversified_top_long_only_candidates": [_candidate_summary_item(item) for item in diversified],
    }


def run_worker(
    *,
    output_root: Path,
    shard_index: int,
    shard_count: int,
    dataset_path: Path,
    candidates_per_shard: int,
    target_window_count: int,
    max_window: int,
    top_bottom_quantile: float,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
    parallel_workers: int,
    max_candidates: int | None,
    use_fast_context: bool = False,
    previous_search_roots: list[Path] | None = None,
    max_family_share: float = 0.0,
    reward_control_roots: list[Path] | None = None,
    reward_exploration_share: float = 0.25,
    policy_state_path: Path | None = None,
    generator_mode: str = "forward_first",
    beam_width: int = 64,
    max_beam_records: int = 4096,
    use_successive_halving: bool = False,
    halving_survivor_fraction: float = 0.35,
    halving_min_survivors: int = 64,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    status_path = output_root / "worker_status.json"
    resolved_policy_state_path = policy_state_path or (output_root / "stock_pit_policy_state.json")
    write_json_artifact(
        status_path,
        {
            "created_at": utc_now_iso(),
            "status": "started",
            "shard_index": shard_index,
            "shard_count": shard_count,
            "dataset_path": str(dataset_path),
            "dataset_role": dataset_role_for_path(dataset_path),
            "use_fast_context": bool(use_fast_context),
            "previous_search_roots": [str(root) for root in previous_search_roots or []],
            "max_family_share": float(max_family_share),
            "reward_control_roots": [str(root) for root in reward_control_roots or []],
            "reward_exploration_share": float(reward_exploration_share),
            "policy_state_path": str(resolved_policy_state_path),
            "generator_mode": generator_mode,
            "beam_width": int(beam_width),
            "max_beam_records": int(max_beam_records),
            "use_successive_halving": bool(use_successive_halving),
            "halving_survivor_fraction": float(halving_survivor_fraction),
            "halving_min_survivors": int(halving_min_survivors),
        },
    )
    search_control_policy = build_stock_pit_search_control_policy(
        reward_control_roots or [],
        expected_dataset_role=dataset_role_for_path(dataset_path),
        exploration_share=reward_exploration_share,
        policy_state_path=resolved_policy_state_path,
    )
    if generator_mode == "rx_typed_beam":
        ledger = build_stock_pit_rx_typed_beam_search_ledger(
            path=dataset_path,
            start_round=shard_index,
            round_count=1,
            candidates_per_round=candidates_per_shard,
            target_window_count=target_window_count,
            max_window=max_window,
            signal_clock=SIGNAL_CLOCK_AFTER_OPEN,
            search_control_policy=search_control_policy,
            beam_width=beam_width,
            max_beam_records=max_beam_records,
        )
    else:
        ledger = build_stock_pit_forward_first_large_search_ledger(
            path=dataset_path,
            start_round=shard_index,
            round_count=1,
            candidates_per_round=candidates_per_shard,
            target_window_count=target_window_count,
            max_window=max_window,
            signal_clock=SIGNAL_CLOCK_AFTER_OPEN,
            search_control_policy=search_control_policy,
        )
    ledger = apply_stock_pit_ledger_selection_policy(
        ledger,
        previous_roots=previous_search_roots or [],
        expected_dataset_role=dataset_role_for_path(dataset_path),
        max_family_share=max_family_share,
    )
    ledger_path = output_root / "candidate_ledger.json"
    write_json_artifact(ledger_path, ledger)
    if use_successive_halving:
        validation = run_stock_pit_successive_halving_validation(
            ledger_path,
            output_root=output_root / "successive_halving",
            path=dataset_path,
            retained_only=True,
            top_bottom_quantile=top_bottom_quantile,
            stage0_recent_quarter_window_count=1,
            stage1_recent_quarter_window_count=recent_quarter_window_count,
            recent_warmup_days=recent_warmup_days,
            parallel_workers=parallel_workers,
            use_fast_context=use_fast_context,
            survivor_fraction=halving_survivor_fraction,
            min_survivors=halving_min_survivors,
            max_family_share=max_family_share if max_family_share > 0 else 0.25,
        )
    else:
        validation = batch_validate_candidate_ledger(
            ledger_path,
            path=dataset_path,
            retained_only=True,
            max_candidates=max_candidates,
            top_bottom_quantile=top_bottom_quantile,
            recent_quarter_window_count=recent_quarter_window_count,
            recent_warmup_days=recent_warmup_days,
            parallel_workers=parallel_workers,
            use_fast_context=use_fast_context,
        )
    validation_path = output_root / "stage1_validation_report.json"
    write_json_artifact(validation_path, validation)
    summary = _summary(
        validation,
        shard_index=shard_index,
        shard_count=shard_count,
        ledger=ledger,
        dataset_path=dataset_path,
    )
    summary["candidate_ledger"] = str(ledger_path)
    summary["stage1_validation_report"] = str(validation_path)
    write_json_artifact(output_root / "stage1_summary.json", summary)
    write_json_artifact(status_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one clean stock-PIT large-search shard.")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, default=16)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--candidates-per-shard", type=int, default=2000)
    parser.add_argument("--target-window-count", type=int, default=24)
    parser.add_argument("--max-window", type=int, default=126)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.05)
    parser.add_argument("--recent-quarter-window-count", type=int, default=2)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    parser.add_argument("--parallel-workers", type=int, default=1)
    parser.add_argument("--max-candidates", type=int, default=None)
    parser.add_argument("--use-fast-context", action="store_true")
    parser.add_argument("--previous-search-root", type=Path, action="append", default=[])
    parser.add_argument("--max-family-share", type=float, default=0.0)
    parser.add_argument("--reward-control-root", type=Path, action="append", default=[])
    parser.add_argument("--reward-exploration-share", type=float, default=0.25)
    parser.add_argument("--policy-state-path", type=Path, default=None)
    parser.add_argument("--generator-mode", choices=["forward_first", "rx_typed_beam"], default="forward_first")
    parser.add_argument("--beam-width", type=int, default=64)
    parser.add_argument("--max-beam-records", type=int, default=4096)
    parser.add_argument("--use-successive-halving", action="store_true")
    parser.add_argument("--halving-survivor-fraction", type=float, default=0.35)
    parser.add_argument("--halving-min-survivors", type=int, default=64)
    args = parser.parse_args()
    summary = run_worker(
        output_root=args.output_root,
        shard_index=args.shard_index,
        shard_count=args.shard_count,
        dataset_path=args.dataset_path,
        candidates_per_shard=args.candidates_per_shard,
        target_window_count=args.target_window_count,
        max_window=args.max_window,
        top_bottom_quantile=args.top_bottom_quantile,
        recent_quarter_window_count=args.recent_quarter_window_count,
        recent_warmup_days=args.recent_warmup_days,
        parallel_workers=max(1, int(args.parallel_workers)),
        max_candidates=args.max_candidates,
        use_fast_context=bool(args.use_fast_context),
        previous_search_roots=list(args.previous_search_root or []),
        max_family_share=max(0.0, float(args.max_family_share)),
        reward_control_roots=list(args.reward_control_root or []),
        reward_exploration_share=max(0.0, float(args.reward_exploration_share)),
        policy_state_path=args.policy_state_path,
        generator_mode=str(args.generator_mode),
        beam_width=max(1, int(args.beam_width)),
        max_beam_records=max(1, int(args.max_beam_records)),
        use_successive_halving=bool(args.use_successive_halving),
        halving_survivor_fraction=max(0.01, min(1.0, float(args.halving_survivor_fraction))),
        halving_min_survivors=max(1, int(args.halving_min_survivors)),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

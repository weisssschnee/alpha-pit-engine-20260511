from __future__ import annotations

import argparse
import json
from collections import defaultdict
from hashlib import sha1
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.a5_parameterized_lane import infer_real_data_windows
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH, dataset_role_for_path
from our_system_phase2.services.real_market_validation import SIGNAL_CLOCK_AFTER_OPEN, batch_validate_candidate_ledger
from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression
from our_system_phase2.services.stock_pit_ledger_policy import (
    apply_stock_pit_ledger_selection_policy,
    apply_stock_pit_search_control_schedule,
    build_stock_pit_search_control_policy,
    diversified_top_candidates,
    family_diversity_report,
)


UNREACHED_SEARCH_VERSION = "phase2-stock-pit-unreached-shape-liquidity-v1-2026-05-04"


def _candidate_id(expression: str) -> str:
    return f"stockpit-ur-{sha1(expression.encode('utf-8')).hexdigest()[:12]}"


def _rank(expression: str) -> str:
    return f"CSRank({expression})"


def _zscore(expression: str) -> str:
    return f"ZScore({expression})"


def _neg(expression: str) -> str:
    return f"Neg({expression})"


def _safe_div(left: str, right: str) -> str:
    return f"Div({left},Add(Abs({right}),0.000001))"


def _gap(window: int) -> str:
    return _safe_div(f"Sub($open,Delay($close,{window}))", f"Delay($close,{window})")


def _range_width(window: int) -> str:
    return _safe_div(f"Sub(Mean($high,{window}),Mean($low,{window}))", f"Mean($close,{window})")


def _open_location(window: int) -> str:
    return _safe_div(f"Sub($open,Mean($low,{window}))", f"Sub(Mean($high,{window}),Mean($low,{window}))")


def _prior_close_location(window: int) -> str:
    return _safe_div(f"Sub(Delay($close,1),Mean($low,{window}))", f"Sub(Mean($high,{window}),Mean($low,{window}))")


def _ret_vol(window: int) -> str:
    return f"Mean(Abs($ret),{max(2, window)})"


def _vol_curve(short: int, long: int) -> str:
    return _safe_div(_ret_vol(short), _ret_vol(long))


def _liquidity(field: str, short: int, long: int) -> str:
    return _safe_div(f"Mean(${field},{short})", f"Mean(${field},{long})")


def _momentum_curve(short: int, long: int) -> str:
    return f"Sub(Mom($close,{short}),Mom($close,{long}))"


def _add(records: list[dict[str, Any]], seen: set[str], *, expression: str, family: str, role: str, metadata: dict[str, Any]) -> None:
    canonical = rank_validation_canonical_expression(expression)
    if canonical in seen:
        return
    seen.add(canonical)
    records.append(
        {
            "candidate_id": _candidate_id(expression),
            "expression": expression,
            "retained": True,
            "source_mode": "stock_pit_unreached_shape_liquidity_search",
            "frontier_lane": "stock_pit_unreached",
            "primitive_family": family,
            "proposal_kind": role,
            "research_family": family,
            "canonical_rank_validation_expression": canonical,
            "recommended_signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
            "uses_after_open_safe_field_lags": True,
            **metadata,
        }
    )


def _parameter_space(path: Path | str, *, target_window_count: int, max_window: int) -> dict[str, Any]:
    source = infer_real_data_windows(path, target_window_count=target_window_count, max_window=max_window)
    windows = sorted({int(window) for window in source["windows"] if 1 <= int(window) <= max_window})
    short_windows = [window for window in windows if window <= 29]
    pairs = [
        (short, long)
        for short in short_windows
        for long in windows
        if short < long and long / max(1, short) >= 1.8
    ]
    return {
        **source,
        "unreached_policy": "shape_location_gap_liquidity_volatility_second_order_interactions",
        "unreached_windows": windows,
        "unreached_short_windows": short_windows,
        "unreached_pairs": pairs,
    }


def build_stock_pit_unreached_ledger(
    *,
    path: Path | str,
    shard_index: int,
    shard_count: int,
    target_window_count: int = 24,
    max_window: int = 126,
    search_control_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parameter_space = _parameter_space(path, target_window_count=target_window_count, max_window=max_window)
    windows = [int(window) for window in parameter_space["unreached_short_windows"]]
    pairs = [(int(short), int(long)) for short, long in parameter_space["unreached_pairs"]]
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    for window in windows:
        atoms = {
            "gap": _gap(window),
            "open_location": _open_location(window),
            "prior_close_location": _prior_close_location(window),
            "range_width": _range_width(window),
        }
        for name, atom in atoms.items():
            for base_kind, base in (
                ("rank", _rank(atom)),
                ("local_z", _rank(_safe_div(f"Sub({atom},Mean({atom},{max(2, window)}) )", f"Std({atom},{max(2, window)})"))),
            ):
                for direction, expression in (("normal", base), ("inverted", _neg(base))):
                    _add(
                        records,
                        seen,
                        expression=expression,
                        family=f"{name}_{base_kind}",
                        role="shape_location_single_axis",
                        metadata={"window": window, "atom": name, "direction": direction},
                    )

    for short, long in pairs:
        left_atoms = {
            "gap": _gap(short),
            "open_location": _open_location(short),
            "range_width": _range_width(short),
            "vol_curve": _vol_curve(short, long),
            "momentum_curve": _momentum_curve(short, long),
        }
        state_atoms = {
            "amount_liquidity": _liquidity("amount", short, long),
            "volume_liquidity": _liquidity("volume", short, long),
            "turnover_liquidity": _liquidity("turnover_rate", short, long),
            "range_width_long": _range_width(long),
            "prior_close_location": _prior_close_location(long),
        }
        for left_name, left in left_atoms.items():
            for right_name, right in state_atoms.items():
                residual = f"CSRank(CSResidual({_rank(left)},{_rank(right)}))"
                product = f"CSRank(Mul({_zscore(left)},{_zscore(right)}))"
                gated = f"CSRank(Mul(CSResidual({_rank(left)},{_rank(right)}),Sign({_zscore(_momentum_curve(short, long))})))"
                for kind, base in (("residual", residual), ("product", product), ("momentum_gated_residual", gated)):
                    for direction, expression in (("normal", base), ("inverted", _neg(base))):
                        _add(
                            records,
                            seen,
                            expression=expression,
                            family=f"{left_name}_x_{right_name}",
                            role=f"unreached_{kind}",
                            metadata={
                                "short_window": short,
                                "long_window": long,
                                "left_atom": left_name,
                                "right_atom": right_name,
                                "direction": direction,
                            },
                        )

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[f"{record['proposal_kind']}::{record['research_family']}"].append(record)
    scheduled: list[dict[str, Any]] = []
    offsets = {key: 0 for key in groups}
    while len(scheduled) < len(records):
        added = False
        for key in sorted(groups):
            offset = offsets[key]
            group = groups[key]
            if offset < len(group):
                scheduled.append(group[offset])
                offsets[key] = offset + 1
                added = True
        if not added:
            break
    scheduled, search_control_audit = apply_stock_pit_search_control_schedule(
        scheduled,
        search_control_policy=search_control_policy,
    )
    selected = scheduled[int(shard_index) :: max(1, int(shard_count))]
    return {
        "run_id": "phase2-stock-pit-unreached-shape-liquidity-ledger",
        "created_at": utc_now_iso(),
        "search_version": UNREACHED_SEARCH_VERSION,
        "scope": "unreached_shape_location_liquidity_volatility_second_order_stock_pit_search",
        "dataset_path": str(path),
        "dataset_role": dataset_role_for_path(path),
        "recommended_validation_kwargs": {
            "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
            "feature_lag_days": 0,
            "execution_lag_days": 1,
            "horizon_days": 1,
            "top_bottom_quantile": 0.02,
            "recent_quarter_window_count": 2,
            "recent_warmup_days": 60,
        },
        "shard_index": int(shard_index),
        "shard_count": int(shard_count),
        "full_space_candidate_count": len(records),
        "record_count": len(selected),
        "parameter_space": parameter_space,
        "search_control_policy": {
            key: value
            for key, value in (search_control_policy or {}).items()
            if key
            in {
                "policy_version",
                "active",
                "scope",
                "terminal_reward_changed",
                "archive_retention_changed",
                "exploration_share",
                "expected_dataset_role",
                "reward_control_roots",
                "source_reports",
                "skipped_sources",
                "family_count",
                "role_count",
                "group_count",
                "motif_count",
                "bandit_method",
                "policy_state_path",
                "bandit_key_type_count",
                "bandit_total_observation_count",
            }
        },
        "search_control_schedule_audit": search_control_audit,
        "records": selected,
    }


def _float_value(value: Any, default: float = -999.0) -> float:
    try:
        return default if value is None else float(value)
    except (TypeError, ValueError):
        return default


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
    previous_search_roots: list[Path] | None = None,
    max_family_share: float = 0.0,
    reward_control_roots: list[Path] | None = None,
    reward_exploration_share: float = 0.25,
    policy_state_path: Path | None = None,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    resolved_policy_state_path = policy_state_path or (output_root / "stock_pit_policy_state.json")
    write_json_artifact(
        output_root / "worker_status.json",
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
        },
    )
    search_control_policy = build_stock_pit_search_control_policy(
        reward_control_roots or [],
        expected_dataset_role=dataset_role_for_path(dataset_path),
        exploration_share=reward_exploration_share,
        policy_state_path=resolved_policy_state_path,
    )
    ledger = build_stock_pit_unreached_ledger(
        path=dataset_path,
        shard_index=shard_index,
        shard_count=shard_count,
        target_window_count=target_window_count,
        max_window=max_window,
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
    write_json_artifact(output_root / "stage1_validation_report.json", validation)
    evaluations = sorted(
        list(validation.get("evaluations", []) or []),
        key=lambda item: (
            _float_value(item.get("mean_window_long_sortino")),
            _float_value(item.get("mean_window_long_return")),
            _float_value(item.get("mean_window_rank_ic")),
        ),
        reverse=True,
    )
    diversified = diversified_top_candidates(evaluations, limit=20, max_per_family=2)
    summary = {
        "created_at": utc_now_iso(),
        "status": "completed",
        "shard_index": shard_index,
        "shard_count": shard_count,
        "dataset_path": str(dataset_path),
        "dataset_role": dataset_role_for_path(dataset_path),
        "search_version": UNREACHED_SEARCH_VERSION,
        "ledger_record_count": ledger["record_count"],
        "full_space_candidate_count": ledger["full_space_candidate_count"],
        "validation_evaluated_count": validation.get("evaluated_count"),
        "validation_unsupported_count": validation.get("unsupported_count"),
        "validation_top_bottom_quantile": validation.get("top_bottom_quantile"),
        "validation_acceleration_mode": validation.get("validation_acceleration_mode"),
        "validation_period": {
            "start": validation.get("evaluation_start_date"),
            "end": validation.get("evaluation_end_date"),
        },
        "ledger_selection_policy": ledger.get("ledger_selection_policy"),
        "search_control_policy": ledger.get("search_control_policy"),
        "search_control_schedule_audit": ledger.get("search_control_schedule_audit"),
        "evaluation_family_diversity": family_diversity_report(evaluations),
        "top_long_only_candidates": [_candidate_summary_item(item) for item in evaluations[:20]],
        "diversified_top_long_only_candidates": [_candidate_summary_item(item) for item in diversified],
        "candidate_ledger": str(ledger_path),
        "stage1_validation_report": str(output_root / "stage1_validation_report.json"),
    }
    write_json_artifact(output_root / "stage1_summary.json", summary)
    write_json_artifact(output_root / "worker_status.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one stock-PIT unreached-space search shard.")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, default=4)
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
        previous_search_roots=list(args.previous_search_root or []),
        max_family_share=max(0.0, float(args.max_family_share)),
        reward_control_roots=list(args.reward_control_root or []),
        reward_exploration_share=max(0.0, float(args.reward_exploration_share)),
        policy_state_path=args.policy_state_path,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

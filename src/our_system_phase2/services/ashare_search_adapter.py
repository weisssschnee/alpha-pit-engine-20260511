from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.a5_parameterized_lane import infer_real_data_windows
from our_system_phase2.services.real_market_validation import SIGNAL_CLOCK_AFTER_OPEN, SIGNAL_CLOCK_PRE_OPEN
from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression


ASHARE_ADAPTER_VERSION = "phase2-ashare-search-adapter-v2-2026-04-27"


def _read_ledger(value: Path | str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return json.loads(Path(value).read_text(encoding="utf-8"))


def ashare_trading_contract(*, signal_clock: str = SIGNAL_CLOCK_AFTER_OPEN) -> dict[str, Any]:
    if signal_clock not in {SIGNAL_CLOCK_AFTER_OPEN, SIGNAL_CLOCK_PRE_OPEN}:
        raise ValueError(f"unsupported_ashare_signal_clock:{signal_clock}")
    after_open = signal_clock == SIGNAL_CLOCK_AFTER_OPEN
    return {
        "market_adapter": "china_a_share",
        "adapter_version": ASHARE_ADAPTER_VERSION,
        "adapter_role": "market_contract_and_evaluation_adapter_not_formula_generator",
        "preserves_core_search_system": True,
        "portable_core_runtime_unchanged": True,
        "does_not_define_formula_space": True,
        "formula_generation_owner": "portable_core_search_or_external_generators_cfg_a5_alphagpt",
        "interaction_policy": "adapter_never_locks_formula_interactions_only_validation_availability_and_tradability",
        "signal_clock": signal_clock,
        "field_availability": "after_open_open_and_overnight_current_day_full_day_bar_prior_day"
        if after_open
        else "pre_open_prior_day_and_earlier_only",
        "execution_model": "t_plus_1_close_to_close_validation_by_default",
        "cannot_use_same_open_fill_when_signal_uses_open_print": after_open,
        "tradability_constraints": [
            "block_buy_limit_up_at_entry",
            "block_sell_limit_down_at_entry",
            "block_suspended_at_entry",
            "do_not_filter_outcomes_using_exit_day_limit_state",
            "st_five_percent_limit_requires_dedicated_data_before_promotion",
        ],
        "promotion_blockers_until_cleared": [
            "cost_slippage_capacity_model",
            "pit_industry_neutral_or_exposure_audit",
            "st_limit_identification",
            "multi_window_oos_beyond_recent_three_months",
            "forward_shadow_validation",
        ],
    }


def annotate_ledger_for_ashare(
    ledger: Path | str | dict[str, Any],
    *,
    signal_clock: str = SIGNAL_CLOCK_AFTER_OPEN,
) -> dict[str, Any]:
    source = _read_ledger(ledger)
    contract = ashare_trading_contract(signal_clock=signal_clock)
    annotated = deepcopy(source)
    records = list(annotated.get("records", []))
    for record in records:
        record["market_adapter"] = contract["market_adapter"]
        record["adapter_version"] = contract["adapter_version"]
        record["recommended_signal_clock"] = signal_clock
        record["ashare_trading_contract"] = {
            "field_availability": contract["field_availability"],
            "execution_model": contract["execution_model"],
            "tradability_constraints": contract["tradability_constraints"],
            "interaction_policy": contract["interaction_policy"],
        }
    annotated["records"] = records
    annotated["market_adapter"] = contract["market_adapter"]
    annotated["adapter_version"] = contract["adapter_version"]
    annotated["adapter_role"] = contract["adapter_role"]
    annotated["does_not_define_formula_space"] = contract["does_not_define_formula_space"]
    annotated["core_search_system_modified"] = False
    annotated["recommended_validation_kwargs"] = {
        "signal_clock": signal_clock,
        "feature_lag_days": 0,
        "execution_lag_days": 1,
    }
    annotated["ashare_trading_contract"] = contract
    annotated["source_run_id"] = source.get("run_id")
    annotated["run_id"] = f"{source.get('run_id', 'ledger')}-ashare-adapted"
    return annotated


def _gap(window: int) -> str:
    return f"Div(Sub($open,Delay($close,{window})),Delay($close,{window}))"


def _rank(expression: str) -> str:
    return f"CSRank({expression})"


def _zscore(expression: str) -> str:
    return f"ZScore({expression})"


def _vol_norm(expression: str, vol_window: int) -> str:
    return f"Div({expression},Mean(Abs($ret),{vol_window}))"


def _add_record(records: list[dict[str, Any]], seen: set[str], record: dict[str, Any]) -> None:
    canonical = rank_validation_canonical_expression(str(record["expression"]))
    if canonical in seen:
        return
    seen.add(canonical)
    records.append(
        {
            "candidate_id": f"ashare-adapter-{len(records) + 1:04d}",
            "retained": True,
            "source_mode": "ashare_adapter_diagnostic_seed_lane_not_primary_search",
            "frontier_lane": "ashare_adapter_diagnostic_replay_seed",
            "archive_cell": "ashare_clock_aware_diagnostic_seed_family",
            "canonical_rank_validation_expression": canonical,
            "ashare_constraints_apply_to_all_candidates": True,
            "primary_search_generator": False,
            **record,
        }
    )


def _gap_records(gap_windows: list[int], signal_clock: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for window in gap_windows:
        gap = _gap(window)
        for transform_name, transformed in (("rank", _rank(gap)), ("zscore", _zscore(gap))):
            for direction, expression in (("normal", transformed), ("inverted", f"Neg({transformed})")):
                records.append(
                    {
                        "expression": expression,
                        "primitive_family": "ashare_gap_reversal",
                        "proposal_kind": "clock_aware_gap",
                        "direction": direction,
                        "base_transform": transform_name,
                        "window": window,
                        "gap_window": window,
                        "recommended_signal_clock": signal_clock,
                    }
                )
    return records


def _anti_momentum_records(momentum_windows: list[int], signal_clock: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for window in momentum_windows:
        momentum = f"Mom($close,{window})"
        for transform_name, transformed in (("rank", _rank(momentum)), ("zscore", _zscore(momentum))):
            records.append(
                {
                    "expression": f"Neg({transformed})",
                    "primitive_family": "ashare_short_term_anti_momentum",
                    "proposal_kind": "clock_aware_anti_momentum",
                    "direction": "inverted",
                    "base_transform": transform_name,
                    "window": window,
                    "momentum_window": window,
                    "recommended_signal_clock": signal_clock,
                }
            )
    return records


def _vol_normalized_gap_records(gap_windows: list[int], vol_windows: list[int], signal_clock: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for gap_window in gap_windows:
        for vol_window in vol_windows:
            if vol_window > max(20, gap_window * 4):
                continue
            signal = _vol_norm(_gap(gap_window), vol_window)
            records.append(
                {
                    "expression": f"Neg({_rank(signal)})",
                    "primitive_family": "ashare_vol_normalized_gap_reversal",
                    "proposal_kind": "clock_aware_gap_vol_normalized",
                    "direction": "inverted",
                    "base_transform": "rank",
                    "window": gap_window,
                    "gap_window": gap_window,
                    "volatility_window": vol_window,
                    "recommended_signal_clock": signal_clock,
                }
            )
    return records


def _round_scheduled_records(
    family_batches: list[list[dict[str, Any]]],
    *,
    start_round: int,
    round_count: int,
    candidates_per_family_per_round: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    per_family = max(1, int(candidates_per_family_per_round))
    for round_index in range(max(0, int(start_round)), max(0, int(start_round)) + max(0, int(round_count))):
        for batch in family_batches:
            if not batch:
                continue
            start = (round_index * per_family) % len(batch)
            for offset in range(per_family):
                candidate = batch[(start + offset) % len(batch)]
                _add_record(selected, seen, candidate)
    return selected


def build_ashare_targeted_search_ledger(
    *,
    path: Path | str,
    start_round: int = 0,
    round_count: int = 4,
    candidates_per_family_per_round: int = 12,
    target_window_count: int = 12,
    signal_clock: str = SIGNAL_CLOCK_AFTER_OPEN,
) -> dict[str, Any]:
    contract = ashare_trading_contract(signal_clock=signal_clock)
    parameter_space = infer_real_data_windows(path, target_window_count=target_window_count)
    windows = [int(window) for window in parameter_space["windows"] if 1 <= int(window) <= 60]
    gap_windows = [window for window in windows if window <= 20]
    momentum_windows = [window for window in windows if 2 <= window <= 30]
    vol_windows = [window for window in windows if 2 <= window <= 20]
    if not vol_windows:
        vol_windows = [2, 3, 5, 8]
    family_batches = [
        _gap_records(gap_windows, signal_clock),
        _anti_momentum_records(momentum_windows, signal_clock),
        _vol_normalized_gap_records(gap_windows, vol_windows, signal_clock),
    ]
    full_space_candidate_count = sum(len(batch) for batch in family_batches)
    records = _round_scheduled_records(
        family_batches,
        start_round=start_round,
        round_count=round_count,
        candidates_per_family_per_round=candidates_per_family_per_round,
    )
    family_counts: dict[str, int] = {}
    for record in records:
        family = str(record["primitive_family"])
        family_counts[family] = family_counts.get(family, 0) + 1

    return {
        "run_id": "phase2-ashare-diagnostic-seed-ledger",
        "created_at": utc_now_iso(),
        "adapter_version": ASHARE_ADAPTER_VERSION,
        "scope": "china_a_share_clock_aware_diagnostic_seed_lane_not_primary_search",
        "core_search_system_modified": False,
        "can_reuse_core_for_other_markets": True,
        "adapter_role": contract["adapter_role"],
        "primary_search_generator": False,
        "does_not_define_formula_space": True,
        "formula_generation_owner": contract["formula_generation_owner"],
        "interaction_policy": contract["interaction_policy"],
        "dataset_path": str(path),
        "round_scheduler": {
            "start_round": start_round,
            "round_count": round_count,
            "candidates_per_family_per_round": candidates_per_family_per_round,
        },
        "search_budget_semantics": "training_style_rounds_for_this_diagnostic_seed_lane_not_candidate_space_limit",
        "infinite_space_preserved_by_main_core_generation_then_ashare_annotation": True,
        "full_space_candidate_count_for_current_parameter_slice": full_space_candidate_count,
        "continuation_policy": "main_path_should_use_core_or_external_generator_ledgers_then_annotate_ledger_for_ashare",
        "record_count": len(records),
        "recommended_validation_kwargs": {
            "signal_clock": signal_clock,
            "feature_lag_days": 0,
            "execution_lag_days": 1,
        },
        "ashare_trading_contract": contract,
        "ashare_constraints_apply_to_all_candidates": True,
        "parameter_space": {
            **parameter_space,
            "ashare_gap_windows": gap_windows,
            "ashare_momentum_windows": momentum_windows,
            "ashare_vol_windows": vol_windows,
        },
        "efficiency_contract": {
            "diagnostic_seed_lane_not_primary_generator": True,
            "targeted_family_count": len(family_counts),
            "family_counts": family_counts,
            "does_not_expand_full_formula_grammar": True,
            "does_not_lock_formula_interactions": True,
            "main_search_interactions_remain_owned_by_core_or_external_generators": True,
            "rounds_are_compute_schedule_not_space_cap": True,
            "all_families_receive_each_round": True,
            "constraints_are_global_not_gap_specific": True,
            "search_efficiency_hypothesis": "diagnostic_replay_only_compare_hit_rate_before_core_large_scale_expansion",
            "competitor_comparison_required": "validate_candidates_per_promoted_candidate_vs_cfg_a5_alphagpt",
        },
        "records": records,
    }

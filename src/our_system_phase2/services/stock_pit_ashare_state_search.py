from __future__ import annotations

from collections import defaultdict
from hashlib import sha1
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.a5_parameterized_lane import infer_real_data_windows
from our_system_phase2.services.market_regime_state import PIT_TREND_STATE_FEATURE_FIELDS, trend_state_feature_contract
from our_system_phase2.services.real_market_data import dataset_role_for_path
from our_system_phase2.services.real_market_validation import SIGNAL_CLOCK_AFTER_OPEN
from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression


ASHARE_STATE_SEARCH_VERSION = "phase2-stock-pit-ashare-state-fresh-v2-pit-trend-state-2026-05-07"


def _candidate_id(expression: str) -> str:
    return f"stockpit-as-{sha1(expression.encode('utf-8')).hexdigest()[:12]}"


def _rank(expression: str) -> str:
    return f"CSRank({expression})"


def _zscore(expression: str) -> str:
    return f"ZScore({expression})"


def _neg(expression: str) -> str:
    return f"Neg({expression})"


def _safe_div(left: str, right: str) -> str:
    return f"Div({left},Add(Abs({right}),0.000001))"


def _range_location(window: int) -> str:
    return _safe_div(f"Sub($close,Mean($low,{window}))", f"Sub(Mean($high,{window}),Mean($low,{window}))")


def _open_gap() -> str:
    return _safe_div("Sub($open,Delay($close,1))", "Delay($close,1)")


def _open_vs_prior_range(window: int) -> str:
    return _safe_div(f"Sub($open,Mean($low,{window}))", f"Sub(Mean($high,{window}),Mean($low,{window}))")


def _prior_limit_up_pressure(window: int) -> str:
    volatility = f"Mean(Abs($ret),{max(2, window)})"
    return _safe_div("$ret", volatility)


def _prior_limit_down_pressure(window: int) -> str:
    volatility = f"Mean(Abs($ret),{max(2, window)})"
    return _safe_div(_neg("$ret"), volatility)


def _upper_tail(window: int) -> str:
    return _safe_div(f"Sub(Mean($high,{window}),$close)", f"Sub(Mean($high,{window}),Mean($low,{window}))")


def _lower_tail(window: int) -> str:
    return _safe_div(f"Sub($close,Mean($low,{window}))", f"Sub(Mean($high,{window}),Mean($low,{window}))")


def _liquidity(field: str, short: int, long: int) -> str:
    return _safe_div(f"Mean(${field},{short})", f"Mean(${field},{long})")


def _momentum_curve(short: int, long: int) -> str:
    return f"Sub(Mom($close,{short}),Mom($close,{long}))"


def _volatility_curve(short: int, long: int) -> str:
    return _safe_div(f"Mean(Abs($ret),{short})", f"Mean(Abs($ret),{long})")


def _add(
    records: list[dict[str, Any]],
    seen: set[str],
    *,
    expression: str,
    family: str,
    role: str,
    metadata: dict[str, Any],
) -> None:
    canonical = rank_validation_canonical_expression(expression)
    if canonical in seen:
        return
    seen.add(canonical)
    records.append(
        {
            "candidate_id": _candidate_id(expression),
            "expression": expression,
            "retained": True,
            "source_mode": "stock_pit_ashare_state_fresh_search",
            "frontier_lane": "stock_pit_ashare_state",
            "primitive_family": family,
            "proposal_kind": role,
            "research_family": family,
            "canonical_rank_validation_expression": canonical,
            "recommended_signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
            "uses_after_open_safe_field_lags": True,
            "uses_limit_flags_as_features": False,
            "uses_prior_limit_event_features": False,
            "uses_pit_trend_state_features": False,
            "limit_flags_reserved_for_tradability_validation": True,
            **metadata,
        }
    )


def _parameter_space(path: Path | str, *, target_window_count: int, max_window: int) -> dict[str, Any]:
    source = infer_real_data_windows(path, target_window_count=target_window_count, max_window=max_window)
    windows = sorted({int(window) for window in source["windows"] if 1 <= int(window) <= max_window})
    short_windows = [window for window in windows if 1 <= window <= 21]
    medium_windows = [window for window in windows if 5 <= window <= 63]
    pairs = [
        (short, long)
        for short in short_windows
        for long in medium_windows
        if short < long and long / max(1, short) >= 1.8
    ]
    return {
        **source,
        "ashare_state_policy": (
            "after_open_safe_limit_proximity_proxies_plus_open_confirmation_"
            "liquidity_pressure_interactions_plus_optional_pit_trend_state_hidden_variables"
        ),
        "pit_trend_state_feature_fields": list(PIT_TREND_STATE_FEATURE_FIELDS),
        "pit_trend_state_feature_contract": trend_state_feature_contract(),
        "short_windows": short_windows,
        "medium_windows": medium_windows,
        "short_long_pairs": pairs,
    }


def _all_candidate_records(parameter_space: dict[str, Any]) -> list[dict[str, Any]]:
    short_windows = [int(window) for window in parameter_space["short_windows"]]
    pairs = [(int(short), int(long)) for short, long in parameter_space["short_long_pairs"]]
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    for window in short_windows:
        state_atoms = {
            "open_gap": _open_gap(),
            "open_vs_prior_range": _open_vs_prior_range(window),
            "prior_limit_up_pressure": _prior_limit_up_pressure(window),
            "prior_limit_down_pressure": _prior_limit_down_pressure(window),
            "prior_limit_up_event": "$limit_up_event",
            "prior_limit_down_event": "$limit_down_event",
            "prior_limit_up_streak": "$limit_up_streak",
            "prior_limit_down_streak": "$limit_down_streak",
            "prior_limit_up_break": "$limit_up_break",
            "prior_limit_down_repair": "$limit_down_repair",
            "prior_range_location": _range_location(window),
            "upper_tail_release": _upper_tail(window),
            "lower_tail_repair": _lower_tail(window),
            "stock_trend_eff": "$stock_trend_eff",
            "stock_trend_slope": "$stock_trend_slope",
            "stock_trend_state": "$stock_trend_state",
            "stock_price_position_state": "$stock_price_position_state",
        }
        limit_event_atom_names = {
            "prior_limit_up_event",
            "prior_limit_down_event",
            "prior_limit_up_streak",
            "prior_limit_down_streak",
            "prior_limit_up_break",
            "prior_limit_down_repair",
        }
        trend_state_atom_names = {
            "stock_trend_eff",
            "stock_trend_slope",
            "stock_trend_state",
            "stock_price_position_state",
        }
        for name, atom in state_atoms.items():
            for transform, base in (("rank", _rank(atom)), ("zscore_rank", _rank(_zscore(atom)))):
                for direction, expression in (("normal", base), ("inverted", _neg(base))):
                    limit_event_metadata = (
                        {
                            "uses_prior_limit_event_features": True,
                            "limit_event_feature_timestamp_policy": (
                                "raw daily limit-event fields are full-day fields and are lagged by "
                                "SIGNAL_CLOCK_AFTER_OPEN before expression evaluation"
                            ),
                        }
                        if name in limit_event_atom_names
                        else {}
                    )
                    trend_state_metadata = (
                        {
                            "uses_pit_trend_state_features": True,
                            "trend_state_feature_timestamp_policy": (
                                "deterministic trend-state fields are full-day state columns and are lagged by "
                                "SIGNAL_CLOCK_AFTER_OPEN before expression evaluation"
                            ),
                        }
                        if name in trend_state_atom_names
                        else {}
                    )
                    _add(
                        records,
                        seen,
                        expression=expression,
                        family=f"{name}_{transform}",
                        role="ashare_state_single_axis_probe",
                        metadata={
                            "window": window,
                            "atom": name,
                            "transform": transform,
                            "direction": direction,
                            **limit_event_metadata,
                            **trend_state_metadata,
                        },
                    )

    for short, long in pairs:
        pressure_atoms = {
            "limit_up_pressure": _prior_limit_up_pressure(short),
            "limit_down_pressure": _prior_limit_down_pressure(short),
            "limit_up_event": "$limit_up_event",
            "limit_down_event": "$limit_down_event",
            "limit_up_streak": "$limit_up_streak",
            "limit_down_streak": "$limit_down_streak",
            "limit_up_break": "$limit_up_break",
            "limit_down_repair": "$limit_down_repair",
            "open_gap": _open_gap(),
            "open_confirm": _open_vs_prior_range(short),
            "range_repair": _range_location(short),
            "stock_trend_eff": "$stock_trend_eff",
            "stock_trend_slope": "$stock_trend_slope",
            "stock_price_position_state": "$stock_price_position_state",
        }
        limit_event_pressure_names = {
            "limit_up_event",
            "limit_down_event",
            "limit_up_streak",
            "limit_down_streak",
            "limit_up_break",
            "limit_down_repair",
        }
        context_atoms = {
            "amount_surge": _liquidity("amount", short, long),
            "volume_surge": _liquidity("volume", short, long),
            "turnover_surge": _liquidity("turnover_rate", short, long),
            "momentum_curve": _momentum_curve(short, long),
            "volatility_curve": _volatility_curve(short, long),
            "stock_trend_eff": "$stock_trend_eff",
            "stock_trend_slope": "$stock_trend_slope",
            "stock_price_position_state": "$stock_price_position_state",
        }
        market_gates = {
            "market_trend_gate": "Sign($market_trend_state)",
            "market_breadth_gate": "Sign(Sub($market_breadth_state,0.5))",
        }
        trend_state_pressure_names = {"stock_trend_eff", "stock_trend_slope", "stock_price_position_state"}
        trend_state_context_names = {"stock_trend_eff", "stock_trend_slope", "stock_price_position_state"}
        for left_name, left in pressure_atoms.items():
            for right_name, right in context_atoms.items():
                product = f"CSRank(Mul({_zscore(left)},{_zscore(right)}))"
                residual = f"CSRank(CSResidual({_rank(left)},{_rank(right)}))"
                gated = f"CSRank(Mul(CSResidual({_rank(left)},{_rank(right)}),Sign({_zscore(_open_gap())})))"
                bases = [
                    ("product", product),
                    ("residual", residual),
                    ("open_gap_gated_residual", gated),
                ]
                for gate_name, gate in market_gates.items():
                    bases.append(
                        (
                            f"{gate_name}_residual",
                            f"CSRank(Mul(CSResidual({_rank(left)},{_rank(right)}),{gate}))",
                        )
                    )
                for kind, base in bases:
                    for direction, expression in (("normal", base), ("inverted", _neg(base))):
                        limit_event_metadata = (
                            {
                                "uses_prior_limit_event_features": True,
                                "limit_event_feature_timestamp_policy": (
                                    "raw daily limit-event fields are full-day fields and are lagged by "
                                    "SIGNAL_CLOCK_AFTER_OPEN before expression evaluation"
                                ),
                            }
                            if left_name in limit_event_pressure_names
                            else {}
                        )
                        trend_state_metadata = (
                            {
                                "uses_pit_trend_state_features": True,
                                "trend_state_feature_timestamp_policy": (
                                    "deterministic trend-state fields are full-day state columns and are lagged by "
                                    "SIGNAL_CLOCK_AFTER_OPEN before expression evaluation"
                                ),
                            }
                            if (
                                left_name in trend_state_pressure_names
                                or right_name in trend_state_context_names
                                or kind.startswith("market_")
                            )
                            else {}
                        )
                        _add(
                            records,
                            seen,
                            expression=expression,
                            family=f"{left_name}_x_{right_name}",
                            role=f"ashare_state_{kind}",
                            metadata={
                                "short_window": short,
                                "long_window": long,
                                "left_atom": left_name,
                                "right_atom": right_name,
                                "direction": direction,
                                **limit_event_metadata,
                                **trend_state_metadata,
                            },
                        )

    return records


def _round_robin_schedule(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
            if offset >= len(group):
                continue
            scheduled.append(group[offset])
            offsets[key] = offset + 1
            added = True
        if not added:
            break
    return scheduled


def build_stock_pit_ashare_state_ledger(
    *,
    path: Path | str,
    shard_index: int = 0,
    shard_count: int = 1,
    target_window_count: int = 24,
    max_window: int = 126,
) -> dict[str, Any]:
    parameter_space = _parameter_space(path, target_window_count=target_window_count, max_window=max_window)
    records = _round_robin_schedule(_all_candidate_records(parameter_space))
    selected = records[int(shard_index) :: max(1, int(shard_count))]
    family_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    for record in selected:
        family_counts[str(record["research_family"])] = family_counts.get(str(record["research_family"]), 0) + 1
        role_counts[str(record["proposal_kind"])] = role_counts.get(str(record["proposal_kind"]), 0) + 1
    return {
        "run_id": "phase2-stock-pit-ashare-state-fresh-ledger",
        "created_at": utc_now_iso(),
        "search_version": ASHARE_STATE_SEARCH_VERSION,
        "scope": "fresh_ashare_after_open_limit_state_proxy_and_liquidity_interaction_search",
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
            "enable_trend_state_features": True,
        },
        "shard_index": int(shard_index),
        "shard_count": int(shard_count),
        "full_space_candidate_count": len(records),
        "record_count": len(selected),
        "parameter_space": parameter_space,
        "field_contract": {
            "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
            "current_open_allowed": True,
            "full_day_bar_fields_lagged_by_evaluator": True,
            "limit_up_down_flags_not_used_as_signal_features": True,
            "limit_up_down_flags_used_only_by_tradability_validation": True,
            "pit_trend_state_adapter_enabled": True,
            "pit_trend_state_fields": list(PIT_TREND_STATE_FEATURE_FIELDS),
            "pit_trend_state_full_day_fields_lagged_by_evaluator": True,
        },
        "efficiency_contract": {
            "core_search_system_modified": False,
            "can_reuse_core_for_other_markets": True,
            "stage1_fast_train_screen": True,
            "stage2_execution_audit_required_before_keep": True,
            "turnover_and_cost_are_soft_selection_penalties_not_stage1_hard_rejects": True,
        },
        "family_counts": family_counts,
        "role_counts": role_counts,
        "records": selected,
    }

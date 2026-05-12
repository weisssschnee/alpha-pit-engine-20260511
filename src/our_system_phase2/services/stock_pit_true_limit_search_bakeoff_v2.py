from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_data import dataset_role_for_path, panel_header
from our_system_phase2.services.real_market_validation import (
    SIGNAL_CLOCK_AFTER_OPEN,
    TDXGP_LIMIT_STATUS_SOURCE,
    batch_validate_candidate_ledger,
)
from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression
from our_system_phase2.services.stock_pit_forward_first_search import build_stock_pit_rx_typed_beam_search_ledger
from our_system_phase2.services.stock_pit_proof_suite import (
    DEFAULT_LOW_CORR_THRESHOLD,
    DEFAULT_PORTFOLIO_REPLAY_COST_BPS,
    _attach_portfolio_replay,
    _attach_signal_clusters,
    _evaluation_reward,
    _fast_rows_from_variant_report,
    _hash_float,
    _mean,
    _safe_float,
    _share,
    _strict_audit_selected_fast_rows,
    _truncate_ledger_records,
    _write_ledger,
    build_stock_pit_simple_template_baseline_ledger,
    summarize_stock_pit_validation_report,
)
from our_system_phase2.services.stock_pit_replay_ranker import score_shadow_selector, score_with_trained_replay_rankers
from our_system_phase2.services.variation import extract_structural_skeleton


TRUE_LIMIT_SEARCH_BAKEOFF_V2_VERSION = "phase2-true-limit-search-bakeoff-v2-2026-05-11"
TRUE_LIMIT_BAKEOFF_VARIANTS = (
    "simple_template",
    "unreached_space",
    "rx_no_policy_true_limit",
    "rx_diverse_beam",
    "typed_random_dark",
    "non_gap_forced_sampler",
    "ast_evolutionary_mutation",
    "cem_adaptive_grammar",
)
ORIGINAL_UCB_STATE = "DISABLED_PENDING_REDESIGN"
DEFAULT_TURNOVER_SURVIVAL_MAX_ONE_WAY = 0.75


def _candidate_id(prefix: str, expression: str) -> str:
    digest = hashlib.sha1(f"{prefix}::{expression}".encode("utf-8")).hexdigest()[:12]
    return f"stockpit-{prefix}-{digest}"


def _rank(expression: str) -> str:
    return f"CSRank({expression})"


def _zscore(expression: str) -> str:
    return f"ZScore({expression})"


def _neg(expression: str) -> str:
    return f"Neg({expression})"


def _safe_div(left: str, right: str) -> str:
    return f"Div({left},Add(Abs({right}),0.000001))"


def _available_fields(path: Path | str) -> set[str]:
    try:
        return set(panel_header(path))
    except Exception:
        return set()


def _base_windows(*, max_window: int, target_window_count: int) -> list[int]:
    anchors = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 126]
    values = [value for value in anchors if value <= max(1, int(max_window))]
    if not values:
        values = [1]
    if len(values) > max(1, int(target_window_count)):
        step = (len(values) - 1) / max(1, int(target_window_count) - 1)
        values = [values[int(round(index * step))] for index in range(max(1, int(target_window_count)))]
    return sorted(set(max(1, min(int(max_window), int(value))) for value in values))


def _window_pairs(windows: list[int]) -> list[tuple[int, int]]:
    return [
        (short, long)
        for short in windows
        for long in windows
        if short < long and long / max(1, short) >= 1.6
    ]


def _fields(expression: str) -> list[str]:
    return sorted({match.group(1) for match in re.finditer(r"\$([A-Za-z_][A-Za-z0-9_]*)", expression)})


def _operators(expression: str) -> list[str]:
    return [match.group(1) for match in re.finditer(r"\b([A-Za-z][A-Za-z0-9_]*)\s*\(", expression)]


def _expression_windows(expression: str, row: dict[str, Any]) -> list[int]:
    values: set[int] = set()
    for key in (
        "window",
        "short_window",
        "long_window",
        "smoothing_window",
        "slope_lag",
        "volatility_window",
        "numerator_window",
        "denominator_window",
        "numerator_smoothing_window",
        "denominator_smoothing_window",
        "momentum_window",
        "gap_window",
    ):
        value = row.get(key)
        if isinstance(value, int) and value > 0:
            values.add(value)
        elif isinstance(value, float) and value > 0 and value.is_integer():
            values.add(int(value))
    for token in re.findall(r",\s*(\d+)\s*\)", expression or ""):
        number = int(token)
        if number > 0:
            values.add(number)
    for token in re.findall(r"Delay\([^,]+,\s*(\d+)\s*\)", expression or "", flags=re.IGNORECASE):
        number = int(token)
        if number > 0:
            values.add(number)
    return sorted(values)


def _field_group(field: str) -> str:
    if field in {"amount", "volume", "turnover_rate", "vwap", "money_flow", "amtm"}:
        return "liquidity"
    if field in {"ret", "return_1d", "return_5d", "return_20d", "reta", "retb", "retc", "retd", "rete", "retf"}:
        return "return_vol"
    if field in {"open", "high", "low", "close", "price_pos", "low_20", "high_20"}:
        return "price_shape"
    if "limit" in field:
        return "limit_state"
    if "cap" in field or "market" in field or "share" in field:
        return "capacity"
    if "trend" in field or field.startswith("rps"):
        return "trend_state"
    return "other"


def _field_groups(expression: str) -> tuple[str, ...]:
    return tuple(sorted({_field_group(field) for field in _fields(expression)})) or ("none",)


def _operator_chain(expression: str) -> str:
    return ">".join(_operators(expression)[:6]) or "raw"


def _is_gap_like(row_or_expression: dict[str, Any] | str) -> bool:
    if isinstance(row_or_expression, dict):
        expression = str(row_or_expression.get("expression") or "")
        family = str(row_or_expression.get("primitive_family") or row_or_expression.get("research_family") or "")
    else:
        expression = str(row_or_expression)
        family = ""
    normalized = expression.replace(" ", "").lower()
    lower_family = family.lower()
    family_claims_gap = (
        "non_gap" not in lower_family
        and (
            "open_gap" in lower_family
            or lower_family == "gap"
            or lower_family.startswith("gap_")
            or lower_family.endswith("_gap")
        )
    )
    if family_claims_gap:
        return True
    return "$open" in normalized and "delay($close" in normalized and "sub(" in normalized


def _is_cap_residual_like(row_or_expression: dict[str, Any] | str) -> bool:
    if isinstance(row_or_expression, dict):
        expression = str(row_or_expression.get("expression") or "")
        family = str(row_or_expression.get("primitive_family") or row_or_expression.get("research_family") or "")
    else:
        expression = str(row_or_expression)
        family = ""
    text = f"{expression} {family}".lower()
    return "csresidual" in text and ("cap" in text or "market_cap" in text or "share" in text)


def _make_record(
    *,
    expression: str,
    family: str,
    role: str,
    variant: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "candidate_id": _candidate_id(variant, expression),
        "expression": expression,
        "canonical_rank_validation_expression": rank_validation_canonical_expression(expression),
        "frontier_lane": f"stock_pit_{variant}",
        "primitive_family": family,
        "proposal_kind": role,
        "research_family": family,
        "side_search_role": role,
        "recommended_signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
        "qlib_forward_compatible": True,
        "uses_only_forward_panel_fields": True,
        "retained": True,
        "true_limit_bakeoff_variant": variant,
        **(metadata or {}),
    }


def _dedupe_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for row in records:
        expression = str(row.get("expression") or "")
        if not expression:
            continue
        key = rank_validation_canonical_expression(expression)
        if key in seen:
            continue
        seen.add(key)
        output.append(dict(row))
    return output


def _ledger_from_records(
    *,
    path: Path | str,
    variant: str,
    records: list[dict[str, Any]],
    scope: str,
    search_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = _dedupe_records(records)
    return {
        "run_id": f"phase2-stock-pit-{variant}-ledger",
        "created_at": utc_now_iso(),
        "search_version": TRUE_LIMIT_SEARCH_BAKEOFF_V2_VERSION,
        "scope": scope,
        "proof_variant": variant,
        "dataset_path": str(path),
        "dataset_role": dataset_role_for_path(path),
        "record_count": len(rows),
        "original_ucb_state": ORIGINAL_UCB_STATE,
        "selection_contract": {
            "evaluator": "TDXGP_true_limit_preferred",
            "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
            "execution_lag_days": 1,
            "feature_lag_days": 0,
            "reward": "R0_current_true_limit",
            "shadow_rewards_do_not_control_selection": True,
        },
        "search_report": search_report or {},
        "records": rows,
    }


def _retag_ledger(ledger: dict[str, Any], *, variant: str, scope: str) -> dict[str, Any]:
    rows = []
    for row in ledger.get("records", []) or []:
        item = dict(row)
        item["proof_variant"] = variant
        item["true_limit_bakeoff_variant"] = variant
        item["frontier_lane"] = f"stock_pit_{variant}"
        item["proposal_kind"] = item.get("proposal_kind") or item.get("side_search_role") or variant
        item["retained"] = bool(item.get("retained", True))
        rows.append(item)
    out = dict(ledger)
    out["run_id"] = f"{ledger.get('run_id', 'stock-pit-ledger')}-{variant}"
    out["search_version"] = ledger.get("search_version") or TRUE_LIMIT_SEARCH_BAKEOFF_V2_VERSION
    out["scope"] = scope
    out["proof_variant"] = variant
    out["original_ucb_state"] = ORIGINAL_UCB_STATE
    out["record_count"] = len(rows)
    out["records"] = rows
    return out


def _select_diverse_records(
    rows: list[dict[str, Any]],
    *,
    candidate_budget: int,
    seed: str,
    gap_share_cap: float = 0.18,
    cap_residual_share_cap: float = 0.22,
    non_gap_bonus: float = 0.35,
) -> list[dict[str, Any]]:
    pool = _dedupe_records(rows)
    selected: list[dict[str, Any]] = []
    skeleton_counts: Counter[str] = Counter()
    field_group_counts: Counter[tuple[str, ...]] = Counter()
    operator_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    gap_count = 0
    cap_residual_count = 0

    while pool and len(selected) < max(0, int(candidate_budget)):
        total_next = len(selected) + 1

        def score(row: dict[str, Any]) -> float:
            expression = str(row.get("expression") or "")
            skeleton = extract_structural_skeleton(expression)
            groups = _field_groups(expression)
            operators = _operator_chain(expression)
            family = str(row.get("primitive_family") or row.get("research_family") or "unknown")
            is_gap = _is_gap_like(row)
            is_cap_residual = _is_cap_residual_like(row)
            novelty = 0.0
            novelty += 1.00 / (1.0 + skeleton_counts[skeleton])
            novelty += 0.75 / (1.0 + field_group_counts[groups])
            novelty += 0.50 / (1.0 + operator_counts[operators])
            novelty += 0.35 / (1.0 + family_counts[family])
            if not is_gap:
                novelty += non_gap_bonus
            if is_gap and (gap_count + 1) / total_next > gap_share_cap:
                novelty -= 2.50
            if is_cap_residual and (cap_residual_count + 1) / total_next > cap_residual_share_cap:
                novelty -= 1.50
            novelty += 0.05 * _hash_float(seed, row.get("candidate_id"), expression)
            return novelty

        best = max(pool, key=score)
        pool.remove(best)
        expression = str(best.get("expression") or "")
        selected.append(best)
        skeleton_counts[extract_structural_skeleton(expression)] += 1
        field_group_counts[_field_groups(expression)] += 1
        operator_counts[_operator_chain(expression)] += 1
        family_counts[str(best.get("primitive_family") or best.get("research_family") or "unknown")] += 1
        gap_count += int(_is_gap_like(best))
        cap_residual_count += int(_is_cap_residual_like(best))
    return selected


def build_stock_pit_rx_diverse_beam_ledger(
    *,
    path: Path | str,
    candidate_budget: int,
    target_window_count: int,
    max_window: int,
    beam_width: int,
    max_beam_records: int,
    seed: str,
) -> dict[str, Any]:
    wide = build_stock_pit_rx_typed_beam_search_ledger(
        path=path,
        round_count=1,
        candidates_per_round=max(int(candidate_budget) * 6, int(max_beam_records)),
        target_window_count=target_window_count,
        max_window=max_window,
        signal_clock=SIGNAL_CLOCK_AFTER_OPEN,
        search_control_policy=None,
        beam_width=beam_width,
        max_beam_records=max(int(max_beam_records), int(candidate_budget) * 6),
    )
    selected = _select_diverse_records(
        [dict(row) for row in wide.get("records", []) or []],
        candidate_budget=candidate_budget,
        seed=seed,
    )
    return _ledger_from_records(
        path=path,
        variant="rx_diverse_beam",
        records=[
            {
                **row,
                "proof_variant": "rx_diverse_beam",
                "true_limit_bakeoff_variant": "rx_diverse_beam",
                "proposal_kind": f"rx_diverse_{row.get('proposal_kind') or row.get('side_search_role') or 'beam'}",
            }
            for row in selected
        ],
        scope="rx_typed_beam_with_structural_diversity_pressure_no_ucb",
        search_report={
            "source_full_record_count": len(wide.get("records", []) or []),
            "diversity_pressure": {
                "novelty_bonus": True,
                "coverage_bonus": True,
                "same_skeleton_penalty": True,
                "same_field_group_penalty": True,
                "same_operator_chain_penalty": True,
                "gap_family_overuse_penalty": True,
                "cap_residual_overuse_penalty": True,
            },
        },
    )


def build_stock_pit_non_gap_forced_sampler_ledger(
    *,
    path: Path | str,
    candidate_budget: int,
    target_window_count: int,
    max_window: int,
    seed: str,
) -> dict[str, Any]:
    fields = _available_fields(path)
    windows = _base_windows(max_window=max_window, target_window_count=target_window_count)
    pairs = _window_pairs(windows)
    records: list[dict[str, Any]] = []

    def has(field: str) -> bool:
        return not fields or field in fields

    def add(expression: str, family: str, role: str, metadata: dict[str, Any] | None = None) -> None:
        if _is_gap_like(expression):
            return
        records.append(
            _make_record(
                expression=expression,
                family=family,
                role=role,
                variant="non_gap_forced_sampler",
                metadata=metadata,
            )
        )

    for window in windows:
        if has("close"):
            mom = f"Mom($close,{window})"
            add(_rank(mom), "close_momentum_non_gap", "non_gap_price_shape", {"window": window})
            add(_neg(_rank(mom)), "close_momentum_non_gap", "non_gap_price_shape", {"window": window, "direction": "inverted"})
        if has("ret"):
            vol = f"Mean(Abs($ret),{max(2, window)})"
            add(_rank(vol), "realized_volatility_non_gap", "non_gap_return_vol", {"window": window})
            add(_neg(_rank(vol)), "realized_volatility_non_gap", "non_gap_return_vol", {"window": window, "direction": "inverted"})
        if has("high") and has("low") and has("close"):
            location = _safe_div(f"Sub($close,Mean($low,{window}))", f"Sub(Mean($high,{window}),Mean($low,{window}))")
            add(_rank(location), "close_range_location_non_gap", "non_gap_price_shape", {"window": window})
            add(_neg(_rank(location)), "close_range_location_non_gap", "non_gap_price_shape", {"window": window, "direction": "inverted"})
        if has("limit_up_streak"):
            streak = f"Mean($limit_up_streak,{max(2, window)})"
            add(_rank(streak), "prior_limit_streak_non_gap", "non_gap_limit_state", {"window": window})
            add(_neg(_rank(streak)), "prior_limit_streak_non_gap", "non_gap_limit_state", {"window": window, "direction": "inverted"})

    for short, long in pairs:
        liquidity_fields = [field for field in ("amount", "volume", "turnover_rate", "vwap") if has(field)]
        for field in liquidity_fields:
            curve = f"Div(Mean(${field},{short}),Mean(${field},{long}))"
            add(_rank(curve), f"{field}_curve_non_gap", "non_gap_liquidity_curve", {"short_window": short, "long_window": long})
            add(
                _neg(_rank(curve)),
                f"{field}_curve_non_gap",
                "non_gap_liquidity_curve",
                {"short_window": short, "long_window": long, "direction": "inverted"},
            )
            if has("ret"):
                interaction = f"Mul({_zscore(curve)},{_zscore(f'Mean(Abs($ret),{short})')})"
                add(
                    _rank(interaction),
                    f"{field}_curve_x_vol_non_gap",
                    "non_gap_two_expression_interaction",
                    {"short_window": short, "long_window": long},
                )
        if has("close") and has("ret"):
            trend = f"Mom($close,{short})"
            vol_curve = f"Div(Mean(Abs($ret),{short}),Mean(Abs($ret),{long}))"
            add(
                _rank(f"Mul({_zscore(trend)},{_zscore(vol_curve)})"),
                "trend_x_volcurve_non_gap",
                "non_gap_two_expression_interaction",
                {"short_window": short, "long_window": long},
            )
        cap_field = next(
            (
                field
                for field in (
                    "final_float_market_cap",
                    "final_total_market_cap",
                    "tdxgp_total_market_cap",
                    "float_market_cap",
                    "market_cap",
                )
                if has(field)
            ),
            None,
        )
        if cap_field and has("turnover_rate"):
            curve = f"Div(Mean($turnover_rate,{short}),Mean($turnover_rate,{long}))"
            residual = f"CSResidual({_rank(curve)},{_rank(f'Log(${cap_field})')})"
            add(
                _rank(residual),
                "turnover_curve_capacity_residual_non_gap",
                "non_gap_capacity_residual",
                {"short_window": short, "long_window": long, "capacity_field": cap_field},
            )

    selected = _select_diverse_records(records, candidate_budget=candidate_budget, seed=seed, gap_share_cap=0.0)
    return _ledger_from_records(
        path=path,
        variant="non_gap_forced_sampler",
        records=selected,
        scope="forced_non_gap_volatility_liquidity_turnover_prior_limit_trend_shape_sampler",
        search_report={
            "non_gap_constraint": "reject_open_gap_and_open_gap_residual_expressions",
            "emphasized_groups": [
                "volatility",
                "liquidity",
                "turnover",
                "prior_limit_state",
                "trend_shape",
                "amount_curve",
            ],
            "source_candidate_count": len(records),
        },
    )


def build_stock_pit_ast_evolutionary_mutation_ledger(
    *,
    path: Path | str,
    candidate_budget: int,
    target_window_count: int,
    max_window: int,
    beam_width: int,
    max_beam_records: int,
    seed: str,
) -> dict[str, Any]:
    simple = build_stock_pit_simple_template_baseline_ledger(path=path, candidate_budget=max(16, candidate_budget), max_window=max_window)
    fresh_rx = build_stock_pit_rx_typed_beam_search_ledger(
        path=path,
        round_count=1,
        candidates_per_round=max(16, candidate_budget),
        target_window_count=target_window_count,
        max_window=max_window,
        signal_clock=SIGNAL_CLOCK_AFTER_OPEN,
        search_control_policy=None,
        beam_width=max(4, beam_width),
        max_beam_records=max(64, max_beam_records),
    )
    seed_rows = _dedupe_records([*(simple.get("records", []) or []), *(fresh_rx.get("records", []) or [])])
    windows = _base_windows(max_window=max_window, target_window_count=target_window_count)
    fields = _available_fields(path)
    cap_controls = [
        field
        for field in ("final_float_market_cap", "final_total_market_cap", "tdxgp_total_market_cap", "float_market_cap", "market_cap")
        if not fields or field in fields
    ][:2]
    records: list[dict[str, Any]] = []

    def add(expression: str, family: str, role: str, source: dict[str, Any], metadata: dict[str, Any] | None = None) -> None:
        records.append(
            _make_record(
                expression=expression,
                family=family,
                role=role,
                variant="ast_evolutionary_mutation",
                metadata={
                    "mutation_source_candidate_id": source.get("candidate_id"),
                    "mutation_source_family": source.get("primitive_family") or source.get("research_family"),
                    **(metadata or {}),
                },
            )
        )

    for row in seed_rows:
        expression = str(row.get("expression") or "")
        if not expression:
            continue
        family = str(row.get("primitive_family") or row.get("research_family") or "unknown")
        add(_neg(expression), f"{family}_neg_mutation", "ast_neg_wrapper", row)
        add(_rank(_zscore(expression)), f"{family}_zscore_rank_mutation", "ast_rank_zscore_wrapper", row)
        if not expression.startswith("CSRank("):
            add(_rank(expression), f"{family}_rank_wrapper_mutation", "ast_rank_wrapper", row)
        for window in windows[:4]:
            mutated = re.sub(r",\s*\d+\)", f",{window})", expression, count=1)
            if mutated != expression:
                add(mutated, f"{family}_window_mutation", "ast_window_mutation", row, {"mutated_window": window})
        for cap_field in cap_controls:
            residual = f"CSResidual({_rank(expression)},{_rank(f'Log(${cap_field})')})"
            add(_rank(residual), f"{family}_capacity_residual_mutation", "ast_residualize_wrapper", row, {"capacity_field": cap_field})

    pair_seeds = seed_rows[: min(len(seed_rows), max(8, candidate_budget // 2))]
    for left_index, left in enumerate(pair_seeds):
        right = pair_seeds[int(_hash_float(seed, "pair", left_index) * max(1, len(pair_seeds))) % max(1, len(pair_seeds))]
        left_expr = str(left.get("expression") or "")
        right_expr = str(right.get("expression") or "")
        if not left_expr or not right_expr or left_expr == right_expr:
            continue
        add(
            _rank(f"Mul({_zscore(left_expr)},{_zscore(right_expr)})"),
            "ast_crossover_product",
            "ast_two_expression_interaction",
            left,
            {"right_candidate_id": right.get("candidate_id")},
        )
        add(
            _rank(f"CSResidual({_rank(left_expr)},{_rank(right_expr)})"),
            "ast_crossover_residual",
            "ast_two_expression_residual",
            left,
            {"right_candidate_id": right.get("candidate_id")},
        )

    selected = _select_diverse_records(records, candidate_budget=candidate_budget, seed=seed)
    return _ledger_from_records(
        path=path,
        variant="ast_evolutionary_mutation",
        records=selected,
        scope="fresh_template_and_rx_seeded_ast_mutation_no_old_invalid_archive",
        search_report={
            "seed_policy": "fresh_simple_templates_plus_fresh_rx_no_policy_candidates_only",
            "old_invalid_archive_used": False,
            "mutation_operators": [
                "feature_or_wrapper_swap",
                "operator_wrapper",
                "window_mutation",
                "rank_zscore_neg_wrapper",
                "residualize_wrapper",
                "two_expression_interaction",
            ],
            "source_seed_count": len(seed_rows),
            "source_mutation_count": len(records),
        },
    )


def _weighted_choice(distribution: dict[str, float], *parts: Any) -> str:
    total = sum(max(0.0, float(value)) for value in distribution.values())
    if total <= 0:
        return sorted(distribution)[0]
    threshold = _hash_float(*parts) * total
    running = 0.0
    for key, value in sorted(distribution.items()):
        running += max(0.0, float(value))
        if running >= threshold:
            return key
    return sorted(distribution)[-1]


def _normalize_distribution(distribution: dict[str, float], *, min_probability: float) -> dict[str, float]:
    if not distribution:
        return {}
    total = sum(max(0.0, float(value)) for value in distribution.values())
    if total <= 0:
        total = float(len(distribution))
        distribution = {key: 1.0 for key in distribution}
    raw = {key: max(0.0, float(value)) / total for key, value in distribution.items()}
    floored = {key: max(float(min_probability), value) for key, value in raw.items()}
    floor_total = sum(floored.values())
    return {key: value / floor_total for key, value in floored.items()}


def _update_distribution_from_elites(
    distribution: dict[str, float],
    elite_tokens: Iterable[str],
    *,
    min_probability: float,
    inertia: float = 0.45,
) -> dict[str, float]:
    counts = Counter(elite_tokens)
    if not counts:
        return _normalize_distribution(distribution, min_probability=min_probability)
    total = sum(counts.values())
    updated: dict[str, float] = {}
    for key in distribution:
        empirical = counts.get(key, 0) / max(1, total)
        updated[key] = inertia * distribution[key] + (1.0 - inertia) * empirical
    return _normalize_distribution(updated, min_probability=min_probability)


def _cem_expression(
    *,
    motif: str,
    field: str,
    op: str,
    window: int,
    second_field: str,
    second_window: int,
    direction: str,
) -> str:
    def atom(active_field: str, active_op: str, active_window: int) -> str:
        if active_op == "raw":
            return f"${active_field}"
        if active_op == "abs_mean":
            return f"Mean(Abs(${active_field}),{max(2, active_window)})"
        operator = {"mom": "Mom", "mean": "Mean", "std": "Std", "delta": "Delta", "med": "Med"}.get(active_op, "Mean")
        return f"{operator}(${active_field},{max(1, active_window)})"

    left = atom(field, op, window)
    right = atom(second_field, op, second_window)
    if motif == "curve":
        base = f"Div(Mean(${field},{max(1, min(window, second_window))}),Mean(${field},{max(window, second_window)}))"
    elif motif == "interaction":
        base = f"Mul({_zscore(left)},{_zscore(right)})"
    elif motif == "residual":
        base = f"CSResidual({_rank(left)},{_rank(right)})"
    elif motif == "gap":
        base = "Div(Sub($open,Delay($close,1)),Delay($close,1))"
    else:
        base = left
    expression = _rank(base)
    return _neg(expression) if direction == "inverted" else expression


def build_stock_pit_cem_adaptive_grammar_ledger(
    *,
    path: Path | str,
    output_root: Path | str,
    candidate_budget: int,
    target_window_count: int,
    max_window: int,
    top_bottom_quantile: float,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
    use_fast_context: bool,
    seed: str,
    rounds: int = 2,
    elite_fraction: float = 0.25,
    min_probability: float = 0.035,
    gap_cluster_cap: float = 0.18,
) -> dict[str, Any]:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    fields = _available_fields(path)
    candidate_fields = [
        field
        for field in (
            "close",
            "ret",
            "amount",
            "volume",
            "turnover_rate",
            "vwap",
            "limit_up_streak",
            "limit_down_streak",
            "price_pos",
            "rps_rank",
            "trend_state",
            "final_float_market_cap",
        )
        if not fields or field in fields
    ] or ["close", "ret", "amount", "volume"]
    windows = _base_windows(max_window=max_window, target_window_count=target_window_count)
    grammar = {
        "motif": _normalize_distribution(
            {"single": 0.26, "curve": 0.24, "interaction": 0.24, "residual": 0.18, "gap": 0.08},
            min_probability=min_probability,
        ),
        "field": _normalize_distribution({field: 1.0 for field in candidate_fields}, min_probability=min_probability),
        "second_field": _normalize_distribution({field: 1.0 for field in candidate_fields}, min_probability=min_probability),
        "op": _normalize_distribution(
            {"raw": 0.08, "mom": 0.22, "mean": 0.22, "std": 0.18, "delta": 0.16, "abs_mean": 0.14},
            min_probability=min_probability,
        ),
        "window": _normalize_distribution({str(window): 1.0 for window in windows}, min_probability=min_probability),
        "direction": _normalize_distribution({"normal": 0.55, "inverted": 0.45}, min_probability=min_probability),
    }
    archive: dict[str, dict[str, Any]] = {}
    round_reports: list[dict[str, Any]] = []
    samples_per_round = max(int(candidate_budget), 32)

    for round_index in range(max(1, int(rounds))):
        records: list[dict[str, Any]] = []
        gap_count = 0
        attempts = 0
        while len(records) < samples_per_round and attempts < samples_per_round * 8:
            attempts += 1
            motif = _weighted_choice(grammar["motif"], seed, round_index, attempts, "motif")
            if motif == "gap" and gap_count / max(1, len(records) + 1) > gap_cluster_cap:
                motif = "interaction"
            field = _weighted_choice(grammar["field"], seed, round_index, attempts, "field")
            second_field = _weighted_choice(grammar["second_field"], seed, round_index, attempts, "second_field")
            op = _weighted_choice(grammar["op"], seed, round_index, attempts, "op")
            window = int(_weighted_choice(grammar["window"], seed, round_index, attempts, "window"))
            second_window = int(_weighted_choice(grammar["window"], seed, round_index, attempts, "second_window"))
            direction = _weighted_choice(grammar["direction"], seed, round_index, attempts, "direction")
            expression = _cem_expression(
                motif=motif,
                field=field,
                op=op,
                window=window,
                second_field=second_field,
                second_window=second_window,
                direction=direction,
            )
            row = _make_record(
                expression=expression,
                family=f"cem_{motif}",
                role="cem_adaptive_grammar_sample",
                variant="cem_adaptive_grammar",
                metadata={
                    "cem_round": round_index,
                    "cem_motif": motif,
                    "cem_field": field,
                    "cem_second_field": second_field,
                    "cem_operator": op,
                    "window": window,
                    "second_window": second_window,
                    "direction": direction,
                },
            )
            key = rank_validation_canonical_expression(expression)
            if key in archive:
                continue
            records.append(row)
            archive[key] = row
            gap_count += int(_is_gap_like(expression))

        round_ledger = _ledger_from_records(
            path=path,
            variant="cem_adaptive_grammar",
            records=records,
            scope="cem_round_internal_fast_evaluation_for_grammar_update",
            search_report={"round_index": round_index},
        )
        ledger_path = _write_ledger(root / f"cem_round_{round_index:02d}_candidate_ledger.json", round_ledger)
        validation = batch_validate_candidate_ledger(
            ledger_path,
            path=path,
            retained_only=True,
            max_candidates=len(records),
            signal_clock=SIGNAL_CLOCK_AFTER_OPEN,
            execution_lag_days=1,
            feature_lag_days=0,
            top_bottom_quantile=top_bottom_quantile,
            recent_quarter_window_count=recent_quarter_window_count,
            recent_warmup_days=recent_warmup_days,
            parallel_workers=1,
            use_fast_context=use_fast_context,
        )
        validation_path = root / f"cem_round_{round_index:02d}_stage1_validation_report.json"
        write_json_artifact(validation_path, validation)
        fast_rows = [dict(row) for row in validation.get("evaluations", []) if isinstance(row, dict)]
        structural_counts = Counter(
            (
                extract_structural_skeleton(str(row.get("expression") or "")),
                tuple(_field_groups(str(row.get("expression") or ""))),
                _operator_chain(str(row.get("expression") or "")),
            )
            for row in fast_rows
        )

        def cem_cluster_weighted_reward(row: dict[str, Any]) -> float:
            expression = str(row.get("expression") or "")
            cluster_key = (extract_structural_skeleton(expression), tuple(_field_groups(expression)), _operator_chain(expression))
            return _evaluation_reward(row) / math.sqrt(max(1, structural_counts[cluster_key]))

        ranked = sorted(fast_rows, key=cem_cluster_weighted_reward, reverse=True)
        elite_count = max(1, int(math.ceil(len(ranked) * float(elite_fraction))))
        elites = ranked[:elite_count]
        record_by_id = {str(row.get("candidate_id")): row for row in records}
        for key in ("motif", "field", "second_field", "op", "window", "direction"):
            token_name = "cem_operator" if key == "op" else f"cem_{key}"
            if key == "window":
                token_name = "window"
            tokens = [
                str(record_by_id.get(str(row.get("candidate_id")), {}).get(token_name))
                for row in elites
                if record_by_id.get(str(row.get("candidate_id")), {}).get(token_name) is not None
            ]
            grammar[key] = _update_distribution_from_elites(grammar[key], tokens, min_probability=min_probability)
        round_reports.append(
            {
                "round_index": round_index,
                "ledger_path": str(ledger_path),
                "validation_report_path": str(validation_path),
                "sample_count": len(records),
                "elite_count": len(elites),
                "mean_fast_reward": _mean(_evaluation_reward(row) for row in fast_rows),
                "elite_objective": "fast_reward_with_inverse_sqrt_structural_cluster_downweight",
                "grammar": grammar,
            }
        )

    selected = _select_diverse_records(list(archive.values()), candidate_budget=candidate_budget, seed=seed, gap_share_cap=gap_cluster_cap)
    return _ledger_from_records(
        path=path,
        variant="cem_adaptive_grammar",
        records=selected,
        scope="cem_adaptive_grammar_symbolic_search_with_entropy_floor",
        search_report={
            "rounds": round_reports,
            "entropy_floor_min_probability": min_probability,
            "gap_cluster_cap": gap_cluster_cap,
            "elite_fraction": elite_fraction,
            "archive_count": len(archive),
        },
    )


def _build_variant_ledgers(
    *,
    root: Path,
    dataset: Path,
    previous_search_roots: list[Path],
    candidate_budget: int,
    target_window_count: int,
    max_window: int,
    beam_width: int,
    max_beam_records: int,
    top_bottom_quantile: float,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
    use_fast_context: bool,
    seed: str,
    include_qd: bool,
) -> list[tuple[str, dict[str, Any]]]:
    from our_system_phase2.runtime.stock_pit_unreached_search_worker import build_stock_pit_unreached_ledger

    wide_typed = build_stock_pit_rx_typed_beam_search_ledger(
        path=dataset,
        round_count=1,
        candidates_per_round=max(int(candidate_budget) * 6, int(max_beam_records)),
        target_window_count=target_window_count,
        max_window=max_window,
        signal_clock=SIGNAL_CLOCK_AFTER_OPEN,
        search_control_policy=None,
        beam_width=beam_width,
        max_beam_records=max(int(max_beam_records), int(candidate_budget) * 6),
    )
    variants: list[tuple[str, dict[str, Any]]] = [
        (
            "simple_template",
            _retag_ledger(
                build_stock_pit_simple_template_baseline_ledger(
                    path=dataset,
                    candidate_budget=candidate_budget,
                    max_window=max_window,
                ),
                variant="simple_template",
                scope="S0_simple_template_true_limit_baseline",
            ),
        ),
        (
            "unreached_space",
            _retag_ledger(
                _truncate_ledger_records(
                    build_stock_pit_unreached_ledger(
                        path=dataset,
                        shard_index=0,
                        shard_count=1,
                        target_window_count=target_window_count,
                        max_window=max_window,
                        search_control_policy=None,
                    ),
                    candidate_budget=candidate_budget,
                    variant_name="unreached_space",
                    selection_mode="scheduled_first",
                    seed=seed,
                ),
                variant="unreached_space",
                scope="S1_unreached_space_one_of_primary_lanes",
            ),
        ),
        (
            "rx_no_policy_true_limit",
            _retag_ledger(
                build_stock_pit_rx_typed_beam_search_ledger(
                    path=dataset,
                    round_count=1,
                    candidates_per_round=candidate_budget,
                    target_window_count=target_window_count,
                    max_window=max_window,
                    signal_clock=SIGNAL_CLOCK_AFTER_OPEN,
                    search_control_policy=None,
                    beam_width=beam_width,
                    max_beam_records=max_beam_records,
                ),
                variant="rx_no_policy_true_limit",
                scope="S2_rx_typed_beam_no_policy_true_limit",
            ),
        ),
        (
            "rx_diverse_beam",
            build_stock_pit_rx_diverse_beam_ledger(
                path=dataset,
                candidate_budget=candidate_budget,
                target_window_count=target_window_count,
                max_window=max_window,
                beam_width=beam_width,
                max_beam_records=max_beam_records,
                seed=f"{seed}::rx_diverse_beam",
            ),
        ),
        (
            "typed_random_dark",
            _retag_ledger(
                _truncate_ledger_records(
                    wide_typed,
                    candidate_budget=candidate_budget,
                    variant_name="typed_random_dark",
                    selection_mode="hash_random",
                    seed=f"{seed}::typed_random_dark",
                ),
                variant="typed_random_dark",
                scope="S4_typed_random_dark_exploration_space_volume_lane",
            ),
        ),
        (
            "non_gap_forced_sampler",
            build_stock_pit_non_gap_forced_sampler_ledger(
                path=dataset,
                candidate_budget=candidate_budget,
                target_window_count=target_window_count,
                max_window=max_window,
                seed=f"{seed}::non_gap_forced_sampler",
            ),
        ),
        (
            "ast_evolutionary_mutation",
            build_stock_pit_ast_evolutionary_mutation_ledger(
                path=dataset,
                candidate_budget=candidate_budget,
                target_window_count=target_window_count,
                max_window=max_window,
                beam_width=beam_width,
                max_beam_records=max_beam_records,
                seed=f"{seed}::ast_evolutionary_mutation",
            ),
        ),
        (
            "cem_adaptive_grammar",
            build_stock_pit_cem_adaptive_grammar_ledger(
                path=dataset,
                output_root=root / "cem_internal",
                candidate_budget=candidate_budget,
                target_window_count=target_window_count,
                max_window=max_window,
                top_bottom_quantile=top_bottom_quantile,
                recent_quarter_window_count=recent_quarter_window_count,
                recent_warmup_days=recent_warmup_days,
                use_fast_context=use_fast_context,
                seed=f"{seed}::cem_adaptive_grammar",
            ),
        ),
    ]
    if include_qd:
        variants.append(
            (
                "map_elites_qd_optional",
                _build_map_elites_qd_ledger(
                    path=dataset,
                    source_records=[
                        row
                        for _, ledger in variants
                        for row in (ledger.get("records", []) or [])
                    ],
                    candidate_budget=candidate_budget,
                    seed=f"{seed}::map_elites_qd_optional",
                ),
            )
        )
    return variants


def _build_map_elites_qd_ledger(
    *,
    path: Path | str,
    source_records: list[dict[str, Any]],
    candidate_budget: int,
    seed: str,
) -> dict[str, Any]:
    cells: dict[tuple[str, str, str, str, str, str, str], list[dict[str, Any]]] = {}
    for row in _dedupe_records(source_records):
        expression = str(row.get("expression") or "")
        fields = _fields(expression)
        window_values = [int(value) for value in re.findall(r",\s*(\d+)\)", expression)]
        max_window = max(window_values) if window_values else 1
        window_bucket = "short" if max_window <= 5 else "medium" if max_window <= 21 else "long"
        complexity = "simple" if len(_operators(expression)) <= 3 else "complex"
        cell = (
            str(row.get("primitive_family") or row.get("research_family") or "unknown"),
            "+".join(_field_group(field) for field in fields[:3]) or "none",
            window_bucket,
            _operator_chain(expression),
            "gap" if _is_gap_like(row) else "non_gap",
            "cap_residual" if _is_cap_residual_like(row) else "non_cap",
            complexity,
        )
        cells.setdefault(cell, []).append(row)
    selected: list[dict[str, Any]] = []
    for cell, rows in sorted(cells.items(), key=lambda item: _hash_float(seed, item[0])):
        selected.extend(
            sorted(rows, key=lambda row: _hash_float(seed, cell, row.get("candidate_id"), row.get("expression")))[:2]
        )
        if len(selected) >= candidate_budget:
            break
    return _ledger_from_records(
        path=path,
        variant="map_elites_qd_optional",
        records=selected[: max(0, int(candidate_budget))],
        scope="S8_optional_map_elites_quality_diversity_archive_from_current_fresh_lanes",
        search_report={"cell_count": len(cells), "source_candidate_count": len(source_records)},
    )


def _validate_variant_ledgers(
    *,
    root: Path,
    dataset: Path,
    variants: list[tuple[str, dict[str, Any]]],
    candidate_budget: int,
    top_bottom_quantile: float,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
    use_fast_context: bool,
) -> list[dict[str, Any]]:
    variant_reports: list[dict[str, Any]] = []
    for variant_name, ledger in variants:
        variant_root = root / "variants" / variant_name
        variant_root.mkdir(parents=True, exist_ok=True)
        ledger_path = _write_ledger(variant_root / "candidate_ledger.json", ledger)
        validation = batch_validate_candidate_ledger(
            ledger_path,
            path=dataset,
            retained_only=True,
            max_candidates=candidate_budget,
            signal_clock=SIGNAL_CLOCK_AFTER_OPEN,
            execution_lag_days=1,
            feature_lag_days=0,
            top_bottom_quantile=top_bottom_quantile,
            recent_quarter_window_count=recent_quarter_window_count,
            recent_warmup_days=recent_warmup_days,
            parallel_workers=1,
            use_fast_context=use_fast_context,
        )
        validation_path = variant_root / "stage1_validation_report.json"
        write_json_artifact(validation_path, validation)
        summary = summarize_stock_pit_validation_report(validation)
        variant_reports.append(
            {
                "variant": variant_name,
                "ledger_path": str(ledger_path),
                "validation_report_path": str(validation_path),
                "candidate_count": int(ledger.get("record_count") or len(ledger.get("records", []))),
                "valid_candidates": len(validation.get("evaluations", []) or []),
                "duplicate_rate": _duplicate_rate(ledger.get("records", []) or []),
                "search_version": ledger.get("search_version"),
                "summary": summary,
                "ledger_search_report": ledger.get("search_report") or {},
            }
        )
    return variant_reports


def _duplicate_rate(records: Iterable[dict[str, Any]]) -> float:
    rows = list(records)
    if not rows:
        return 0.0
    keys = [rank_validation_canonical_expression(str(row.get("expression") or "")) for row in rows]
    return round(1.0 - len(set(keys)) / max(1, len(keys)), 6)


def _reward_decile_map(rows: list[dict[str, Any]]) -> dict[str, int]:
    ranked = sorted(rows, key=_evaluation_reward)
    total = len(ranked)
    mapping: dict[str, int] = {}
    for index, row in enumerate(ranked):
        decile = min(10, max(1, int(math.floor((index / max(1, total)) * 10.0)) + 1))
        mapping[_row_key(row)] = decile
    return mapping


def _row_key(row: dict[str, Any]) -> str:
    return str(row.get("candidate_id") or row.get("expression") or "")


def _add_selected(
    selected: list[dict[str, Any]],
    seen: set[str],
    row: dict[str, Any] | None,
    *,
    role: str,
    reward_deciles: dict[str, int],
) -> bool:
    if row is None:
        return False
    key = _row_key(row)
    if not key or key in seen:
        return False
    item = dict(row)
    item["strict_selection_role"] = role
    item.setdefault("selection_policy", "r0_control")
    item.setdefault("selection_pool_type", "common_pool")
    item["reward_decile"] = reward_deciles.get(key)
    selected.append(item)
    seen.add(key)
    return True


def _stratified_strict_inputs(
    rows: list[dict[str, Any]],
    *,
    top_n: int,
    random_n: int,
    seed: str,
) -> list[dict[str, Any]]:
    ranked = sorted(rows, key=_evaluation_reward, reverse=True)
    reward_deciles = _reward_decile_map(rows)
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in ranked[: max(0, int(top_n))]:
        _add_selected(selected, seen, row, role="top_fast_reward", reward_deciles=reward_deciles)
    pool = [row for row in ranked if _row_key(row) not in seen]
    low_pool = [row for row in pool if (reward_deciles.get(_row_key(row)) or 10) <= 2]
    middle_pool = [row for row in pool if 4 <= (reward_deciles.get(_row_key(row)) or 0) <= 7]
    non_gap_pool = [row for row in pool if not _is_gap_like(row)]
    skeleton_counts = Counter(extract_structural_skeleton(str(row.get("expression") or "")) for row in rows)
    family_counts = Counter(str(row.get("primitive_family") or "unknown") for row in rows)

    def novelty_score(row: dict[str, Any]) -> float:
        expression = str(row.get("expression") or "")
        skeleton = extract_structural_skeleton(expression)
        family = str(row.get("primitive_family") or "unknown")
        return (
            1.0 / max(1, skeleton_counts[skeleton])
            + 0.6 / max(1, family_counts[family])
            + 0.2 * int(not _is_gap_like(row))
            + 0.01 * _hash_float(seed, "novelty", row.get("candidate_id"), expression)
        )

    roles = [
        (
            "random_low_reward_decile",
            sorted(low_pool, key=lambda row: _hash_float(seed, "low", row.get("candidate_id"), row.get("expression"))),
        ),
        (
            "random_non_gap_candidate",
            sorted(non_gap_pool, key=lambda row: _hash_float(seed, "non_gap", row.get("candidate_id"), row.get("expression"))),
        ),
        (
            "random_middle_reward_decile",
            sorted(middle_pool, key=lambda row: _hash_float(seed, "middle", row.get("candidate_id"), row.get("expression"))),
        ),
        ("random_high_novelty", sorted(pool, key=novelty_score, reverse=True)),
    ]
    added_random = 0
    for role, role_pool in roles:
        if added_random >= max(0, int(random_n)):
            break
        for row in role_pool:
            if _add_selected(selected, seen, row, role=role, reward_deciles=reward_deciles):
                added_random += 1
                break
    fallback = sorted(pool, key=lambda row: _hash_float(seed, "fallback", row.get("candidate_id"), row.get("expression")))
    for row in fallback:
        if added_random >= max(0, int(random_n)):
            break
        if _add_selected(selected, seen, row, role="random_pass_through_fallback", reward_deciles=reward_deciles):
            added_random += 1
    return selected


def _replay_ranker_feature_row(row: dict[str, Any], *, seed: str, source_index: int) -> dict[str, Any]:
    expression = str(row.get("expression") or "")
    fields = _fields(expression)
    operators = _operators(expression)
    windows = _expression_windows(expression, row)
    gap_score = 1.0 if _is_gap_like(row) else 0.0
    normalized = str(row.get("canonical_rank_validation_expression") or rank_validation_canonical_expression(expression))
    variant = str(row.get("proof_variant") or row.get("true_limit_bakeoff_variant") or "unknown")
    event_payload = f"{seed}::{variant}::{source_index}::{row.get('candidate_id')}::{normalized}"
    return {
        "candidate_event_id": hashlib.sha1(event_payload.encode("utf-8")).hexdigest()[:20],
        "candidate_id": row.get("candidate_id") or _candidate_id(variant, expression),
        "parent_id": row.get("parent_id") or row.get("parent_candidate_id"),
        "generation_time": row.get("created_at"),
        "generator_name": variant,
        "generator_seed": seed,
        "expression": expression,
        "normalized_expression": normalized,
        "ast_hash": hashlib.sha1(extract_structural_skeleton(normalized).encode("utf-8")).hexdigest()[:16],
        "structural_skeleton": extract_structural_skeleton(normalized),
        "operator_list": operators,
        "field_list": fields,
        "field_family_list": sorted({_field_group(field) for field in fields}),
        "window_list": windows,
        "decay": row.get("decay") or row.get("decay_window"),
        "neutralization": row.get("neutralization") or row.get("orthogonalization_mode"),
        "universe": row.get("universe") or "stock_pit_panel",
        "delay": row.get("execution_lag_days") or 1,
        "region": "CN_A",
        "complexity_score": round(len(operators) + 0.75 * len(fields) + 0.25 * len(windows) + 0.15 * expression.count("("), 6),
        "cheap_backtest_sharpe": row.get("mean_window_sharpe") or row.get("mean_window_long_sortino"),
        "cheap_backtest_fitness": row.get("fast_reward") if row.get("fast_reward") is not None else _evaluation_reward(row),
        "cheap_backtest_turnover": row.get("mean_window_one_way_turnover")
        or row.get("mean_one_way_turnover")
        or row.get("mean_window_long_selected_turnover_rate"),
        "cheap_backtest_returns": row.get("mean_window_long_return"),
        "cheap_backtest_drawdown": row.get("mean_window_drawdown") or row.get("max_drawdown"),
        "cheap_backtest_ic": row.get("mean_window_ic") or row.get("mean_window_rank_ic"),
        "cheap_backtest_rank_ic": row.get("mean_window_rank_ic"),
        "cheap_backtest_margin": row.get("mean_window_sortino"),
        "gap_score": gap_score,
        "non_gap_score": 1.0 - gap_score,
        "gap_minus_non_gap": gap_score - (1.0 - gap_score),
        "train_valid_decay": row.get("fast_to_strict_ic_decay"),
        "subperiod_stability": row.get("recent_positive_rank_ic_ratio") or row.get("positive_window_rank_ic_ratio"),
        "regime_stability": row.get("recent_positive_rank_ic_ratio") or row.get("positive_window_rank_ic_ratio"),
        "sector_exposure": row.get("sector_exposure"),
        "style_exposure": row.get("style_exposure"),
        "beta_exposure": row.get("beta_exposure"),
        "liquidity_exposure": row.get("mean_window_long_selected_turnover_rate"),
        "corr_to_existing_max": row.get("max_abs_signal_corr_to_prior"),
        "corr_cluster_id": row.get("signal_cluster_id"),
        "strict_pass": False,
        "replay_attempted": False,
        "replay_pass": False,
        "non_gap_replay_pass": False,
        "_source_index": int(source_index),
    }


def _replay_aware_strict_inputs(
    rows: list[dict[str, Any]],
    *,
    model_dir: Path | str | None,
    n_per_variant: int,
    seed: str,
    already_selected_keys: set[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    budget = max(0, int(n_per_variant))
    if budget <= 0:
        return [], {"status": "disabled", "reason": "n_per_variant_zero"}
    if model_dir is None:
        return [], {"status": "disabled", "reason": "model_dir_not_set"}
    candidates: list[dict[str, Any]] = []
    source_rows: dict[int, dict[str, Any]] = {}
    for source_index, row in enumerate(rows):
        key = _row_key(row)
        if not key or key in already_selected_keys:
            continue
        feature_row = _replay_ranker_feature_row(row, seed=seed, source_index=source_index)
        candidates.append(feature_row)
        source_rows[source_index] = row
    if not candidates:
        return [], {"status": "no_available_candidates_after_r0_control"}
    scored, scoring_report = score_with_trained_replay_rankers(pd.DataFrame(candidates), model_dir=Path(model_dir))
    selected_frame = score_shadow_selector(scored, selection_budget=budget)
    selected_frame = selected_frame[selected_frame["selector_selected"]].sort_values("selection_score", ascending=False)
    selected: list[dict[str, Any]] = []
    for _, scored_row in selected_frame.iterrows():
        source_index = int(scored_row["_source_index"])
        source = source_rows.get(source_index)
        if source is None:
            continue
        key = _row_key(source)
        if not key or key in already_selected_keys:
            continue
        item = dict(source)
        bucket = str(scored_row.get("selector_bucket") or "ranker_selected")
        item["strict_selection_role"] = f"replay_aware_shadow_slice_{bucket}"
        item["selection_policy"] = "replay_aware_shadow_slice"
        item["selection_pool_type"] = "R0_leftover"
        item["replay_ranker_selection_score"] = round(_safe_float(scored_row.get("selection_score")), 6)
        item["p_non_gap_replay"] = round(_safe_float(scored_row.get("p_non_gap_replay")), 6)
        item["p_replay"] = round(_safe_float(scored_row.get("p_replay")), 6)
        item["replay_ranker_selector_bucket"] = bucket
        selected.append(item)
        already_selected_keys.add(key)
    return selected, {
        "status": "completed",
        "requested_budget": int(budget),
        "candidate_rows": int(len(candidates)),
        "selected_count": int(len(selected)),
        "model_dir": str(model_dir),
        "scoring_report": scoring_report,
        "selected_bucket_counts": Counter(str(row.get("replay_ranker_selector_bucket") or "") for row in selected),
    }


def _attach_shadow_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cluster_counts = Counter(str(row.get("signal_cluster_id") or "unknown") for row in rows)
    output: list[dict[str, Any]] = []
    for row in rows:
        replay_sortino = _safe_float(row.get("portfolio_replay_long_only_sortino"))
        replay_mean = _safe_float(row.get("portfolio_replay_long_only_net_mean"))
        turnover = _safe_float(row.get("strict_mean_one_way_turnover"))
        spread = _safe_float(row.get("strict_mean_cost_adjusted_window_spread"))
        cluster_share = _share(cluster_counts[str(row.get("signal_cluster_id") or "unknown")], len(rows))
        gap_penalty = 1.0 if _is_gap_like(row) else 0.0
        item = dict(row)
        item["is_gap_family"] = bool(_is_gap_like(row))
        item["is_cap_residual_family"] = bool(_is_cap_residual_like(row))
        item["shadow_rewards_selection_role"] = "shadow_only_not_used_for_topk_or_stratified_random_selection"
        item["shadow_replay_aware_reward"] = round(replay_mean * 10_000.0 + 0.20 * replay_sortino, 6)
        item["shadow_cluster_contribution_reward"] = round((1.0 if item.get("portfolio_replay_pass") else 0.0) - cluster_share, 6)
        item["shadow_cost_turnover_capacity_reward"] = round(spread * 10_000.0 - max(0.0, turnover - 0.75) * 2.0, 6)
        item["shadow_gap_residual_reward"] = round(-gap_penalty - 0.5 * int(_is_cap_residual_like(row)), 6)
        item["shadow_triple_barrier_auxiliary"] = round(
            (1.0 if replay_mean > 0 else -1.0) + (0.25 if replay_sortino > 0.5 else 0.0),
            6,
        )
        output.append(item)
    return output


def _cluster_share_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"max_cluster_share": 0.0, "cluster_entropy": 0.0}
    counts = Counter(str(row.get("signal_cluster_id") or "unknown") for row in rows)
    return {
        "max_cluster_share": round(max(counts.values()) / max(1, len(rows)), 6),
        "cluster_entropy": _entropy(counts.values()),
    }


def _entropy(counts: Iterable[int]) -> float:
    values = [int(value) for value in counts if int(value) > 0]
    total = sum(values)
    if total <= 0:
        return 0.0
    entropy = 0.0
    for value in values:
        share = value / total
        entropy -= share * math.log(share)
    return round(entropy, 6)


def _variant_main_row(
    *,
    variant_report: dict[str, Any],
    strict_rows: list[dict[str, Any]],
    turnover_survival_max_one_way: float,
) -> dict[str, Any]:
    variant = str(variant_report["variant"])
    strict_count = len(strict_rows)
    strict_pass = [row for row in strict_rows if bool(row.get("strict_pass_proxy"))]
    replay_pass = [row for row in strict_rows if bool(row.get("portfolio_replay_pass"))]
    cost_survive = [row for row in strict_rows if bool(row.get("cost_survives"))]
    turnover_survive = [
        row for row in strict_rows if _safe_float(row.get("strict_mean_one_way_turnover"), default=999.0) <= turnover_survival_max_one_way
    ]
    non_gap_strict = [row for row in strict_pass if not _is_gap_like(row)]
    non_gap_replay = [row for row in replay_pass if not _is_gap_like(row)]
    pass_clusters = {
        str(row.get("signal_cluster_id"))
        for row in strict_pass
        if row.get("signal_cluster_id") and row.get("signal_cluster_id") != "cluster_error"
    }
    random_rows = [row for row in strict_rows if str(row.get("strict_selection_role") or "").startswith("random_")]
    random_strict = [row for row in random_rows if bool(row.get("strict_pass_proxy"))]
    random_replay = [row for row in random_rows if bool(row.get("portfolio_replay_pass"))]
    cluster = _cluster_share_report(strict_rows)
    return {
        "variant": variant,
        "valid_candidates": int(variant_report.get("valid_candidates") or 0),
        "candidate_count": int(variant_report.get("candidate_count") or 0),
        "duplicate_rate": variant_report.get("duplicate_rate"),
        "fast_reward_mean": variant_report.get("summary", {}).get("mean_reward"),
        "strict_audited_count": strict_count,
        "strict_pass": len(strict_pass),
        "strict_pass_rate": _share(len(strict_pass), strict_count),
        "cost_survival": len(cost_survive),
        "cost_survival_rate": _share(len(cost_survive), strict_count),
        "turnover_survival": len(turnover_survive),
        "turnover_survival_rate": _share(len(turnover_survive), strict_count),
        "turnover_survival_max_one_way": float(turnover_survival_max_one_way),
        "low_corr_strict_pass": len(pass_clusters),
        "low_corr_strict_pass_definition": "unique_signal_cluster_count_among_strict_pass_rows",
        "non_gap_strict_pass": len(non_gap_strict),
        "portfolio_replay_pass": len(replay_pass),
        "non_gap_replay_pass": len(non_gap_replay),
        "max_cluster_share": cluster["max_cluster_share"],
        "gap_cluster_share": _share(sum(1 for row in strict_rows if _is_gap_like(row)), strict_count),
        "cluster_entropy": cluster["cluster_entropy"],
        "random_pass_strict": len(random_strict),
        "random_pass_replay": len(random_replay),
        "strict_yield_per_100": round(len(strict_pass) * 100.0 / max(1, int(variant_report.get("valid_candidates") or 0)), 6),
        "replay_yield_per_100": round(len(replay_pass) * 100.0 / max(1, int(variant_report.get("valid_candidates") or 0)), 6),
    }


def _decision_from_main_table(main_table: list[dict[str, Any]]) -> dict[str, Any]:
    simple = next((row for row in main_table if row["variant"] == "simple_template"), None)
    pass_reasons: list[str] = []
    hold_reasons: list[str] = []
    fail_reasons: list[str] = []
    if simple is not None:
        simple_yield = _safe_float(simple.get("replay_yield_per_100"))
        for row in main_table:
            if row["variant"] == "simple_template":
                continue
            if _safe_float(row.get("replay_yield_per_100")) > simple_yield:
                pass_reasons.append(f"{row['variant']}_replay_yield_gt_simple_template")
    for row in main_table:
        if row["variant"] != "simple_template" and int(row.get("non_gap_replay_pass") or 0) > 0:
            pass_reasons.append(f"{row['variant']}_non_gap_replay_pass_gt_0")
        if row["variant"] == "rx_diverse_beam" and _safe_float(row.get("gap_cluster_share")) < 0.35 and int(row.get("strict_pass") or 0) > 0:
            pass_reasons.append("rx_diverse_reduced_gap_share_without_strict_collapse")
        if row["variant"] in {"cem_adaptive_grammar", "ast_evolutionary_mutation", "map_elites_qd_optional"} and int(row.get("low_corr_strict_pass") or 0) > 0:
            pass_reasons.append(f"{row['variant']}_low_corr_strict_survivor")
        if row["variant"] == "unreached_space" and (
            int(row.get("portfolio_replay_pass") or 0) > 0 or int(row.get("non_gap_strict_pass") or 0) > 0
        ):
            pass_reasons.append("unreached_space_stable_contribution")
        if int(row.get("strict_pass") or 0) > 0 and int(row.get("portfolio_replay_pass") or 0) == 0:
            hold_reasons.append(f"{row['variant']}_strict_without_replay")
    advanced = [row for row in main_table if row["variant"] not in {"simple_template", "unreached_space"}]
    if not pass_reasons:
        if all(_safe_float(row.get("replay_yield_per_100")) <= _safe_float((simple or {}).get("replay_yield_per_100")) for row in advanced):
            fail_reasons.append("all_advanced_search_not_better_than_simple_template_replay_yield")
        if all(_safe_float(row.get("gap_cluster_share")) >= 0.50 for row in advanced if int(row.get("strict_audited_count") or 0) > 0):
            fail_reasons.append("advanced_search_gap_share_still_high")
    status = "PASS" if pass_reasons else "HOLD" if hold_reasons and not fail_reasons else "FAIL"
    return {
        "bakeoff_gate": status,
        "pass_reasons": sorted(set(pass_reasons)),
        "hold_reasons": sorted(set(hold_reasons)),
        "fail_reasons": sorted(set(fail_reasons)),
        "commercial_claim_allowed": False,
        "algorithm_upgrade_allowed": status == "PASS",
    }


def run_true_limit_search_bakeoff_v2(
    *,
    output_root: Path | str,
    dataset_path: Path | str,
    previous_search_roots: Iterable[Path | str] = (),
    candidate_budget: int = 32,
    target_window_count: int = 8,
    max_window: int = 40,
    beam_width: int = 24,
    max_beam_records: int = 512,
    strict_top_n_per_variant: int = 2,
    stratified_random_n_per_variant: int = 2,
    top_bottom_quantile: float = 0.02,
    recent_quarter_window_count: int = 2,
    recent_warmup_days: int = 60,
    use_fast_context: bool = True,
    strict_cost_bps: float = DEFAULT_PORTFOLIO_REPLAY_COST_BPS,
    low_corr_threshold: float = DEFAULT_LOW_CORR_THRESHOLD,
    turnover_survival_max_one_way: float = DEFAULT_TURNOVER_SURVIVAL_MAX_ONE_WAY,
    seed: str = "true_limit_search_bakeoff_v2_smoke",
    include_qd: bool = False,
    replay_ranker_model_dir: Path | str | None = None,
    replay_aware_slice_n_per_variant: int = 0,
) -> dict[str, Any]:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    dataset = Path(dataset_path)
    previous_roots = [Path(root_path) for root_path in previous_search_roots]
    experiment_id = f"true_limit_search_bakeoff_v2_{seed}"

    ledgers = _build_variant_ledgers(
        root=root,
        dataset=dataset,
        previous_search_roots=previous_roots,
        candidate_budget=candidate_budget,
        target_window_count=target_window_count,
        max_window=max_window,
        beam_width=beam_width,
        max_beam_records=max_beam_records,
        top_bottom_quantile=top_bottom_quantile,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
        use_fast_context=use_fast_context,
        seed=seed,
        include_qd=include_qd,
    )
    variant_reports = _validate_variant_ledgers(
        root=root,
        dataset=dataset,
        variants=ledgers,
        candidate_budget=candidate_budget,
        top_bottom_quantile=top_bottom_quantile,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
        use_fast_context=use_fast_context,
    )
    write_json_artifact(root / "stage1_variant_reports.json", {"variants": variant_reports})

    all_fast_rows: list[dict[str, Any]] = []
    r0_strict_inputs: list[dict[str, Any]] = []
    replay_aware_inputs: list[dict[str, Any]] = []
    replay_aware_reports: list[dict[str, Any]] = []
    for variant_report in variant_reports:
        fast_rows = _fast_rows_from_variant_report(variant_report)
        all_fast_rows.extend(fast_rows)
        selected = _stratified_strict_inputs(
            fast_rows,
            top_n=strict_top_n_per_variant,
            random_n=stratified_random_n_per_variant,
            seed=f"{seed}::{variant_report['variant']}",
        )
        r0_strict_inputs.extend(selected)
        seen_keys = {_row_key(row) for row in selected if _row_key(row)}
        variant_replay_aware, variant_replay_report = _replay_aware_strict_inputs(
            fast_rows,
            model_dir=replay_ranker_model_dir,
            n_per_variant=replay_aware_slice_n_per_variant,
            seed=f"{seed}::{variant_report['variant']}::replay_aware",
            already_selected_keys=seen_keys,
        )
        variant_replay_report = {"variant": variant_report["variant"], **variant_replay_report}
        replay_aware_reports.append(variant_replay_report)
        replay_aware_inputs.extend(variant_replay_aware)
    strict_inputs = r0_strict_inputs + replay_aware_inputs
    write_json_artifact(
        root / "strict_selection_inputs.json",
        {
            "selected": strict_inputs,
            "r0_control_selected": r0_strict_inputs,
            "replay_aware_shadow_selected": replay_aware_inputs,
            "replay_aware_selector_reports": replay_aware_reports,
            "contract": {
                "r0_control_remains_main_decision": True,
                "replay_aware_slice_is_capped_shadow_replay": bool(replay_aware_slice_n_per_variant),
                "replay_aware_slice_n_per_variant": int(replay_aware_slice_n_per_variant),
            },
        },
    )

    strict_rows = _strict_audit_selected_fast_rows(
        strict_inputs,
        output_root=root / "strict_by_variant",
        dataset_path=dataset,
        top_bottom_quantile=top_bottom_quantile,
        cost_bps=strict_cost_bps,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    strict_rows, replay_report = _attach_portfolio_replay(
        strict_rows,
        dataset_path=dataset,
        top_bottom_quantile=top_bottom_quantile,
        cost_bps=strict_cost_bps,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    strict_rows, cluster_report = _attach_signal_clusters(
        strict_rows,
        dataset_path=dataset,
        threshold=low_corr_threshold,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    strict_rows = _attach_shadow_metrics(strict_rows)
    write_json_artifact(root / "strict_by_variant_rows.json", {"strict_rows": strict_rows})

    control_strict_rows = [row for row in strict_rows if str(row.get("selection_policy") or "r0_control") == "r0_control"]
    replay_aware_strict_rows = [row for row in strict_rows if str(row.get("selection_policy") or "") == "replay_aware_shadow_slice"]
    main_table = [
        _variant_main_row(
            variant_report=variant_report,
            strict_rows=[row for row in control_strict_rows if row.get("proof_variant") == variant_report["variant"]],
            turnover_survival_max_one_way=turnover_survival_max_one_way,
        )
        for variant_report in variant_reports
    ]
    all_audited_main_table = [
        _variant_main_row(
            variant_report=variant_report,
            strict_rows=[row for row in strict_rows if row.get("proof_variant") == variant_report["variant"]],
            turnover_survival_max_one_way=turnover_survival_max_one_way,
        )
        for variant_report in variant_reports
    ]
    replay_aware_slice_table = [
        _variant_main_row(
            variant_report=variant_report,
            strict_rows=[row for row in replay_aware_strict_rows if row.get("proof_variant") == variant_report["variant"]],
            turnover_survival_max_one_way=turnover_survival_max_one_way,
        )
        for variant_report in variant_reports
    ]
    decision = _decision_from_main_table(main_table)
    report = {
        "proof_suite_version": TRUE_LIMIT_SEARCH_BAKEOFF_V2_VERSION,
        "experiment_id": experiment_id,
        "created_at": utc_now_iso(),
        "objective": "compare_search_lanes_by_replay_useful_low_corr_non_gap_cost_survived_alpha_not_fast_reward",
        "status": "completed",
        "dataset_path": str(dataset),
        "dataset_role": dataset_role_for_path(dataset),
        "output_root": str(root),
        "previous_search_roots": [str(item) for item in previous_roots],
        "quarantine": {
            "old_9_8_limit_results": "QUARANTINED_FOR_TRUE_LIMIT_REVIEW",
            "old_ucb_memory": "NOT_USED_IN_THIS_BAKEOFF",
            "original_ucb": ORIGINAL_UCB_STATE,
        },
        "fixed_contract": {
            "evaluator": "TDXGP true-limit preferred",
            "limit_status_preferred_source": TDXGP_LIMIT_STATUS_SOURCE,
            "fallback_limit_flags": "only_if_tdxgp_status_unavailable",
            "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
            "execution_lag_days": 1,
            "feature_lag_days": 0,
            "cost_bps": float(strict_cost_bps),
            "top_bottom_quantile": float(top_bottom_quantile),
            "reward_for_selection": "R0_current_true_limit",
            "shadow_rewards_do_not_control_selection": True,
        },
        "parameters": {
            "candidate_budget": int(candidate_budget),
            "target_window_count": int(target_window_count),
            "max_window": int(max_window),
            "beam_width": int(beam_width),
            "max_beam_records": int(max_beam_records),
            "strict_top_n_per_variant": int(strict_top_n_per_variant),
            "stratified_random_n_per_variant": int(stratified_random_n_per_variant),
            "recent_quarter_window_count": int(recent_quarter_window_count),
            "recent_warmup_days": int(recent_warmup_days),
            "low_corr_threshold": float(low_corr_threshold),
            "turnover_survival_max_one_way": float(turnover_survival_max_one_way),
            "seed": str(seed),
            "include_qd": bool(include_qd),
            "replay_ranker_model_dir": str(replay_ranker_model_dir) if replay_ranker_model_dir is not None else None,
            "replay_aware_slice_n_per_variant": int(replay_aware_slice_n_per_variant),
        },
        "search_lanes": list(TRUE_LIMIT_BAKEOFF_VARIANTS) + (["map_elites_qd_optional"] if include_qd else []),
        "variant_stage1_reports": variant_reports,
        "main_table": main_table,
        "main_table_scope": "r0_control_only",
        "all_audited_main_table": all_audited_main_table,
        "replay_aware_slice_table": replay_aware_slice_table,
        "replay_aware_selector_contract": {
            "status": "enabled" if int(replay_aware_slice_n_per_variant) > 0 else "disabled",
            "control_decision_uses": "main_table_r0_control_only",
            "slice_policy": "capped_shadow_replay_extra_strict_inputs",
            "model_dir": str(replay_ranker_model_dir) if replay_ranker_model_dir is not None else None,
            "slice_n_per_variant": int(replay_aware_slice_n_per_variant),
            "pure_rl_controls_main_search": False,
        },
        "replay_aware_selector_reports": replay_aware_reports,
        "portfolio_replay_report": replay_report,
        "signal_cluster_report": cluster_report,
        "shadow_reward_contract": {
            "recorded_only": True,
            "shadow_metrics": [
                "shadow_replay_aware_reward",
                "shadow_cluster_contribution_reward",
                "shadow_cost_turnover_capacity_reward",
                "shadow_gap_residual_reward",
                "shadow_triple_barrier_auxiliary",
            ],
        },
        "decision": decision,
        "reproducibility": {
            "input_file": str(dataset),
            "commands": "python -m our_system_phase2.runtime.stock_pit_true_limit_search_bakeoff_v2 ...",
            "outputs": [
                "true_limit_search_bakeoff_v2_report.json",
                "stage1_variant_reports.json",
                "strict_selection_inputs.json",
                "strict_by_variant_rows.json",
                "replay_aware_slice_table in true_limit_search_bakeoff_v2_report.json",
                "variants/*/candidate_ledger.json",
                "variants/*/stage1_validation_report.json",
            ],
            "result_claim": "research_bakeoff_only_not_commercial_proof",
        },
    }
    write_json_artifact(root / "true_limit_search_bakeoff_v2_report.json", report)
    return report

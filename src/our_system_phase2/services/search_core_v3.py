from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

import numpy as np
import pandas as pd

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH
from our_system_phase2.services.search_core_v2 import dedupe_scale_twins


SEARCH_CORE_V3_VERSION = "phase2-search-core-v3-regime-specialist-2026-04-26"
DEFAULT_SPECIALIST_TOP_FRACTION = 0.25
DEFAULT_MIN_SPECIALIST_WINDOWS = 4


def _read_report(value: Path | str | dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    return json.loads(Path(value).read_text(encoding="utf-8"))


def _metric(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(numeric):
        return default
    return numeric


def _window_score(window: dict[str, Any]) -> float:
    rank_ic = _metric(window.get("mean_rank_ic"))
    sortino = max(-3.0, min(3.0, _metric(window.get("long_short_sortino")))) / 3.0
    hit_rate = _metric(window.get("rank_ic_hit_rate"), default=0.5) - 0.5
    return round((0.58 * rank_ic) + (0.26 * sortino) + (0.16 * hit_rate), 6)


def candidate_regime_profile(
    candidate: dict[str, Any],
    *,
    top_fraction: float = DEFAULT_SPECIALIST_TOP_FRACTION,
    min_specialist_windows: int = DEFAULT_MIN_SPECIALIST_WINDOWS,
) -> dict[str, Any]:
    windows = [dict(window) for window in candidate.get("windows") or candidate.get("recent_windows") or []]
    scored = []
    for window in windows:
        scored.append(
            {
                "window": window.get("window"),
                "score": _window_score(window),
                "mean_rank_ic": _metric(window.get("mean_rank_ic")),
                "long_short_sortino": _metric(window.get("long_short_sortino")),
                "rank_ic_hit_rate": _metric(window.get("rank_ic_hit_rate"), default=0.5),
                "trading_day_count": int(_metric(window.get("trading_day_count"))),
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    window_count = len(scored)
    top_count = max(min_specialist_windows, int(math.ceil(window_count * top_fraction))) if window_count else 0
    top_count = min(top_count, window_count)
    top = scored[:top_count]
    bottom = scored[-top_count:] if top_count else []
    all_scores = [item["score"] for item in scored]
    top_scores = [item["score"] for item in top]
    bottom_scores = [item["score"] for item in bottom]
    mean_score = mean(all_scores) if all_scores else 0.0
    top_mean_score = mean(top_scores) if top_scores else 0.0
    bottom_mean_score = mean(bottom_scores) if bottom_scores else 0.0
    score_std = pstdev(all_scores) if len(all_scores) > 1 else 0.0
    positive_ratio = sum(1 for item in scored if item["mean_rank_ic"] > 0) / window_count if window_count else 0.0
    specialist_lift = top_mean_score - mean_score
    fragility = score_std + max(0.0, -bottom_mean_score)
    coverage = top_count / window_count if window_count else 0.0
    if window_count < min_specialist_windows:
        edge_mode = "insufficient_windows"
    elif positive_ratio >= 0.65 and mean_score > 0.02:
        edge_mode = "broad_edge"
    elif top_mean_score > 0.08 and specialist_lift > 0.05:
        edge_mode = "regime_specialist_edge"
    elif top_mean_score > 0.04:
        edge_mode = "weak_regime_specialist"
    else:
        edge_mode = "watch"
    specialist_score = round(top_mean_score + (0.35 * specialist_lift) - (0.10 * max(0.0, fragility - 0.25)), 6)
    broad_score = round(mean_score + (0.05 * positive_ratio) - (0.08 * score_std), 6)
    return {
        "candidate_id": candidate.get("candidate_id"),
        "primitive_family": candidate.get("primitive_family"),
        "expression": candidate.get("expression"),
        "edge_mode": edge_mode,
        "window_count": window_count,
        "specialist_window_count": top_count,
        "specialist_coverage": round(coverage, 6),
        "positive_rank_ic_window_ratio": round(positive_ratio, 6),
        "mean_window_score": round(mean_score, 6),
        "top_window_mean_score": round(top_mean_score, 6),
        "bottom_window_mean_score": round(bottom_mean_score, 6),
        "specialist_lift": round(specialist_lift, 6),
        "score_std": round(score_std, 6),
        "fragility_score": round(fragility, 6),
        "specialist_score": specialist_score,
        "broad_score": broad_score,
        "activation_windows": top,
    }


def _profiles_by_family(profiles: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for profile in profiles:
        family = str(profile.get("primitive_family") or "unknown")
        grouped.setdefault(family, []).append(profile)
    return grouped


def _family_allocation(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = _profiles_by_family(profiles)
    total = sum(len(items) for items in grouped.values()) or 1
    rows = []
    for family, items in grouped.items():
        best_specialist = max(items, key=lambda item: item["specialist_score"])
        best_broad = max(items, key=lambda item: item["broad_score"])
        specialist_count = sum(1 for item in items if item["edge_mode"] in {"regime_specialist_edge", "weak_regime_specialist"})
        broad_count = sum(1 for item in items if item["edge_mode"] == "broad_edge")
        uncertainty_bonus = math.sqrt(math.log(total + 1) / (len(items) + 1))
        qd_bonus = 0.04 if specialist_count and broad_count == 0 else 0.02 if specialist_count else 0.0
        allocation_score = round(
            max(best_specialist["specialist_score"], best_broad["broad_score"])
            + (0.18 * uncertainty_bonus)
            + qd_bonus,
            6,
        )
        if specialist_count:
            next_action = "specialist_gate_search"
        elif broad_count:
            next_action = "broad_audit_search"
        else:
            next_action = "low_budget_watch"
        rows.append(
            {
                "primitive_family": family,
                "allocation_score": allocation_score,
                "next_action": next_action,
                "candidate_count": len(items),
                "specialist_candidate_count": specialist_count,
                "broad_candidate_count": broad_count,
                "best_specialist_candidate_id": best_specialist.get("candidate_id"),
                "best_specialist_score": best_specialist["specialist_score"],
                "best_broad_candidate_id": best_broad.get("candidate_id"),
                "best_broad_score": best_broad["broad_score"],
                "uncertainty_bonus": round(uncertainty_bonus, 6),
                "quality_diversity_bonus": qd_bonus,
            }
        )
    return sorted(rows, key=lambda item: item["allocation_score"], reverse=True)


def _activation_map(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for profile in sorted(profiles, key=lambda item: item["specialist_score"], reverse=True):
        if profile["edge_mode"] not in {"regime_specialist_edge", "weak_regime_specialist", "broad_edge"}:
            continue
        rows.append(
            {
                "candidate_id": profile["candidate_id"],
                "primitive_family": profile["primitive_family"],
                "edge_mode": profile["edge_mode"],
                "specialist_score": profile["specialist_score"],
                "broad_score": profile["broad_score"],
                "activation_windows": [
                    {
                        "window": item["window"],
                        "score": item["score"],
                        "mean_rank_ic": item["mean_rank_ic"],
                        "long_short_sortino": item["long_short_sortino"],
                    }
                    for item in profile["activation_windows"]
                ],
                "gate_features_to_learn": [
                    "market_return_state",
                    "cross_sectional_volatility_state",
                    "liquidity_turnover_state",
                    "breadth_state",
                ],
            }
        )
    return rows


def build_phase2_search_core_v3_plan(
    *,
    full_history_report: Path | str | dict[str, Any],
    fast_screen_report: Path | str | dict[str, Any] | None = None,
    top_fraction: float = DEFAULT_SPECIALIST_TOP_FRACTION,
    min_specialist_windows: int = DEFAULT_MIN_SPECIALIST_WINDOWS,
) -> dict[str, Any]:
    full = _read_report(full_history_report) or {}
    fast = _read_report(fast_screen_report) or {}
    full_candidates, full_duplicates = dedupe_scale_twins(list(full.get("evaluations", [])))
    fast_candidates, fast_duplicates = dedupe_scale_twins(list(fast.get("evaluations", []))) if fast else ([], [])
    profiles = [
        candidate_regime_profile(
            candidate,
            top_fraction=top_fraction,
            min_specialist_windows=min_specialist_windows,
        )
        for candidate in full_candidates
    ]
    profiles.sort(key=lambda item: max(item["specialist_score"], item["broad_score"]), reverse=True)
    specialist_candidates = [item for item in profiles if item["edge_mode"] in {"regime_specialist_edge", "weak_regime_specialist"}]
    broad_candidates = [item for item in profiles if item["edge_mode"] == "broad_edge"]
    watch_candidates = [item for item in profiles if item["edge_mode"] not in {"regime_specialist_edge", "weak_regime_specialist", "broad_edge"}]
    return {
        "run_id": "phase2-search-core-v3-regime-specialist-plan",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V3_VERSION,
        "scope": "conditional_edge_search_not_cross_regime_stability_maximization",
        "not_claiming_tradable_alpha": True,
        "paper_inspired_principles": [
            "hierarchical_quality_diversity_search",
            "multi_dimension_evaluation_beyond_single_ic",
            "dynamic_factor_combination_and_non_fixed_weights",
            "grammar_or_memory_guided_redundancy_reduction",
        ],
        "objective_correction": {
            "old_bias_to_avoid": "treating cross_regime_stability_as_the_only_good_alpha_shape",
            "new_objective": "find broad edges and identifiable regime-specialist edges, then learn gates for conditional deployment",
            "stability_role": "diagnostic_for_fragility_not_primary_objective",
        },
        "input_reports": {
            "full_history": full.get("ledger_path") or "provided_dict",
            "fast_screen": fast.get("ledger_path") if fast else None,
        },
        "candidate_counts": {
            "full_after_scale_dedupe": len(full_candidates),
            "fast_after_scale_dedupe": len(fast_candidates),
            "scale_twin_duplicate_count": len(full_duplicates) + len(fast_duplicates),
            "specialist_candidate_count": len(specialist_candidates),
            "broad_candidate_count": len(broad_candidates),
            "watch_candidate_count": len(watch_candidates),
        },
        "family_allocation": _family_allocation(profiles),
        "candidate_regime_profiles": profiles,
        "activation_map": _activation_map(profiles),
        "next_computational_tasks": [
            "derive_market_state_features_for_activation_windows",
            "train_lightweight_gate_to_predict_candidate_activation",
            "allocate_search_budget_with_family_ucb_plus_quality_diversity_bonus",
            "expand_formula_grammar_near_specialist_families_not_only_broad_stable_families",
            "evaluate_conditional_utility_after_gate_costs",
        ],
        "decision": "CONTINUE_PHASE2_SEARCH_CORE_V3_CONDITIONAL_EDGE_SEARCH",
    }


def _quarter_label(date: pd.Timestamp) -> str:
    quarter = ((int(date.month) - 1) // 3) + 1
    return f"{int(date.year)}Q{quarter}"


def _market_state_by_quarter(path: Path | str = DEFAULT_REAL_MARKET_DATASET_PATH) -> dict[str, dict[str, Any]]:
    frame = pd.read_csv(path, usecols=["date", "close", "amount", "volume", "code"])
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date", "close", "code"]).copy()
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
    frame = frame.sort_values(["code", "date"])
    frame["ret_1d"] = frame.groupby("code", sort=False)["close"].pct_change()
    frame["window"] = frame["date"].map(_quarter_label)
    daily = (
        frame.groupby(["window", "date"], sort=True)
        .agg(
            equal_weight_return=("ret_1d", "mean"),
            cross_sectional_volatility=("ret_1d", "std"),
            breadth=("ret_1d", lambda item: float(np.mean(pd.to_numeric(item, errors="coerce") > 0))),
            median_amount=("amount", "median"),
            median_volume=("volume", "median"),
            instrument_count=("code", "nunique"),
        )
        .reset_index()
    )
    states: dict[str, dict[str, Any]] = {}
    for window, group in daily.groupby("window", sort=True):
        states[str(window)] = {
            "window": str(window),
            "trading_day_count": int(len(group)),
            "market_return_state": round(float(pd.to_numeric(group["equal_weight_return"], errors="coerce").sum()), 6),
            "cross_sectional_volatility_state": round(
                float(pd.to_numeric(group["cross_sectional_volatility"], errors="coerce").mean()), 6
            ),
            "breadth_state": round(float(pd.to_numeric(group["breadth"], errors="coerce").mean()), 6),
            "liquidity_amount_state": round(float(np.log1p(pd.to_numeric(group["median_amount"], errors="coerce").mean())), 6),
            "liquidity_volume_state": round(float(np.log1p(pd.to_numeric(group["median_volume"], errors="coerce").mean())), 6),
            "mean_instrument_count": round(float(pd.to_numeric(group["instrument_count"], errors="coerce").mean()), 3),
        }
    return states


def build_phase2_activation_gate_dataset(
    *,
    v3_plan: Path | str | dict[str, Any],
    market_panel_path: Path | str = DEFAULT_REAL_MARKET_DATASET_PATH,
) -> dict[str, Any]:
    plan = _read_report(v3_plan) or {}
    market_states = _market_state_by_quarter(market_panel_path)
    rows: list[dict[str, Any]] = []
    for activation in plan.get("activation_map", []):
        active_windows = {str(item.get("window")) for item in activation.get("activation_windows", [])}
        candidate_id = str(activation.get("candidate_id"))
        for window, state in market_states.items():
            rows.append(
                {
                    "candidate_id": candidate_id,
                    "primitive_family": activation.get("primitive_family"),
                    "edge_mode": activation.get("edge_mode"),
                    "window": window,
                    "activated": window in active_windows,
                    **state,
                }
            )
    activated = [row for row in rows if row["activated"]]
    return {
        "run_id": "phase2-search-core-v3-activation-gate-dataset",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V3_VERSION,
        "scope": "market_state_activation_dataset_for_conditional_edge_gating",
        "market_panel_path": str(market_panel_path),
        "candidate_count": len({row["candidate_id"] for row in rows}),
        "window_count": len(market_states),
        "row_count": len(rows),
        "activated_row_count": len(activated),
        "feature_columns": [
            "market_return_state",
            "cross_sectional_volatility_state",
            "breadth_state",
            "liquidity_amount_state",
            "liquidity_volume_state",
            "mean_instrument_count",
        ],
        "target_column": "activated",
        "rows": rows,
    }

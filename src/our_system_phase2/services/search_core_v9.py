from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.search_core_v8 import (
    extract_expression_window,
    rank_validation_canonical_expression,
)


SEARCH_CORE_V9_VERSION = "phase2-search-core-v9-rank-quotient-continuous-posterior-2026-04-26"


def _read_report(value: Path | str | dict[str, Any]) -> dict[str, Any]:
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


def _softmax(values: np.ndarray, temperature: float = 0.012) -> np.ndarray:
    if values.size == 0:
        return values
    shifted = values - values.max()
    weights = np.exp(shifted / max(temperature, 1e-9))
    denom = float(weights.sum())
    if denom <= 0:
        return np.full(values.shape, 1.0 / len(values), dtype=float)
    return weights / denom


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
    order = np.argsort(values)
    values = values[order]
    weights = weights[order]
    cumulative = np.cumsum(weights)
    if cumulative[-1] <= 0:
        return float(np.quantile(values, quantile))
    cumulative = cumulative / cumulative[-1]
    index = int(np.searchsorted(cumulative, quantile, side="left"))
    return float(values[min(index, len(values) - 1)])


def _objective_value(evaluation: dict[str, Any]) -> float:
    mean_ic = _metric(evaluation.get("mean_window_rank_ic"))
    recent_ic = _metric(evaluation.get("recent_mean_rank_ic"))
    sortino = max(-2.0, min(2.0, _metric(evaluation.get("mean_window_sortino"))))
    pass_bonus = 0.004 if evaluation.get("passes_real_market_smoke") else 0.0
    return mean_ic + (0.0025 * sortino) + (0.15 * max(recent_ic, 0.0)) + pass_bonus


def _base_expression(family: str, window: int) -> str:
    if family == "a5_momentum":
        return f"Mom($close,{window})"
    if family == "a5_gap":
        return f"Div(Sub($open,Delay($close,{window})),Delay($close,{window}))"
    if family == "a5_volatility":
        return f"Std($ret,{window})"
    raise ValueError(f"unsupported_family:{family}")


def _rank_expression(family: str, window: int) -> str:
    return f"CSRank({_base_expression(family, window)})"


def _collapse_rank_quotient(evaluations: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: dict[str, dict[str, Any]] = {}
    dropped: list[dict[str, Any]] = []
    for evaluation in evaluations:
        canonical = rank_validation_canonical_expression(str(evaluation.get("expression", "")))
        enriched = {
            **evaluation,
            "canonical_rank_validation_expression": canonical,
            "quotient_objective_value": round(_objective_value(evaluation), 6),
        }
        current = kept.get(canonical)
        if current is None:
            kept[canonical] = enriched
            continue
        current_value = _metric(current.get("quotient_objective_value"))
        next_value = _metric(enriched.get("quotient_objective_value"))
        if next_value > current_value:
            dropped.append(
                {
                    "candidate_id": current.get("candidate_id"),
                    "expression": current.get("expression"),
                    "kept_candidate_id": enriched.get("candidate_id"),
                    "canonical_rank_validation_expression": canonical,
                }
            )
            kept[canonical] = enriched
        else:
            dropped.append(
                {
                    "candidate_id": enriched.get("candidate_id"),
                    "expression": enriched.get("expression"),
                    "kept_candidate_id": current.get("candidate_id"),
                    "canonical_rank_validation_expression": canonical,
                }
            )
    return list(kept.values()), dropped


def infer_rank_quotient_posterior(
    *,
    full_history_report: Path | str | dict[str, Any],
    fast_screen_report: Path | str | dict[str, Any] | None = None,
) -> dict[str, Any]:
    full = _read_report(full_history_report)
    quotient_rows, dropped = _collapse_rank_quotient(list(full.get("evaluations", [])))
    fast_quotient_rows: list[dict[str, Any]] = []
    fast_dropped: list[dict[str, Any]] = []
    if fast_screen_report is not None:
        fast = _read_report(fast_screen_report)
        fast_quotient_rows, fast_dropped = _collapse_rank_quotient(list(fast.get("evaluations", [])))

    families: list[dict[str, Any]] = []
    for family in sorted({str(row.get("primitive_family")) for row in quotient_rows if row.get("primitive_family")}):
        family_rows = [row for row in quotient_rows if row.get("primitive_family") == family]
        windows = np.array([float(row.get("window") or extract_expression_window(str(row.get("expression", ""))) or 0) for row in family_rows])
        values = np.array([_metric(row.get("quotient_objective_value")) for row in family_rows], dtype=float)
        valid = windows > 0
        windows = windows[valid]
        values = values[valid]
        if values.size == 0:
            continue
        weights = _softmax(values)
        mean = float(np.sum(windows * weights))
        variance = float(np.sum(weights * np.square(windows - mean)))
        best = max(family_rows, key=lambda row: _metric(row.get("quotient_objective_value")))
        families.append(
            {
                "primitive_family": family,
                "quotient_sample_count": len(family_rows),
                "passed_count": sum(1 for row in family_rows if row.get("passes_real_market_smoke")),
                "weighted_window_mean": round(mean, 6),
                "weighted_window_std": round(math.sqrt(max(variance, 1e-9)), 6),
                "weighted_window_q20": round(_weighted_quantile(windows, weights, 0.20), 6),
                "weighted_window_q50": round(_weighted_quantile(windows, weights, 0.50), 6),
                "weighted_window_q80": round(_weighted_quantile(windows, weights, 0.80), 6),
                "best_candidate_id": best.get("candidate_id"),
                "best_expression": best.get("expression"),
                "best_window": best.get("window") or extract_expression_window(str(best.get("expression", ""))),
                "best_quotient_objective_value": best.get("quotient_objective_value"),
                "best_mean_window_rank_ic": best.get("mean_window_rank_ic"),
                "best_mean_window_sortino": best.get("mean_window_sortino"),
            }
        )
    families.sort(key=lambda item: _metric(item.get("best_quotient_objective_value")), reverse=True)

    recent_shadow = []
    for row in fast_quotient_rows:
        if row.get("fast_screen_decision") != "needs_full_history_review":
            continue
        family = str(row.get("primitive_family"))
        matching_full = [
            item for item in quotient_rows if item.get("canonical_rank_validation_expression") == row["canonical_rank_validation_expression"]
        ]
        full_passed = bool(matching_full and matching_full[0].get("passes_real_market_smoke"))
        if full_passed:
            continue
        recent_shadow.append(
            {
                "candidate_id": row.get("candidate_id"),
                "primitive_family": family,
                "expression": row.get("expression"),
                "window": row.get("window") or extract_expression_window(str(row.get("expression", ""))),
                "recent_mean_rank_ic": row.get("recent_mean_rank_ic"),
                "recent_positive_rank_ic_ratio": row.get("recent_positive_rank_ic_ratio"),
                "fast_screen_decision": row.get("fast_screen_decision"),
                "shadow_reason": "recent_positive_but_not_full_history_passed",
            }
        )
    recent_shadow.sort(key=lambda item: _metric(item.get("recent_mean_rank_ic")), reverse=True)

    return {
        "run_id": "phase2-search-core-v9-rank-quotient-posterior",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V9_VERSION,
        "source_full_history_run_id": full.get("source_run_id"),
        "full_history_evaluation_count": len(full.get("evaluations", [])),
        "full_history_quotient_count": len(quotient_rows),
        "full_history_rank_duplicate_count": len(dropped),
        "fast_screen_quotient_count": len(fast_quotient_rows),
        "fast_screen_rank_duplicate_count": len(fast_dropped),
        "family_posteriors": families,
        "recent_shadow_candidates": recent_shadow[:12],
    }


def _posterior_windows(family: dict[str, Any], *, limit: int = 6) -> list[int]:
    mean = float(family["weighted_window_mean"])
    std = max(1.0, float(family["weighted_window_std"]))
    seeds = {
        int(round(mean)),
        int(round(mean - std)),
        int(round(mean + std)),
        int(round(float(family["weighted_window_q20"]))),
        int(round(float(family["weighted_window_q50"]))),
        int(round(float(family["weighted_window_q80"]))),
        int(family["best_window"]),
    }
    for z in (-0.5, 0.5, 1.25):
        seeds.add(int(round(mean + (z * std))))
    return sorted(window for window in seeds if 1 <= window <= 252)[:limit]


def _family_mass(families: list[dict[str, Any]]) -> dict[str, float]:
    values = np.array([_metric(item.get("best_quotient_objective_value")) for item in families], dtype=float)
    weights = _softmax(values, temperature=0.01)
    return {str(item["primitive_family"]): round(float(weight), 6) for item, weight in zip(families, weights)}


def _beta_weight_points(mean: float, concentration: float = 18.0) -> list[float]:
    alpha = 1.0 + (mean * concentration)
    beta = 1.0 + ((1.0 - mean) * concentration)
    variance = (alpha * beta) / (((alpha + beta) ** 2) * (alpha + beta + 1.0))
    std = math.sqrt(max(variance, 1e-9))
    dist = NormalDist(mu=mean, sigma=std)
    points = {mean, dist.inv_cdf(0.2), dist.inv_cdf(0.5), dist.inv_cdf(0.8)}
    return sorted(round(min(0.9, max(0.1, point)), 3) for point in points)


def build_v9_continuous_proposal_ledger(
    *,
    full_history_report: Path | str | dict[str, Any],
    fast_screen_report: Path | str | dict[str, Any] | None = None,
    max_windows_per_family: int = 6,
) -> dict[str, Any]:
    posterior = infer_rank_quotient_posterior(
        full_history_report=full_history_report,
        fast_screen_report=fast_screen_report,
    )
    masses = _family_mass(posterior["family_posteriors"])
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    broad_families = [
        family for family in posterior["family_posteriors"] if family["primitive_family"] in {"a5_momentum", "a5_gap"}
    ]
    for family in broad_families:
        family_name = str(family["primitive_family"])
        for window in _posterior_windows(family, limit=max_windows_per_family):
            expression = _rank_expression(family_name, window)
            canonical = rank_validation_canonical_expression(expression)
            if canonical in seen:
                continue
            seen.add(canonical)
            records.append(
                {
                    "candidate_id": f"v9-continuous-{len(records) + 1:04d}",
                    "expression": expression,
                    "retained": True,
                    "source_mode": "search_core_v9_rank_quotient_continuous_posterior",
                    "frontier_lane": "search_core_v9_quotient_broad",
                    "archive_cell": f"v9_{family_name}_quotient",
                    "primitive_family": family_name,
                    "proposal_kind": "rank_quotient_posterior_window",
                    "window": window,
                    "posterior_mean": family["weighted_window_mean"],
                    "posterior_std": family["weighted_window_std"],
                    "family_mass": masses.get(family_name),
                    "canonical_rank_validation_expression": canonical,
                }
            )

    by_family = {str(family["primitive_family"]): family for family in broad_families}
    if {"a5_momentum", "a5_gap"}.issubset(by_family):
        momentum_windows = _posterior_windows(by_family["a5_momentum"], limit=3)
        gap_windows = _posterior_windows(by_family["a5_gap"], limit=3)
        momentum_mass = masses.get("a5_momentum", 0.5)
        for weight in _beta_weight_points(momentum_mass):
            gap_weight = round(1.0 - weight, 3)
            for momentum_window in momentum_windows:
                for gap_window in gap_windows:
                    expression = (
                        "CSRank(Add("
                        f"Mul({weight},ZScore({_base_expression('a5_momentum', momentum_window)})),"
                        f"Mul({gap_weight},ZScore({_base_expression('a5_gap', gap_window)}))"
                        "))"
                    )
                    canonical = rank_validation_canonical_expression(expression)
                    if canonical in seen:
                        continue
                    seen.add(canonical)
                    records.append(
                        {
                            "candidate_id": f"v9-continuous-{len(records) + 1:04d}",
                            "expression": expression,
                            "retained": True,
                            "source_mode": "search_core_v9_rank_quotient_continuous_posterior",
                            "frontier_lane": "search_core_v9_continuous_mix",
                            "archive_cell": "v9_momentum_gap_continuous_mix",
                            "primitive_family": "a5_momentum+a5_gap",
                            "proposal_kind": "posterior_continuous_mix_weight",
                            "momentum_window": momentum_window,
                            "gap_window": gap_window,
                            "momentum_weight": weight,
                            "gap_weight": gap_weight,
                            "family_mass": momentum_mass,
                            "canonical_rank_validation_expression": canonical,
                        }
                    )

    for shadow in posterior["recent_shadow_candidates"][:6]:
        family_name = str(shadow["primitive_family"])
        if family_name != "a5_volatility":
            continue
        window = int(shadow["window"])
        expression = _rank_expression(family_name, window)
        canonical = rank_validation_canonical_expression(expression)
        if canonical in seen:
            continue
        seen.add(canonical)
        records.append(
            {
                "candidate_id": f"v9-continuous-{len(records) + 1:04d}",
                "expression": expression,
                "retained": True,
                "source_mode": "search_core_v9_rank_quotient_continuous_posterior",
                "frontier_lane": "search_core_v9_recent_regime_shadow",
                "archive_cell": "v9_volatility_recent_shadow",
                "primitive_family": family_name,
                "proposal_kind": "recent_shadow_rank_quotient",
                "window": window,
                "recent_mean_rank_ic": shadow["recent_mean_rank_ic"],
                "canonical_rank_validation_expression": canonical,
            }
        )

    return {
        "run_id": "phase2-search-core-v9-continuous-proposal-ledger",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V9_VERSION,
        "scope": "rank_quotient_continuous_formula_generation",
        "posterior_report": posterior,
        "family_mass": masses,
        "record_count": len(records),
        "records": records,
    }

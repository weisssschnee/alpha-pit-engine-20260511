from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np

from our_system_phase2.domain.models import utc_now_iso


SEARCH_CORE_V8_VERSION = "phase2-search-core-v8-natural-parameter-posterior-2026-04-26"


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


def extract_expression_window(expression: str) -> int | None:
    matches = re.findall(r",\s*(\d+)\)", expression)
    if not matches:
        return None
    return int(matches[-1])


def _softmax(values: np.ndarray, temperature: float = 0.035) -> np.ndarray:
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
    sorted_values = values[order]
    sorted_weights = weights[order]
    cumulative = np.cumsum(sorted_weights)
    if cumulative[-1] <= 0:
        return float(np.quantile(values, quantile))
    cumulative = cumulative / cumulative[-1]
    index = int(np.searchsorted(cumulative, quantile, side="left"))
    return float(sorted_values[min(index, len(sorted_values) - 1)])


def _family_expression(family: str, window: int) -> str | None:
    if family == "a5_volatility":
        return f"CSRank(Std($ret,{window}))"
    if family == "a5_momentum":
        return f"CSRank(Mom($close,{window}))"
    if family == "a5_gap":
        return f"CSRank(Div(Sub($open,Delay($close,{window})),Delay($close,{window})))"
    if family == "a5_dev_ma":
        return f"CSRank(Div(Sub($close,Mean($close,{window})),Mean($close,{window})))"
    if family == "a5_amihud":
        return f"Neg(CSRank(Mean(Div(Abs($ret),$amount),{window})))"
    return None


def rank_validation_canonical_expression(expression: str) -> str:
    expression = expression.strip()
    call = re.match(r"^(CSRank|Rank|ZScore)\((.*)\)$", expression, flags=re.IGNORECASE)
    if call is None:
        return expression
    return f"RankEquivalent({call.group(2).strip()})"


def _structural_variants(family: str, window: int, posterior_mean: float) -> list[tuple[str, str]]:
    variants: list[tuple[str, str]] = []
    long_window = max(window + 1, int(round(max(window * 1.8, posterior_mean * 1.8))))
    short_window = max(1, int(round(max(1.0, window / 2.0))))
    if family == "a5_volatility":
        variants.extend(
            [
                ("zscore_scale", f"ZScore(Std($ret,{window}))"),
                ("vol_ratio", f"CSRank(Div(Std($ret,{short_window}),Std($ret,{long_window})))"),
                ("vol_momentum_interaction", f"CSRank(Mul(ZScore(Std($ret,{window})),ZScore(Mom($close,{window}))))"),
            ]
        )
    elif family == "a5_momentum":
        variants.extend(
            [
                ("zscore_scale", f"ZScore(Mom($close,{window}))"),
                ("momentum_vol_interaction", f"CSRank(Mul(ZScore(Mom($close,{window})),ZScore(Std($ret,{short_window}))))"),
                ("momentum_acceleration", f"CSRank(Sub(Mom($close,{short_window}),Mom($close,{long_window})))"),
            ]
        )
    elif family == "a5_gap":
        gap = f"Div(Sub($open,Delay($close,{window})),Delay($close,{window}))"
        variants.extend(
            [
                ("zscore_scale", f"ZScore({gap})"),
                ("gap_vol_interaction", f"CSRank(Mul(ZScore({gap}),ZScore(Std($ret,{short_window}))))"),
                ("gap_momentum_interaction", f"CSRank(Mul(ZScore({gap}),ZScore(Mom($close,{short_window}))))"),
            ]
        )
    return variants


def infer_family_parameter_posterior(actual_objective_plan: Path | str | dict[str, Any]) -> dict[str, Any]:
    plan = _read_report(actual_objective_plan)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for profile in plan.get("actual_objective_profiles", []):
        family = str(profile.get("primitive_family"))
        window = extract_expression_window(str(profile.get("expression", "")))
        if window is None:
            continue
        grouped.setdefault(family, []).append({**profile, "window": window})

    posteriors = []
    for family, items in grouped.items():
        windows = np.array([float(item["window"]) for item in items], dtype=float)
        values = np.array([_metric(item.get("math_search_value")) for item in items], dtype=float)
        weights = _softmax(values)
        mean = float(np.sum(windows * weights))
        variance = float(np.sum(weights * np.square(windows - mean)))
        std = math.sqrt(max(variance, 1e-9))
        top_item = max(items, key=lambda item: _metric(item.get("math_search_value")))
        posteriors.append(
            {
                "primitive_family": family,
                "sample_count": len(items),
                "weighted_window_mean": round(mean, 6),
                "weighted_window_std": round(std, 6),
                "weighted_window_q20": round(_weighted_quantile(windows, weights, 0.20), 6),
                "weighted_window_q50": round(_weighted_quantile(windows, weights, 0.50), 6),
                "weighted_window_q80": round(_weighted_quantile(windows, weights, 0.80), 6),
                "best_candidate_id": top_item.get("candidate_id"),
                "best_expression": top_item.get("expression"),
                "best_window": top_item["window"],
                "best_math_search_value": round(_metric(top_item.get("math_search_value")), 6),
                "items": [
                    {
                        "candidate_id": item.get("candidate_id"),
                        "window": item["window"],
                        "math_search_value": item.get("math_search_value"),
                        "weight": round(float(weight), 6),
                    }
                    for item, weight in sorted(zip(items, weights), key=lambda pair: pair[1], reverse=True)
                ],
            }
        )
    posteriors.sort(key=lambda item: item["best_math_search_value"], reverse=True)
    return {
        "run_id": "phase2-search-core-v8-family-parameter-posterior",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V8_VERSION,
        "source_run_id": plan.get("run_id"),
        "family_count": len(posteriors),
        "family_parameter_posteriors": posteriors,
    }


def _natural_windows(posterior: dict[str, Any], *, max_windows: int) -> list[int]:
    mean = float(posterior["weighted_window_mean"])
    std = max(1.0, float(posterior["weighted_window_std"]))
    seeds = {
        int(round(mean)),
        int(round(mean - std)),
        int(round(mean + std)),
        int(round(float(posterior["weighted_window_q20"]))),
        int(round(float(posterior["weighted_window_q50"]))),
        int(round(float(posterior["weighted_window_q80"]))),
        int(posterior["best_window"]),
    }
    for z in (-1.5, -0.75, 0.75, 1.5):
        seeds.add(int(round(mean + (z * std))))
    return sorted(window for window in seeds if 1 <= window <= 252)[:max_windows]


def build_natural_parameter_proposal_ledger(
    *,
    actual_objective_plan: Path | str | dict[str, Any],
    max_windows_per_family: int = 7,
    include_structural_variants: bool = True,
) -> dict[str, Any]:
    posterior_report = infer_family_parameter_posterior(actual_objective_plan)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for posterior in posterior_report["family_parameter_posteriors"]:
        family = str(posterior["primitive_family"])
        windows = _natural_windows(posterior, max_windows=max_windows_per_family)
        for window in windows:
            expression = _family_expression(family, window)
            if expression is not None and expression not in seen:
                seen.add(expression)
                records.append(
                    {
                        "candidate_id": f"v8-natural-{len(records) + 1:04d}",
                        "expression": expression,
                        "retained": True,
                        "source_mode": "search_core_v8_natural_parameter_posterior",
                        "frontier_lane": "search_core_v8_natural_parameter",
                        "archive_cell": f"v8_{family}_natural",
                        "primitive_family": family,
                        "direction": "normal" if family != "a5_amihud" else "inverted",
                        "window": window,
                        "proposal_kind": "posterior_window",
                        "posterior_mean": posterior["weighted_window_mean"],
                        "posterior_std": posterior["weighted_window_std"],
                    }
                )
            if include_structural_variants:
                for kind, variant in _structural_variants(family, window, float(posterior["weighted_window_mean"])):
                    if variant in seen:
                        continue
                    seen.add(variant)
                    records.append(
                        {
                            "candidate_id": f"v8-natural-{len(records) + 1:04d}",
                            "expression": variant,
                            "retained": True,
                            "source_mode": "search_core_v8_natural_parameter_posterior",
                            "frontier_lane": "search_core_v8_natural_parameter",
                            "archive_cell": f"v8_{family}_natural",
                            "primitive_family": family,
                            "direction": "normal",
                            "window": window,
                            "proposal_kind": kind,
                            "posterior_mean": posterior["weighted_window_mean"],
                            "posterior_std": posterior["weighted_window_std"],
                        }
                    )
    return {
        "run_id": "phase2-search-core-v8-natural-parameter-proposal-ledger",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V8_VERSION,
        "scope": "natural_parameter_posterior_formula_generation",
        "source_actual_objective_run_id": _read_report(actual_objective_plan).get("run_id"),
        "posterior_report": posterior_report,
        "record_count": len(records),
        "records": records,
    }


def build_rank_quotient_proposal_ledger(proposal_ledger: Path | str | dict[str, Any]) -> dict[str, Any]:
    ledger = _read_report(proposal_ledger)
    records: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    dropped: list[dict[str, Any]] = []
    for record in ledger.get("records", []):
        expression = str(record.get("expression", ""))
        canonical = rank_validation_canonical_expression(expression)
        if canonical in seen:
            dropped.append(
                {
                    "candidate_id": record.get("candidate_id"),
                    "expression": expression,
                    "canonical_rank_validation_expression": canonical,
                    "kept_candidate_id": seen[canonical],
                    "drop_reason": "rank_validation_monotone_equivalent_duplicate",
                }
            )
            continue
        seen[canonical] = str(record.get("candidate_id", ""))
        records.append(
            {
                **record,
                "rank_quotient_candidate_id": f"v8-rankq-{len(records) + 1:04d}",
                "canonical_rank_validation_expression": canonical,
            }
        )
    return {
        "run_id": "phase2-search-core-v8-rank-quotient-proposal-ledger",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V8_VERSION,
        "source_run_id": ledger.get("run_id"),
        "scope": "rank_validation_quotient_space",
        "source_record_count": len(ledger.get("records", [])),
        "record_count": len(records),
        "dropped_rank_equivalent_count": len(dropped),
        "dropped_rank_equivalent_records": dropped,
        "records": records,
    }

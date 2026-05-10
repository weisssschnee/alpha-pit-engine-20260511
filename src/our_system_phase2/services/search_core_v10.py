from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression


SEARCH_CORE_V10_VERSION = "phase2-search-core-v10-tradable-local-continuous-surface-2026-04-26"


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


def _softmax(values: np.ndarray, temperature: float = 0.0035) -> np.ndarray:
    if values.size == 0:
        return values
    shifted = values - values.max()
    weights = np.exp(shifted / max(temperature, 1e-9))
    denom = float(weights.sum())
    if denom <= 0:
        return np.full(values.shape, 1.0 / len(values), dtype=float)
    return weights / denom


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


def _objective(record: dict[str, Any]) -> float:
    ic = _metric(record.get("mean_window_rank_ic", record.get("tradable_recent_4q_mean_window_rank_ic")))
    sortino = max(-2.0, min(2.0, _metric(record.get("mean_window_sortino", record.get("tradable_recent_4q_mean_window_sortino")))))
    pass_bonus = 0.002 if record.get("passes_real_market_smoke", True) else 0.0
    return ic + (0.0015 * sortino) + pass_bonus


def _mix_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = report.get("evaluations", report.get("records", []))
    return [
        row
        for row in rows
        if row.get("proposal_kind") == "posterior_continuous_mix_weight"
        and row.get("momentum_weight") is not None
        and row.get("gap_weight") is not None
    ]


def _weighted_stats(values: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
    weights = _softmax(scores)
    mean = float(np.sum(values * weights))
    variance = float(np.sum(weights * np.square(values - mean)))
    return mean, math.sqrt(max(variance, 1e-9))


def infer_v10_local_surface(tradable_report: Path | str | dict[str, Any], *, top_k: int = 12) -> dict[str, Any]:
    report = _read_report(tradable_report)
    mixes = sorted(_mix_rows(report), key=_objective, reverse=True)
    top = mixes[:top_k]
    if not top:
        raise ValueError("no_continuous_mix_rows")
    weights = np.array([float(row["momentum_weight"]) for row in top], dtype=float)
    scores = np.array([_objective(row) for row in top], dtype=float)
    weight_mean, weight_std = _weighted_stats(weights, scores)
    weight_step = max(0.01, min(0.04, weight_std / 2.5))
    center = round(weight_mean, 4)
    weight_grid = {
        round(min(0.78, max(0.22, center + (offset * weight_step))), 3)
        for offset in range(-5, 6)
    }
    best = top[0]
    weight_grid.add(round(float(best["momentum_weight"]), 3))

    pair_scores: dict[tuple[int, int], list[float]] = {}
    for row in mixes:
        key = (int(row["momentum_window"]), int(row["gap_window"]))
        pair_scores.setdefault(key, []).append(_objective(row))
    top_pairs = [
        {
            "momentum_window": pair[0],
            "gap_window": pair[1],
            "mean_objective": round(float(np.mean(values)), 6),
            "best_objective": round(max(values), 6),
        }
        for pair, values in sorted(pair_scores.items(), key=lambda item: max(item[1]), reverse=True)
    ][:6]

    pure_rows = [
        row
        for row in report.get("evaluations", report.get("records", []))
        if row.get("proposal_kind") in {"rank_quotient_posterior_window", "recent_shadow_rank_quotient"}
    ]
    pure_top = sorted(pure_rows, key=_objective, reverse=True)[:8]

    return {
        "run_id": "phase2-search-core-v10-local-surface",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V10_VERSION,
        "source_run_id": report.get("source_run_id"),
        "source_experiment_id": report.get("experiment_id"),
        "source_screening_mode": report.get("screening_mode"),
        "source_evaluation_start_date": report.get("evaluation_start_date"),
        "source_evaluation_end_date": report.get("evaluation_end_date"),
        "mix_sample_count": len(mixes),
        "top_k": len(top),
        "local_momentum_weight_mean": round(weight_mean, 6),
        "local_momentum_weight_std": round(weight_std, 6),
        "local_weight_step": round(weight_step, 6),
        "momentum_weight_grid": sorted(weight_grid),
        "top_mix_candidates": [
            {
                "candidate_id": row.get("candidate_id"),
                "momentum_weight": row.get("momentum_weight"),
                "gap_weight": row.get("gap_weight"),
                "momentum_window": row.get("momentum_window"),
                "gap_window": row.get("gap_window"),
                "mean_window_rank_ic": row.get("mean_window_rank_ic", row.get("tradable_recent_4q_mean_window_rank_ic")),
                "mean_window_sortino": row.get("mean_window_sortino", row.get("tradable_recent_4q_mean_window_sortino")),
                "local_objective": round(_objective(row), 6),
            }
            for row in top
        ],
        "top_window_pairs": top_pairs,
        "top_pure_candidates": [
            {
                "candidate_id": row.get("candidate_id"),
                "primitive_family": row.get("primitive_family"),
                "window": row.get("window"),
                "mean_window_rank_ic": row.get("mean_window_rank_ic", row.get("tradable_recent_4q_mean_window_rank_ic")),
                "mean_window_sortino": row.get("mean_window_sortino", row.get("tradable_recent_4q_mean_window_sortino")),
                "local_objective": round(_objective(row), 6),
            }
            for row in pure_top
        ],
    }


def build_v10_local_continuous_ledger(
    tradable_report: Path | str | dict[str, Any],
    *,
    top_pair_count: int = 4,
    include_pure_and_shadow: bool = True,
) -> dict[str, Any]:
    surface = infer_v10_local_surface(tradable_report)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_record(record: dict[str, Any]) -> None:
        canonical = rank_validation_canonical_expression(str(record["expression"]))
        if canonical in seen:
            return
        seen.add(canonical)
        records.append(
            {
                "candidate_id": f"v10-local-{len(records) + 1:04d}",
                "retained": True,
                "source_mode": "search_core_v10_tradable_local_continuous_surface",
                "canonical_rank_validation_expression": canonical,
                **record,
            }
        )

    for pair in surface["top_window_pairs"][:top_pair_count]:
        momentum_window = int(pair["momentum_window"])
        gap_window = int(pair["gap_window"])
        for momentum_weight in surface["momentum_weight_grid"]:
            gap_weight = round(1.0 - momentum_weight, 3)
            expression = (
                "CSRank(Add("
                f"Mul({momentum_weight},ZScore({_base_expression('a5_momentum', momentum_window)})),"
                f"Mul({gap_weight},ZScore({_base_expression('a5_gap', gap_window)}))"
                "))"
            )
            add_record(
                {
                    "expression": expression,
                    "frontier_lane": "search_core_v10_local_continuous_mix",
                    "archive_cell": "v10_momentum_gap_local_surface",
                    "primitive_family": "a5_momentum+a5_gap",
                    "proposal_kind": "local_surface_continuous_mix_weight",
                    "momentum_window": momentum_window,
                    "gap_window": gap_window,
                    "momentum_weight": momentum_weight,
                    "gap_weight": gap_weight,
                    "source_pair_best_objective": pair["best_objective"],
                }
            )

    if include_pure_and_shadow:
        for item in surface["top_pure_candidates"]:
            family = str(item["primitive_family"])
            if family not in {"a5_gap", "a5_momentum", "a5_volatility"}:
                continue
            window = int(item["window"])
            add_record(
                {
                    "expression": _rank_expression(family, window),
                    "frontier_lane": "search_core_v10_local_anchor"
                    if family != "a5_volatility"
                    else "search_core_v10_recent_regime_shadow",
                    "archive_cell": f"v10_{family}_local_anchor",
                    "primitive_family": family,
                    "proposal_kind": "local_anchor_rank_quotient",
                    "window": window,
                    "source_anchor_objective": item["local_objective"],
                }
            )

    return {
        "run_id": "phase2-search-core-v10-local-continuous-proposal-ledger",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V10_VERSION,
        "scope": "tradable_rank_quotient_local_continuous_formula_generation",
        "surface_report": surface,
        "record_count": len(records),
        "records": records,
    }

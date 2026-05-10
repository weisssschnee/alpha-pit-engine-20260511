from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression


SEARCH_CORE_V11_VERSION = "phase2-search-core-v11-tplus1-momentum-heavy-surface-2026-04-26"


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


def _objective(row: dict[str, Any]) -> float:
    ic = _metric(row.get("mean_window_rank_ic", row.get("tplus1_tradable_recent_4q_mean_window_rank_ic")))
    sortino = max(-2.0, min(2.0, _metric(row.get("mean_window_sortino", row.get("tplus1_tradable_recent_4q_mean_window_sortino")))))
    pass_bonus = 0.002 if row.get("passes_real_market_smoke", True) else 0.0
    return ic + (0.0015 * sortino) + pass_bonus


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


def _rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    return list(report.get("evaluations", report.get("records", [])))


def infer_v11_tplus1_surface(tplus1_report: Path | str | dict[str, Any], *, top_k: int = 12) -> dict[str, Any]:
    report = _read_report(tplus1_report)
    rows = _rows(report)
    mixes = [
        row
        for row in rows
        if row.get("proposal_kind") == "local_surface_continuous_mix_weight"
        and row.get("momentum_weight") is not None
        and row.get("gap_weight") is not None
    ]
    mixes = sorted(mixes, key=_objective, reverse=True)
    if not mixes:
        raise ValueError("no_tplus1_mix_rows")
    top = mixes[:top_k]
    weights = np.array([float(row["momentum_weight"]) for row in top], dtype=float)
    scores = np.array([_objective(row) for row in top], dtype=float)
    centered = scores - scores.max()
    probs = np.exp(centered / 0.0035)
    probs = probs / max(float(probs.sum()), 1e-12)
    mean_weight = float(np.sum(weights * probs))
    best = top[0]
    max_seen_weight = max(float(row["momentum_weight"]) for row in mixes)
    min_seen_weight = min(float(row["momentum_weight"]) for row in mixes)
    best_at_upper_edge = float(best["momentum_weight"]) >= max_seen_weight - 1e-9

    if best_at_upper_edge:
        weight_grid = {round(value, 3) for value in np.linspace(float(best["momentum_weight"]), 0.92, 9)}
    else:
        weight_grid = {round(min(0.95, max(0.35, mean_weight + offset)), 3) for offset in (-0.09, -0.06, -0.03, 0, 0.03, 0.06, 0.09)}
    weight_grid.add(round(float(best["momentum_weight"]), 3))

    pair_scores: dict[tuple[int, int], list[float]] = {}
    for row in mixes:
        pair_scores.setdefault((int(row["momentum_window"]), int(row["gap_window"])), []).append(_objective(row))
    top_pairs = [
        {
            "momentum_window": pair[0],
            "gap_window": pair[1],
            "best_objective": round(max(values), 6),
            "mean_objective": round(float(np.mean(values)), 6),
        }
        for pair, values in sorted(pair_scores.items(), key=lambda item: max(item[1]), reverse=True)
    ][:5]

    anchors = [
        row
        for row in rows
        if row.get("proposal_kind") == "local_anchor_rank_quotient"
        and row.get("primitive_family") in {"a5_momentum", "a5_gap", "a5_volatility"}
    ]
    anchors = sorted(anchors, key=_objective, reverse=True)
    return {
        "run_id": "phase2-search-core-v11-tplus1-surface",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V11_VERSION,
        "source_run_id": report.get("source_run_id"),
        "source_experiment_id": report.get("experiment_id"),
        "source_execution_policy": report.get("execution_policy"),
        "source_screening_mode": report.get("screening_mode"),
        "mix_sample_count": len(mixes),
        "top_k": len(top),
        "local_momentum_weight_mean": round(mean_weight, 6),
        "best_mix_candidate_id": best.get("candidate_id"),
        "best_mix_momentum_weight": best.get("momentum_weight"),
        "best_mix_gap_weight": best.get("gap_weight"),
        "best_at_upper_edge": best_at_upper_edge,
        "seen_weight_range": [round(min_seen_weight, 6), round(max_seen_weight, 6)],
        "momentum_weight_grid": sorted(weight_grid),
        "top_window_pairs": top_pairs,
        "top_anchors": [
            {
                "candidate_id": row.get("candidate_id"),
                "primitive_family": row.get("primitive_family"),
                "window": row.get("window"),
                "mean_window_rank_ic": row.get("mean_window_rank_ic", row.get("tplus1_tradable_recent_4q_mean_window_rank_ic")),
                "mean_window_sortino": row.get("mean_window_sortino", row.get("tplus1_tradable_recent_4q_mean_window_sortino")),
                "objective": round(_objective(row), 6),
            }
            for row in anchors[:8]
        ],
        "top_mix_candidates": [
            {
                "candidate_id": row.get("candidate_id"),
                "momentum_weight": row.get("momentum_weight"),
                "gap_weight": row.get("gap_weight"),
                "momentum_window": row.get("momentum_window"),
                "gap_window": row.get("gap_window"),
                "mean_window_rank_ic": row.get("mean_window_rank_ic", row.get("tplus1_tradable_recent_4q_mean_window_rank_ic")),
                "mean_window_sortino": row.get("mean_window_sortino", row.get("tplus1_tradable_recent_4q_mean_window_sortino")),
                "objective": round(_objective(row), 6),
            }
            for row in top
        ],
    }


def build_v11_tplus1_momentum_heavy_ledger(
    tplus1_report: Path | str | dict[str, Any],
    *,
    top_pair_count: int = 3,
) -> dict[str, Any]:
    surface = infer_v11_tplus1_surface(tplus1_report)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(record: dict[str, Any]) -> None:
        canonical = rank_validation_canonical_expression(str(record["expression"]))
        if canonical in seen:
            return
        seen.add(canonical)
        records.append(
            {
                "candidate_id": f"v11-tplus1-{len(records) + 1:04d}",
                "retained": True,
                "source_mode": "search_core_v11_tplus1_momentum_heavy_surface",
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
            add(
                {
                    "expression": expression,
                    "frontier_lane": "search_core_v11_tplus1_momentum_heavy_mix",
                    "archive_cell": "v11_momentum_heavy_gap_mix",
                    "primitive_family": "a5_momentum+a5_gap",
                    "proposal_kind": "tplus1_momentum_heavy_mix_weight",
                    "momentum_window": momentum_window,
                    "gap_window": gap_window,
                    "momentum_weight": momentum_weight,
                    "gap_weight": gap_weight,
                    "source_pair_best_objective": pair["best_objective"],
                }
            )

    for family, windows in {
        "a5_momentum": [7, 8, 9, 10, 11],
        "a5_gap": [8, 9],
        "a5_volatility": [9, 10, 11],
    }.items():
        for window in windows:
            add(
                {
                    "expression": _rank_expression(family, window),
                    "frontier_lane": "search_core_v11_tplus1_anchor"
                    if family != "a5_volatility"
                    else "search_core_v11_tplus1_volatility_shadow",
                    "archive_cell": f"v11_{family}_tplus1_anchor",
                    "primitive_family": family,
                    "proposal_kind": "tplus1_anchor_rank_quotient",
                    "window": window,
                }
            )

    return {
        "run_id": "phase2-search-core-v11-tplus1-momentum-heavy-ledger",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V11_VERSION,
        "scope": "tplus1_tradable_rank_quotient_momentum_heavy_generation",
        "surface_report": surface,
        "record_count": len(records),
        "records": records,
    }

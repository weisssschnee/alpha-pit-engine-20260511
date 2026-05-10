from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression
from our_system_phase2.services.search_core_v16 import quarter_floor_stats


SEARCH_CORE_V17_VERSION = "phase2-search-core-v17-tplus1-stable-denominator-refinement-2026-04-26"


def _read_report(value: Path | str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return json.loads(Path(value).read_text(encoding="utf-8"))


def _metric(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    return list(report.get("evaluations", report.get("records", [])))


def _rank(expression: str) -> str:
    return f"CSRank({expression})"


def _momentum(window: int) -> str:
    return f"Mom($close,{window})"


def _denominator(kind: str, window: int) -> str:
    if kind == "std_ret":
        return f"Std($ret,{window})"
    if kind == "mean_abs_ret":
        return f"Mean(Abs($ret),{window})"
    if kind == "wma_abs_ret":
        return f"WMA(Abs($ret),{window})"
    raise ValueError(f"unsupported_denominator:{kind}")


def infer_v17_stable_denominator_surface(tplus1_report: Path | str | dict[str, Any]) -> dict[str, Any]:
    report = _read_report(tplus1_report)
    candidates: list[dict[str, Any]] = []
    for row in _rows(report):
        if not row.get("passes_real_market_smoke", True):
            continue
        if row.get("research_track") != "stable_quarter_floor":
            continue
        if row.get("primitive_family") != "a5_vol_normalized_momentum":
            continue
        enriched = {**row, **quarter_floor_stats(row)}
        if enriched.get("quarter_floor_pass"):
            candidates.append(enriched)
    if not candidates:
        raise ValueError("no_stable_quarter_floor_candidates")
    candidates.sort(
        key=lambda row: (
            _metric(row.get("quarter_floor_score"), -999.0),
            _metric(row.get("mean_window_rank_ic"), -999.0),
        ),
        reverse=True,
    )
    return {
        "run_id": "phase2-search-core-v17-tplus1-stable-denominator-surface",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V17_VERSION,
        "source_run_id": report.get("source_run_id"),
        "source_execution_policy": report.get("execution_policy"),
        "source_screening_mode": report.get("screening_mode"),
        "stable_input_count": len(candidates),
        "numerator_window_grid": [8, 9],
        "denominator_window_grid": [3, 4, 5, 6, 7, 8],
        "denominator_family_grid": ["std_ret", "mean_abs_ret", "wma_abs_ret"],
        "ranking_objective": "quarter_floor_score_then_mean_ic",
        "top_stable_candidates": [
            {
                "candidate_id": row.get("candidate_id"),
                "expression": row.get("expression"),
                "denominator_family": row.get("denominator_family"),
                "numerator_window": row.get("numerator_window"),
                "denominator_window": row.get("denominator_window"),
                "mean_window_rank_ic": row.get("mean_window_rank_ic"),
                "mean_window_sortino": row.get("mean_window_sortino"),
                "min_quarter_ic": row.get("min_quarter_ic"),
                "quarter_floor_score": row.get("quarter_floor_score"),
            }
            for row in candidates[:8]
        ],
    }


def build_v17_stable_denominator_ledger(tplus1_report: Path | str | dict[str, Any]) -> dict[str, Any]:
    surface = infer_v17_stable_denominator_surface(tplus1_report)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(record: dict[str, Any]) -> None:
        canonical = rank_validation_canonical_expression(str(record["expression"]))
        if canonical in seen:
            return
        seen.add(canonical)
        records.append(
            {
                "candidate_id": f"v17-tplus1-{len(records) + 1:04d}",
                "retained": True,
                "source_mode": "search_core_v17_tplus1_stable_denominator_refinement",
                "canonical_rank_validation_expression": canonical,
                **record,
            }
        )

    for numerator_window in surface["numerator_window_grid"]:
        for denominator_window in surface["denominator_window_grid"]:
            for denominator_family in surface["denominator_family_grid"]:
                add(
                    {
                        "expression": _rank(
                            f"Div({_momentum(int(numerator_window))},{_denominator(denominator_family, int(denominator_window))})"
                        ),
                        "frontier_lane": "search_core_v17_tplus1_stable_denominator",
                        "archive_cell": "v17_stable_denominator_refinement",
                        "primitive_family": "a5_vol_normalized_momentum",
                        "proposal_kind": "v17_stable_denominator_refinement",
                        "research_track": "stable_quarter_floor",
                        "quarter_floor_required": True,
                        "regime_conditional_audit": False,
                        "window": int(numerator_window),
                        "numerator_window": int(numerator_window),
                        "denominator_window": int(denominator_window),
                        "volatility_window": int(denominator_window) if denominator_family == "std_ret" else None,
                        "denominator_family": denominator_family,
                    }
                )

    return {
        "run_id": "phase2-search-core-v17-tplus1-stable-denominator-ledger",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V17_VERSION,
        "scope": "tplus1_tradable_stable_denominator_refinement",
        "surface_report": surface,
        "record_count": len(records),
        "records": records,
    }


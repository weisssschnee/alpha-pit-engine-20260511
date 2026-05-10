from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression


SEARCH_CORE_V16_VERSION = "phase2-search-core-v16-tplus1-quarter-floor-denominator-2026-04-26"


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


def _rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    return list(report.get("evaluations", report.get("records", [])))


def _rank(expression: str) -> str:
    return f"CSRank({expression})"


def _momentum(window: int) -> str:
    return f"Mom($close,{window})"


def _downside_abs_ret() -> str:
    return "Div(Sub(Abs($ret),$ret),2)"


def _denominator(kind: str, window: int) -> str:
    if kind == "mean_abs_ret":
        return f"Mean(Abs($ret),{window})"
    if kind == "wma_abs_ret":
        return f"WMA(Abs($ret),{window})"
    if kind == "std_ret":
        return f"Std($ret,{window})"
    if kind == "med_downside_abs_ret":
        return f"Med({_downside_abs_ret()},{window})"
    raise ValueError(f"unsupported_denominator:{kind}")


def quarter_floor_stats(row: dict[str, Any]) -> dict[str, Any]:
    windows = list(row.get("recent_windows") or row.get("windows") or [])
    ics = [_metric(window.get("mean_rank_ic"), default=float("nan")) for window in windows]
    ics = [value for value in ics if math.isfinite(value)]
    if not ics:
        return {
            "quarter_count": 0,
            "min_quarter_ic": None,
            "negative_quarter_count": None,
            "positive_quarter_ratio": None,
            "quarter_ic_std": None,
            "quarter_concentration_ratio": None,
            "quarter_floor_pass": False,
            "quarter_floor_score": None,
        }
    mean_ic = _metric(row.get("mean_window_rank_ic", row.get("tplus1_tradable_recent_4q_mean_window_rank_ic")))
    sortino = _metric(row.get("mean_window_sortino", row.get("tplus1_tradable_recent_4q_mean_window_sortino")))
    min_ic = min(ics)
    max_ic = max(ics)
    negative_count = sum(1 for value in ics if value < 0)
    positive_ratio = sum(1 for value in ics if value > 0) / len(ics)
    std = float(np.std(np.array(ics, dtype=float), ddof=0))
    concentration = max_ic / max(abs(mean_ic), 1e-6)
    floor_pass = negative_count == 0 and min_ic >= 0.0
    penalty = max(0.0, -min_ic) * 1.5 + std * 0.25 + max(0.0, concentration - 2.5) * 0.002
    bonus = 0.006 if floor_pass else 0.0
    score = mean_ic + 0.0015 * max(-2.0, min(2.0, sortino)) + bonus - penalty
    return {
        "quarter_count": len(ics),
        "min_quarter_ic": round(float(min_ic), 6),
        "negative_quarter_count": int(negative_count),
        "positive_quarter_ratio": round(float(positive_ratio), 6),
        "quarter_ic_std": round(float(std), 6),
        "quarter_concentration_ratio": round(float(concentration), 6),
        "quarter_floor_pass": floor_pass,
        "quarter_floor_score": round(float(score), 6),
    }


def infer_v16_quarter_floor_surface(tplus1_report: Path | str | dict[str, Any]) -> dict[str, Any]:
    report = _read_report(tplus1_report)
    candidates: list[dict[str, Any]] = []
    for row in _rows(report):
        if not row.get("passes_real_market_smoke", True):
            continue
        if row.get("primitive_family") != "a5_vol_normalized_momentum":
            continue
        stats = quarter_floor_stats(row)
        candidates.append({**row, **stats})
    if not candidates:
        raise ValueError("no_quarter_floor_candidates")

    stable = [row for row in candidates if row["quarter_floor_pass"]]
    spiky = [row for row in candidates if not row["quarter_floor_pass"]]
    stable.sort(key=lambda row: _metric(row.get("quarter_floor_score"), -999.0), reverse=True)
    spiky.sort(key=lambda row: _metric(row.get("mean_window_rank_ic"), -999.0), reverse=True)

    stable_top = stable[0] if stable else max(candidates, key=lambda row: _metric(row.get("quarter_floor_score"), -999.0))
    stable_num = int(stable_top.get("numerator_window") or stable_top.get("window"))
    stable_den = int(stable_top.get("denominator_window") or stable_top.get("volatility_window") or 6)
    spiky_top = spiky[0] if spiky else None
    spiky_num = int((spiky_top or stable_top).get("numerator_window") or (spiky_top or stable_top).get("window"))
    spiky_den = int((spiky_top or stable_top).get("denominator_window") or (spiky_top or stable_top).get("volatility_window") or 6)

    return {
        "run_id": "phase2-search-core-v16-tplus1-quarter-floor-surface",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V16_VERSION,
        "source_run_id": report.get("source_run_id"),
        "source_execution_policy": report.get("execution_policy"),
        "source_screening_mode": report.get("screening_mode"),
        "candidate_count": len(candidates),
        "stable_candidate_count": len(stable),
        "spiky_candidate_count": len(spiky),
        "stable_numerator_window_grid": sorted({max(2, stable_num - 1), stable_num, stable_num + 1}),
        "stable_denominator_window_grid": sorted({max(2, stable_den - 2), max(2, stable_den - 1), stable_den, stable_den + 1, stable_den + 2}),
        "stable_denominator_family_grid": ["mean_abs_ret", "wma_abs_ret", "std_ret"],
        "spiky_numerator_window_grid": sorted({max(2, spiky_num - 1), spiky_num}),
        "spiky_denominator_window_grid": sorted({max(2, spiky_den - 1), spiky_den, spiky_den + 1}),
        "spiky_denominator_family_grid": ["med_downside_abs_ret"],
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
            for row in stable[:8]
        ],
        "top_spiky_candidates": [
            {
                "candidate_id": row.get("candidate_id"),
                "expression": row.get("expression"),
                "denominator_family": row.get("denominator_family"),
                "numerator_window": row.get("numerator_window"),
                "denominator_window": row.get("denominator_window"),
                "mean_window_rank_ic": row.get("mean_window_rank_ic"),
                "mean_window_sortino": row.get("mean_window_sortino"),
                "min_quarter_ic": row.get("min_quarter_ic"),
                "quarter_concentration_ratio": row.get("quarter_concentration_ratio"),
                "quarter_floor_score": row.get("quarter_floor_score"),
            }
            for row in spiky[:8]
        ],
    }


def build_v16_quarter_floor_ledger(tplus1_report: Path | str | dict[str, Any]) -> dict[str, Any]:
    surface = infer_v16_quarter_floor_surface(tplus1_report)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(record: dict[str, Any]) -> None:
        canonical = rank_validation_canonical_expression(str(record["expression"]))
        if canonical in seen:
            return
        seen.add(canonical)
        records.append(
            {
                "candidate_id": f"v16-tplus1-{len(records) + 1:04d}",
                "retained": True,
                "source_mode": "search_core_v16_tplus1_quarter_floor_denominator",
                "canonical_rank_validation_expression": canonical,
                **record,
            }
        )

    for numerator_window in surface["stable_numerator_window_grid"]:
        for denominator_window in surface["stable_denominator_window_grid"]:
            for denominator_family in surface["stable_denominator_family_grid"]:
                add(
                    {
                        "expression": _rank(
                            f"Div({_momentum(int(numerator_window))},{_denominator(denominator_family, int(denominator_window))})"
                        ),
                        "frontier_lane": "search_core_v16_tplus1_quarter_floor_stable",
                        "archive_cell": "v16_quarter_floor_stable_denominator",
                        "primitive_family": "a5_vol_normalized_momentum",
                        "proposal_kind": "v16_quarter_floor_stable_denominator",
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

    for numerator_window in surface["spiky_numerator_window_grid"]:
        for denominator_window in surface["spiky_denominator_window_grid"]:
            add(
                {
                    "expression": _rank(
                        f"Div({_momentum(int(numerator_window))},{_denominator('med_downside_abs_ret', int(denominator_window))})"
                    ),
                    "frontier_lane": "search_core_v16_tplus1_regime_conditional_audit",
                    "archive_cell": "v16_spiky_median_downside_audit",
                    "primitive_family": "a5_vol_normalized_momentum",
                    "proposal_kind": "v16_regime_conditional_median_downside_audit",
                    "research_track": "spiky_regime_conditional_audit",
                    "quarter_floor_required": False,
                    "regime_conditional_audit": True,
                    "window": int(numerator_window),
                    "numerator_window": int(numerator_window),
                    "denominator_window": int(denominator_window),
                    "denominator_family": "med_downside_abs_ret",
                }
            )

    return {
        "run_id": "phase2-search-core-v16-tplus1-quarter-floor-ledger",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V16_VERSION,
        "scope": "tplus1_tradable_quarter_floor_denominator_generation",
        "surface_report": surface,
        "record_count": len(records),
        "records": records,
    }


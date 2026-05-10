from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression
from our_system_phase2.services.search_core_v16 import quarter_floor_stats


SEARCH_CORE_V18_VERSION = "phase2-search-core-v18-tplus1-light-smoothing-cost-shadow-2026-04-26"


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


def _price(transform: str, smooth_window: int | None) -> str:
    if transform in {"raw", "mean_signal"}:
        return "$close"
    if transform == "wma_price":
        return f"WMA($close,{int(smooth_window or 2)})"
    raise ValueError(f"unsupported_numerator_transform:{transform}")


def _momentum(window: int, *, transform: str = "raw", smooth_window: int | None = None) -> str:
    signal = f"Mom({_price(transform, smooth_window)},{window})"
    if transform == "mean_signal":
        return f"Mean({signal},{int(smooth_window or 2)})"
    return signal


def _abs_ret_base(transform: str, smooth_window: int | None) -> str:
    base = "Abs($ret)"
    if transform == "raw":
        return base
    if transform == "mean_abs":
        return f"Mean({base},{int(smooth_window or 2)})"
    if transform == "wma_abs":
        return f"WMA({base},{int(smooth_window or 2)})"
    raise ValueError(f"unsupported_denominator_transform:{transform}")


def _denominator(kind: str, window: int, *, transform: str = "raw", smooth_window: int | None = None) -> str:
    if kind == "std_ret":
        return f"Std($ret,{window})"
    if kind == "mean_abs_ret":
        return f"Mean({_abs_ret_base(transform, smooth_window)},{window})"
    if kind == "wma_abs_ret":
        return f"WMA({_abs_ret_base(transform, smooth_window)},{window})"
    raise ValueError(f"unsupported_denominator:{kind}")


def infer_v18_light_smoothing_surface(tplus1_report: Path | str | dict[str, Any]) -> dict[str, Any]:
    report = _read_report(tplus1_report)
    candidates: list[dict[str, Any]] = []
    for row in _rows(report):
        if not row.get("passes_real_market_smoke", True):
            continue
        if row.get("research_track") != "stable_quarter_floor":
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
    top = candidates[0]
    return {
        "run_id": "phase2-search-core-v18-tplus1-light-smoothing-surface",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V18_VERSION,
        "source_run_id": report.get("source_run_id"),
        "source_execution_policy": report.get("execution_policy"),
        "source_screening_mode": report.get("screening_mode"),
        "stable_input_count": len(candidates),
        "center_candidate_id": top.get("candidate_id"),
        "center_expression": top.get("expression"),
        "center_numerator_window": top.get("numerator_window"),
        "center_denominator_window": top.get("denominator_window"),
        "center_denominator_family": top.get("denominator_family"),
        "center_quarter_floor_score": top.get("quarter_floor_score"),
        "numerator_window_grid": [8, 9],
        "denominator_window_grid": [2, 3, 4],
        "denominator_family_grid": ["mean_abs_ret", "std_ret", "wma_abs_ret"],
        "numerator_transform_grid": ["raw", "mean_signal", "wma_price"],
        "denominator_transform_grid": ["raw", "mean_abs", "wma_abs"],
        "smoothing_window_grid": [2, 3],
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


def build_v18_light_smoothing_ledger(tplus1_report: Path | str | dict[str, Any]) -> dict[str, Any]:
    surface = infer_v18_light_smoothing_surface(tplus1_report)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(record: dict[str, Any]) -> None:
        canonical = rank_validation_canonical_expression(str(record["expression"]))
        if canonical in seen:
            return
        seen.add(canonical)
        records.append(
            {
                "candidate_id": f"v18-tplus1-{len(records) + 1:04d}",
                "retained": True,
                "source_mode": "search_core_v18_tplus1_light_smoothing_cost_shadow",
                "canonical_rank_validation_expression": canonical,
                **record,
            }
        )

    for numerator_window in surface["numerator_window_grid"]:
        for denominator_window in surface["denominator_window_grid"]:
            for denominator_family in surface["denominator_family_grid"]:
                for numerator_transform in surface["numerator_transform_grid"]:
                    numerator_smooth_options = surface["smoothing_window_grid"] if numerator_transform != "raw" else [None]
                    for numerator_smooth in numerator_smooth_options:
                        denominator_transform_options = (
                            surface["denominator_transform_grid"]
                            if denominator_family in {"mean_abs_ret", "wma_abs_ret"}
                            else ["raw"]
                        )
                        for denominator_transform in denominator_transform_options:
                            denominator_smooth_options = (
                                surface["smoothing_window_grid"] if denominator_transform != "raw" else [None]
                            )
                            for denominator_smooth in denominator_smooth_options:
                                add(
                                    {
                                        "expression": _rank(
                                            "Div("
                                            f"{_momentum(int(numerator_window), transform=numerator_transform, smooth_window=numerator_smooth)},"
                                            f"{_denominator(denominator_family, int(denominator_window), transform=denominator_transform, smooth_window=denominator_smooth)}"
                                            ")"
                                        ),
                                        "frontier_lane": "search_core_v18_tplus1_light_smoothing",
                                        "archive_cell": "v18_light_smoothing_stable_center",
                                        "primitive_family": "a5_vol_normalized_momentum",
                                        "proposal_kind": "v18_light_smoothing_stable_denominator",
                                        "research_track": "stable_quarter_floor",
                                        "quarter_floor_required": True,
                                        "regime_conditional_audit": False,
                                        "turnover_cost_shadow_required": True,
                                        "window": int(numerator_window),
                                        "numerator_window": int(numerator_window),
                                        "denominator_window": int(denominator_window),
                                        "volatility_window": int(denominator_window) if denominator_family == "std_ret" else None,
                                        "denominator_family": denominator_family,
                                        "numerator_transform": numerator_transform,
                                        "denominator_transform": denominator_transform,
                                        "numerator_smoothing_window": None
                                        if numerator_smooth is None
                                        else int(numerator_smooth),
                                        "denominator_smoothing_window": None
                                        if denominator_smooth is None
                                        else int(denominator_smooth),
                                    }
                                )

    return {
        "run_id": "phase2-search-core-v18-tplus1-light-smoothing-ledger",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V18_VERSION,
        "scope": "tplus1_tradable_light_smoothing_stable_denominator_generation",
        "surface_report": surface,
        "record_count": len(records),
        "records": records,
    }


def build_v18_compact_validation_ledger(v18_ledger: Path | str | dict[str, Any]) -> dict[str, Any]:
    ledger = _read_report(v18_ledger)
    records = list(ledger.get("records", []))
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(record: dict[str, Any]) -> None:
        canonical = str(record.get("canonical_rank_validation_expression") or record.get("expression"))
        if canonical in seen:
            return
        seen.add(canonical)
        selected.append(record)

    for record in records:
        if record.get("numerator_transform") == "raw" and record.get("denominator_transform") == "raw":
            add(record)

    for record in records:
        if record.get("denominator_transform") != "raw":
            continue
        if record.get("numerator_transform") == "mean_signal" and record.get("numerator_smoothing_window") == 2:
            add(record)
        elif record.get("numerator_transform") == "wma_price" and record.get("numerator_smoothing_window") == 2:
            add(record)

    for record in records:
        if record.get("numerator_transform") != "raw":
            continue
        if record.get("denominator_transform") == "mean_abs" and record.get("denominator_smoothing_window") == 2:
            add(record)
        elif record.get("denominator_transform") == "wma_abs" and record.get("denominator_smoothing_window") == 2:
            add(record)

    return {
        "run_id": "phase2-search-core-v18-tplus1-compact-validation-ledger",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V18_VERSION,
        "scope": "compact_validation_subset_raw_and_single_side_smoothing",
        "source_run_id": ledger.get("run_id"),
        "surface_report": ledger.get("surface_report"),
        "selection_policy": {
            "include_all_raw_baselines": True,
            "include_numerator_smoothing_window_2_only": True,
            "include_denominator_smoothing_window_2_only": True,
            "exclude_double_smoothing_crosses": True,
        },
        "record_count": len(selected),
        "records": selected,
    }

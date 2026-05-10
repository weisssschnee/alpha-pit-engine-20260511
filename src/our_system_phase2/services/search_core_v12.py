from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression


SEARCH_CORE_V12_VERSION = "phase2-search-core-v12-tplus1-natural-residual-surface-2026-04-26"


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
    return ic + (0.0015 * sortino)


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


def _natural_neighbor_windows(center: int, *, radius: int = 1) -> list[int]:
    return list(range(max(2, center - radius), center + radius + 1))


def infer_v12_tplus1_residual_surface(tplus1_report: Path | str | dict[str, Any]) -> dict[str, Any]:
    report = _read_report(tplus1_report)
    rows = _rows(report)
    passed_rows = [row for row in rows if row.get("passes_real_market_smoke", True)]
    anchors = [
        row
        for row in passed_rows
        if row.get("primitive_family") == "a5_momentum" and row.get("window") is not None
    ]
    if not anchors:
        raise ValueError("no_tplus1_momentum_anchor_rows")
    anchors = sorted(anchors, key=_objective, reverse=True)
    top_anchor = anchors[0]
    top_anchor_window = int(top_anchor["window"])

    mixes = [
        row
        for row in passed_rows
        if row.get("primitive_family") == "a5_momentum+a5_gap"
        and row.get("gap_weight") is not None
        and row.get("gap_window") is not None
        and row.get("momentum_window") is not None
    ]
    mixes = sorted(mixes, key=_objective, reverse=True)
    residual_center = float(mixes[0]["gap_weight"]) if mixes else 0.08
    residual_offsets = np.array([-1.0, -0.5, 0.0, 0.5, 1.0], dtype=float) * max(residual_center, 0.03)
    residual_grid = {
        round(min(0.18, max(0.0, residual_center + float(offset))), 3)
        for offset in residual_offsets
    }
    residual_grid.add(0.0)
    residual_grid.add(round(residual_center, 3))

    gap_windows = {9}
    if mixes:
        gap_windows.update(int(row["gap_window"]) for row in mixes[:5])
    gap_windows = {window for window in gap_windows if 2 <= window <= 30}

    momentum_windows = set(_natural_neighbor_windows(top_anchor_window, radius=1))
    momentum_windows.update(int(row["window"]) for row in anchors[:2])

    return {
        "run_id": "phase2-search-core-v12-tplus1-residual-surface",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V12_VERSION,
        "source_run_id": report.get("source_run_id"),
        "source_execution_policy": report.get("execution_policy"),
        "source_screening_mode": report.get("screening_mode"),
        "top_momentum_anchor_candidate_id": top_anchor.get("candidate_id"),
        "top_momentum_anchor_window": top_anchor_window,
        "top_momentum_anchor_objective": round(_objective(top_anchor), 6),
        "top_momentum_anchor_ic": top_anchor.get("mean_window_rank_ic", top_anchor.get("tplus1_tradable_recent_4q_mean_window_rank_ic")),
        "residual_gap_center": round(residual_center, 6),
        "gap_residual_weight_grid": sorted(residual_grid),
        "momentum_window_grid": sorted(momentum_windows),
        "gap_window_grid": sorted(gap_windows),
        "top_momentum_anchors": [
            {
                "candidate_id": row.get("candidate_id"),
                "window": row.get("window"),
                "mean_window_rank_ic": row.get("mean_window_rank_ic", row.get("tplus1_tradable_recent_4q_mean_window_rank_ic")),
                "mean_window_sortino": row.get("mean_window_sortino", row.get("tplus1_tradable_recent_4q_mean_window_sortino")),
                "objective": round(_objective(row), 6),
            }
            for row in anchors[:5]
        ],
        "top_residual_mixes": [
            {
                "candidate_id": row.get("candidate_id"),
                "momentum_window": row.get("momentum_window"),
                "gap_window": row.get("gap_window"),
                "momentum_weight": row.get("momentum_weight"),
                "gap_weight": row.get("gap_weight"),
                "mean_window_rank_ic": row.get("mean_window_rank_ic", row.get("tplus1_tradable_recent_4q_mean_window_rank_ic")),
                "mean_window_sortino": row.get("mean_window_sortino", row.get("tplus1_tradable_recent_4q_mean_window_sortino")),
                "objective": round(_objective(row), 6),
            }
            for row in mixes[:8]
        ],
    }


def build_v12_tplus1_residual_ledger(tplus1_report: Path | str | dict[str, Any]) -> dict[str, Any]:
    surface = infer_v12_tplus1_residual_surface(tplus1_report)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(record: dict[str, Any]) -> None:
        canonical = rank_validation_canonical_expression(str(record["expression"]))
        if canonical in seen:
            return
        seen.add(canonical)
        records.append(
            {
                "candidate_id": f"v12-tplus1-{len(records) + 1:04d}",
                "retained": True,
                "source_mode": "search_core_v12_tplus1_natural_residual_surface",
                "canonical_rank_validation_expression": canonical,
                **record,
            }
        )

    for momentum_window in surface["momentum_window_grid"]:
        add(
            {
                "expression": _rank_expression("a5_momentum", int(momentum_window)),
                "frontier_lane": "search_core_v12_tplus1_momentum_anchor",
                "archive_cell": "v12_tplus1_momentum_anchor",
                "primitive_family": "a5_momentum",
                "proposal_kind": "tplus1_natural_momentum_anchor",
                "window": int(momentum_window),
            }
        )

    for momentum_window in surface["momentum_window_grid"]:
        for gap_window in surface["gap_window_grid"]:
            for gap_weight in surface["gap_residual_weight_grid"]:
                if gap_weight <= 0:
                    continue
                momentum_weight = round(1.0 - float(gap_weight), 3)
                expression = (
                    "CSRank(Add("
                    f"Mul({momentum_weight},ZScore({_base_expression('a5_momentum', int(momentum_window))})),"
                    f"Mul({gap_weight},ZScore({_base_expression('a5_gap', int(gap_window))}))"
                    "))"
                )
                add(
                    {
                        "expression": expression,
                        "frontier_lane": "search_core_v12_tplus1_gap_residual",
                        "archive_cell": "v12_tplus1_momentum_gap_residual",
                        "primitive_family": "a5_momentum+a5_gap",
                        "proposal_kind": "tplus1_natural_gap_residual_weight",
                        "momentum_window": int(momentum_window),
                        "gap_window": int(gap_window),
                        "momentum_weight": momentum_weight,
                        "gap_weight": float(gap_weight),
                    }
                )

    for window in [7, 8, 9, 10, 11]:
        add(
            {
                "expression": _rank_expression("a5_volatility", window),
                "frontier_lane": "search_core_v12_tplus1_volatility_shadow",
                "archive_cell": "v12_tplus1_volatility_shadow",
                "primitive_family": "a5_volatility",
                "proposal_kind": "tplus1_volatility_shadow_anchor",
                "window": window,
            }
        )

    return {
        "run_id": "phase2-search-core-v12-tplus1-residual-ledger",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V12_VERSION,
        "scope": "tplus1_tradable_natural_momentum_residual_generation",
        "surface_report": surface,
        "record_count": len(records),
        "records": records,
    }


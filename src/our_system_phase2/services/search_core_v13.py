from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression


SEARCH_CORE_V13_VERSION = "phase2-search-core-v13-tplus1-higher-order-momentum-2026-04-26"


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


def _rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    return list(report.get("evaluations", report.get("records", [])))


def _momentum(window: int) -> str:
    return f"Mom($close,{window})"


def _rank(expression: str) -> str:
    return f"CSRank({expression})"


def infer_v13_higher_order_surface(tplus1_report: Path | str | dict[str, Any]) -> dict[str, Any]:
    report = _read_report(tplus1_report)
    rows = [row for row in _rows(report) if row.get("passes_real_market_smoke", True)]
    momentum_anchors = [
        row
        for row in rows
        if row.get("primitive_family") == "a5_momentum" and row.get("window") is not None
    ]
    if not momentum_anchors:
        raise ValueError("no_tplus1_momentum_anchor_rows")
    momentum_anchors = sorted(momentum_anchors, key=_objective, reverse=True)
    center = int(momentum_anchors[0]["window"])
    momentum_windows = sorted({max(2, center - 1), center, center + 1})
    short_windows = sorted({max(2, center // 2), max(2, center // 2 + 1)})
    long_windows = sorted({center, center + 1, center + 2})
    smoothing_windows = sorted({2, 3, 4})
    slope_lags = sorted({1, 2, 3})
    vol_windows = sorted({max(3, center - 1), center, center + 2})
    moment_windows = sorted({max(5, center - 1), center, center + 1})
    return {
        "run_id": "phase2-search-core-v13-tplus1-higher-order-surface",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V13_VERSION,
        "source_run_id": report.get("source_run_id"),
        "source_execution_policy": report.get("execution_policy"),
        "source_screening_mode": report.get("screening_mode"),
        "center_momentum_window": center,
        "momentum_window_grid": momentum_windows,
        "short_window_grid": short_windows,
        "long_window_grid": long_windows,
        "smoothing_window_grid": smoothing_windows,
        "slope_lag_grid": slope_lags,
        "volatility_window_grid": vol_windows,
        "moment_shape_window_grid": moment_windows,
        "top_momentum_anchors": [
            {
                "candidate_id": row.get("candidate_id"),
                "window": row.get("window"),
                "mean_window_rank_ic": row.get("mean_window_rank_ic", row.get("tplus1_tradable_recent_4q_mean_window_rank_ic")),
                "mean_window_sortino": row.get("mean_window_sortino", row.get("tplus1_tradable_recent_4q_mean_window_sortino")),
                "objective": round(_objective(row), 6),
            }
            for row in momentum_anchors[:5]
        ],
    }


def build_v13_higher_order_momentum_ledger(tplus1_report: Path | str | dict[str, Any]) -> dict[str, Any]:
    surface = infer_v13_higher_order_surface(tplus1_report)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(record: dict[str, Any]) -> None:
        canonical = rank_validation_canonical_expression(str(record["expression"]))
        if canonical in seen:
            return
        seen.add(canonical)
        records.append(
            {
                "candidate_id": f"v13-tplus1-{len(records) + 1:04d}",
                "retained": True,
                "source_mode": "search_core_v13_tplus1_higher_order_momentum",
                "canonical_rank_validation_expression": canonical,
                **record,
            }
        )

    for window in surface["momentum_window_grid"]:
        add(
            {
                "expression": _rank(_momentum(int(window))),
                "frontier_lane": "search_core_v13_tplus1_momentum_anchor",
                "archive_cell": "v13_momentum_anchor",
                "primitive_family": "a5_momentum",
                "proposal_kind": "tplus1_momentum_anchor",
                "window": int(window),
            }
        )

    for window in surface["momentum_window_grid"]:
        for smooth in surface["smoothing_window_grid"]:
            add(
                {
                    "expression": _rank(f"Mean({_momentum(int(window))},{int(smooth)})"),
                    "frontier_lane": "search_core_v13_tplus1_smoothed_momentum",
                    "archive_cell": "v13_smoothed_momentum",
                    "primitive_family": "a5_momentum_smooth",
                    "proposal_kind": "higher_order_smoothed_momentum",
                    "window": int(window),
                    "smoothing_window": int(smooth),
                }
            )
            add(
                {
                    "expression": _rank(f"Mom(WMA($close,{int(smooth)}),{int(window)})"),
                    "frontier_lane": "search_core_v13_tplus1_wma_momentum",
                    "archive_cell": "v13_wma_momentum",
                    "primitive_family": "a5_momentum_wma",
                    "proposal_kind": "higher_order_wma_price_momentum",
                    "window": int(window),
                    "smoothing_window": int(smooth),
                }
            )

    for short in surface["short_window_grid"]:
        for long in surface["long_window_grid"]:
            if int(short) >= int(long):
                continue
            add(
                {
                    "expression": _rank(f"Sub({_momentum(int(short))},{_momentum(int(long))})"),
                    "frontier_lane": "search_core_v13_tplus1_momentum_acceleration",
                    "archive_cell": "v13_momentum_acceleration",
                    "primitive_family": "a5_momentum_acceleration",
                    "proposal_kind": "higher_order_momentum_acceleration",
                    "short_window": int(short),
                    "long_window": int(long),
                }
            )

    for window in surface["momentum_window_grid"]:
        for lag in surface["slope_lag_grid"]:
            add(
                {
                    "expression": _rank(f"Div(Sub({_momentum(int(window))},Delay({_momentum(int(window))},{int(lag)})),{int(lag)})"),
                    "frontier_lane": "search_core_v13_tplus1_momentum_slope",
                    "archive_cell": "v13_momentum_slope",
                    "primitive_family": "a5_momentum_slope",
                    "proposal_kind": "higher_order_momentum_slope",
                    "window": int(window),
                    "slope_lag": int(lag),
                }
            )
            add(
                {
                    "expression": _rank(
                        "Sub("
                        f"Sub({_momentum(int(window))},Delay({_momentum(int(window))},{int(lag)})),"
                        f"Sub(Delay({_momentum(int(window))},{int(lag)}),Delay({_momentum(int(window))},{int(lag * 2)}))"
                        ")"
                    ),
                    "frontier_lane": "search_core_v13_tplus1_momentum_curvature",
                    "archive_cell": "v13_momentum_curvature",
                    "primitive_family": "a5_momentum_curvature",
                    "proposal_kind": "higher_order_momentum_curvature",
                    "window": int(window),
                    "slope_lag": int(lag),
                }
            )

    for window in surface["momentum_window_grid"]:
        for vol_window in surface["volatility_window_grid"]:
            add(
                {
                    "expression": _rank(f"Div({_momentum(int(window))},Std($ret,{int(vol_window)}))"),
                    "frontier_lane": "search_core_v13_tplus1_vol_normalized_momentum",
                    "archive_cell": "v13_vol_normalized_momentum",
                    "primitive_family": "a5_vol_normalized_momentum",
                    "proposal_kind": "higher_order_vol_normalized_momentum",
                    "window": int(window),
                    "volatility_window": int(vol_window),
                }
            )

    for window in surface["moment_shape_window_grid"]:
        add(
            {
                "expression": _rank(f"Skew($ret,{int(window)})"),
                "frontier_lane": "search_core_v13_tplus1_higher_moment_shadow",
                "archive_cell": "v13_higher_moment_shadow",
                "primitive_family": "a5_return_skew_shadow",
                "proposal_kind": "higher_order_return_skew_shadow",
                "window": int(window),
            }
        )
        add(
            {
                "expression": _rank(f"Kurt($ret,{int(window)})"),
                "frontier_lane": "search_core_v13_tplus1_higher_moment_shadow",
                "archive_cell": "v13_higher_moment_shadow",
                "primitive_family": "a5_return_kurt_shadow",
                "proposal_kind": "higher_order_return_kurt_shadow",
                "window": int(window),
            }
        )

    return {
        "run_id": "phase2-search-core-v13-tplus1-higher-order-ledger",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V13_VERSION,
        "scope": "tplus1_tradable_higher_order_momentum_generation",
        "surface_report": surface,
        "record_count": len(records),
        "records": records,
    }


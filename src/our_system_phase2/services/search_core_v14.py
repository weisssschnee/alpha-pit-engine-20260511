from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression


SEARCH_CORE_V14_VERSION = "phase2-search-core-v14-tplus1-curvature-volnorm-manifold-2026-04-26"


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


def _rank(expression: str) -> str:
    return f"CSRank({expression})"


def _price_base(transform: str, smooth_window: int | None) -> str:
    if transform in {"raw", "mean_signal"}:
        return "$close"
    if transform == "wma_price":
        return f"WMA($close,{int(smooth_window or 2)})"
    raise ValueError(f"unsupported_price_transform:{transform}")


def _momentum(window: int, *, transform: str = "raw", smooth_window: int | None = None) -> str:
    return f"Mom({_price_base(transform, smooth_window)},{window})"


def _smooth_signal(signal: str, transform: str, smooth_window: int | None) -> str:
    if transform == "raw":
        return signal
    if transform == "mean_signal":
        return f"Mean({signal},{int(smooth_window or 2)})"
    if transform == "wma_price":
        return signal
    raise ValueError(f"unsupported_signal_transform:{transform}")


def _curvature(signal: str, lag: int) -> str:
    return f"Sub(Sub({signal},Delay({signal},{lag})),Sub(Delay({signal},{lag}),Delay({signal},{lag * 2})))"


def _vol_denominator(kind: str, window: int) -> str:
    if kind == "std_ret":
        return f"Std($ret,{window})"
    if kind == "mean_abs_ret":
        return f"Mean(Abs($ret),{window})"
    raise ValueError(f"unsupported_denominator:{kind}")


def infer_v14_curvature_volnorm_surface(tplus1_report: Path | str | dict[str, Any]) -> dict[str, Any]:
    report = _read_report(tplus1_report)
    rows = [row for row in _rows(report) if row.get("passes_real_market_smoke", True)]
    curvature_rows = [
        row
        for row in rows
        if row.get("proposal_kind") == "higher_order_momentum_curvature"
        and row.get("window") is not None
    ]
    volnorm_rows = [
        row
        for row in rows
        if row.get("proposal_kind") == "higher_order_vol_normalized_momentum"
        and row.get("window") is not None
    ]
    if not curvature_rows and not volnorm_rows:
        raise ValueError("no_v13_winning_manifold_rows")

    curvature_rows = sorted(curvature_rows, key=_objective, reverse=True)
    volnorm_rows = sorted(volnorm_rows, key=_objective, reverse=True)
    center_window = int((curvature_rows or volnorm_rows)[0]["window"])
    numerator_center = int((volnorm_rows or curvature_rows)[0]["window"])
    curvature_windows = sorted({max(2, center_window - 1), center_window, center_window + 1})
    numerator_windows = sorted({max(2, numerator_center - 1), numerator_center, numerator_center + 1})
    denominator_center = int((volnorm_rows[0].get("volatility_window") or numerator_center - 1) if volnorm_rows else max(2, numerator_center - 1))
    denominator_windows = sorted({max(2, denominator_center - 2), max(2, denominator_center - 1), denominator_center, denominator_center + 1})
    return {
        "run_id": "phase2-search-core-v14-tplus1-curvature-volnorm-surface",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V14_VERSION,
        "source_run_id": report.get("source_run_id"),
        "source_execution_policy": report.get("execution_policy"),
        "source_screening_mode": report.get("screening_mode"),
        "curvature_window_grid": curvature_windows,
        "curvature_lag_grid": [1, 2],
        "curvature_transform_grid": ["raw", "mean_signal", "wma_price"],
        "smoothing_window_grid": [2, 3],
        "volnorm_numerator_window_grid": numerator_windows,
        "volnorm_denominator_window_grid": denominator_windows,
        "volnorm_denominator_grid": ["std_ret", "mean_abs_ret"],
        "top_curvature": [
            {
                "candidate_id": row.get("candidate_id"),
                "window": row.get("window"),
                "slope_lag": row.get("slope_lag"),
                "mean_window_rank_ic": row.get("mean_window_rank_ic", row.get("tplus1_tradable_recent_4q_mean_window_rank_ic")),
                "mean_window_sortino": row.get("mean_window_sortino", row.get("tplus1_tradable_recent_4q_mean_window_sortino")),
                "objective": round(_objective(row), 6),
            }
            for row in curvature_rows[:5]
        ],
        "top_volnorm": [
            {
                "candidate_id": row.get("candidate_id"),
                "window": row.get("window"),
                "volatility_window": row.get("volatility_window"),
                "mean_window_rank_ic": row.get("mean_window_rank_ic", row.get("tplus1_tradable_recent_4q_mean_window_rank_ic")),
                "mean_window_sortino": row.get("mean_window_sortino", row.get("tplus1_tradable_recent_4q_mean_window_sortino")),
                "objective": round(_objective(row), 6),
            }
            for row in volnorm_rows[:5]
        ],
    }


def build_v14_curvature_volnorm_ledger(tplus1_report: Path | str | dict[str, Any]) -> dict[str, Any]:
    surface = infer_v14_curvature_volnorm_surface(tplus1_report)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(record: dict[str, Any]) -> None:
        canonical = rank_validation_canonical_expression(str(record["expression"]))
        if canonical in seen:
            return
        seen.add(canonical)
        records.append(
            {
                "candidate_id": f"v14-tplus1-{len(records) + 1:04d}",
                "retained": True,
                "source_mode": "search_core_v14_tplus1_curvature_volnorm_manifold",
                "canonical_rank_validation_expression": canonical,
                **record,
            }
        )

    for window in surface["curvature_window_grid"]:
        for lag in surface["curvature_lag_grid"]:
            for transform in surface["curvature_transform_grid"]:
                smooth_options = surface["smoothing_window_grid"] if transform in {"mean_signal", "wma_price"} else [None]
                for smooth_window in smooth_options:
                    raw_momentum = _momentum(int(window), transform=transform, smooth_window=smooth_window)
                    signal = _smooth_signal(raw_momentum, transform, smooth_window)
                    add(
                        {
                            "expression": _rank(_curvature(signal, int(lag))),
                            "frontier_lane": "search_core_v14_tplus1_momentum_curvature",
                            "archive_cell": "v14_momentum_curvature_manifold",
                            "primitive_family": "a5_momentum_curvature",
                            "proposal_kind": "v14_momentum_curvature_manifold",
                            "window": int(window),
                            "slope_lag": int(lag),
                            "base_transform": transform,
                            "smoothing_window": None if smooth_window is None else int(smooth_window),
                        }
                    )

    for numerator_window in surface["volnorm_numerator_window_grid"]:
        for denominator_window in surface["volnorm_denominator_window_grid"]:
            for denominator_kind in surface["volnorm_denominator_grid"]:
                add(
                    {
                        "expression": _rank(
                            f"Div({_momentum(int(numerator_window))},{_vol_denominator(denominator_kind, int(denominator_window))})"
                        ),
                        "frontier_lane": "search_core_v14_tplus1_vol_normalized_momentum",
                        "archive_cell": "v14_vol_normalized_momentum_manifold",
                        "primitive_family": "a5_vol_normalized_momentum",
                        "proposal_kind": "v14_vol_normalized_momentum_manifold",
                        "window": int(numerator_window),
                        "numerator_window": int(numerator_window),
                        "denominator_window": int(denominator_window),
                        "volatility_window": int(denominator_window) if denominator_kind == "std_ret" else None,
                        "denominator_family": denominator_kind,
                    }
                )

    return {
        "run_id": "phase2-search-core-v14-tplus1-curvature-volnorm-ledger",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V14_VERSION,
        "scope": "tplus1_tradable_curvature_and_volnorm_manifold_generation",
        "surface_report": surface,
        "record_count": len(records),
        "records": records,
    }

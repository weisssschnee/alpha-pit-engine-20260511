from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression
from our_system_phase2.services.search_core_v16 import quarter_floor_stats


SEARCH_CORE_V19_VERSION = "phase2-search-core-v19-continuous-kernel-residual-2026-04-26"
V18_CENTER_SIGNAL = "Div(Mom($close,8),Mean(Mean(Abs($ret),2),2))"


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


def _term(weight: float, expression: str) -> str:
    if abs(weight - 1.0) < 1e-12:
        return expression
    return f"Mul({weight:.6g},{expression})"


def _add_many(expressions: list[str]) -> str:
    if not expressions:
        raise ValueError("empty_weighted_kernel")
    current = expressions[0]
    for expression in expressions[1:]:
        current = f"Add({current},{expression})"
    return current


def _weighted_kernel(components: list[tuple[float, str]]) -> str:
    non_zero = [(float(weight), expression) for weight, expression in components if abs(float(weight)) > 1e-12]
    total = sum(weight for weight, _expression in non_zero)
    if total <= 0.0:
        raise ValueError("kernel_weights_must_sum_positive")
    normalized = [(weight / total, expression) for weight, expression in non_zero]
    return _add_many([_term(weight, expression) for weight, expression in normalized])


def _mean_abs(window: int) -> str:
    return f"Mean(Abs($ret),{window})"


def _wma_abs(window: int) -> str:
    return f"WMA(Abs($ret),{window})"


def _nested_mean_abs(inner: int, outer: int) -> str:
    return f"Mean(Mean(Abs($ret),{inner}),{outer})"


def _kernel_specs() -> list[dict[str, Any]]:
    center = _nested_mean_abs(2, 2)
    raw_specs = [
        {
            "kernel_id": "center_mean2x2",
            "kernel_expression": center,
            "effective_horizon": 2.0,
            "kernel_shape": "center",
            "weights": {"mean2x2": 1.0},
        },
        {
            "kernel_id": "mean2x2_80_mean3_20",
            "kernel_expression": _weighted_kernel([(0.8, center), (0.2, _mean_abs(3))]),
            "effective_horizon": 2.2,
            "kernel_shape": "continuous_blend",
            "weights": {"mean2x2": 0.8, "mean3": 0.2},
        },
        {
            "kernel_id": "mean2x2_60_mean3_40",
            "kernel_expression": _weighted_kernel([(0.6, center), (0.4, _mean_abs(3))]),
            "effective_horizon": 2.4,
            "kernel_shape": "continuous_blend",
            "weights": {"mean2x2": 0.6, "mean3": 0.4},
        },
        {
            "kernel_id": "mean2x2_80_wma3_20",
            "kernel_expression": _weighted_kernel([(0.8, center), (0.2, _wma_abs(3))]),
            "effective_horizon": 2.2,
            "kernel_shape": "continuous_blend",
            "weights": {"mean2x2": 0.8, "wma3": 0.2},
        },
        {
            "kernel_id": "mean2x2_60_wma3_40",
            "kernel_expression": _weighted_kernel([(0.6, center), (0.4, _wma_abs(3))]),
            "effective_horizon": 2.4,
            "kernel_shape": "continuous_blend",
            "weights": {"mean2x2": 0.6, "wma3": 0.4},
        },
        {
            "kernel_id": "mean2x2_70_std3_30",
            "kernel_expression": _weighted_kernel([(0.7, center), (0.3, "Std($ret,3)")]),
            "effective_horizon": 2.3,
            "kernel_shape": "risk_blend",
            "weights": {"mean2x2": 0.7, "std3": 0.3},
        },
        {
            "kernel_id": "mean2x2_50_mean3_30_wma4_20",
            "kernel_expression": _weighted_kernel([(0.5, center), (0.3, _mean_abs(3)), (0.2, _wma_abs(4))]),
            "effective_horizon": 2.7,
            "kernel_shape": "three_point_continuous_blend",
            "weights": {"mean2x2": 0.5, "mean3": 0.3, "wma4": 0.2},
        },
        {
            "kernel_id": "mean2x2_50_wma3_30_mean4_20",
            "kernel_expression": _weighted_kernel([(0.5, center), (0.3, _wma_abs(3)), (0.2, _mean_abs(4))]),
            "effective_horizon": 2.7,
            "kernel_shape": "three_point_continuous_blend",
            "weights": {"mean2x2": 0.5, "wma3": 0.3, "mean4": 0.2},
        },
        {
            "kernel_id": "mean2x2_40_mean3_40_mean4_20",
            "kernel_expression": _weighted_kernel([(0.4, center), (0.4, _mean_abs(3)), (0.2, _mean_abs(4))]),
            "effective_horizon": 2.8,
            "kernel_shape": "three_point_continuous_blend",
            "weights": {"mean2x2": 0.4, "mean3": 0.4, "mean4": 0.2},
        },
        {
            "kernel_id": "mean2x2_90_mean3_10",
            "kernel_expression": _weighted_kernel([(0.9, center), (0.1, _mean_abs(3))]),
            "effective_horizon": 2.1,
            "kernel_shape": "fine_center_blend",
            "weights": {"mean2x2": 0.9, "mean3": 0.1},
        },
    ]
    return raw_specs


def infer_v19_continuous_kernel_surface(v18_report: Path | str | dict[str, Any]) -> dict[str, Any]:
    report = _read_report(v18_report)
    candidates: list[dict[str, Any]] = []
    for row in _rows(report):
        if not row.get("passes_real_market_smoke", True):
            continue
        enriched = {**row, **quarter_floor_stats(row)}
        if enriched.get("quarter_floor_pass"):
            candidates.append(enriched)
    if not candidates:
        raise ValueError("no_v18_stable_candidates")
    candidates.sort(
        key=lambda row: (
            _metric(row.get("quarter_floor_score"), -999.0),
            _metric(row.get("mean_window_rank_ic"), -999.0),
        ),
        reverse=True,
    )
    top = candidates[0]
    return {
        "run_id": "phase2-search-core-v19-continuous-kernel-surface",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V19_VERSION,
        "source_run_id": report.get("run_id") or report.get("source_run_id"),
        "source_execution_policy": report.get("execution_policy"),
        "source_screening_mode": report.get("screening_mode"),
        "center_candidate_id": top.get("candidate_id"),
        "center_expression": top.get("expression"),
        "center_signal_expression": V18_CENTER_SIGNAL,
        "center_quarter_floor_score": top.get("quarter_floor_score"),
        "numerator_window_grid": [8, 9],
        "kernel_specs": _kernel_specs(),
        "orthogonalization_modes": ["raw", "cs_residual_to_v18_center"],
        "top_v18_reference_candidates": [
            {
                "candidate_id": row.get("candidate_id"),
                "expression": row.get("expression"),
                "mean_window_rank_ic": row.get("mean_window_rank_ic"),
                "mean_window_sortino": row.get("mean_window_sortino"),
                "min_quarter_ic": row.get("min_quarter_ic"),
                "quarter_floor_score": row.get("quarter_floor_score"),
            }
            for row in candidates[:6]
        ],
    }


def build_v19_continuous_kernel_ledger(v18_report: Path | str | dict[str, Any]) -> dict[str, Any]:
    surface = infer_v19_continuous_kernel_surface(v18_report)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(record: dict[str, Any]) -> None:
        canonical = rank_validation_canonical_expression(str(record["expression"]))
        if canonical in seen:
            return
        seen.add(canonical)
        records.append(
            {
                "candidate_id": f"v19-tplus1-{len(records) + 1:04d}",
                "retained": True,
                "source_mode": "search_core_v19_continuous_kernel_residual",
                "canonical_rank_validation_expression": canonical,
                **record,
            }
        )

    for numerator_window in surface["numerator_window_grid"]:
        numerator = f"Mom($close,{int(numerator_window)})"
        for kernel in surface["kernel_specs"]:
            base_signal = f"Div({numerator},{kernel['kernel_expression']})"
            for mode in surface["orthogonalization_modes"]:
                signal = (
                    base_signal
                    if mode == "raw"
                    else f"CSResidual({base_signal},{surface['center_signal_expression']})"
                )
                add(
                    {
                        "expression": _rank(signal),
                        "frontier_lane": "search_core_v19_continuous_kernel",
                        "archive_cell": "v19_continuous_kernel_center_orthogonal",
                        "primitive_family": "a5_vol_normalized_momentum",
                        "proposal_kind": "v19_continuous_denominator_kernel",
                        "research_track": "continuous_kernel_residual_audit",
                        "quarter_floor_required": True,
                        "regime_conditional_audit": False,
                        "turnover_cost_shadow_required": mode == "raw",
                        "center_overlap_audit_required": True,
                        "center_signal_expression": surface["center_signal_expression"],
                        "orthogonalization_mode": mode,
                        "window": int(numerator_window),
                        "numerator_window": int(numerator_window),
                        "denominator_kernel_id": kernel["kernel_id"],
                        "denominator_kernel_expression": kernel["kernel_expression"],
                        "denominator_kernel_shape": kernel["kernel_shape"],
                        "denominator_kernel_weights": kernel["weights"],
                        "effective_denominator_horizon": kernel["effective_horizon"],
                    }
                )

    return {
        "run_id": "phase2-search-core-v19-tplus1-continuous-kernel-ledger",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V19_VERSION,
        "scope": "continuous_weighted_denominator_kernels_and_v18_center_residuals",
        "surface_report": surface,
        "record_count": len(records),
        "records": records,
    }


def build_v19_compact_validation_ledger(v19_ledger: Path | str | dict[str, Any]) -> dict[str, Any]:
    ledger = _read_report(v19_ledger)
    records = list(ledger.get("records", []))
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    raw_keep = {
        "center_mean2x2",
        "mean2x2_90_mean3_10",
        "mean2x2_80_mean3_20",
        "mean2x2_60_mean3_40",
        "mean2x2_80_wma3_20",
        "mean2x2_70_std3_30",
        "mean2x2_50_mean3_30_wma4_20",
    }
    residual_keep = {
        "center_mean2x2",
        "mean2x2_80_mean3_20",
        "mean2x2_60_mean3_40",
        "mean2x2_80_wma3_20",
        "mean2x2_70_std3_30",
    }

    def add(record: dict[str, Any]) -> None:
        canonical = str(record.get("canonical_rank_validation_expression") or record.get("expression"))
        if canonical in seen:
            return
        seen.add(canonical)
        selected.append(record)

    for record in records:
        kernel_id = str(record.get("denominator_kernel_id"))
        mode = str(record.get("orthogonalization_mode"))
        if mode == "raw" and kernel_id in raw_keep:
            add(record)
        elif mode == "cs_residual_to_v18_center" and kernel_id in residual_keep:
            add(record)

    return {
        "run_id": "phase2-search-core-v19-tplus1-compact-validation-ledger",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V19_VERSION,
        "scope": "compact_validation_subset_continuous_kernels_plus_residuals",
        "source_run_id": ledger.get("run_id"),
        "surface_report": ledger.get("surface_report"),
        "selection_policy": {
            "raw_kernel_ids": sorted(raw_keep),
            "residual_kernel_ids": sorted(residual_keep),
            "numerator_windows": [8, 9],
            "center_overlap_audit_required": True,
        },
        "record_count": len(selected),
        "records": selected,
    }

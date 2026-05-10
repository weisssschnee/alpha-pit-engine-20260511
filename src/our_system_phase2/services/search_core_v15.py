from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression


SEARCH_CORE_V15_VERSION = "phase2-search-core-v15-tplus1-robust-denominator-topology-2026-04-26"


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


def _momentum(window: int) -> str:
    return f"Mom($close,{window})"


def _downside_abs_ret() -> str:
    return "Div(Sub(Abs($ret),$ret),2)"


def _denominator(kind: str, window: int) -> str:
    if kind == "std_ret":
        return f"Std($ret,{window})"
    if kind == "mean_abs_ret":
        return f"Mean(Abs($ret),{window})"
    if kind == "med_abs_ret":
        return f"Med(Abs($ret),{window})"
    if kind == "wma_abs_ret":
        return f"WMA(Abs($ret),{window})"
    if kind == "mean_downside_abs_ret":
        return f"Mean({_downside_abs_ret()},{window})"
    if kind == "med_downside_abs_ret":
        return f"Med({_downside_abs_ret()},{window})"
    if kind == "wma_downside_abs_ret":
        return f"WMA({_downside_abs_ret()},{window})"
    raise ValueError(f"unsupported_denominator:{kind}")


def infer_v15_robust_denominator_surface(tplus1_report: Path | str | dict[str, Any]) -> dict[str, Any]:
    report = _read_report(tplus1_report)
    rows = [row for row in _rows(report) if row.get("passes_real_market_smoke", True)]
    volnorm_rows = [
        row
        for row in rows
        if row.get("primitive_family") == "a5_vol_normalized_momentum"
        and row.get("numerator_window", row.get("window")) is not None
        and row.get("denominator_window", row.get("volatility_window")) is not None
    ]
    if not volnorm_rows:
        raise ValueError("no_tplus1_vol_normalized_rows")
    volnorm_rows = sorted(volnorm_rows, key=_objective, reverse=True)
    top = volnorm_rows[0]
    numerator_center = int(top.get("numerator_window") or top["window"])
    denominator_center = int(top.get("denominator_window") or top.get("volatility_window"))
    numerator_windows = sorted({max(2, numerator_center - 1), numerator_center, numerator_center + 1})
    denominator_windows = sorted({max(2, denominator_center - 1), denominator_center, denominator_center + 1})
    return {
        "run_id": "phase2-search-core-v15-tplus1-robust-denominator-surface",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V15_VERSION,
        "source_run_id": report.get("source_run_id"),
        "source_execution_policy": report.get("execution_policy"),
        "source_screening_mode": report.get("screening_mode"),
        "top_volnorm_candidate_id": top.get("candidate_id"),
        "top_numerator_window": numerator_center,
        "top_denominator_window": denominator_center,
        "numerator_window_grid": numerator_windows,
        "denominator_window_grid": denominator_windows,
        "denominator_family_grid": [
            "mean_abs_ret",
            "med_abs_ret",
            "wma_abs_ret",
            "mean_downside_abs_ret",
            "med_downside_abs_ret",
            "wma_downside_abs_ret",
            "std_ret",
        ],
        "top_volnorm_rows": [
            {
                "candidate_id": row.get("candidate_id"),
                "window": row.get("window"),
                "numerator_window": row.get("numerator_window"),
                "denominator_window": row.get("denominator_window"),
                "denominator_family": row.get("denominator_family"),
                "mean_window_rank_ic": row.get("mean_window_rank_ic", row.get("tplus1_tradable_recent_4q_mean_window_rank_ic")),
                "mean_window_sortino": row.get("mean_window_sortino", row.get("tplus1_tradable_recent_4q_mean_window_sortino")),
                "objective": round(_objective(row), 6),
            }
            for row in volnorm_rows[:8]
        ],
    }


def build_v15_robust_denominator_ledger(tplus1_report: Path | str | dict[str, Any]) -> dict[str, Any]:
    surface = infer_v15_robust_denominator_surface(tplus1_report)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(record: dict[str, Any]) -> None:
        canonical = rank_validation_canonical_expression(str(record["expression"]))
        if canonical in seen:
            return
        seen.add(canonical)
        records.append(
            {
                "candidate_id": f"v15-tplus1-{len(records) + 1:04d}",
                "retained": True,
                "source_mode": "search_core_v15_tplus1_robust_denominator_topology",
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
                        "frontier_lane": "search_core_v15_tplus1_robust_denominator",
                        "archive_cell": "v15_robust_denominator_topology",
                        "primitive_family": "a5_vol_normalized_momentum",
                        "proposal_kind": "v15_robust_denominator_topology",
                        "window": int(numerator_window),
                        "numerator_window": int(numerator_window),
                        "denominator_window": int(denominator_window),
                        "volatility_window": int(denominator_window) if denominator_family == "std_ret" else None,
                        "denominator_family": denominator_family,
                    }
                )

    return {
        "run_id": "phase2-search-core-v15-tplus1-robust-denominator-ledger",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V15_VERSION,
        "scope": "tplus1_tradable_robust_denominator_topology_generation",
        "surface_report": surface,
        "record_count": len(records),
        "records": records,
    }


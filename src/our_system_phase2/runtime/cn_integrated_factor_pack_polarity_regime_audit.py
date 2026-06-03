"""Polarity and regime audit for integrated factor pack candidates.

This is a diagnostic follow-up to the X0/R3 marginal audit. It does not search,
change X0/R3, or promote candidates. It answers whether signal-new integrated
RZRQ candidates failed because direction was wrong, R3 was the wrong regime, or
the candidates were simply weak daily-proxy alphas in this short OOS window.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.runtime.cn_integrated_factor_pack_x0_marginal_audit import (
    DEFAULT_SIGNAL_NOVELTY_ROWS,
    _as_bool,
    _book_row,
    _candidate_rows,
    _safe_float,
    _write_csv,
)
from our_system_phase2.runtime.cn_underutilized_field_book_marginal_audit import (
    DEFAULT_R3_GATE_LEDGER,
    _build_x0_base_from_locked_gate,
    _load_frame,
    _resolve_x0_daily,
)
from our_system_phase2.runtime.phase3ab_candidate_deep_validation import (
    OOS_2026_END,
    OOS_2026_START,
    SIGNAL_CLOCK_AFTER_OPEN,
    TRAIN_2025H2_END,
    TRAIN_2025H2_START,
    _candidate_daily,
    _metrics,
    _round,
)
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_validation import _signal_evaluation_frame


VERSION = "cn-integrated-factor-pack-polarity-regime-audit-v1-2026-06-03"
DEFAULT_OUTPUT_ROOT = Path("reports/cn_integrated_factor_pack_v2_polarity_regime_audit_20260603")


def _metrics_row(prefix: str, values: pd.Series) -> dict[str, Any]:
    metrics = _metrics(pd.to_numeric(values, errors="coerce").dropna())
    return {f"{prefix}_{key}": value for key, value in metrics.items()}


def _daily_returns(
    row: dict[str, str],
    *,
    frame: pd.DataFrame,
    signal_frame: pd.DataFrame,
    field_lags: dict[str, int],
    top_bottom_quantile: float,
    polarity: str,
) -> tuple[pd.Series | None, pd.Series | None, str | None]:
    expression = str(row.get("expression") or "")
    use_expression = expression if polarity == "original" else f"Neg({expression})"
    try:
        daily = _candidate_daily(
            frame,
            signal_frame,
            field_lags,
            use_expression,
            top_bottom_quantile=top_bottom_quantile,
        )
    except Exception as exc:  # noqa: BLE001 - audit should continue.
        return None, None, f"{type(exc).__name__}:{str(exc)[:300]}"
    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
    daily = daily.dropna(subset=["date"]).sort_values("date")
    returns = pd.to_numeric(daily["long_net_10bps"], errors="coerce").fillna(0.0)
    turnover = pd.to_numeric(daily["average_one_way_turnover"], errors="coerce")
    return (
        pd.Series(returns.to_numpy(), index=daily["date"], name=str(row.get("candidate_id") or "")),
        pd.Series(turnover.to_numpy(), index=daily["date"], name=str(row.get("candidate_id") or "")),
        None,
    )


def _window_masks(index: pd.Index, r3: pd.Series) -> dict[str, pd.Series]:
    dates = pd.Series(pd.to_datetime(index), index=index)
    r3_aligned = r3.reindex(index).fillna(False).astype(bool)
    return {
        "train_2025h2_all": (dates >= TRAIN_2025H2_START) & (dates <= TRAIN_2025H2_END),
        "train_2025h2_r3_on": (dates >= TRAIN_2025H2_START) & (dates <= TRAIN_2025H2_END) & r3_aligned,
        "train_2025h2_r3_off": (dates >= TRAIN_2025H2_START) & (dates <= TRAIN_2025H2_END) & ~r3_aligned,
        "oos_2026_all": (dates >= OOS_2026_START) & (dates <= OOS_2026_END),
        "oos_2026_r3_on": (dates >= OOS_2026_START) & (dates <= OOS_2026_END) & r3_aligned,
        "oos_2026_r3_off": (dates >= OOS_2026_START) & (dates <= OOS_2026_END) & ~r3_aligned,
    }


def _candidate_metric_rows(
    rows: list[dict[str, str]],
    returns_by_key: dict[tuple[str, str], pd.Series],
    turnover_by_key: dict[tuple[str, str], pd.Series],
    *,
    r3: pd.Series,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        candidate_id = str(row.get("candidate_id") or "")
        for polarity in ("original", "reversed"):
            ret = returns_by_key.get((candidate_id, polarity))
            if ret is None:
                continue
            turnover = turnover_by_key.get((candidate_id, polarity), pd.Series(dtype=float)).reindex(ret.index)
            for window, mask in _window_masks(ret.index, r3).items():
                use = ret.loc[mask]
                turn = pd.to_numeric(turnover.loc[mask], errors="coerce")
                out.append(
                    {
                        "candidate_id": candidate_id,
                        "factor_lane": row.get("factor_lane"),
                        "polarity": polarity,
                        "window": window,
                        "days": int(use.shape[0]),
                        "median_turnover": _round(turn.median()),
                        "p90_turnover": _round(turn.quantile(0.90)),
                        **_metrics(use),
                        "expression": row.get("expression"),
                    }
                )
    return out


def _wide_frame(rows: list[dict[str, str]], returns_by_key: dict[tuple[str, str], pd.Series], polarity: str) -> pd.DataFrame:
    series = []
    for row in rows:
        item = returns_by_key.get((str(row.get("candidate_id") or ""), polarity))
        if item is not None:
            series.append(item)
    if not series:
        return pd.DataFrame()
    return pd.concat(series, axis=1).sort_index()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows-csv", type=Path, default=DEFAULT_SIGNAL_NOVELTY_ROWS)
    parser.add_argument("--dataset-path", type=Path, required=True)
    parser.add_argument("--x0-daily-path", type=Path, default=None)
    parser.add_argument("--r3-gate-ledger-path", type=Path, default=DEFAULT_R3_GATE_LEDGER)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--include-signal-duplicates", action="store_true")
    parser.add_argument("--include-nondeployable", action="store_true")
    args = parser.parse_args()

    output_root = args.output_root
    output_root.mkdir(parents=True, exist_ok=True)
    selected_rows = _candidate_rows(
        args.rows_csv,
        require_signal_new=not bool(args.include_signal_duplicates),
        require_deployable=not bool(args.include_nondeployable),
    )

    resolved_x0_daily = _resolve_x0_daily(args.x0_daily_path)
    base = _build_x0_base_from_locked_gate(resolved_x0_daily, args.r3_gate_ledger_path)
    base["date"] = pd.to_datetime(base["date"], errors="coerce")
    base = base.dropna(subset=["date"]).sort_values("date").set_index("date")
    r3 = base["R3_liquidity_low"].fillna(False).astype(bool)
    x0_cash = pd.to_numeric(base["x0_net10"], errors="coerce").fillna(0.0)
    x0_r3 = x0_cash.where(r3, 0.0)

    frame = _load_frame(args.dataset_path)
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)

    returns_by_key: dict[tuple[str, str], pd.Series] = {}
    turnover_by_key: dict[tuple[str, str], pd.Series] = {}
    errors: list[dict[str, Any]] = []
    for row in selected_rows:
        candidate_id = str(row.get("candidate_id") or "")
        for polarity in ("original", "reversed"):
            returns, turnover, error = _daily_returns(
                row,
                frame=frame,
                signal_frame=signal_frame,
                field_lags=signal_clock_report["field_lags"],
                top_bottom_quantile=float(args.top_bottom_quantile),
                polarity=polarity,
            )
            if error:
                errors.append({"candidate_id": candidate_id, "polarity": polarity, "error": error, "expression": row.get("expression")})
                continue
            if returns is not None:
                returns_by_key[(candidate_id, polarity)] = returns
            if turnover is not None:
                turnover_by_key[(candidate_id, polarity)] = turnover

    original_wide = _wide_frame(selected_rows, returns_by_key, "original")
    reversed_wide = _wide_frame(selected_rows, returns_by_key, "reversed")
    common_index = base.index[(base.index >= OOS_2026_START) & (base.index <= OOS_2026_END)]
    if not original_wide.empty:
        common_index = common_index[common_index.isin(original_wide.index)]
    if not reversed_wide.empty:
        common_index = common_index[common_index.isin(reversed_wide.index)]

    r3_oos = r3.reindex(common_index).fillna(False).astype(bool)
    x0_cash_oos = x0_cash.reindex(common_index).fillna(0.0)
    x0_r3_oos = x0_r3.reindex(common_index).fillna(0.0)
    original_equal = original_wide.reindex(common_index).fillna(0.0).mean(axis=1) if not original_wide.empty else pd.Series(0.0, index=common_index)
    reversed_equal = reversed_wide.reindex(common_index).fillna(0.0).mean(axis=1) if not reversed_wide.empty else pd.Series(0.0, index=common_index)
    original_r3 = original_equal.where(r3_oos, 0.0)
    reversed_r3 = reversed_equal.where(r3_oos, 0.0)
    reversed_blend_10 = ((x0_cash_oos * 0.90) + (reversed_equal * 0.10)).where(r3_oos, 0.0)
    reversed_blend_20 = ((x0_cash_oos * 0.80) + (reversed_equal * 0.20)).where(r3_oos, 0.0)

    factor_counts = Counter(str(row.get("factor_lane") or "unknown") for row in selected_rows)
    book_rows = [
        _book_row("B0_x0_r3", x0_r3_oos, x0_r3=x0_r3_oos, r3=r3_oos, cluster_count=6),
        _book_row("I0_original_signal_new_r3_equal", original_r3, x0_r3=x0_r3_oos, r3=r3_oos, cluster_count=len(original_wide.columns), factor_counts=factor_counts),
        _book_row("I1_reversed_signal_new_r3_equal", reversed_r3, x0_r3=x0_r3_oos, r3=r3_oos, cluster_count=len(reversed_wide.columns), factor_counts=factor_counts),
        _book_row("B1_x0_plus_reversed_10pct_overlay", reversed_blend_10, x0_r3=x0_r3_oos, r3=r3_oos, cluster_count=6 + len(reversed_wide.columns), factor_counts=factor_counts),
        _book_row("B1_x0_plus_reversed_20pct_overlay", reversed_blend_20, x0_r3=x0_r3_oos, r3=r3_oos, cluster_count=6 + len(reversed_wide.columns), factor_counts=factor_counts),
    ]

    original_oos = next(row for row in book_rows if row["book"] == "I0_original_signal_new_r3_equal")
    reversed_oos = next(row for row in book_rows if row["book"] == "I1_reversed_signal_new_r3_equal")
    best_overlay = max([row for row in book_rows if row["book"].startswith("B1_")], key=lambda row: _safe_float(row.get("ann_compound"), -999.0) or -999.0)
    direction_flipped = (_safe_float(reversed_oos.get("ann_compound"), -999.0) or -999.0) > (_safe_float(original_oos.get("ann_compound"), -999.0) or -999.0)
    overlay_beats_x0 = (_safe_float(best_overlay.get("delta_ann_vs_x0_r3"), -999.0) or -999.0) > 0.03 and (_safe_float(best_overlay.get("delta_sortino_vs_x0_r3"), -999.0) or -999.0) >= -0.25
    decision = (
        "PASS_REVERSAL_OVERLAY_DIAGNOSTIC_ONLY"
        if direction_flipped and overlay_beats_x0
        else "HOLD_DIRECTIONAL_REVERSAL_DIAGNOSTIC_NO_X0_PROMOTION"
        if direction_flipped
        else "HOLD_NO_POLARITY_OR_REGIME_RESCUE"
    )

    candidate_rows = _candidate_metric_rows(selected_rows, returns_by_key, turnover_by_key, r3=r3)
    daily = pd.DataFrame(
        {
            "date": common_index,
            "R3_liquidity_low": r3_oos.to_numpy(),
            "B0_x0_r3": x0_r3_oos.to_numpy(),
            "I0_original_signal_new_r3_equal": original_r3.reindex(common_index).fillna(0.0).to_numpy(),
            "I1_reversed_signal_new_r3_equal": reversed_r3.reindex(common_index).fillna(0.0).to_numpy(),
            "B1_x0_plus_reversed_10pct_overlay": reversed_blend_10.reindex(common_index).fillna(0.0).to_numpy(),
            "B1_x0_plus_reversed_20pct_overlay": reversed_blend_20.reindex(common_index).fillna(0.0).to_numpy(),
        }
    )

    _write_csv(output_root / "polarity_regime_candidate_metrics.csv", candidate_rows)
    _write_csv(output_root / "polarity_regime_book_metrics.csv", book_rows)
    _write_csv(output_root / "polarity_regime_errors.csv", errors)
    daily.to_csv(output_root / "polarity_regime_daily_returns.csv", index=False)

    report = {
        "version": VERSION,
        "decision": decision,
        "scope": "diagnostic_no_search_no_x0_change",
        "candidate_count": len(selected_rows),
        "eval_errors": len(errors),
        "evaluation_start": common_index.min().date().isoformat() if len(common_index) else None,
        "evaluation_end": common_index.max().date().isoformat() if len(common_index) else None,
        "oos_days": int(len(common_index)),
        "r3_active_days": int(r3_oos.sum()),
        "direction_flipped": bool(direction_flipped),
        "overlay_beats_x0": bool(overlay_beats_x0),
        "best_overlay": best_overlay,
        "book_metrics": book_rows,
        "notes": [
            "Reversed polarity is evaluated as Neg(expression), not by negating realized returns.",
            "This is a short-window diagnostic on the integrated v2 dataset and cannot promote candidates.",
        ],
    }
    write_json_artifact(output_root / "polarity_regime_audit.json", report)

    lines = [
        "# CN Integrated Factor Pack V2 Polarity / Regime Audit",
        "",
        f"Decision: `{decision}`",
        "",
        "| book | clusters | ann | sortino | maxDD | corr_to_x0 | delta_ann | delta_sortino |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in book_rows:
        lines.append(
            f"| {row.get('book')} | {row.get('cluster_count')} | {row.get('ann_compound')} | {row.get('sortino')} | "
            f"{row.get('max_drawdown')} | {row.get('corr_to_x0_r3')} | {row.get('delta_ann_vs_x0_r3')} | {row.get('delta_sortino_vs_x0_r3')} |"
        )
    lines.extend(
        [
            "",
            "Interpretation boundary: this is a diagnostic polarity/regime rescue audit. It does not modify X0/R3 or promote integrated candidates.",
        ]
    )
    (output_root / "CN_INTEGRATED_FACTOR_PACK_V2_POLARITY_REGIME_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

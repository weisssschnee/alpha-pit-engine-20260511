"""Book-level marginal audit for integrated factor candidates versus X0/R3.

This is no-search and no-selector. It reads signal-novelty audit rows, evaluates
the selected candidate expressions into daily return series, and compares them
against the locked X0/R3 shadow object.
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

from our_system_phase2.runtime.cn_underutilized_field_book_marginal_audit import (
    DEFAULT_R3_GATE_LEDGER,
    _build_x0_base_from_locked_gate,
    _corr,
    _load_frame,
    _resolve_x0_daily,
)
from our_system_phase2.runtime.phase3ab_candidate_deep_validation import (
    OOS_2026_END,
    OOS_2026_START,
    SIGNAL_CLOCK_AFTER_OPEN,
    _candidate_daily,
    _metrics,
    _round,
)
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_validation import _signal_evaluation_frame


VERSION = "cn-integrated-factor-pack-x0-marginal-audit-v1-2026-06-03"
DEFAULT_SIGNAL_NOVELTY_ROWS = Path("reports/cn_integrated_factor_pack_v2_signal_novelty_audit_20260603/signal_novelty_rows.csv")
DEFAULT_OUTPUT_ROOT = Path("reports/cn_integrated_factor_pack_v2_x0_marginal_audit_20260603")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "1.0", "true", "yes", "y", "pass"}


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _candidate_rows(path: Path, *, require_signal_new: bool, require_deployable: bool) -> list[dict[str, str]]:
    rows = _read_csv(path)
    out: list[dict[str, str]] = []
    for row in rows:
        if require_signal_new and not _as_bool(row.get("signal_new_vs_149_proxy")):
            continue
        if require_deployable and not _as_bool(row.get("deployable_proxy")):
            continue
        if not row.get("expression"):
            continue
        out.append(row)
    return out


def _series_by_candidate(
    rows: list[dict[str, str]],
    *,
    frame: pd.DataFrame,
    signal_frame: pd.DataFrame,
    field_lags: dict[str, int],
    top_bottom_quantile: float,
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]]]:
    series: dict[str, pd.Series] = {}
    metrics: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for row in rows:
        candidate_id = str(row.get("candidate_id") or "")
        expression = str(row.get("expression") or "")
        try:
            daily = _candidate_daily(
                frame,
                signal_frame,
                field_lags,
                expression,
                top_bottom_quantile=top_bottom_quantile,
            )
        except Exception as exc:  # noqa: BLE001 - audit should continue.
            errors.append(
                {
                    "candidate_id": candidate_id,
                    "factor_lane": row.get("factor_lane"),
                    "error": f"{type(exc).__name__}:{str(exc)[:300]}",
                    "expression": expression,
                }
            )
            continue
        daily = daily.copy()
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
        daily = daily.dropna(subset=["date"]).sort_values("date")
        returns = pd.to_numeric(daily["long_net_10bps"], errors="coerce").fillna(0.0)
        turnover = pd.to_numeric(daily["average_one_way_turnover"], errors="coerce")
        series[candidate_id] = pd.Series(returns.to_numpy(), index=daily["date"], name=candidate_id)
        oos_mask = (daily["date"] >= OOS_2026_START) & (daily["date"] <= OOS_2026_END)
        oos_ret = returns.loc[oos_mask]
        oos_turn = turnover.loc[oos_mask]
        metrics.append(
            {
                "candidate_id": candidate_id,
                "factor_lane": row.get("factor_lane"),
                "deployable_proxy": row.get("deployable_proxy"),
                "signal_new_vs_149_proxy": row.get("signal_new_vs_149_proxy"),
                "max_corr_to_149_signal_vector": row.get("max_corr_to_149_signal_vector"),
                "oos_days": int(oos_ret.shape[0]),
                "oos_median_turnover": _round(oos_turn.median()),
                "oos_p90_turnover": _round(oos_turn.quantile(0.90)),
                **{f"oos_{key}": value for key, value in _metrics(oos_ret).items()},
                "expression": expression,
            }
        )
    if not series:
        return pd.DataFrame(), metrics, errors
    return pd.concat(series.values(), axis=1).sort_index(), metrics, errors


def _book_row(book: str, values: pd.Series, *, x0_r3: pd.Series, r3: pd.Series, cluster_count: int, factor_counts: Counter[str] | None = None) -> dict[str, Any]:
    values = values.sort_index()
    x0_aligned = x0_r3.reindex(values.index).fillna(0.0)
    metrics = _metrics(values)
    x0_metrics = _metrics(x0_aligned)
    active = values.loc[r3.reindex(values.index).fillna(False).astype(bool)]
    ann_delta = None
    if metrics.get("ann_compound") is not None and x0_metrics.get("ann_compound") is not None:
        ann_delta = _round(float(metrics["ann_compound"]) - float(x0_metrics["ann_compound"]))
    sortino_delta = None
    if metrics.get("sortino") is not None and x0_metrics.get("sortino") is not None:
        sortino_delta = _round(float(metrics["sortino"]) - float(x0_metrics["sortino"]))
    return {
        "book": book,
        "cluster_count": cluster_count,
        **metrics,
        "active_days": int(r3.reindex(values.index).fillna(False).astype(bool).sum()),
        "active_day_mean": _round(pd.to_numeric(active, errors="coerce").mean(), 8) if not active.empty else None,
        "corr_to_x0_r3": _corr(values, x0_aligned),
        "delta_ann_vs_x0_r3": ann_delta,
        "delta_sortino_vs_x0_r3": sortino_delta,
        "factor_top": factor_counts.most_common(1)[0][0] if factor_counts else None,
        "factor_top_share": _round(factor_counts.most_common(1)[0][1] / max(1, cluster_count)) if factor_counts else None,
        "factor_counts": json.dumps(dict(factor_counts or {}), ensure_ascii=False),
    }


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
    wide, candidate_metrics, errors = _series_by_candidate(
        selected_rows,
        frame=frame,
        signal_frame=signal_frame,
        field_lags=signal_clock_report["field_lags"],
        top_bottom_quantile=float(args.top_bottom_quantile),
    )
    if wide.empty:
        oos_index = base.index[(base.index >= OOS_2026_START) & (base.index <= OOS_2026_END)]
    else:
        oos_index = base.index[(base.index >= OOS_2026_START) & (base.index <= OOS_2026_END) & (base.index.isin(wide.index))]
    wide_oos = wide.reindex(oos_index).fillna(0.0)
    r3_oos = r3.reindex(oos_index).fillna(False).astype(bool)
    x0_cash_oos = x0_cash.reindex(oos_index).fillna(0.0)
    x0_r3_oos = x0_r3.reindex(oos_index).fillna(0.0)

    candidates_equal = wide_oos.mean(axis=1) if not wide_oos.empty else pd.Series(0.0, index=oos_index)
    candidates_r3 = candidates_equal.where(r3_oos, 0.0)
    cluster_count = len(wide_oos.columns)
    blend_equal = (((x0_cash_oos * 6.0) + (candidates_equal * max(1, cluster_count))) / (6.0 + max(1, cluster_count))).where(r3_oos, 0.0)
    blend_10 = ((x0_cash_oos * 0.90) + (candidates_equal * 0.10)).where(r3_oos, 0.0)
    blend_20 = ((x0_cash_oos * 0.80) + (candidates_equal * 0.20)).where(r3_oos, 0.0)

    factor_counts = Counter(str(row.get("factor_lane") or "unknown") for row in selected_rows)
    book_rows = [
        _book_row("B0_x0_r3", x0_r3_oos, x0_r3=x0_r3_oos, r3=r3_oos, cluster_count=6),
        _book_row("I0_integrated_signal_new_r3_equal", candidates_r3, x0_r3=x0_r3_oos, r3=r3_oos, cluster_count=cluster_count, factor_counts=factor_counts),
        _book_row("I0_integrated_signal_new_ungated_equal", candidates_equal, x0_r3=x0_r3_oos, r3=r3_oos, cluster_count=cluster_count, factor_counts=factor_counts),
        _book_row("B1_x0_plus_integrated_equal_weight", blend_equal, x0_r3=x0_r3_oos, r3=r3_oos, cluster_count=6 + cluster_count, factor_counts=factor_counts),
        _book_row("B1_x0_plus_integrated_10pct_overlay", blend_10, x0_r3=x0_r3_oos, r3=r3_oos, cluster_count=6 + cluster_count, factor_counts=factor_counts),
        _book_row("B1_x0_plus_integrated_20pct_overlay", blend_20, x0_r3=x0_r3_oos, r3=r3_oos, cluster_count=6 + cluster_count, factor_counts=factor_counts),
    ]
    b0 = next(row for row in book_rows if row["book"] == "B0_x0_r3")
    overlays = [row for row in book_rows if row["book"].startswith("B1_")]
    best_overlay = max(overlays, key=lambda row: _safe_float(row.get("ann_compound"), -999.0) or -999.0) if overlays else None
    best_ann_delta = (_safe_float(best_overlay.get("ann_compound"), 0.0) or 0.0) - (_safe_float(b0.get("ann_compound"), 0.0) or 0.0) if best_overlay else 0.0
    best_sortino_delta = (_safe_float(best_overlay.get("sortino"), 0.0) or 0.0) - (_safe_float(b0.get("sortino"), 0.0) or 0.0) if best_overlay else 0.0
    decision = (
        "PASS_X0_R3_MARGINAL_OVERLAY_PROXY"
        if best_ann_delta > 0.03 and best_sortino_delta >= -0.25
        else "HOLD_NO_CLEAR_X0_R3_MARGINAL_OVERLAY"
    )

    daily = pd.DataFrame({"date": oos_index})
    daily["R3_liquidity_low"] = r3_oos.to_numpy()
    daily["B0_x0_r3"] = x0_r3_oos.to_numpy()
    daily["I0_integrated_signal_new_r3_equal"] = candidates_r3.reindex(oos_index).fillna(0.0).to_numpy()
    daily["B1_x0_plus_integrated_equal_weight"] = blend_equal.reindex(oos_index).fillna(0.0).to_numpy()
    daily["B1_x0_plus_integrated_10pct_overlay"] = blend_10.reindex(oos_index).fillna(0.0).to_numpy()
    daily["B1_x0_plus_integrated_20pct_overlay"] = blend_20.reindex(oos_index).fillna(0.0).to_numpy()

    _write_csv(output_root / "x0_marginal_book_metrics.csv", book_rows)
    _write_csv(output_root / "x0_marginal_candidate_metrics.csv", candidate_metrics)
    _write_csv(output_root / "x0_marginal_errors.csv", errors)
    daily.to_csv(output_root / "x0_marginal_daily_returns.csv", index=False)
    report = {
        "version": VERSION,
        "decision": decision,
        "scope": "no_search_daily_proxy_marginal_audit_vs_locked_x0_r3",
        "rows_csv": str(args.rows_csv),
        "dataset_path": str(args.dataset_path),
        "x0_daily_path": str(resolved_x0_daily),
        "r3_gate_ledger_path": str(args.r3_gate_ledger_path),
        "output_root": str(output_root),
        "candidate_count": len(selected_rows),
        "candidate_eval_errors": len(errors),
        "evaluation_start": oos_index.min().date().isoformat() if len(oos_index) else None,
        "evaluation_end": oos_index.max().date().isoformat() if len(oos_index) else None,
        "oos_days": int(len(oos_index)),
        "r3_active_days": int(r3_oos.sum()),
        "best_overlay": best_overlay,
        "best_overlay_delta_ann": _round(best_ann_delta),
        "best_overlay_delta_sortino": _round(best_sortino_delta),
        "book_metrics": book_rows,
    }
    write_json_artifact(output_root / "x0_marginal_audit.json", report)
    markdown = [
        "# CN Integrated Factor Pack V2 X0/R3 Marginal Audit",
        "",
        f"Decision: `{decision}`",
        "",
        "| book | clusters | ann | sortino | maxDD | corr_to_x0 | delta_ann | delta_sortino |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in book_rows:
        markdown.append(
            f"| {row.get('book')} | {row.get('cluster_count')} | {row.get('ann_compound')} | {row.get('sortino')} | "
            f"{row.get('max_drawdown')} | {row.get('corr_to_x0_r3')} | {row.get('delta_ann_vs_x0_r3')} | {row.get('delta_sortino_vs_x0_r3')} |"
        )
    markdown.extend(
        [
            "",
            "This is daily-proxy marginal value only. It does not confirm execution, capacity, or live survival.",
        ]
    )
    (output_root / "CN_INTEGRATED_FACTOR_PACK_V2_X0_MARGINAL_AUDIT.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

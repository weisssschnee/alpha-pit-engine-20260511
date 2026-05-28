"""OOS/regime audit for Phase3Z45b deep-identity candidates.

This is a no-search audit. It takes representative expressions from the
Phase3Z45b deep identity audit, rebuilds their daily portfolio proxies on the
long daily panel, and reports split/regime/cost behavior.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.services.market_regime_state import build_pit_market_regime_state_frame
from our_system_phase2.services.real_market_validation import (
    SIGNAL_CLOCK_AFTER_OPEN,
    _available_market_panel_usecols,
    _prepare_market_panel,
    _signal_evaluation_frame,
    evaluate_panel_expression,
)
from our_system_phase2.services.stock_pit_compact_ensemble import build_stock_pit_compact_top6_daily_portfolio


DEFAULT_DATASET = Path(
    r"G:\Project_V7_Rotation\scripts\data\phase3n_stock_tdx_official_20200101_to_20260508_maxopt.parquet"
)
DEFAULT_REPORT_DIR = Path("reports/phase3z45b_parametric_limit_open_touch_20260528")
DEFAULT_INPUT = DEFAULT_REPORT_DIR / "deep_identity_audit" / "phase3z45b_deep_identity_cluster_audit.csv"
DEFAULT_OUTPUT = DEFAULT_REPORT_DIR / "oos_regime_audit"
LOAD_START = pd.Timestamp("2025-04-01")
TRAIN_START = pd.Timestamp("2025-07-01")
TRAIN_END = pd.Timestamp("2025-12-31")
OOS_START = pd.Timestamp("2026-01-01")
OOS_END = pd.Timestamp("2026-05-08")
COST_BPS_GRID = (0.0, 10.0, 20.0, 30.0, 50.0)
TOP_BOTTOM_QUANTILE = 0.02


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _round(value: Any, digits: int = 6) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return round(value, digits)


def _max_drawdown(values: pd.Series) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return None
    curve = (1.0 + clean).cumprod()
    return _round((curve / curve.cummax() - 1.0).min(), 8)


def _metrics(values: pd.Series) -> dict[str, Any]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return {
            "days": 0,
            "mean_daily": None,
            "ann_compound": None,
            "sharpe": None,
            "sortino": None,
            "hit_rate": None,
            "max_drawdown": None,
            "total_return": None,
        }
    mean = float(clean.mean())
    std = float(clean.std(ddof=0))
    downside = clean[clean < 0.0]
    downside_std = float(downside.std(ddof=0)) if not downside.empty else 0.0
    return {
        "days": int(clean.shape[0]),
        "mean_daily": _round(mean, 8),
        "ann_compound": _round((1.0 + mean) ** 252 - 1.0 if mean > -1.0 else None),
        "sharpe": _round(mean / std * math.sqrt(252.0) if std > 1e-12 else None),
        "sortino": _round(mean / downside_std * math.sqrt(252.0) if downside_std > 1e-12 else None),
        "hit_rate": _round((clean > 0.0).mean()),
        "max_drawdown": _max_drawdown(clean),
        "total_return": _round((1.0 + clean).prod() - 1.0, 8),
    }


def _bucket_by_train_thresholds(values: pd.Series, train_mask: pd.Series, prefix: str) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    labels = pd.Series(f"{prefix}_unknown", index=numeric.index, dtype=object)
    train_values = numeric[train_mask & numeric.notna()]
    if train_values.nunique(dropna=True) < 3:
        return labels
    q1 = float(train_values.quantile(1 / 3))
    q2 = float(train_values.quantile(2 / 3))
    labels[numeric <= q1] = f"{prefix}_low"
    labels[(numeric > q1) & (numeric <= q2)] = f"{prefix}_mid"
    labels[numeric > q2] = f"{prefix}_high"
    return labels


def _load_frame(dataset: Path) -> pd.DataFrame:
    usecols = _available_market_panel_usecols(dataset)
    frame = pd.read_parquet(dataset, columns=usecols)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame[frame["date"] >= LOAD_START].copy()
    return _prepare_market_panel(frame, source_path=dataset)


def _build_regime(frame: pd.DataFrame) -> pd.DataFrame:
    cols = ["date", "code", "close", "amount"]
    if "rt_change_pct" in frame.columns:
        cols.append("rt_change_pct")
    panel = frame[cols].copy()
    regime = build_pit_market_regime_state_frame(panel)
    regime["date"] = pd.to_datetime(regime["date"], errors="coerce")
    train_mask = (regime["date"] >= TRAIN_START) & (regime["date"] <= TRAIN_END)
    regime["liquidity_bucket"] = _bucket_by_train_thresholds(
        regime["liquidity_ratio_lag1"],
        train_mask,
        "liquidity",
    )
    regime["R3_liquidity_low"] = regime["liquidity_bucket"].eq("liquidity_low")
    return regime[["date", "R3_liquidity_low", "liquidity_bucket"]]


def _candidate_daily(
    frame: pd.DataFrame,
    expression: str,
    *,
    cluster_id: str,
    expression_cache: dict[str, pd.Series],
) -> pd.DataFrame:
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    signal = evaluate_panel_expression(
        signal_frame,
        expression,
        cache=expression_cache,
        field_lags=signal_clock_report["field_lags"],
    )
    daily, _masks = build_stock_pit_compact_top6_daily_portfolio(
        frame,
        signal=signal,
        evaluation_start_date=TRAIN_START,
        evaluation_end_date=OOS_END,
        horizon_days=1,
        execution_lag_days=1,
        rebalance_frequency_days=1,
        top_bottom_quantile=TOP_BOTTOM_QUANTILE,
    )
    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
    daily["signal_cluster_id"] = cluster_id
    daily["expression"] = expression
    turnover = pd.to_numeric(daily["average_one_way_turnover"], errors="coerce").fillna(0.0)
    for cost in COST_BPS_GRID:
        daily[f"long_net_{int(cost)}bps"] = pd.to_numeric(daily["long_ret"], errors="coerce") - turnover * (
            float(cost) / 10_000.0
        )
    return daily


def _window_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    date = pd.to_datetime(frame["date"], errors="coerce")
    return {
        "train_2025h2": (date >= TRAIN_START) & (date <= TRAIN_END),
        "oos_2026_all": (date >= OOS_START) & (date <= OOS_END),
        "recent_2025h2_2026": (date >= TRAIN_START) & (date <= OOS_END),
        "oos_2026_jan": (date >= "2026-01-01") & (date <= "2026-01-31"),
        "oos_2026_feb": (date >= "2026-02-01") & (date <= "2026-02-28"),
        "oos_2026_mar": (date >= "2026-03-01") & (date <= "2026-03-31"),
        "oos_2026_apr_may": (date >= "2026-04-01") & (date <= OOS_END),
        "oos_2026_r3_on": (date >= OOS_START) & (date <= OOS_END) & frame["R3_liquidity_low"].fillna(False).astype(bool),
        "oos_2026_r3_off": (date >= OOS_START) & (date <= OOS_END) & ~frame["R3_liquidity_low"].fillna(False).astype(bool),
    }


def _summarize_candidate(row: dict[str, str], daily: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    metric_rows: list[dict[str, Any]] = []
    stress_rows: list[dict[str, Any]] = []
    masks = _window_masks(daily)
    for window, mask in masks.items():
        use = daily[mask].copy()
        turnover = pd.to_numeric(use["average_one_way_turnover"], errors="coerce")
        base = {
            "signal_cluster_id": row["signal_cluster_id"],
            "candidate_action": row.get("next_action", ""),
            "event_family": row.get("event_family", ""),
            "window": window,
            "expression": row.get("representative_expression", ""),
            "active_day_count": int(mask.sum()),
            "r3_active_day_count": int(use["R3_liquidity_low"].fillna(False).sum()) if "R3_liquidity_low" in use else 0,
            "median_turnover": _round(turnover.median()),
            "p90_turnover": _round(turnover.quantile(0.90)),
            "mean_long_entry_amount_median": _round(pd.to_numeric(use.get("long_entry_amount_median"), errors="coerce").mean())
            if "long_entry_amount_median" in use
            else None,
        }
        metrics_10 = _metrics(use["long_net_10bps"])
        metric_rows.append({**base, **{f"long10_{key}": value for key, value in metrics_10.items()}})
        for cost in COST_BPS_GRID:
            stress = _metrics(use[f"long_net_{int(cost)}bps"])
            stress_rows.append(
                {
                    "signal_cluster_id": row["signal_cluster_id"],
                    "window": window,
                    "cost_bps": cost,
                    "days": stress["days"],
                    "ann_compound": stress["ann_compound"],
                    "sortino": stress["sortino"],
                    "max_drawdown": stress["max_drawdown"],
                    "mean_daily": stress["mean_daily"],
                    "total_return": stress["total_return"],
                }
            )
    return metric_rows, stress_rows


def run(input_path: Path, dataset: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    rows = _read_csv(input_path)
    selected = [row for row in rows if row.get("signal_cluster_id")]
    frame = _load_frame(dataset)
    regime = _build_regime(frame)
    cache: dict[str, pd.Series] = {}
    metric_rows: list[dict[str, Any]] = []
    stress_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    for row in selected:
        daily = _candidate_daily(
            frame,
            row.get("representative_expression", ""),
            cluster_id=row["signal_cluster_id"],
            expression_cache=cache,
        )
        daily = daily.merge(regime, on="date", how="left")
        metrics, stress = _summarize_candidate(row, daily)
        metric_rows.extend(metrics)
        stress_rows.extend(stress)
        keep = daily[
            [
                "date",
                "signal_cluster_id",
                "long_ret",
                "long_net_10bps",
                "average_one_way_turnover",
                "R3_liquidity_low",
                "liquidity_bucket",
                "long_count",
                "long_entry_amount_median",
            ]
        ].copy()
        daily_rows.extend(keep.to_dict(orient="records"))

    _write_csv(output_root / "phase3z45b_oos_regime_metrics.csv", metric_rows)
    _write_csv(output_root / "phase3z45b_oos_regime_cost_stress.csv", stress_rows)
    _write_csv(output_root / "phase3z45b_oos_regime_daily.csv", daily_rows)

    oos_rows = [row for row in metric_rows if row["window"] == "oos_2026_all"]
    pass_rows = [
        row
        for row in oos_rows
        if (row.get("long10_ann_compound") is not None and float(row["long10_ann_compound"]) > 0.0)
        and (row.get("long10_sortino") is not None and float(row["long10_sortino"]) > 0.5)
    ]
    summary = {
        "decision": "HOLD_RESEARCH_OOS_REGIME_AUDIT_COMPLETE",
        "dataset": str(dataset),
        "input": str(input_path),
        "candidate_count": len(selected),
        "oos_2026_positive_sortino_count": len(pass_rows),
        "top_oos_2026": sorted(
            oos_rows,
            key=lambda item: float(item.get("long10_sortino") or -999.0),
            reverse=True,
        )[:5],
        "outputs": {
            "metrics": str(output_root / "phase3z45b_oos_regime_metrics.csv"),
            "cost_stress": str(output_root / "phase3z45b_oos_regime_cost_stress.csv"),
            "daily": str(output_root / "phase3z45b_oos_regime_daily.csv"),
            "markdown": str(output_root / "PHASE3Z45B_OOS_REGIME_CANDIDATE_AUDIT_2026-05-28.md"),
        },
    }
    (output_root / "phase3z45b_oos_regime_candidate_audit.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )

    lines = [
        "# Phase3Z45b OOS / Regime Candidate Audit",
        "",
        "Decision: `HOLD_RESEARCH_OOS_REGIME_AUDIT_COMPLETE`.",
        "",
        "This audit is no-search and no-promotion. It replays frozen representative expressions on the long daily panel.",
        "",
        "## 2026 OOS Summary",
        "",
        "| cluster | action | family | ann | sortino | max_dd | median_turnover | p90_turnover |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(oos_rows, key=lambda item: float(item.get("long10_sortino") or -999.0), reverse=True):
        lines.append(
            "| {signal_cluster_id} | {candidate_action} | {event_family} | {ann} | {sortino} | {dd} | {turnover} | {p90} |".format(
                signal_cluster_id=row["signal_cluster_id"],
                candidate_action=row["candidate_action"],
                event_family=row["event_family"],
                ann=row.get("long10_ann_compound"),
                sortino=row.get("long10_sortino"),
                dd=row.get("long10_max_drawdown"),
                turnover=row.get("median_turnover"),
                p90=row.get("p90_turnover"),
            )
        )
    lines.extend(
        [
            "",
            "## Bias Boundary",
            "",
            "- Signal clock: after-open with full-day fields lagged by the existing evaluator policy.",
            "- Execution lag: T+1 daily proxy.",
            "- Cost stress: 0/10/20/30/50 bps one-way turnover deduction.",
            "- Evidence remains weak recent-daily until longer locked forward replay exists.",
        ]
    )
    (output_root / "PHASE3Z45B_OOS_REGIME_CANDIDATE_AUDIT_2026-05-28.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    summary = run(args.input, args.dataset, args.output_root)
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()

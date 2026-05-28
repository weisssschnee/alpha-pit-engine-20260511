"""Regime and timing audit for Phase3Z45b diagnostic candidates.

This is no-search and no-promotion. It replays the frozen representative
expressions from the Z45b deep-identity audit across several holding horizons
and market-state buckets. The output is intended to answer where the candidates
work, how quickly they decay, and whether the effect is only a narrow regime
slice.
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
DEFAULT_INPUT = Path(
    "reports/phase3z45b_parametric_limit_open_touch_20260528/deep_identity_audit/"
    "phase3z45b_deep_identity_cluster_audit.csv"
)
DEFAULT_OUTPUT = Path("reports/phase3z45b_parametric_limit_open_touch_20260528/regime_timing_audit")

LOAD_START = pd.Timestamp("2025-04-01")
TRAIN_START = pd.Timestamp("2025-07-01")
TRAIN_END = pd.Timestamp("2025-12-31")
OOS_START = pd.Timestamp("2026-01-01")
OOS_END = pd.Timestamp("2026-05-08")
TOP_BOTTOM_QUANTILE = 0.02
HORIZONS = (1, 2, 3, 5, 10)
WINDOWS = {
    "train_2025h2": (TRAIN_START, TRAIN_END),
    "oos_2026": (OOS_START, OOS_END),
    "recent_2025h2_2026": (TRAIN_START, OOS_END),
}
REGIME_AXES = {
    "trend": "trend_mean_lag1",
    "volatility": "volatility_lag1",
    "liquidity": "liquidity_ratio_lag1",
    "limit_density": "limit_density_lag1",
    "breadth": "up_ratio",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _round(value: Any, digits: int = 6) -> float | None:
    value = _safe_float(value)
    return round(value, digits) if value is not None else None


def _max_drawdown(values: pd.Series) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return None
    curve = (1.0 + clean).cumprod()
    return _round((curve / curve.cummax() - 1.0).min(), 8)


def _metrics(values: pd.Series, *, horizon_days: int) -> dict[str, Any]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return {
            "days": 0,
            "mean_horizon_return": None,
            "mean_daily_equiv": None,
            "ann_daily_equiv": None,
            "sortino_daily_equiv": None,
            "hit_rate": None,
            "max_drawdown_on_horizon_series": None,
            "total_return_on_horizon_series": None,
        }
    daily_equiv = clean / max(1, int(horizon_days))
    mean_daily = float(daily_equiv.mean())
    std_down = float(daily_equiv[daily_equiv < 0.0].std(ddof=0)) if (daily_equiv < 0.0).any() else 0.0
    return {
        "days": int(clean.shape[0]),
        "mean_horizon_return": _round(clean.mean(), 8),
        "mean_daily_equiv": _round(mean_daily, 8),
        "ann_daily_equiv": _round((1.0 + mean_daily) ** 252 - 1.0 if mean_daily > -1.0 else None),
        "sortino_daily_equiv": _round(mean_daily / std_down * math.sqrt(252.0) if std_down > 1e-12 else None),
        "hit_rate": _round((clean > 0.0).mean()),
        "max_drawdown_on_horizon_series": _max_drawdown(clean),
        "total_return_on_horizon_series": _round(float((1.0 + clean).prod() - 1.0), 8),
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
    regime = build_pit_market_regime_state_frame(frame[cols].copy())
    regime["date"] = pd.to_datetime(regime["date"], errors="coerce")
    train_mask = (regime["date"] >= TRAIN_START) & (regime["date"] <= TRAIN_END)
    for axis, column in REGIME_AXES.items():
        regime[f"{axis}_bucket"] = _bucket_by_train_thresholds(regime[column], train_mask, axis)
    regime["R1_volatility_high"] = regime["volatility_bucket"].eq("volatility_high")
    regime["R2_trend_low"] = regime["trend_bucket"].eq("trend_low")
    regime["R3_liquidity_low"] = regime["liquidity_bucket"].eq("liquidity_low")
    regime["R4_limit_density_high"] = regime["limit_density_bucket"].eq("limit_density_high")
    regime["R5_vol_or_trendlow_or_liqlow"] = (
        regime["R1_volatility_high"] | regime["R2_trend_low"] | regime["R3_liquidity_low"]
    )
    regime["R6_at_least_2_of_vol_trend_liq"] = (
        regime[["R1_volatility_high", "R2_trend_low", "R3_liquidity_low"]].astype(int).sum(axis=1) >= 2
    )
    keep = [
        "date",
        "pit_regime_label",
        "trend_bucket",
        "volatility_bucket",
        "liquidity_bucket",
        "limit_density_bucket",
        "breadth_bucket",
        "R1_volatility_high",
        "R2_trend_low",
        "R3_liquidity_low",
        "R4_limit_density_high",
        "R5_vol_or_trendlow_or_liqlow",
        "R6_at_least_2_of_vol_trend_liq",
        "liquidity_ratio_lag1",
        "limit_density_lag1",
    ]
    return regime[keep]


def _candidate_daily_by_horizon(
    frame: pd.DataFrame,
    signal: pd.Series,
    *,
    cluster_id: str,
    expression: str,
    horizon: int,
) -> pd.DataFrame:
    daily, _masks = build_stock_pit_compact_top6_daily_portfolio(
        frame,
        signal=signal,
        evaluation_start_date=TRAIN_START,
        evaluation_end_date=OOS_END,
        horizon_days=horizon,
        execution_lag_days=1,
        rebalance_frequency_days=1,
        top_bottom_quantile=TOP_BOTTOM_QUANTILE,
    )
    out = daily.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["signal_cluster_id"] = cluster_id
    out["expression"] = expression
    out["horizon_days"] = int(horizon)
    turnover = pd.to_numeric(out["average_one_way_turnover"], errors="coerce").fillna(0.0)
    out["long_net_10bps"] = pd.to_numeric(out["long_ret"], errors="coerce") - turnover * 0.001
    return out


def _window_mask(frame: pd.DataFrame, window: str) -> pd.Series:
    start, end = WINDOWS[window]
    date = pd.to_datetime(frame["date"], errors="coerce")
    return (date >= start) & (date <= end)


def _regime_rows(row: dict[str, str], daily_h1: pd.DataFrame) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    regime_specs: list[tuple[str, str, pd.Series]] = []
    for column in [
        "pit_regime_label",
        "trend_bucket",
        "volatility_bucket",
        "liquidity_bucket",
        "limit_density_bucket",
        "breadth_bucket",
    ]:
        for label in sorted(str(item) for item in daily_h1[column].dropna().unique()):
            regime_specs.append((column, label, daily_h1[column].astype(str).eq(label)))
    for gate in [
        "R1_volatility_high",
        "R2_trend_low",
        "R3_liquidity_low",
        "R4_limit_density_high",
        "R5_vol_or_trendlow_or_liqlow",
        "R6_at_least_2_of_vol_trend_liq",
    ]:
        flag = daily_h1[gate].fillna(False).astype(bool)
        regime_specs.append((gate, f"{gate}_on", flag))
        regime_specs.append((gate, f"{gate}_off", ~flag))

    for window in WINDOWS:
        win = _window_mask(daily_h1, window)
        for axis, label, mask in regime_specs:
            use = daily_h1[win & mask]
            if use.empty:
                continue
            metrics = _metrics(use["long_net_10bps"], horizon_days=1)
            output.append(
                {
                    "signal_cluster_id": row["signal_cluster_id"],
                    "event_family": row.get("event_family", ""),
                    "window": window,
                    "regime_axis": axis,
                    "regime_label": label,
                    "days": metrics["days"],
                    "active_ratio_in_window": _round(len(use) / max(1, int(win.sum()))),
                    "median_turnover": _round(pd.to_numeric(use["average_one_way_turnover"], errors="coerce").median()),
                    "p90_turnover": _round(pd.to_numeric(use["average_one_way_turnover"], errors="coerce").quantile(0.90)),
                    **{f"h1_{key}": value for key, value in metrics.items()},
                }
            )
    return output


def _horizon_rows(row: dict[str, str], daily_by_horizon: dict[int, pd.DataFrame]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for horizon, daily in daily_by_horizon.items():
        masks = {
            "train_2025h2": _window_mask(daily, "train_2025h2"),
            "oos_2026": _window_mask(daily, "oos_2026"),
            "oos_2026_r3_on": _window_mask(daily, "oos_2026") & daily["R3_liquidity_low"].fillna(False).astype(bool),
            "oos_2026_r3_off": _window_mask(daily, "oos_2026") & ~daily["R3_liquidity_low"].fillna(False).astype(bool),
            "oos_2026_limit_high": _window_mask(daily, "oos_2026")
            & daily["limit_density_bucket"].astype(str).eq("limit_density_high"),
        }
        for window, mask in masks.items():
            use = daily[mask]
            if use.empty:
                continue
            metrics = _metrics(use["long_net_10bps"], horizon_days=horizon)
            output.append(
                {
                    "signal_cluster_id": row["signal_cluster_id"],
                    "event_family": row.get("event_family", ""),
                    "window": window,
                    "horizon_days": horizon,
                    "median_turnover": _round(pd.to_numeric(use["average_one_way_turnover"], errors="coerce").median()),
                    "p90_turnover": _round(pd.to_numeric(use["average_one_way_turnover"], errors="coerce").quantile(0.90)),
                    **metrics,
                }
            )
    return output


def _profile_rows(horizon_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    by_cluster: dict[str, list[dict[str, Any]]] = {}
    for row in horizon_rows:
        if row.get("window") != "oos_2026":
            continue
        by_cluster.setdefault(str(row["signal_cluster_id"]), []).append(row)
    for cluster_id, rows in sorted(by_cluster.items()):
        rows = sorted(rows, key=lambda item: int(item["horizon_days"]))
        h1 = next((item for item in rows if int(item["horizon_days"]) == 1), None)
        best = max(rows, key=lambda item: float(item.get("ann_daily_equiv") or -999.0))
        h1_mean = _safe_float(h1.get("mean_daily_equiv")) if h1 else None
        half_life = None
        if h1_mean is not None and h1_mean > 0:
            for item in rows:
                mean = _safe_float(item.get("mean_daily_equiv"))
                if mean is not None and mean < 0.5 * h1_mean:
                    half_life = int(item["horizon_days"])
                    break
        h3 = next((item for item in rows if int(item["horizon_days"]) == 3), None)
        h5 = next((item for item in rows if int(item["horizon_days"]) == 5), None)
        h3_ratio = None
        h5_ratio = None
        if h1_mean is not None and abs(h1_mean) > 1e-12:
            if h3:
                h3_ratio = _round((_safe_float(h3.get("mean_daily_equiv")) or 0.0) / h1_mean)
            if h5:
                h5_ratio = _round((_safe_float(h5.get("mean_daily_equiv")) or 0.0) / h1_mean)
        if int(best["horizon_days"]) == 1 and (h3_ratio is not None and h3_ratio < 0.7):
            timing = "front_loaded"
        elif int(best["horizon_days"]) >= 3:
            timing = "delayed_or_persistent"
        else:
            timing = "short_horizon"
        output.append(
            {
                "signal_cluster_id": cluster_id,
                "best_oos_horizon_days": int(best["horizon_days"]),
                "best_oos_ann_daily_equiv": best.get("ann_daily_equiv"),
                "h1_ann_daily_equiv": h1.get("ann_daily_equiv") if h1 else None,
                "h1_mean_daily_equiv": h1_mean,
                "h3_mean_ratio_vs_h1": h3_ratio,
                "h5_mean_ratio_vs_h1": h5_ratio,
                "first_horizon_below_half_h1": half_life,
                "timing_profile": timing,
            }
        )
    return output


def _summary(
    regime_rows: list[dict[str, Any]],
    horizon_rows: list[dict[str, Any]],
    profile_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    oos_regimes = [
        row
        for row in regime_rows
        if row.get("window") == "oos_2026" and int(row.get("days") or 0) >= 5
    ]
    best_by_cluster: dict[str, dict[str, Any]] = {}
    for row in oos_regimes:
        cid = str(row["signal_cluster_id"])
        current = best_by_cluster.get(cid)
        if current is None or float(row.get("h1_ann_daily_equiv") or -999.0) > float(
            current.get("h1_ann_daily_equiv") or -999.0
        ):
            best_by_cluster[cid] = row
    h_oos = [row for row in horizon_rows if row.get("window") == "oos_2026"]
    return {
        "decision": "HOLD_RESEARCH_REGIME_TIMING_AUDIT_COMPLETE",
        "candidate_count": len({row["signal_cluster_id"] for row in h_oos}),
        "regime_rows": len(regime_rows),
        "horizon_rows": len(horizon_rows),
        "best_oos_regime_by_cluster": best_by_cluster,
        "timing_profiles": profile_rows,
        "bias_boundary": {
            "search": "none",
            "promotion": "none",
            "signal_clock": "after_open evaluator with full-day fields lagged by evaluator policy",
            "execution_lag_days": 1,
            "cost_model": "10bps times average one-way turnover",
            "oos_sample_grade": "WEAK recent daily sample",
        },
    }


def run(input_path: Path, dataset: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    identity_rows = [row for row in _read_csv(input_path) if row.get("signal_cluster_id")]
    frame = _load_frame(dataset)
    regime = _build_regime(frame)
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    expression_cache: dict[str, pd.Series] = {}

    regime_output: list[dict[str, Any]] = []
    horizon_output: list[dict[str, Any]] = []
    for row in identity_rows:
        expression = row.get("representative_expression", "")
        signal = evaluate_panel_expression(
            signal_frame,
            expression,
            cache=expression_cache,
            field_lags=signal_clock_report["field_lags"],
        )
        daily_by_horizon: dict[int, pd.DataFrame] = {}
        for horizon in HORIZONS:
            daily = _candidate_daily_by_horizon(
                frame,
                signal,
                cluster_id=row["signal_cluster_id"],
                expression=expression,
                horizon=horizon,
            )
            daily = daily.merge(regime, on="date", how="left")
            daily_by_horizon[horizon] = daily
        regime_output.extend(_regime_rows(row, daily_by_horizon[1]))
        horizon_output.extend(_horizon_rows(row, daily_by_horizon))

    profile_output = _profile_rows(horizon_output)
    summary = _summary(regime_output, horizon_output, profile_output)

    _write_csv(output_root / "phase3z45b_regime_effectiveness.csv", regime_output)
    _write_csv(output_root / "phase3z45b_horizon_decay.csv", horizon_output)
    _write_csv(output_root / "phase3z45b_timing_profile.csv", profile_output)
    _write_json(output_root / "phase3z45b_regime_timing_audit.json", summary)

    best_rows = list(summary["best_oos_regime_by_cluster"].values())
    lines = [
        "# Phase3Z45b Regime / Timing Audit",
        "",
        "Decision: `HOLD_RESEARCH_REGIME_TIMING_AUDIT_COMPLETE`.",
        "",
        "This is a diagnostic-only audit. It does not change X0/R3 or promote any Z45b candidate.",
        "",
        "## Best 2026 OOS Regime Slice By Cluster",
        "",
        "| cluster | best regime | days | ann daily-equiv | sortino | turnover |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in sorted(best_rows, key=lambda item: float(item.get("h1_ann_daily_equiv") or -999.0), reverse=True):
        lines.append(
            "| {cid} | {axis}:{label} | {days} | {ann} | {sortino} | {turnover} |".format(
                cid=row["signal_cluster_id"],
                axis=row["regime_axis"],
                label=row["regime_label"],
                days=row["days"],
                ann=row.get("h1_ann_daily_equiv"),
                sortino=row.get("h1_sortino_daily_equiv"),
                turnover=row.get("median_turnover"),
            )
        )
    lines.extend(
        [
            "",
            "## Timing Profile",
            "",
            "| cluster | best horizon | h1 ann | best ann | h3/h1 mean ratio | h5/h1 mean ratio | profile |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in profile_output:
        lines.append(
            "| {cid} | {best_h} | {h1_ann} | {best_ann} | {h3} | {h5} | {profile} |".format(
                cid=row["signal_cluster_id"],
                best_h=row["best_oos_horizon_days"],
                h1_ann=row.get("h1_ann_daily_equiv"),
                best_ann=row.get("best_oos_ann_daily_equiv"),
                h3=row.get("h3_mean_ratio_vs_h1"),
                h5=row.get("h5_mean_ratio_vs_h1"),
                profile=row.get("timing_profile"),
            )
        )
    lines.extend(
        [
            "",
            "## Bias Boundary",
            "",
            "- No new search and no parameter tuning were performed.",
            "- Regime buckets use 2025H2 train thresholds, then report 2026 OOS behavior.",
            "- Timing metrics use T+1 execution and 10bps one-way-turnover deduction.",
            "- Multi-day horizon metrics are daily-equivalent diagnostics from overlapping horizon labels, not production PnL.",
            "- Evidence remains `HOLD_RESEARCH` because OOS sample is recent and weak.",
        ]
    )
    (output_root / "PHASE3Z45B_REGIME_TIMING_AUDIT_2026-05-28.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase3Z45b regime/timing diagnostic audit.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    summary = run(args.input, args.dataset, args.output_root)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()

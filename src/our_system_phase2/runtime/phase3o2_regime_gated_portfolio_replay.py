"""Full-calendar regime-gated replay and placebo audit for Phase3O.

This script converts train-window regime buckets into executable full-calendar
gates. It does not change alpha formulas, cluster membership, or book weights.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from our_system_phase2.services.market_regime_state import build_pit_market_regime_state_frame


DEFAULT_DATASET = Path(r"G:\Project_V7_Rotation\scripts\data\phase3n_stock_tdx_official_20200101_to_20260508_maxopt.parquet")
DEFAULT_DAILY_RETURNS = Path("reports/phase3n_long_history_locked_validation_20260517/phase3n_daily_returns.csv")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3o2_regime_gated_portfolio_replay_20260517")

TRAIN_START = "2025-07-01"
TRAIN_END = "2025-12-31"
OOS_START = "2026-01-01"
OOS_END = "2026-05-08"
BOOK = "candidate_book_6"

AXES = {
    "trend": "trend_mean_lag1",
    "volatility": "volatility_lag1",
    "liquidity": "liquidity_ratio_lag1",
    "limit_density": "limit_density_lag1",
    "breadth": "up_ratio",
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
    return float((curve / curve.cummax() - 1.0).min())


def _metrics(values: pd.Series) -> dict[str, Any]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return {
            "days": 0,
            "mean_daily": None,
            "ann_simple": None,
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
        "ann_simple": _round(mean * 252.0),
        "ann_compound": _round((1.0 + mean) ** 252 - 1.0 if mean > -1.0 else None),
        "sharpe": _round(mean / std * math.sqrt(252.0) if std > 1e-12 else None),
        "sortino": _round(mean / downside_std * math.sqrt(252.0) if downside_std > 1e-12 else None),
        "hit_rate": _round((clean > 0.0).mean()),
        "max_drawdown": _round(_max_drawdown(clean), 8),
        "total_return": _round(float((1.0 + clean).prod() - 1.0)),
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


def _evaluate_gate(name: str, gate: pd.Series, returns: pd.Series, *, window_mask: pd.Series) -> dict[str, Any]:
    gate = gate.reindex(returns.index).fillna(False).astype(bool)
    active = window_mask & gate
    inactive = window_mask & (~gate)
    gated = returns.where(active, 0.0)
    full = _metrics(gated[window_mask])
    active_metrics = _metrics(returns[active])
    inactive_metrics = _metrics(returns[inactive])
    switches = int(gate[window_mask].astype(int).diff().abs().fillna(0).sum())
    out = {
        "gate": name,
        "calendar_days": int(window_mask.sum()),
        "active_days": int(active.sum()),
        "active_day_ratio": _round(active.sum() / window_mask.sum() if int(window_mask.sum()) else None),
        "gate_switch_count": switches,
    }
    out.update({f"full_{key}": value for key, value in full.items()})
    out.update({f"active_{key}": value for key, value in active_metrics.items()})
    out.update({f"inactive_{key}": value for key, value in inactive_metrics.items()})
    return out


def _random_placebo_rows(
    *,
    name: str,
    active_count: int,
    returns: pd.Series,
    window_mask: pd.Series,
    draws: int,
) -> list[dict[str, Any]]:
    idx = np.flatnonzero(window_mask.to_numpy())
    rows: list[dict[str, Any]] = []
    if active_count <= 0 or len(idx) <= 0:
        return rows
    active_count = min(active_count, len(idx))
    rng = np.random.default_rng(20260517)
    for draw in range(draws):
        selected = set(rng.choice(idx, size=active_count, replace=False).tolist())
        mask = pd.Series(False, index=returns.index)
        mask.iloc[list(selected)] = True
        row = _evaluate_gate(f"{name}_random_{draw:03d}", mask, returns, window_mask=window_mask)
        row["placebo_group"] = name
        row["draw"] = draw
        rows.append(row)
    return rows


def run(*, dataset_path: Path, daily_returns_path: Path, output_root: Path, placebo_draws: int) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    panel = pd.read_parquet(dataset_path, columns=["date", "code", "close", "amount", "rt_change_pct"])
    regime = build_pit_market_regime_state_frame(panel)
    returns = pd.read_csv(daily_returns_path, parse_dates=["date"])
    merged = returns.merge(regime, on="date", how="left").sort_values("date").reset_index(drop=True)
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce")
    train_mask = (merged["date"] >= TRAIN_START) & (merged["date"] <= TRAIN_END)
    oos_mask = (merged["date"] >= OOS_START) & (merged["date"] <= OOS_END)
    full_recent_mask = (merged["date"] >= TRAIN_START) & (merged["date"] <= OOS_END)
    returns_series = pd.to_numeric(merged[BOOK], errors="coerce").fillna(0.0)

    labels: dict[str, pd.Series] = {}
    for axis, column in AXES.items():
        labels[axis] = _bucket_by_train_thresholds(merged[column], train_mask, axis)

    gates: dict[str, pd.Series] = {
        "R0_no_gate": pd.Series(True, index=merged.index),
        "R1_volatility_high": labels["volatility"] == "volatility_high",
        "R2_trend_low": labels["trend"] == "trend_low",
        "R3_liquidity_low": labels["liquidity"] == "liquidity_low",
        "R4_limit_density_high": labels["limit_density"] == "limit_density_high",
        "R5_vol_or_trendlow_or_liqlow": (
            (labels["volatility"] == "volatility_high")
            | (labels["trend"] == "trend_low")
            | (labels["liquidity"] == "liquidity_low")
        ),
        "R6_at_least_2_of_vol_trend_liq": (
            (
                (labels["volatility"] == "volatility_high").astype(int)
                + (labels["trend"] == "trend_low").astype(int)
                + (labels["liquidity"] == "liquidity_low").astype(int)
            )
            >= 2
        ),
        "F1_breadth_low_failed_control": labels["breadth"] == "breadth_low",
        "F2_trend_high_failed_control": labels["trend"] == "trend_high",
        "F3_liquidity_high_failed_control": labels["liquidity"] == "liquidity_high",
    }

    train_weights = {}
    for gate_name in ["R1_volatility_high", "R2_trend_low", "R3_liquidity_low"]:
        active = gates[gate_name] & train_mask
        train_weights[gate_name] = max(0.0, float(returns_series[active].mean())) if active.any() else 0.0
    score = (
        train_weights["R1_volatility_high"] * gates["R1_volatility_high"].astype(float)
        + train_weights["R2_trend_low"] * gates["R2_trend_low"].astype(float)
        + train_weights["R3_liquidity_low"] * gates["R3_liquidity_low"].astype(float)
    )
    train_score = score[train_mask & (score > 0.0)]
    threshold = float(train_score.quantile(0.50)) if not train_score.empty else float("inf")
    gates["R7_weighted_train_score_gate"] = score >= threshold

    gate_rows: list[dict[str, Any]] = []
    for name, gate in gates.items():
        for window_name, mask in [
            ("train_2025h2", train_mask),
            ("oos_2026", oos_mask),
            ("recent_full_2025h2_2026", full_recent_mask),
        ]:
            row = _evaluate_gate(name, gate, returns_series, window_mask=mask)
            row["window"] = window_name
            row["book"] = BOOK
            gate_rows.append(row)

    placebo_rows: list[dict[str, Any]] = []
    for name in ["R1_volatility_high", "R2_trend_low", "R3_liquidity_low", "R5_vol_or_trendlow_or_liqlow", "R6_at_least_2_of_vol_trend_liq", "R7_weighted_train_score_gate"]:
        gate = gates[name]
        oos_active = int((gate & oos_mask).sum())
        true_row = _evaluate_gate(name, gate, returns_series, window_mask=oos_mask)
        true_row["placebo_type"] = "true_gate"
        placebo_rows.append(true_row)
        shuffled_gate = pd.Series(gate[oos_mask].sample(frac=1.0, random_state=20260517).to_numpy(), index=merged.index[oos_mask])
        full_shuffle = pd.Series(False, index=merged.index)
        full_shuffle.loc[oos_mask] = shuffled_gate
        shuffle_row = _evaluate_gate(name + "_shuffle", full_shuffle, returns_series, window_mask=oos_mask)
        shuffle_row["placebo_type"] = "shuffle"
        placebo_rows.append(shuffle_row)
        wrong_lag = gate.shift(-1).fillna(False)
        wrong_row = _evaluate_gate(name + "_wrong_lag_plus1", wrong_lag, returns_series, window_mask=oos_mask)
        wrong_row["placebo_type"] = "wrong_lag"
        placebo_rows.append(wrong_row)
        inverted_row = _evaluate_gate(name + "_inverted", ~gate, returns_series, window_mask=oos_mask)
        inverted_row["placebo_type"] = "inverted"
        placebo_rows.append(inverted_row)
        placebo_rows.extend(
            _random_placebo_rows(
                name=name,
                active_count=oos_active,
                returns=returns_series,
                window_mask=oos_mask,
                draws=placebo_draws,
            )
        )

    random_summary_rows: list[dict[str, Any]] = []
    for name in sorted({row.get("placebo_group") for row in placebo_rows if row.get("placebo_group")}):
        rows = [row for row in placebo_rows if row.get("placebo_group") == name]
        values = pd.Series([_safe_float(row.get("full_ann_compound")) for row in rows], dtype=float).dropna()
        true = next(row for row in placebo_rows if row["gate"] == name and row.get("placebo_type") == "true_gate")
        random_summary_rows.append(
            {
                "gate": name,
                "true_oos_ann_compound": true.get("full_ann_compound"),
                "random_mean_ann_compound": _round(values.mean()),
                "random_p90_ann_compound": _round(values.quantile(0.9)),
                "random_p95_ann_compound": _round(values.quantile(0.95)),
                "true_gt_random_p95": (_safe_float(true.get("full_ann_compound")) or -999.0) > float(values.quantile(0.95)),
                "draws": len(values),
            }
        )

    _write_csv(output_root / "phase3o2_gate_metrics.csv", gate_rows)
    _write_csv(output_root / "phase3o2_placebo_metrics.csv", placebo_rows)
    _write_csv(output_root / "phase3o2_random_placebo_summary.csv", random_summary_rows)

    oos_rows = [row for row in gate_rows if row["window"] == "oos_2026"]
    best_non_oracle = sorted(
        [row for row in oos_rows if row["gate"].startswith("R")],
        key=lambda row: _safe_float(row.get("full_ann_compound")) or -999.0,
        reverse=True,
    )
    decision = "PASS_REGIME_GATED_FULL_CALENDAR_CANDIDATE" if best_non_oracle and (_safe_float(best_non_oracle[0].get("full_ann_compound")) or -1.0) > (_safe_float(oos_rows[0].get("full_ann_compound")) or 999.0) else "HOLD_REGIME_GATED_FULL_CALENDAR"
    summary = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3o2_regime_gated_portfolio_replay",
        "decision": decision,
        "scope": "full_calendar_regime_gated_candidate_book_no_formula_or_weight_tuning",
        "train_window": [TRAIN_START, TRAIN_END],
        "oos_window": [OOS_START, OOS_END],
        "book": BOOK,
        "train_weights_for_R7": train_weights,
        "r7_threshold": threshold,
        "best_oos_gate": best_non_oracle[0] if best_non_oracle else None,
        "outputs": {
            "gate_metrics_csv": str(output_root / "phase3o2_gate_metrics.csv"),
            "placebo_metrics_csv": str(output_root / "phase3o2_placebo_metrics.csv"),
            "random_placebo_summary_csv": str(output_root / "phase3o2_random_placebo_summary.csv"),
            "summary_json": str(output_root / "phase3o2_regime_gated_replay.json"),
            "summary_md": str(output_root / "PHASE3O2_REGIME_GATED_PORTFOLIO_REPLAY_2026-05-17.md"),
        },
    }
    _write_json(output_root / "phase3o2_regime_gated_replay.json", summary)

    md = [
        "# Phase3O2 Regime-Gated Portfolio Replay",
        "",
        f"- decision: `{decision}`",
        f"- book: `{BOOK}`",
        f"- train_window: `{TRAIN_START}` to `{TRAIN_END}`",
        f"- oos_window: `{OOS_START}` to `{OOS_END}`",
        "",
        "## OOS Full-Calendar Gates",
        "",
        "| gate | active ratio | full ann | sharpe | sortino | max dd | active ann | inactive ann | switches |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in sorted(oos_rows, key=lambda item: _safe_float(item.get("full_ann_compound")) or -999.0, reverse=True):
        md.append(
            f"| {row['gate']} | {row.get('active_day_ratio')} | {row.get('full_ann_compound')} | {row.get('full_sharpe')} | {row.get('full_sortino')} | {row.get('full_max_drawdown')} | {row.get('active_ann_compound')} | {row.get('inactive_ann_compound')} | {row.get('gate_switch_count')} |"
        )
    md.extend(
        [
            "",
            "## Random Placebo Summary",
            "",
            "| gate | true full ann | random mean | random p95 | true > random p95 |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in random_summary_rows:
        md.append(
            f"| {row['gate']} | {row.get('true_oos_ann_compound')} | {row.get('random_mean_ann_compound')} | {row.get('random_p95_ann_compound')} | {row.get('true_gt_random_p95')} |"
        )
    md.extend(
        [
            "",
            "## Boundaries",
            "",
            "- Bucket thresholds are fitted only on 2025H2 and applied to 2026.",
            "- Full-calendar gated return is zero on inactive days; bucket annualization is not used as the headline.",
            "- Placebo tests are diagnostic; this is still daily proxy evidence, not execution proof.",
            "",
        ]
    )
    (output_root / "PHASE3O2_REGIME_GATED_PORTFOLIO_REPLAY_2026-05-17.md").write_text("\n".join(md), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--daily-returns", type=Path, default=DEFAULT_DAILY_RETURNS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--placebo-draws", type=int, default=200)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        dataset_path=args.dataset_path,
        daily_returns_path=args.daily_returns,
        output_root=args.output_root,
        placebo_draws=args.placebo_draws,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

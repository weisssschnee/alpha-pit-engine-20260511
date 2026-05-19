"""Strict placebo and persistence audit for Phase3O2 regime gates.

This audit keeps the Phase3O2 gate definitions fixed and tests whether the
full-calendar 2026 result survives stronger timing/placebo controls.
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
DEFAULT_OUTPUT_ROOT = Path("reports/phase3o3_regime_gate_robustness_audit_20260517")

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
PRIMARY_GATES = ["R3_liquidity_low", "R5_vol_or_trendlow_or_liqlow", "R6_at_least_2_of_vol_trend_liq"]
CONTROL_GATES = ["R1_volatility_high", "R2_trend_low", "F1_breadth_low_failed_control", "F2_trend_high_failed_control", "F3_liquidity_high_failed_control"]
WRONG_LAGS = [-5, -2, -1, 1, 2, 5]


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


def _evaluate_gate(name: str, gate: pd.Series, returns: pd.Series, window_mask: pd.Series) -> dict[str, Any]:
    gate = gate.reindex(returns.index).fillna(False).astype(bool)
    active = window_mask & gate
    inactive = window_mask & (~gate)
    gated = returns.where(active, 0.0)
    full = _metrics(gated[window_mask])
    active_metrics = _metrics(returns[active])
    inactive_metrics = _metrics(returns[inactive])
    spread = pd.to_numeric(returns[active], errors="coerce").dropna().mean() - pd.to_numeric(returns[inactive], errors="coerce").dropna().mean()
    out = {
        "gate": name,
        "calendar_days": int(window_mask.sum()),
        "active_days": int(active.sum()),
        "active_day_ratio": _round(active.sum() / window_mask.sum() if int(window_mask.sum()) else None),
        "active_minus_inactive_mean_daily": _round(spread, 8),
    }
    out.update({f"full_{key}": value for key, value in full.items()})
    out.update({f"active_{key}": value for key, value in active_metrics.items()})
    out.update({f"inactive_{key}": value for key, value in inactive_metrics.items()})
    return out


def _run_lengths(mask: pd.Series) -> list[int]:
    values = mask.fillna(False).astype(bool).to_list()
    runs: list[int] = []
    current = 0
    for value in values:
        if value:
            current += 1
        elif current:
            runs.append(current)
            current = 0
    if current:
        runs.append(current)
    return runs


def _persistence(gate: pd.Series, window_mask: pd.Series) -> dict[str, Any]:
    sub = gate[window_mask].fillna(False).astype(bool)
    runs = _run_lengths(sub)
    switches = int(sub.astype(int).diff().abs().fillna(0).sum())
    return {
        "active_days": int(sub.sum()),
        "active_run_count": len(runs),
        "mean_active_run_length": _round(float(np.mean(runs)) if runs else 0.0),
        "max_active_run_length": int(max(runs)) if runs else 0,
        "gate_switch_count": switches,
    }


def _block_run_mask(length: int, run_lengths: list[int], rng: np.random.Generator) -> np.ndarray:
    mask = np.zeros(length, dtype=bool)
    if not run_lengths:
        return mask
    for run in sorted(run_lengths, reverse=True):
        placed = False
        for _ in range(1000):
            start = int(rng.integers(0, max(1, length - run + 1)))
            if not mask[start : start + run].any():
                mask[start : start + run] = True
                placed = True
                break
        if not placed:
            free = np.where(~mask)[0]
            if len(free) >= run:
                chosen = rng.choice(free, size=run, replace=False)
                mask[chosen] = True
    return mask


def _build_gates(merged: pd.DataFrame, train_mask: pd.Series) -> dict[str, pd.Series]:
    labels = {axis: _bucket_by_train_thresholds(merged[column], train_mask, axis) for axis, column in AXES.items()}
    return {
        "R1_volatility_high": labels["volatility"] == "volatility_high",
        "R2_trend_low": labels["trend"] == "trend_low",
        "R3_liquidity_low": labels["liquidity"] == "liquidity_low",
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


def run(*, dataset_path: Path, daily_returns_path: Path, output_root: Path, random_draws: int, block_draws: int) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    panel = pd.read_parquet(dataset_path, columns=["date", "code", "close", "amount", "rt_change_pct"])
    regime = build_pit_market_regime_state_frame(panel)
    returns = pd.read_csv(daily_returns_path, parse_dates=["date"])
    merged = returns.merge(regime, on="date", how="left").sort_values("date").reset_index(drop=True)
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce")
    train_mask = (merged["date"] >= TRAIN_START) & (merged["date"] <= TRAIN_END)
    oos_mask = (merged["date"] >= OOS_START) & (merged["date"] <= OOS_END)
    returns_series = pd.to_numeric(merged[BOOK], errors="coerce").fillna(0.0)
    gates = _build_gates(merged, train_mask)

    gate_names = PRIMARY_GATES + CONTROL_GATES
    true_rows: list[dict[str, Any]] = []
    placebo_rows: list[dict[str, Any]] = []
    persistence_rows: list[dict[str, Any]] = []
    rng = np.random.default_rng(20260517)
    oos_positions = np.flatnonzero(oos_mask.to_numpy())

    for gate_name in gate_names:
        gate = gates[gate_name]
        true_row = _evaluate_gate(gate_name, gate, returns_series, oos_mask)
        true_row["test_type"] = "true_gate"
        true_rows.append(true_row)
        persistence_rows.append({"gate": gate_name, **_persistence(gate, oos_mask)})

        gate_oos = gate[oos_mask].fillna(False).astype(bool).reset_index(drop=True)
        active_count = int(gate_oos.sum())
        for draw in range(random_draws):
            selected = set(rng.choice(oos_positions, size=active_count, replace=False).tolist()) if active_count else set()
            mask = pd.Series(False, index=merged.index)
            if selected:
                mask.iloc[list(selected)] = True
            row = _evaluate_gate(gate_name, mask, returns_series, oos_mask)
            row["test_type"] = "random_active_days"
            row["draw"] = draw
            placebo_rows.append(row)

        run_lengths = _run_lengths(gate_oos)
        for draw in range(block_draws):
            block = _block_run_mask(int(oos_mask.sum()), run_lengths, rng)
            mask = pd.Series(False, index=merged.index)
            mask.iloc[oos_positions] = block
            row = _evaluate_gate(gate_name, mask, returns_series, oos_mask)
            row["test_type"] = "block_run_placebo"
            row["draw"] = draw
            placebo_rows.append(row)

        for shift in range(1, max(1, len(gate_oos))):
            shifted = np.roll(gate_oos.to_numpy(dtype=bool), shift)
            mask = pd.Series(False, index=merged.index)
            mask.iloc[oos_positions] = shifted
            row = _evaluate_gate(gate_name, mask, returns_series, oos_mask)
            row["test_type"] = "circular_shift"
            row["draw"] = shift
            placebo_rows.append(row)

        for lag in WRONG_LAGS:
            shifted = gate.shift(lag).fillna(False)
            row = _evaluate_gate(gate_name, shifted, returns_series, oos_mask)
            row["test_type"] = "wrong_lag"
            row["draw"] = lag
            placebo_rows.append(row)

        inverted = ~gate.fillna(False).astype(bool)
        row = _evaluate_gate(gate_name, inverted, returns_series, oos_mask)
        row["test_type"] = "inverted"
        row["draw"] = 0
        placebo_rows.append(row)

    summary_rows: list[dict[str, Any]] = []
    for true_row in true_rows:
        gate_name = true_row["gate"]
        row = {
            "gate": gate_name,
            "primary_gate": gate_name in PRIMARY_GATES,
            "true_full_ann_compound": true_row.get("full_ann_compound"),
            "true_full_sharpe": true_row.get("full_sharpe"),
            "true_full_max_drawdown": true_row.get("full_max_drawdown"),
            "active_day_ratio": true_row.get("active_day_ratio"),
        }
        pass_count = 0
        required_tests = ["random_active_days", "block_run_placebo", "circular_shift"]
        for test_type in required_tests:
            values = pd.Series(
                [
                    _safe_float(item.get("full_ann_compound"))
                    for item in placebo_rows
                    if item["gate"] == gate_name and item["test_type"] == test_type
                ],
                dtype=float,
            ).dropna()
            p90 = float(values.quantile(0.90)) if not values.empty else None
            p95 = float(values.quantile(0.95)) if not values.empty else None
            row[f"{test_type}_p90_ann"] = _round(p90)
            row[f"{test_type}_p95_ann"] = _round(p95)
            row[f"true_gt_{test_type}_p95"] = (
                (_safe_float(true_row.get("full_ann_compound")) or -999.0) > p95
                if p95 is not None
                else False
            )
            pass_count += 1 if row[f"true_gt_{test_type}_p95"] else 0
        wrong_lag_values = [
            _safe_float(item.get("full_ann_compound"))
            for item in placebo_rows
            if item["gate"] == gate_name and item["test_type"] == "wrong_lag"
        ]
        row["max_wrong_lag_ann"] = _round(max(value for value in wrong_lag_values if value is not None), 6) if any(value is not None for value in wrong_lag_values) else None
        inv = next(item for item in placebo_rows if item["gate"] == gate_name and item["test_type"] == "inverted")
        row["inverted_ann"] = inv.get("full_ann_compound")
        row["robustness_pass_count"] = pass_count
        row["decision"] = "PASS_STRICT_GATE_ROBUSTNESS" if pass_count >= 2 and (_safe_float(row.get("inverted_ann")) or 0.0) < 0.0 else "HOLD_STRICT_GATE_ROBUSTNESS"
        summary_rows.append(row)

    _write_csv(output_root / "phase3o3_true_gate_metrics.csv", true_rows)
    _write_csv(output_root / "phase3o3_placebo_metrics.csv", placebo_rows)
    _write_csv(output_root / "phase3o3_persistence_metrics.csv", persistence_rows)
    _write_csv(output_root / "phase3o3_robustness_summary.csv", summary_rows)

    primary_passes = [row for row in summary_rows if row["primary_gate"] and row["decision"] == "PASS_STRICT_GATE_ROBUSTNESS"]
    decision = "PASS_STRICT_REGIME_GATE_ROBUSTNESS" if primary_passes else "HOLD_STRICT_REGIME_GATE_ROBUSTNESS"
    summary = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3o3_regime_gate_robustness_audit",
        "decision": decision,
        "scope": "strict_placebo_and_persistence_for_fixed_phase3o2_gates",
        "book": BOOK,
        "train_window": [TRAIN_START, TRAIN_END],
        "oos_window": [OOS_START, OOS_END],
        "random_draws": random_draws,
        "block_draws": block_draws,
        "primary_pass_gates": [row["gate"] for row in primary_passes],
        "outputs": {
            "true_gate_metrics_csv": str(output_root / "phase3o3_true_gate_metrics.csv"),
            "placebo_metrics_csv": str(output_root / "phase3o3_placebo_metrics.csv"),
            "persistence_metrics_csv": str(output_root / "phase3o3_persistence_metrics.csv"),
            "robustness_summary_csv": str(output_root / "phase3o3_robustness_summary.csv"),
            "summary_json": str(output_root / "phase3o3_regime_gate_robustness.json"),
            "summary_md": str(output_root / "PHASE3O3_REGIME_GATE_ROBUSTNESS_AUDIT_2026-05-17.md"),
        },
    }
    _write_json(output_root / "phase3o3_regime_gate_robustness.json", summary)

    md = [
        "# Phase3O3 Regime Gate Robustness Audit",
        "",
        f"- decision: `{decision}`",
        f"- primary_pass_gates: `{','.join(summary['primary_pass_gates']) or 'none'}`",
        f"- random_draws: `{random_draws}`",
        f"- block_draws: `{block_draws}`",
        "",
        "## Robustness Summary",
        "",
        "| gate | true ann | active ratio | random p95 | block p95 | circular p95 | inverted ann | pass count | decision |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in sorted(summary_rows, key=lambda item: _safe_float(item.get("true_full_ann_compound")) or -999.0, reverse=True):
        md.append(
            f"| {row['gate']} | {row.get('true_full_ann_compound')} | {row.get('active_day_ratio')} | {row.get('random_active_days_p95_ann')} | {row.get('block_run_placebo_p95_ann')} | {row.get('circular_shift_p95_ann')} | {row.get('inverted_ann')} | {row.get('robustness_pass_count')} | {row.get('decision')} |"
        )
    md.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Random active-day placebo tests whether the gate beats random days with the same active count.",
            "- Block-run placebo preserves active run lengths but randomizes their position.",
            "- Circular shift preserves the full active/inactive sequence and tests timing alignment within 2026.",
            "- A gate can be useful even if it fails circular-shift p95, but then the evidence is weaker and should be called timing-sensitive.",
            "",
        ]
    )
    (output_root / "PHASE3O3_REGIME_GATE_ROBUSTNESS_AUDIT_2026-05-17.md").write_text("\n".join(md), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--daily-returns", type=Path, default=DEFAULT_DAILY_RETURNS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--random-draws", type=int, default=1000)
    parser.add_argument("--block-draws", type=int, default=1000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        dataset_path=args.dataset_path,
        daily_returns_path=args.daily_returns,
        output_root=args.output_root,
        random_draws=args.random_draws,
        block_draws=args.block_draws,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

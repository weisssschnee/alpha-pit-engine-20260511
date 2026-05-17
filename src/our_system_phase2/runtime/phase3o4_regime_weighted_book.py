"""Regime + cluster-variant + walk-forward weighting diagnostic.

Phase3O4 keeps the Phase3O2/3 gates fixed and evaluates non-oracle cluster
sets under full-calendar 2026 OOS. Walk-forward weights use only past cluster
returns and are diagnostic only.
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
DEFAULT_OUTPUT_ROOT = Path("reports/phase3o4_regime_weighted_book_20260517")

TRAIN_START = "2025-07-01"
TRAIN_END = "2025-12-31"
OOS_START = "2026-01-01"
OOS_END = "2026-05-08"
WEIGHT_HISTORY_START = "2025-07-01"

AXES = {
    "trend": "trend_mean_lag1",
    "volatility": "volatility_lag1",
    "liquidity": "liquidity_ratio_lag1",
}

GATES = [
    "R0_no_gate",
    "R3_liquidity_low",
    "R5_vol_or_trendlow_or_liqlow",
    "R6_at_least_2_of_vol_trend_liq",
]

VARIANTS = {
    "X0_official_6": ["cluster_001", "cluster_005", "cluster_006", "cluster_009", "cluster_002", "cluster_004"],
    "X1_research_9": [
        "cluster_001",
        "cluster_005",
        "cluster_008",
        "cluster_006",
        "cluster_009",
        "cluster_003",
        "cluster_002",
        "cluster_007",
        "cluster_004",
    ],
    "X2_official_6_plus_003": [
        "cluster_001",
        "cluster_005",
        "cluster_006",
        "cluster_009",
        "cluster_002",
        "cluster_004",
        "cluster_003",
    ],
    "X3_official_6_minus_002": ["cluster_001", "cluster_005", "cluster_006", "cluster_009", "cluster_004"],
    "X4_official_6_plus_003_minus_002": [
        "cluster_001",
        "cluster_005",
        "cluster_006",
        "cluster_009",
        "cluster_004",
        "cluster_003",
    ],
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


def _build_gates(merged: pd.DataFrame, train_mask: pd.Series) -> dict[str, pd.Series]:
    labels = {axis: _bucket_by_train_thresholds(merged[column], train_mask, axis) for axis, column in AXES.items()}
    return {
        "R0_no_gate": pd.Series(True, index=merged.index),
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
    }


def _weighted_cluster_returns(
    cluster_frame: pd.DataFrame,
    clusters: list[str],
    *,
    lookback: int,
    max_weight: float,
    shrink: float,
) -> tuple[pd.Series, list[dict[str, Any]]]:
    out = pd.Series(index=cluster_frame.index, dtype=float)
    rows: list[dict[str, Any]] = []
    equal = pd.Series(1.0 / len(clusters), index=clusters)
    weights = equal.copy()
    for pos, date in enumerate(cluster_frame.index):
        if pos >= lookback:
            hist = cluster_frame.iloc[pos - lookback : pos][clusters]
            scores = hist.mean() / hist.std(ddof=0).replace(0.0, np.nan)
            scores = scores.replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(lower=0.0)
            if float(scores.sum()) > 1e-12:
                raw = scores / scores.sum()
                raw = raw.clip(upper=max_weight)
                raw = raw / raw.sum() if float(raw.sum()) > 1e-12 else equal
            else:
                raw = equal
            weights = shrink * equal + (1.0 - shrink) * raw
            weights = weights / weights.sum()
            rows.append(
                {
                    "date": pd.Timestamp(date).date().isoformat(),
                    "lookback": lookback,
                    "max_weight": max_weight,
                    "shrink_to_equal": shrink,
                    "max_weight_realized": _round(weights.max()),
                    "weights": json.dumps({cluster: _round(weights[cluster]) for cluster in clusters}, sort_keys=True),
                }
            )
        out.loc[date] = float((cluster_frame.loc[date, clusters] * weights).sum())
    return out, rows


def _apply_gate(series: pd.Series, gate: pd.Series, oos_mask: pd.Series) -> tuple[pd.Series, int, float]:
    gate = gate.reindex(series.index).fillna(False).astype(bool)
    active = oos_mask & gate
    window = oos_mask.reindex(series.index).fillna(False).astype(bool)
    gated = series.where(active, 0.0)
    ratio = float(active.sum() / window.sum()) if int(window.sum()) else 0.0
    return gated[window], int(active.sum()), ratio


def run(*, dataset_path: Path, daily_returns_path: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    panel = pd.read_parquet(dataset_path, columns=["date", "code", "close", "amount", "rt_change_pct"])
    regime = build_pit_market_regime_state_frame(panel)
    returns = pd.read_csv(daily_returns_path, parse_dates=["date"]).sort_values("date")
    merged = returns.merge(regime, on="date", how="left").sort_values("date").reset_index(drop=True)
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce")
    train_mask = (merged["date"] >= TRAIN_START) & (merged["date"] <= TRAIN_END)
    oos_mask = (merged["date"] >= OOS_START) & (merged["date"] <= OOS_END)
    gates = _build_gates(merged, train_mask)
    cluster_frame = merged.set_index("date")[[cluster for clusters in VARIANTS.values() for cluster in clusters]].loc[:, lambda x: ~x.columns.duplicated()]
    oos_by_date = pd.Series(oos_mask.to_numpy(), index=merged["date"])
    gates_by_date = {name: pd.Series(mask.to_numpy(), index=merged["date"]) for name, mask in gates.items()}

    equal_rows: list[dict[str, Any]] = []
    wf_rows: list[dict[str, Any]] = []
    weight_rows: list[dict[str, Any]] = []
    for variant, clusters in VARIANTS.items():
        equal_series = cluster_frame[clusters].mean(axis=1, skipna=True)
        for gate_name in GATES:
            gated, active_days, active_ratio = _apply_gate(equal_series, gates_by_date[gate_name], oos_by_date)
            row = {
                "variant": variant,
                "clusters": "|".join(clusters),
                "cluster_count": len(clusters),
                "gate": gate_name,
                "weight_mode": "equal",
                "active_days": active_days,
                "active_day_ratio": _round(active_ratio),
            }
            row.update(_metrics(gated))
            equal_rows.append(row)

        history = cluster_frame[cluster_frame.index >= WEIGHT_HISTORY_START][clusters].copy()
        for lookback in [60, 90, 120]:
            wf_series, rows = _weighted_cluster_returns(
                history,
                clusters,
                lookback=lookback,
                max_weight=0.30,
                shrink=0.50,
            )
            for gate_name in GATES:
                gated, active_days, active_ratio = _apply_gate(wf_series, gates_by_date[gate_name], oos_by_date)
                row = {
                    "variant": variant,
                    "clusters": "|".join(clusters),
                    "cluster_count": len(clusters),
                    "gate": gate_name,
                    "weight_mode": "walk_forward",
                    "lookback": lookback,
                    "max_weight": 0.30,
                    "shrink_to_equal": 0.50,
                    "active_days": active_days,
                    "active_day_ratio": _round(active_ratio),
                }
                row.update(_metrics(gated))
                wf_rows.append(row)
            for row in rows:
                row["variant"] = variant
            weight_rows.extend(rows)

    all_rows = equal_rows + wf_rows
    best_equal = max(
        [row for row in equal_rows if row["gate"] != "R0_no_gate"],
        key=lambda row: _safe_float(row.get("ann_compound")) or -999.0,
    )
    best_wf = max(
        [row for row in wf_rows if row["gate"] != "R0_no_gate"],
        key=lambda row: _safe_float(row.get("ann_compound")) or -999.0,
    )
    _write_csv(output_root / "phase3o4_equal_gate_variant_metrics.csv", equal_rows)
    _write_csv(output_root / "phase3o4_walk_forward_gate_variant_metrics.csv", wf_rows)
    _write_csv(output_root / "phase3o4_walk_forward_weights.csv", weight_rows)

    summary = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3o4_regime_weighted_book",
        "decision": "PASS_REGIME_WEIGHTED_DIAGNOSTIC_COMPLETED",
        "scope": "fixed_regime_gates_non_oracle_variants_walk_forward_weighting_diagnostic",
        "train_window": [TRAIN_START, TRAIN_END],
        "oos_window": [OOS_START, OOS_END],
        "best_equal_gated": best_equal,
        "best_walk_forward_gated": best_wf,
        "outputs": {
            "equal_metrics_csv": str(output_root / "phase3o4_equal_gate_variant_metrics.csv"),
            "walk_forward_metrics_csv": str(output_root / "phase3o4_walk_forward_gate_variant_metrics.csv"),
            "walk_forward_weights_csv": str(output_root / "phase3o4_walk_forward_weights.csv"),
            "summary_json": str(output_root / "phase3o4_regime_weighted_book.json"),
            "summary_md": str(output_root / "PHASE3O4_REGIME_WEIGHTED_BOOK_2026-05-17.md"),
        },
    }
    _write_json(output_root / "phase3o4_regime_weighted_book.json", summary)

    top_equal = sorted(equal_rows, key=lambda row: _safe_float(row.get("ann_compound")) or -999.0, reverse=True)[:15]
    top_wf = sorted(wf_rows, key=lambda row: _safe_float(row.get("ann_compound")) or -999.0, reverse=True)[:20]
    md = [
        "# Phase3O4 Regime Weighted Book Diagnostic",
        "",
        "- decision: `PASS_REGIME_WEIGHTED_DIAGNOSTIC_COMPLETED`",
        "- scope: `fixed_regime_gates_non_oracle_variants_walk_forward_weighting_diagnostic`",
        f"- train_window: `{TRAIN_START}` to `{TRAIN_END}`",
        f"- oos_window: `{OOS_START}` to `{OOS_END}`",
        "",
        "## Top Equal-Weight Gated Variants",
        "",
        "| variant | gate | ann | sharpe | sortino | max dd | active ratio | total return |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in top_equal:
        md.append(
            f"| {row['variant']} | {row['gate']} | {row.get('ann_compound')} | {row.get('sharpe')} | {row.get('sortino')} | {row.get('max_drawdown')} | {row.get('active_day_ratio')} | {row.get('total_return')} |"
        )
    md.extend(
        [
            "",
            "## Top Walk-Forward Weighted Gated Variants",
            "",
            "| variant | gate | lookback | ann | sharpe | sortino | max dd | active ratio | total return |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in top_wf:
        md.append(
            f"| {row['variant']} | {row['gate']} | {row.get('lookback')} | {row.get('ann_compound')} | {row.get('sharpe')} | {row.get('sortino')} | {row.get('max_drawdown')} | {row.get('active_day_ratio')} | {row.get('total_return')} |"
        )
    md.extend(
        [
            "",
            "## Boundaries",
            "",
            "- This is diagnostic only. It does not promote cluster_003 or weighting rules into the formal proof book.",
            "- Walk-forward weights use only prior cluster returns, max 30% per cluster, 50% shrinkage to equal weight.",
            "- No formula, gate threshold, or cluster expression was tuned in this run.",
            "",
        ]
    )
    (output_root / "PHASE3O4_REGIME_WEIGHTED_BOOK_2026-05-17.md").write_text("\n".join(md), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--daily-returns", type=Path, default=DEFAULT_DAILY_RETURNS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(dataset_path=args.dataset_path, daily_returns_path=args.daily_returns, output_root=args.output_root)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

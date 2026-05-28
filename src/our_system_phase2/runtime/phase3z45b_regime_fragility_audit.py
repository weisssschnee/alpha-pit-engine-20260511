"""Fragility audit for Phase3Z45b regime slices.

This script does not re-evaluate formulas. It uses the existing h1 daily replay
rows and regime timing summary to test whether the best-looking OOS regime
slices are fragile: small sample, top-day driven, train/OOS inconsistent, or
easy to reproduce with random active days.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from our_system_phase2.services.market_regime_state import build_pit_market_regime_state_frame


DEFAULT_DATASET = Path(
    r"G:\Project_V7_Rotation\scripts\data\phase3n_stock_tdx_official_20200101_to_20260508_maxopt.parquet"
)
DEFAULT_DAILY = Path(
    "reports/phase3z45b_parametric_limit_open_touch_20260528/oos_regime_audit/phase3z45b_oos_regime_daily.csv"
)
DEFAULT_EFFECTIVENESS = Path(
    "reports/phase3z45b_parametric_limit_open_touch_20260528/regime_timing_audit/"
    "phase3z45b_regime_effectiveness.csv"
)
DEFAULT_OUTPUT = Path("reports/phase3z45b_parametric_limit_open_touch_20260528/regime_fragility_audit")

TRAIN_START = pd.Timestamp("2025-07-01")
TRAIN_END = pd.Timestamp("2025-12-31")
OOS_START = pd.Timestamp("2026-01-01")
OOS_END = pd.Timestamp("2026-05-08")
REGIME_AXES = {
    "trend": "trend_mean_lag1",
    "volatility": "volatility_lag1",
    "liquidity": "liquidity_ratio_lag1",
    "limit_density": "limit_density_lag1",
    "breadth": "up_ratio",
}


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


def _metrics(values: pd.Series) -> dict[str, Any]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return {
            "days": 0,
            "mean_daily": None,
            "ann_compound": None,
            "sortino": None,
            "hit_rate": None,
            "max_drawdown": None,
            "total_return": None,
            "top1_abs_share": None,
            "top3_positive_share": None,
            "remove_top1_ann": None,
            "winsor_05_95_ann": None,
        }
    mean = float(clean.mean())
    downside = clean[clean < 0.0]
    downside_std = float(downside.std(ddof=0)) if not downside.empty else 0.0
    positives = clean[clean > 0.0].sort_values(ascending=False)
    positive_sum = float(positives.sum()) if not positives.empty else 0.0
    abs_sum = float(clean.abs().sum())
    top1_abs_share = float(clean.abs().max() / abs_sum) if abs_sum > 1e-12 else None
    top3_positive_share = float(positives.head(3).sum() / positive_sum) if positive_sum > 1e-12 else None
    remove_top1 = clean.drop(index=clean.abs().idxmax()) if len(clean) > 1 else pd.Series(dtype=float)
    winsor = clean.clip(lower=clean.quantile(0.05), upper=clean.quantile(0.95)) if len(clean) >= 5 else clean
    remove_top_mean = float(remove_top1.mean()) if not remove_top1.empty else None
    winsor_mean = float(winsor.mean()) if not winsor.empty else None
    return {
        "days": int(clean.shape[0]),
        "mean_daily": _round(mean, 8),
        "ann_compound": _round((1.0 + mean) ** 252 - 1.0 if mean > -1.0 else None),
        "sortino": _round(mean / downside_std * math.sqrt(252.0) if downside_std > 1e-12 else None),
        "hit_rate": _round((clean > 0.0).mean()),
        "max_drawdown": _max_drawdown(clean),
        "total_return": _round(float((1.0 + clean).prod() - 1.0), 8),
        "top1_abs_share": _round(top1_abs_share),
        "top3_positive_share": _round(top3_positive_share),
        "remove_top1_ann": _round((1.0 + remove_top_mean) ** 252 - 1.0 if remove_top_mean is not None and remove_top_mean > -1.0 else None),
        "winsor_05_95_ann": _round((1.0 + winsor_mean) ** 252 - 1.0 if winsor_mean is not None and winsor_mean > -1.0 else None),
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


def _build_regime(dataset: Path) -> pd.DataFrame:
    panel = pd.read_parquet(dataset, columns=["date", "code", "close", "amount", "rt_change_pct"])
    regime = build_pit_market_regime_state_frame(panel)
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
    return regime[
        [
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
        ]
    ]


def _best_oos_regimes(effectiveness_path: Path) -> list[dict[str, Any]]:
    rows = pd.read_csv(effectiveness_path)
    rows = rows[(rows["window"].astype(str) == "oos_2026") & (pd.to_numeric(rows["days"], errors="coerce") >= 5)].copy()
    rows["score"] = pd.to_numeric(rows["h1_ann_daily_equiv"], errors="coerce")
    out: list[dict[str, Any]] = []
    for cid, group in rows.groupby("signal_cluster_id", sort=True):
        best = group.sort_values("score", ascending=False).iloc[0].to_dict()
        out.append(
            {
                "signal_cluster_id": str(cid),
                "regime_axis": str(best["regime_axis"]),
                "regime_label": str(best["regime_label"]),
                "oos_best_ann_from_effectiveness": _round(best.get("h1_ann_daily_equiv")),
                "oos_best_days_from_effectiveness": int(best.get("days") or 0),
            }
        )
    return out


def _mask_for_spec(frame: pd.DataFrame, axis: str, label: str) -> pd.Series:
    if axis in frame.columns and label.endswith("_on"):
        return frame[axis].fillna(False).astype(bool)
    if axis in frame.columns and label.endswith("_off"):
        return ~frame[axis].fillna(False).astype(bool)
    if axis in frame.columns:
        return frame[axis].astype(str).eq(label)
    return pd.Series(False, index=frame.index)


def _random_placebo(
    returns: pd.Series,
    window_mask: pd.Series,
    active_count: int,
    *,
    draws: int = 1000,
    seed: int = 20260528,
) -> dict[str, Any]:
    available = returns[window_mask].dropna()
    if active_count <= 0 or len(available) < active_count:
        return {
            "random_draws": 0,
            "random_ann_p50": None,
            "random_ann_p95": None,
            "true_ann_percentile_vs_random": None,
        }
    idx = available.index.to_numpy()
    values = available.to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    anns: list[float] = []
    for _ in range(draws):
        pos = rng.choice(len(idx), size=active_count, replace=False)
        sample = pd.Series(values[pos])
        metric = _metrics(sample).get("ann_compound")
        if metric is not None:
            anns.append(float(metric))
    if not anns:
        return {
            "random_draws": 0,
            "random_ann_p50": None,
            "random_ann_p95": None,
            "true_ann_percentile_vs_random": None,
        }
    return {
        "random_draws": len(anns),
        "random_ann_p50": _round(np.quantile(anns, 0.50)),
        "random_ann_p95": _round(np.quantile(anns, 0.95)),
        "random_ann_p99": _round(np.quantile(anns, 0.99)),
    }


def _stable_seed(text: str) -> int:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def run(dataset: Path, daily_path: Path, effectiveness_path: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    daily = pd.read_csv(daily_path, parse_dates=["date"])
    regime = _build_regime(dataset)
    frame = daily.merge(regime, on="date", how="left")
    frame["long_net_10bps"] = pd.to_numeric(frame["long_net_10bps"], errors="coerce")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    train_mask = (frame["date"] >= TRAIN_START) & (frame["date"] <= TRAIN_END)
    oos_mask = (frame["date"] >= OOS_START) & (frame["date"] <= OOS_END)
    specs = _best_oos_regimes(effectiveness_path)

    rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    for spec in specs:
        cid = spec["signal_cluster_id"]
        block = frame[frame["signal_cluster_id"].astype(str).eq(cid)].copy()
        spec_mask = _mask_for_spec(block, spec["regime_axis"], spec["regime_label"])
        for window_name, mask in {
            "train_2025h2": (block["date"] >= TRAIN_START) & (block["date"] <= TRAIN_END),
            "oos_2026": (block["date"] >= OOS_START) & (block["date"] <= OOS_END),
        }.items():
            active = mask & spec_mask
            metrics = _metrics(block.loc[active, "long_net_10bps"])
            row = {
                **spec,
                "window": window_name,
                **metrics,
            }
            if window_name == "oos_2026":
                placebo = _random_placebo(
                    block["long_net_10bps"],
                    (block["date"] >= OOS_START) & (block["date"] <= OOS_END),
                    int(metrics["days"] or 0),
                    seed=20260528 + _stable_seed(cid) % 10000,
                )
                row.update(placebo)
                if placebo.get("random_ann_p95") is not None and row.get("ann_compound") is not None:
                    true_ann = float(row["ann_compound"])
                    # Reconstruct percentile approximately with a second deterministic draw list would be wasteful here;
                    # p95/p99 and pass flags are the actionable diagnostics.
                    row["beats_random_p95"] = bool(true_ann > float(placebo["random_ann_p95"]))
                    row["beats_random_p99"] = bool(
                        placebo.get("random_ann_p99") is not None and true_ann > float(placebo["random_ann_p99"])
                    )
                else:
                    row["beats_random_p95"] = False
                    row["beats_random_p99"] = False
            rows.append(row)

        use = block.loc[oos_mask & spec_mask, ["date", "signal_cluster_id", "long_net_10bps"]].copy()
        use["regime_axis"] = spec["regime_axis"]
        use["regime_label"] = spec["regime_label"]
        use["abs_return_rank_in_slice"] = use["long_net_10bps"].abs().rank(method="first", ascending=False)
        daily_rows.extend(use.to_dict(orient="records"))

    # Add train/OOS consistency flags.
    by_cid: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_cid.setdefault(str(row["signal_cluster_id"]), {})[str(row["window"])] = row
    for cid, parts in by_cid.items():
        train = parts.get("train_2025h2", {})
        oos = parts.get("oos_2026", {})
        consistent = (_safe_float(train.get("mean_daily")) or 0.0) > 0.0 and (_safe_float(oos.get("mean_daily")) or 0.0) > 0.0
        fragile = False
        reasons: list[str] = []
        if int(oos.get("days") or 0) < 15:
            fragile = True
            reasons.append("small_oos_slice")
        if (_safe_float(oos.get("top3_positive_share")) or 0.0) > 0.65:
            fragile = True
            reasons.append("top3_positive_concentrated")
        if not consistent:
            fragile = True
            reasons.append("train_oos_not_both_positive")
        if not bool(oos.get("beats_random_p95")):
            fragile = True
            reasons.append("does_not_beat_random_p95")
        for row in rows:
            if row["signal_cluster_id"] == cid:
                row["train_oos_same_sign_positive"] = consistent
                row["fragility_flag"] = fragile
                row["fragility_reasons"] = "|".join(reasons)

    _write_csv(output_root / "phase3z45b_regime_fragility.csv", rows)
    _write_csv(output_root / "phase3z45b_best_slice_daily_returns.csv", daily_rows)
    summary = {
        "decision": "HOLD_RESEARCH_REGIME_FRAGILITY_AUDIT_COMPLETE",
        "candidate_count": len(specs),
        "fragile_oos_count": sum(1 for row in rows if row.get("window") == "oos_2026" and row.get("fragility_flag")),
        "outputs": {
            "fragility_csv": str(output_root / "phase3z45b_regime_fragility.csv"),
            "daily_csv": str(output_root / "phase3z45b_best_slice_daily_returns.csv"),
            "markdown": str(output_root / "PHASE3Z45B_REGIME_FRAGILITY_AUDIT_2026-05-28.md"),
        },
    }
    _write_json(output_root / "phase3z45b_regime_fragility_audit.json", summary)

    lines = [
        "# Phase3Z45b Regime Fragility Audit",
        "",
        "Decision: `HOLD_RESEARCH_REGIME_FRAGILITY_AUDIT_COMPLETE`.",
        "",
        "This audit tests whether the best-looking OOS regime slices are stable enough to interpret.",
        "",
        "| cluster | best slice | oos days | oos ann | train ann | top3 positive share | remove top1 ann | random p95 | beats random p95 | fragility |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for cid, parts in sorted(by_cid.items()):
        train = parts.get("train_2025h2", {})
        oos = parts.get("oos_2026", {})
        lines.append(
            "| {cid} | {axis}:{label} | {days} | {oos_ann} | {train_ann} | {top3} | {remove_top1} | {random_p95} | {beats} | {fragile} {reasons} |".format(
                cid=cid,
                axis=oos.get("regime_axis"),
                label=oos.get("regime_label"),
                days=oos.get("days"),
                oos_ann=oos.get("ann_compound"),
                train_ann=train.get("ann_compound"),
                top3=oos.get("top3_positive_share"),
                remove_top1=oos.get("remove_top1_ann"),
                random_p95=oos.get("random_ann_p95"),
                beats=oos.get("beats_random_p95"),
                fragile=oos.get("fragility_flag"),
                reasons=oos.get("fragility_reasons", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Best slices were selected from OOS diagnostics, so this is not a promotion protocol.",
            "- A slice is marked fragile if it is too small, top-day concentrated, train/OOS sign inconsistent, or fails same-active-count random p95.",
            "- Passing this audit would still not promote a candidate; it would only justify a locked forward diagnostic.",
        ]
    )
    (output_root / "PHASE3Z45B_REGIME_FRAGILITY_AUDIT_2026-05-28.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit fragility of Phase3Z45b best regime slices.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--daily", type=Path, default=DEFAULT_DAILY)
    parser.add_argument("--effectiveness", type=Path, default=DEFAULT_EFFECTIVENESS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    summary = run(args.dataset, args.daily, args.effectiveness, args.output_root)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()

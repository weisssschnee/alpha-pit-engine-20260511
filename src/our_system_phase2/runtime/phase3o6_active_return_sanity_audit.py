"""Phase3O6 active-return sanity audit for the locked R3 shadow book.

This is a narrow audit. It does not change the locked X0 book, R3 gate,
cluster membership, weights, or any search setting.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.services.market_regime_state import build_pit_market_regime_state_frame


DEFAULT_DATASET = Path(
    r"G:\Project_V7_Rotation\scripts\data\phase3n_stock_tdx_official_20200101_to_20260508_maxopt.parquet"
)
DEFAULT_DAILY_RETURNS = Path("reports/phase3n_long_history_locked_validation_20260517/phase3n_daily_returns.csv")
DEFAULT_O3_SUMMARY = Path("reports/phase3o3_regime_gate_robustness_audit_20260517/phase3o3_robustness_summary.csv")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3o6_active_return_sanity_audit_20260517")

TRAIN_START = "2025-07-01"
TRAIN_END = "2025-12-31"
OOS_START = "2026-01-01"
OOS_END = "2026-05-08"
BOOK = "candidate_book_6"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _round(value: Any, digits: int = 6) -> float | None:
    value = _safe_float(value)
    return round(value, digits) if value is not None else None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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
            "median_daily": None,
            "ann_compound": None,
            "sharpe": None,
            "max_drawdown": None,
            "total_return": None,
            "hit_rate": None,
        }
    mean = float(clean.mean())
    std = float(clean.std(ddof=0))
    return {
        "days": int(clean.shape[0]),
        "mean_daily": _round(mean, 8),
        "median_daily": _round(float(clean.median()), 8),
        "ann_compound": _round((1.0 + mean) ** 252 - 1.0 if mean > -1.0 else None),
        "sharpe": _round(mean / std * math.sqrt(252.0) if std > 1e-12 else None),
        "max_drawdown": _round(_max_drawdown(clean), 8),
        "total_return": _round(float((1.0 + clean).prod() - 1.0)),
        "hit_rate": _round(float((clean > 0.0).mean())),
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


def _winsorized(values: pd.Series, tail: float) -> pd.Series:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return clean
    lower = float(clean.quantile(tail))
    upper = float(clean.quantile(1.0 - tail))
    return clean.clip(lower=lower, upper=upper)


def _load_frame(dataset_path: Path, daily_returns_path: Path) -> pd.DataFrame:
    panel = pd.read_parquet(dataset_path, columns=["date", "code", "close", "amount", "rt_change_pct"])
    regime = build_pit_market_regime_state_frame(panel)
    regime["date"] = pd.to_datetime(regime["date"], errors="coerce")
    returns = pd.read_csv(daily_returns_path, parse_dates=["date"])
    frame = returns.merge(regime, on="date", how="left").sort_values("date").reset_index(drop=True)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    return frame


def run(
    *,
    dataset_path: Path,
    daily_returns_path: Path,
    o3_summary_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    frame = _load_frame(dataset_path, daily_returns_path)
    train_mask = (frame["date"] >= TRAIN_START) & (frame["date"] <= TRAIN_END)
    oos_mask = (frame["date"] >= OOS_START) & (frame["date"] <= OOS_END)
    returns = pd.to_numeric(frame[BOOK], errors="coerce").fillna(0.0)

    liquidity_label = _bucket_by_train_thresholds(frame["liquidity_ratio_lag1"], train_mask, "liquidity")
    limit_label = _bucket_by_train_thresholds(frame["limit_density_lag1"], train_mask, "limit_density")
    r3_gate = liquidity_label == "liquidity_low"
    r4_gate = limit_label == "limit_density_high"
    active = oos_mask & r3_gate
    inactive = oos_mask & (~r3_gate)
    gated = returns.where(active, 0.0)
    active_returns = returns[active]

    prev_dates = frame["date"].shift(1)
    gate_lag_rows: list[dict[str, Any]] = []
    for idx, row in frame[oos_mask].iterrows():
        gate_lag_rows.append(
            {
                "trade_date": row["date"].date().isoformat(),
                "feature_source_date": prev_dates.loc[idx].date().isoformat() if pd.notna(prev_dates.loc[idx]) else None,
                "gate_feature_columns": "liquidity_ratio_lag1|limit_density_lag1",
                "feature_source_before_trade_date": bool(pd.notna(prev_dates.loc[idx]) and prev_dates.loc[idx] < row["date"]),
                "r3_gate_active": bool(r3_gate.loc[idx]),
                "limit_density_bucket": str(limit_label.loc[idx]),
            }
        )
    gate_lag_pass = all(item["feature_source_before_trade_date"] for item in gate_lag_rows)

    active_sorted = active_returns.sort_values(ascending=False)
    active_sum = float(active_returns.sum()) if not active_returns.empty else 0.0
    top_rows: list[dict[str, Any]] = []
    for rank, (idx, value) in enumerate(active_sorted.head(10).items(), start=1):
        top_rows.append(
            {
                "rank": rank,
                "date": frame.loc[idx, "date"].date().isoformat(),
                "return": _round(value, 8),
                "share_of_active_arithmetic_sum": _round(value / active_sum if abs(active_sum) > 1e-12 else None),
                "limit_density_bucket": str(limit_label.loc[idx]),
                "liquidity_bucket": str(liquidity_label.loc[idx]),
            }
        )

    contribution_rows = []
    for n in [1, 3, 5]:
        top_sum = float(active_sorted.head(n).sum()) if not active_sorted.empty else 0.0
        contribution_rows.append(
            {
                "top_n_active_days": n,
                "top_n_sum_return": _round(top_sum, 8),
                "share_of_active_arithmetic_sum": _round(top_sum / active_sum if abs(active_sum) > 1e-12 else None),
            }
        )

    winsor_rows = []
    for tail in [0.025, 0.05, 0.10]:
        win = _winsorized(active_returns, tail)
        row = {"winsor_tail": tail}
        row.update({f"winsor_active_{key}": value for key, value in _metrics(win).items()})
        winsor_rows.append(row)

    two_by_two_rows = []
    for r3_name, r3_mask in [("R3_on", r3_gate), ("R3_off", ~r3_gate)]:
        for limit_name, limit_mask in [
            ("limit_high", r4_gate),
            ("limit_not_high", ~r4_gate),
            ("limit_low", limit_label == "limit_density_low"),
            ("limit_mid", limit_label == "limit_density_mid"),
        ]:
            mask = oos_mask & r3_mask & limit_mask
            row = {"r3_state": r3_name, "limit_state": limit_name}
            row.update(_metrics(returns[mask]))
            row["days"] = int(mask.sum())
            row["return_sum"] = _round(float(returns[mask].sum()) if int(mask.sum()) else None, 8)
            two_by_two_rows.append(row)

    placebo_summary = []
    if o3_summary_path.exists():
        o3 = pd.read_csv(o3_summary_path)
        block = o3[o3["gate"].astype(str) == "R3_liquidity_low"]
        if not block.empty:
            placebo_summary = block.to_dict("records")

    summary = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3o6_active_return_sanity_audit",
        "decision": "PASS_ACTIVE_RETURN_SANITY_AUDIT" if gate_lag_pass else "FAIL_GATE_LAG_AUDIT",
        "scope": "locked_X0_R3_active_day_sanity_no_gate_or_book_changes",
        "book": BOOK,
        "window": [OOS_START, OOS_END],
        "gate_lag_check": {
            "decision": "PASS" if gate_lag_pass else "FAIL",
            "gate_features": ["liquidity_ratio_lag1", "limit_density_lag1"],
            "source_implementation": "build_pit_market_regime_state_frame uses rolling aggregates shifted by one trading day",
            "checked_oos_rows": len(gate_lag_rows),
            "violations": sum(1 for item in gate_lag_rows if not item["feature_source_before_trade_date"]),
        },
        "full_calendar_metrics": _metrics(gated[oos_mask]),
        "active_metrics": _metrics(active_returns),
        "inactive_metrics": _metrics(returns[inactive]),
        "active_day_concentration": {
            "active_arithmetic_sum": _round(active_sum, 8),
            "max_active_day_return": _round(float(active_returns.max()) if not active_returns.empty else None, 8),
            "top_1_share": contribution_rows[0]["share_of_active_arithmetic_sum"],
            "top_3_share": contribution_rows[1]["share_of_active_arithmetic_sum"],
            "top_5_share": contribution_rows[2]["share_of_active_arithmetic_sum"],
        },
        "placebo_summary_source": str(o3_summary_path) if placebo_summary else None,
        "placebo_summary_R3": placebo_summary,
        "outputs": {
            "gate_lag_csv": str(output_root / "phase3o6_gate_lag_check.csv"),
            "active_top_days_csv": str(output_root / "phase3o6_active_top_days.csv"),
            "active_contribution_csv": str(output_root / "phase3o6_active_day_contribution.csv"),
            "winsorized_csv": str(output_root / "phase3o6_winsorized_active_metrics.csv"),
            "r3_limit_2x2_csv": str(output_root / "phase3o6_r3_limit_density_2x2.csv"),
            "summary_json": str(output_root / "phase3o6_active_return_sanity_audit.json"),
            "summary_md": str(output_root / "PHASE3O6_ACTIVE_RETURN_SANITY_AUDIT_2026-05-17.md"),
        },
    }

    _write_csv(output_root / "phase3o6_gate_lag_check.csv", gate_lag_rows)
    _write_csv(output_root / "phase3o6_active_top_days.csv", top_rows)
    _write_csv(output_root / "phase3o6_active_day_contribution.csv", contribution_rows)
    _write_csv(output_root / "phase3o6_winsorized_active_metrics.csv", winsor_rows)
    _write_csv(output_root / "phase3o6_r3_limit_density_2x2.csv", two_by_two_rows)
    _write_json(output_root / "phase3o6_active_return_sanity_audit.json", summary)

    md = [
        "# Phase3O6 Active Return Sanity Audit",
        "",
        f"- decision: `{summary['decision']}`",
        f"- book: `{BOOK}`",
        f"- window: `{OOS_START}` to `{OOS_END}`",
        "- scope: no formula, cluster, gate, or weight changes.",
        "",
        "## Gate Lag",
        "",
        f"- gate_lag_decision: `{summary['gate_lag_check']['decision']}`",
        "- gate features are `liquidity_ratio_lag1` and `limit_density_lag1`.",
        f"- checked_oos_rows: `{summary['gate_lag_check']['checked_oos_rows']}`",
        f"- violations: `{summary['gate_lag_check']['violations']}`",
        "",
        "## R3 Performance Decomposition",
        "",
        f"- full_calendar_ann_compound: `{summary['full_calendar_metrics']['ann_compound']}`",
        f"- active_ann_compound: `{summary['active_metrics']['ann_compound']}`",
        f"- active_days: `{summary['active_metrics']['days']}`",
        f"- active_mean_daily: `{summary['active_metrics']['mean_daily']}`",
        f"- active_median_daily: `{summary['active_metrics']['median_daily']}`",
        f"- active_total_return: `{summary['active_metrics']['total_return']}`",
        "",
        "## Active-Day Concentration",
        "",
        f"- top_1_share_of_active_arithmetic_sum: `{summary['active_day_concentration']['top_1_share']}`",
        f"- top_3_share_of_active_arithmetic_sum: `{summary['active_day_concentration']['top_3_share']}`",
        f"- top_5_share_of_active_arithmetic_sum: `{summary['active_day_concentration']['top_5_share']}`",
        "",
        "## R3 x Limit-Density 2x2",
        "",
        "| R3 | limit state | days | mean daily | ann compound | return sum | max dd |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in two_by_two_rows:
        if row["limit_state"] in {"limit_high", "limit_not_high"}:
            md.append(
                f"| {row['r3_state']} | {row['limit_state']} | {row['days']} | {row.get('mean_daily')} | {row.get('ann_compound')} | {row.get('return_sum')} | {row.get('max_drawdown')} |"
            )
    md.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Active-day annualization is a conditional intensity metric, not full strategy annualization.",
            "- The formal strategy headline remains full-calendar gated performance.",
            "- Limit density is evaluated here as an explanatory interaction, not a promoted gate change.",
            "",
        ]
    )
    (output_root / "PHASE3O6_ACTIVE_RETURN_SANITY_AUDIT_2026-05-17.md").write_text("\n".join(md), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--daily-returns", type=Path, default=DEFAULT_DAILY_RETURNS)
    parser.add_argument("--o3-summary", type=Path, default=DEFAULT_O3_SUMMARY)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        dataset_path=args.dataset_path,
        daily_returns_path=args.daily_returns,
        o3_summary_path=args.o3_summary,
        output_root=args.output_root,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

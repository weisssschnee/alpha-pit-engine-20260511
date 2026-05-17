"""Regime-conditioned OOS audit for locked Phase3L/Phase3N books.

This is a no-search audit. It uses lagged market-state features to select
regime buckets on a training window, then evaluates the frozen daily book
returns on a later window.
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


DEFAULT_DATASET = Path(r"G:\Project_V7_Rotation\scripts\data\phase3n_stock_tdx_official_20200101_to_20260508_maxopt.parquet")
DEFAULT_DAILY_RETURNS = Path("reports/phase3n_long_history_locked_validation_20260517/phase3n_daily_returns.csv")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3o_regime_conditioned_oos_20260517")

BOOK_COLUMNS = ["candidate_book_6", "research_pool_9", "oracle_diagnostic_3"]
AXES = {
    "trend": "trend_mean_lag1",
    "volatility": "volatility_lag1",
    "liquidity": "liquidity_ratio_lag1",
    "limit_density": "limit_density_lag1",
    "breadth": "up_ratio",
}
SPLITS = [
    {
        "split_id": "pre2025_train_to_2025h2_oos",
        "train_start": "2020-01-01",
        "train_end": "2024-12-31",
        "oos_start": "2025-07-01",
        "oos_end": "2025-12-31",
    },
    {
        "split_id": "2025h2_train_to_2026_oos",
        "train_start": "2025-07-01",
        "train_end": "2025-12-31",
        "oos_start": "2026-01-01",
        "oos_end": "2026-05-08",
    },
]


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
    total = float((1.0 + clean).prod() - 1.0)
    return {
        "days": int(clean.shape[0]),
        "mean_daily": _round(mean, 8),
        "ann_simple": _round(mean * 252.0),
        "ann_compound": _round((1.0 + mean) ** 252 - 1.0 if mean > -1.0 else None),
        "sharpe": _round(mean / std * math.sqrt(252.0) if std > 1e-12 else None),
        "sortino": _round(mean / downside_std * math.sqrt(252.0) if downside_std > 1e-12 else None),
        "hit_rate": _round((clean > 0.0).mean()),
        "max_drawdown": _round(_max_drawdown(clean), 8),
        "total_return": _round(total),
    }


def _bucket_by_train_thresholds(
    values: pd.Series,
    *,
    train_mask: pd.Series,
    prefix: str,
) -> pd.Series:
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


def _selected_bucket(row: dict[str, Any]) -> bool:
    return (
        int(row.get("train_days") or 0) >= 25
        and (row.get("regime_bucket") or "").find("unknown") < 0
        and (_safe_float(row.get("train_mean_daily")) or -1.0) > 0.0
        and (_safe_float(row.get("train_hit_rate")) or 0.0) >= 0.50
    )


def run(*, dataset_path: Path, daily_returns_path: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    panel = pd.read_parquet(
        dataset_path,
        columns=["date", "code", "close", "amount", "rt_change_pct"],
    )
    regime = build_pit_market_regime_state_frame(panel)
    regime["date"] = pd.to_datetime(regime["date"], errors="coerce")
    returns = pd.read_csv(daily_returns_path, parse_dates=["date"])
    merged = returns.merge(regime, on="date", how="left").sort_values("date")

    unconditional_rows: list[dict[str, Any]] = []
    bucket_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []

    for split in SPLITS:
        split_id = split["split_id"]
        train_mask = (merged["date"] >= split["train_start"]) & (merged["date"] <= split["train_end"])
        oos_mask = (merged["date"] >= split["oos_start"]) & (merged["date"] <= split["oos_end"])
        for book in BOOK_COLUMNS:
            train_metrics = _metrics(merged.loc[train_mask, book])
            oos_metrics = _metrics(merged.loc[oos_mask, book])
            unconditional_rows.append(
                {
                    "split_id": split_id,
                    "book": book,
                    "train_start": split["train_start"],
                    "train_end": split["train_end"],
                    "oos_start": split["oos_start"],
                    "oos_end": split["oos_end"],
                    **{f"train_{k}": v for k, v in train_metrics.items()},
                    **{f"oos_{k}": v for k, v in oos_metrics.items()},
                }
            )
        for axis, column in AXES.items():
            labels = _bucket_by_train_thresholds(merged[column], train_mask=train_mask, prefix=axis)
            for book in BOOK_COLUMNS:
                for bucket in sorted(labels.dropna().unique()):
                    bucket_mask = labels == bucket
                    train_metrics = _metrics(merged.loc[train_mask & bucket_mask, book])
                    oos_metrics = _metrics(merged.loc[oos_mask & bucket_mask, book])
                    row = {
                        "split_id": split_id,
                        "book": book,
                        "regime_axis": axis,
                        "regime_column": column,
                        "regime_bucket": str(bucket),
                        "train_start": split["train_start"],
                        "train_end": split["train_end"],
                        "oos_start": split["oos_start"],
                        "oos_end": split["oos_end"],
                        **{f"train_{k}": v for k, v in train_metrics.items()},
                        **{f"oos_{k}": v for k, v in oos_metrics.items()},
                    }
                    row["selected_by_train_rule"] = _selected_bucket(row)
                    bucket_rows.append(row)
                    if row["selected_by_train_rule"]:
                        selected_rows.append(row)

    _write_csv(output_root / "phase3o_unconditional_split_metrics.csv", unconditional_rows)
    _write_csv(output_root / "phase3o_regime_bucket_oos_metrics.csv", bucket_rows)
    _write_csv(output_root / "phase3o_selected_regime_oos_metrics.csv", selected_rows)

    candidate_selected = [
        row
        for row in selected_rows
        if row["book"] == "candidate_book_6"
        and row["split_id"] == "2025h2_train_to_2026_oos"
        and int(row.get("oos_days") or 0) >= 15
    ]
    candidate_positive_oos = [row for row in candidate_selected if (_safe_float(row.get("oos_mean_daily")) or -1.0) > 0.0]
    earlier_selected = [
        row
        for row in selected_rows
        if row["book"] == "candidate_book_6"
        and row["split_id"] == "pre2025_train_to_2025h2_oos"
        and int(row.get("oos_days") or 0) >= 15
    ]
    earlier_positive_oos = [row for row in earlier_selected if (_safe_float(row.get("oos_mean_daily")) or -1.0) > 0.0]
    decision = (
        "PASS_RECENT_REGIME_CONDITIONED_OOS"
        if candidate_selected and len(candidate_positive_oos) >= max(1, math.ceil(len(candidate_selected) * 0.5))
        else "HOLD_RECENT_REGIME_CONDITIONED_OOS"
    )
    summary = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3o_regime_conditioned_oos",
        "decision": decision,
        "scope": "locked_daily_returns_lagged_market_regime_no_formula_tuning",
        "dataset_path": str(dataset_path),
        "daily_returns_path": str(daily_returns_path),
        "splits": SPLITS,
        "book_columns": BOOK_COLUMNS,
        "axes": AXES,
        "candidate_2025h2_selected_bucket_count": len(candidate_selected),
        "candidate_2025h2_selected_positive_oos_count": len(candidate_positive_oos),
        "candidate_pre2025_selected_bucket_count": len(earlier_selected),
        "candidate_pre2025_selected_positive_oos_count": len(earlier_positive_oos),
        "outputs": {
            "unconditional_csv": str(output_root / "phase3o_unconditional_split_metrics.csv"),
            "bucket_csv": str(output_root / "phase3o_regime_bucket_oos_metrics.csv"),
            "selected_csv": str(output_root / "phase3o_selected_regime_oos_metrics.csv"),
            "summary_json": str(output_root / "phase3o_regime_conditioned_oos.json"),
            "summary_md": str(output_root / "PHASE3O_REGIME_CONDITIONED_OOS_2026-05-17.md"),
        },
        "not_confirmed": [
            "true_hmm_regime_model",
            "minute_execution",
            "live_regime_switching",
        ],
    }
    _write_json(output_root / "phase3o_regime_conditioned_oos.json", summary)

    best_recent = sorted(
        candidate_selected,
        key=lambda row: _safe_float(row.get("oos_mean_daily")) or -999.0,
        reverse=True,
    )[:8]
    md = [
        "# Phase3O Regime-Conditioned OOS Audit",
        "",
        f"- decision: `{decision}`",
        "- scope: `locked_daily_returns_lagged_market_regime_no_formula_tuning`",
        f"- dataset: `{dataset_path}`",
        f"- daily_returns: `{daily_returns_path}`",
        "",
        "## Interpretation",
        "",
        "- This audit tests whether regime buckets selected on one window remain useful on the next window.",
        "- The 2025H2 -> 2026 split is the relevant recent-regime OOS test.",
        "- The 2020-2024 -> 2025H2 split tests whether the same book had an earlier stable regime rule.",
        "",
        "## Unconditional Splits",
        "",
        "| split | book | train ann | train sharpe | oos ann | oos sharpe | oos dd |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in unconditional_rows:
        md.append(
            f"| {row['split_id']} | {row['book']} | {row.get('train_ann_compound')} | {row.get('train_sharpe')} | {row.get('oos_ann_compound')} | {row.get('oos_sharpe')} | {row.get('oos_max_drawdown')} |"
        )
    md.extend(
        [
            "",
            "## Candidate Book: 2025H2-Selected Regimes Tested on 2026",
            "",
            "| axis | bucket | train days | train ann | train sharpe | oos days | oos ann | oos sharpe | oos dd |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in best_recent:
        md.append(
            f"| {row['regime_axis']} | {row['regime_bucket']} | {row.get('train_days')} | {row.get('train_ann_compound')} | {row.get('train_sharpe')} | {row.get('oos_days')} | {row.get('oos_ann_compound')} | {row.get('oos_sharpe')} | {row.get('oos_max_drawdown')} |"
        )
    md.extend(
        [
            "",
            "## Boundaries",
            "",
            "- Regime buckets use lagged market aggregates; no formula or book weights were changed.",
            "- Bucket thresholds for quantile axes are fitted on the train window only, then applied to OOS.",
            "- This is still daily proxy evidence, not execution or live proof.",
            "",
        ]
    )
    (output_root / "PHASE3O_REGIME_CONDITIONED_OOS_2026-05-17.md").write_text("\n".join(md), encoding="utf-8")
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

"""Historical analog replay for the locked R3 liquidity-low gate.

This script does not search, retune, or change alpha clusters. It applies the
fixed R3 threshold learned from 2025H2 to earlier history and reports whether
similar liquidity-low states existed before the recent regime.
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
DEFAULT_OUTPUT_ROOT = Path("reports/phase3p_historical_analog_regime_replay_20260517")
BOOK = "candidate_book_6"
TRAIN_START = "2025-07-01"
TRAIN_END = "2025-12-31"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


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


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _round(value: Any, digits: int = 6) -> float | None:
    value = _safe_float(value)
    return round(value, digits) if value is not None else None


def _max_drawdown(values: pd.Series) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").fillna(0.0)
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


def _window_row(name: str, frame: pd.DataFrame, mask: pd.Series) -> dict[str, Any]:
    returns = pd.to_numeric(frame[BOOK], errors="coerce").fillna(0.0)
    gate = frame["r3_liquidity_low_active"].fillna(False).astype(bool)
    active = mask & gate
    inactive = mask & (~gate)
    gated_full = returns.where(active, 0.0)
    row = {
        "window": name,
        "calendar_days": int(mask.sum()),
        "active_days": int(active.sum()),
        "active_ratio": _round(active.sum() / mask.sum() if int(mask.sum()) else None),
        "liquidity_ratio_lag1_median_active": _round(frame.loc[active, "liquidity_ratio_lag1"].median()),
        "liquidity_ratio_lag1_p10_active": _round(frame.loc[active, "liquidity_ratio_lag1"].quantile(0.1)),
        "liquidity_ratio_lag1_p90_active": _round(frame.loc[active, "liquidity_ratio_lag1"].quantile(0.9)),
    }
    row.update({f"full_{key}": value for key, value in _metrics(gated_full[mask]).items()})
    row.update({f"active_{key}": value for key, value in _metrics(returns[active]).items()})
    row.update({f"inactive_{key}": value for key, value in _metrics(returns[inactive]).items()})
    return row


def run(*, dataset_path: Path, daily_returns_path: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    panel = pd.read_parquet(dataset_path, columns=["date", "code", "close", "amount", "rt_change_pct"])
    regime = build_pit_market_regime_state_frame(panel)
    regime["date"] = pd.to_datetime(regime["date"], errors="coerce")
    train_mask = (regime["date"] >= TRAIN_START) & (regime["date"] <= TRAIN_END)
    liquidity = pd.to_numeric(regime["liquidity_ratio_lag1"], errors="coerce")
    threshold = float(liquidity[train_mask & liquidity.notna()].quantile(1 / 3))
    regime["r3_liquidity_low_active"] = liquidity <= threshold
    returns = pd.read_csv(daily_returns_path, parse_dates=["date"])
    merged = returns.merge(regime, on="date", how="left").sort_values("date").reset_index(drop=True)
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce")

    windows = {
        "all_history_2020_2026": (merged["date"] >= "2020-01-01") & (merged["date"] <= "2026-05-08"),
        "historical_2020_2024": (merged["date"] >= "2020-01-01") & (merged["date"] <= "2024-12-31"),
        "train_2025h2": (merged["date"] >= "2025-07-01") & (merged["date"] <= "2025-12-31"),
        "recent_oos_2026": (merged["date"] >= "2026-01-01") & (merged["date"] <= "2026-05-08"),
        "recent_2025h2_2026": (merged["date"] >= "2025-07-01") & (merged["date"] <= "2026-05-08"),
    }
    rows = [_window_row(name, merged, mask) for name, mask in windows.items()]
    yearly_rows = []
    for year in range(2020, 2027):
        mask = merged["date"].dt.year == year
        if int(mask.sum()) > 0:
            yearly_rows.append(_window_row(str(year), merged, mask))

    active_days = merged[merged["r3_liquidity_low_active"].fillna(False).astype(bool)].copy()
    active_days["return"] = pd.to_numeric(active_days[BOOK], errors="coerce")
    active_day_rows = [
        {
            "date": row["date"].date().isoformat(),
            "return": _round(row["return"], 8),
            "liquidity_ratio_lag1": _round(row.get("liquidity_ratio_lag1")),
            "pit_regime_label": row.get("pit_regime_label"),
            "window": (
                "historical_2020_2024"
                if row["date"] <= pd.Timestamp("2024-12-31")
                else "recent_2025_2026"
            ),
        }
        for row in active_days.to_dict(orient="records")
    ]

    historical = next(row for row in rows if row["window"] == "historical_2020_2024")
    recent = next(row for row in rows if row["window"] == "recent_2025h2_2026")
    if historical["active_days"] < 40:
        decision = "HOLD_R3_HISTORICAL_ANALOG_SAMPLE_TOO_SMALL"
    elif (_safe_float(historical.get("active_ann_compound")) or -999.0) <= 0.0 and (
        _safe_float(recent.get("active_ann_compound")) or -999.0
    ) > 0.0:
        decision = "HOLD_R3_POST_2025_REGIME_ONLY"
    else:
        decision = "PASS_R3_HISTORICAL_ANALOG_SUPPORT"

    _write_csv(output_root / "phase3p_historical_analog_window_metrics.csv", rows)
    _write_csv(output_root / "phase3p_historical_analog_yearly_metrics.csv", yearly_rows)
    _write_csv(output_root / "phase3p_historical_analog_active_days.csv", active_day_rows)
    summary = {
        "created_at": _now(),
        "decision": decision,
        "scope": "fixed_r3_historical_analog_replay_no_search_no_threshold_tuning",
        "book": BOOK,
        "train_window": [TRAIN_START, TRAIN_END],
        "r3_liquidity_ratio_lag1_threshold": threshold,
        "window_metrics": rows,
        "outputs": {
            "window_metrics_csv": str(output_root / "phase3p_historical_analog_window_metrics.csv"),
            "yearly_metrics_csv": str(output_root / "phase3p_historical_analog_yearly_metrics.csv"),
            "active_days_csv": str(output_root / "phase3p_historical_analog_active_days.csv"),
            "summary_json": str(output_root / "phase3p_historical_analog_summary.json"),
            "summary_md": str(output_root / "PHASE3P_HISTORICAL_ANALOG_REGIME_REPLAY_2026-05-17.md"),
        },
        "not_confirmed": ["production_ready", "live_survival", "minute_execution", "true_capacity"],
    }
    _write_json(output_root / "phase3p_historical_analog_summary.json", summary)
    md = [
        "# Phase3P Historical Analog Regime Replay",
        "",
        f"- decision: `{decision}`",
        f"- fixed_gate: `R3_liquidity_low`",
        f"- threshold: `{threshold}`",
        f"- book: `{BOOK}`",
        "",
        "## Window Metrics",
        "",
        "| window | calendar days | active days | active ratio | full ann | active ann | inactive ann | active sharpe | active max dd |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        md.append(
            f"| {row['window']} | {row['calendar_days']} | {row['active_days']} | {row['active_ratio']} | {row['full_ann_compound']} | {row['active_ann_compound']} | {row['inactive_ann_compound']} | {row['active_sharpe']} | {row['active_max_drawdown']} |"
        )
    md.extend(
        [
            "",
            "## Interpretation",
            "",
            "- This replay applies the 2025H2 R3 threshold to earlier history without retuning.",
            "- If historical analog states exist but do not work, R3 should be treated as a recent structural-regime gate, not a long-history universal regime.",
            "- This is a regime explanation audit, not a new alpha search.",
            "",
        ]
    )
    (output_root / "PHASE3P_HISTORICAL_ANALOG_REGIME_REPLAY_2026-05-17.md").write_text(
        "\n".join(md),
        encoding="utf-8",
    )
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


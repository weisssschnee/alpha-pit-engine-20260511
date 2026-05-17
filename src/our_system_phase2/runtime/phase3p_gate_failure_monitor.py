"""Failure monitor for the locked Phase3P R3-gated book.

No search, no retuning, no cluster changes. This script explains:
- which clusters contribute to gate-on losses,
- which regimes contribute to gate-off missed gains,
- whether liquidity/limit-density state combinations explain failures.
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
DEFAULT_OUTPUT_ROOT = Path("reports/phase3p_gate_failure_monitor_20260517")

TRAIN_START = "2025-07-01"
TRAIN_END = "2025-12-31"
BOOK = "candidate_book_6"
OFFICIAL_CLUSTERS = ["cluster_001", "cluster_005", "cluster_006", "cluster_009", "cluster_002", "cluster_004"]
WINDOWS = {
    "historical_2020_2024": ("2020-01-01", "2024-12-31"),
    "train_2025h2": ("2025-07-01", "2025-12-31"),
    "recent_oos_2026": ("2026-01-01", "2026-05-08"),
    "recent_2025h2_2026": ("2025-07-01", "2026-05-08"),
}
AXES = {
    "trend": "trend_mean_lag1",
    "volatility": "volatility_lag1",
    "liquidity": "liquidity_ratio_lag1",
    "limit_density": "limit_density_lag1",
    "breadth": "up_ratio",
}


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


def _prepare_frame(dataset_path: Path, daily_returns_path: Path) -> tuple[pd.DataFrame, float]:
    panel = pd.read_parquet(dataset_path, columns=["date", "code", "close", "amount", "rt_change_pct"])
    regime = build_pit_market_regime_state_frame(panel)
    regime["date"] = pd.to_datetime(regime["date"], errors="coerce")
    train_mask = (regime["date"] >= TRAIN_START) & (regime["date"] <= TRAIN_END)
    liquidity = pd.to_numeric(regime["liquidity_ratio_lag1"], errors="coerce")
    threshold = float(liquidity[train_mask & liquidity.notna()].quantile(1 / 3))
    regime["r3_liquidity_low_active"] = liquidity <= threshold
    for axis, column in AXES.items():
        regime[f"{axis}_bucket"] = _bucket_by_train_thresholds(regime[column], train_mask, axis)
    returns = pd.read_csv(daily_returns_path, parse_dates=["date"])
    merged = returns.merge(regime, on="date", how="left").sort_values("date").reset_index(drop=True)
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce")
    cluster_frame = merged[OFFICIAL_CLUSTERS].apply(pd.to_numeric, errors="coerce")
    valid_counts = cluster_frame.notna().sum(axis=1).replace(0, pd.NA)
    for cluster in OFFICIAL_CLUSTERS:
        merged[f"{cluster}_book_contribution"] = cluster_frame[cluster] / valid_counts
    merged["book_return_recomputed"] = cluster_frame.mean(axis=1, skipna=True)
    return merged, threshold


def _window_mask(frame: pd.DataFrame, window: str) -> pd.Series:
    start, end = WINDOWS[window]
    return (frame["date"] >= start) & (frame["date"] <= end)


def _cluster_loss_rows(frame: pd.DataFrame, window: str) -> list[dict[str, Any]]:
    mask = _window_mask(frame, window)
    active_loss = mask & frame["r3_liquidity_low_active"].fillna(False).astype(bool) & (pd.to_numeric(frame[BOOK], errors="coerce") < 0)
    rows = []
    total_loss = -float(pd.to_numeric(frame.loc[active_loss, BOOK], errors="coerce").sum()) if int(active_loss.sum()) else 0.0
    for cluster in OFFICIAL_CLUSTERS:
        contrib = pd.to_numeric(frame.loc[active_loss, f"{cluster}_book_contribution"], errors="coerce").fillna(0.0)
        raw = pd.to_numeric(frame.loc[active_loss, cluster], errors="coerce")
        negative_contrib = -float(contrib[contrib < 0].sum()) if not contrib.empty else 0.0
        rows.append(
            {
                "window": window,
                "cluster_id": cluster,
                "active_loss_days": int(active_loss.sum()),
                "cluster_available_days": int(raw.notna().sum()),
                "cluster_negative_days": int((raw < 0).sum()),
                "cluster_mean_return_on_loss_days": _round(raw.mean(), 8),
                "cluster_sum_book_contribution_on_loss_days": _round(contrib.sum(), 8),
                "cluster_negative_book_contribution": _round(negative_contrib, 8),
                "share_of_total_loss_abs": _round(negative_contrib / total_loss if total_loss > 1e-12 else None),
            }
        )
    return rows


def _active_loss_day_rows(frame: pd.DataFrame, window: str) -> list[dict[str, Any]]:
    mask = _window_mask(frame, window)
    active_loss = frame[
        mask & frame["r3_liquidity_low_active"].fillna(False).astype(bool) & (pd.to_numeric(frame[BOOK], errors="coerce") < 0)
    ].copy()
    rows = []
    for _, row in active_loss.sort_values(BOOK).head(40).iterrows():
        contribs = {
            cluster: _safe_float(row.get(f"{cluster}_book_contribution"), 0.0) or 0.0
            for cluster in OFFICIAL_CLUSTERS
        }
        worst_cluster = min(contribs, key=contribs.get) if contribs else None
        rows.append(
            {
                "window": window,
                "date": row["date"].date().isoformat(),
                "book_return": _round(row.get(BOOK), 8),
                "worst_cluster": worst_cluster,
                "worst_cluster_contribution": _round(contribs.get(worst_cluster), 8) if worst_cluster else None,
                "liquidity_ratio_lag1": _round(row.get("liquidity_ratio_lag1")),
                "limit_density_lag1": _round(row.get("limit_density_lag1")),
                "trend_bucket": row.get("trend_bucket"),
                "volatility_bucket": row.get("volatility_bucket"),
                "liquidity_bucket": row.get("liquidity_bucket"),
                "limit_density_bucket": row.get("limit_density_bucket"),
                "pit_regime_label": row.get("pit_regime_label"),
            }
        )
    return rows


def _missed_return_rows(frame: pd.DataFrame, window: str, group_col: str) -> list[dict[str, Any]]:
    mask = _window_mask(frame, window)
    gate_off = mask & (~frame["r3_liquidity_low_active"].fillna(False).astype(bool))
    returns = pd.to_numeric(frame[BOOK], errors="coerce").fillna(0.0)
    missed_gain = gate_off & (returns > 0)
    rows = []
    for group, block in frame.loc[gate_off].groupby(group_col, dropna=False):
        block_returns = pd.to_numeric(block[BOOK], errors="coerce").fillna(0.0)
        block_positive = block_returns[block_returns > 0]
        rows.append(
            {
                "window": window,
                "group_col": group_col,
                "group": str(group),
                "gate_off_days": int(block.shape[0]),
                "missed_positive_days": int((block_returns > 0).sum()),
                "missed_positive_sum": _round(block_positive.sum(), 8),
                "gate_off_total_return_sum": _round(block_returns.sum(), 8),
                "gate_off_mean_return": _round(block_returns.mean(), 8),
                "share_of_all_missed_positive_sum": None,
            }
        )
    total_positive = sum((_safe_float(row["missed_positive_sum"], 0.0) or 0.0) for row in rows)
    for row in rows:
        row["share_of_all_missed_positive_sum"] = _round(
            (_safe_float(row["missed_positive_sum"], 0.0) or 0.0) / total_positive if total_positive > 1e-12 else None
        )
    return sorted(rows, key=lambda item: _safe_float(item.get("missed_positive_sum"), 0.0) or 0.0, reverse=True)


def _state_combo_rows(frame: pd.DataFrame, window: str) -> list[dict[str, Any]]:
    mask = _window_mask(frame, window)
    work = frame[mask].copy()
    returns = pd.to_numeric(work[BOOK], errors="coerce").fillna(0.0)
    work["book_return"] = returns
    rows = []
    for (liquidity_bucket, limit_bucket), block in work.groupby(["liquidity_bucket", "limit_density_bucket"], dropna=False):
        block_returns = pd.to_numeric(block["book_return"], errors="coerce").fillna(0.0)
        gate = block["r3_liquidity_low_active"].fillna(False).astype(bool)
        active = block_returns[gate]
        inactive = block_returns[~gate]
        rows.append(
            {
                "window": window,
                "liquidity_bucket": str(liquidity_bucket),
                "limit_density_bucket": str(limit_bucket),
                "days": int(block.shape[0]),
                "active_days": int(gate.sum()),
                "inactive_days": int((~gate).sum()),
                "active_mean_return": _round(active.mean(), 8),
                "active_negative_days": int((active < 0).sum()),
                "inactive_mean_return": _round(inactive.mean(), 8),
                "inactive_positive_days": int((inactive > 0).sum()),
                "inactive_positive_sum": _round(inactive[inactive > 0].sum(), 8),
            }
        )
    return rows


def run(*, dataset_path: Path, daily_returns_path: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    frame, threshold = _prepare_frame(dataset_path, daily_returns_path)
    windows = ["historical_2020_2024", "train_2025h2", "recent_oos_2026", "recent_2025h2_2026"]
    cluster_loss_rows: list[dict[str, Any]] = []
    active_loss_day_rows: list[dict[str, Any]] = []
    missed_rows: list[dict[str, Any]] = []
    state_combo_rows: list[dict[str, Any]] = []
    for window in windows:
        cluster_loss_rows.extend(_cluster_loss_rows(frame, window))
        active_loss_day_rows.extend(_active_loss_day_rows(frame, window))
        for group_col in ["pit_regime_label", "trend_bucket", "volatility_bucket", "liquidity_bucket", "limit_density_bucket", "breadth_bucket"]:
            missed_rows.extend(_missed_return_rows(frame, window, group_col))
        state_combo_rows.extend(_state_combo_rows(frame, window))

    _write_csv(output_root / "phase3p_gate_on_loss_cluster_attribution.csv", cluster_loss_rows)
    _write_csv(output_root / "phase3p_gate_on_loss_days.csv", active_loss_day_rows)
    _write_csv(output_root / "phase3p_gate_off_missed_return_by_regime.csv", missed_rows)
    _write_csv(output_root / "phase3p_gate_state_combo_monitor.csv", state_combo_rows)

    recent_cluster_loss = [row for row in cluster_loss_rows if row["window"] == "recent_oos_2026"]
    recent_missed = [row for row in missed_rows if row["window"] == "recent_oos_2026" and row["group_col"] == "pit_regime_label"]
    worst_loss_cluster = max(
        recent_cluster_loss,
        key=lambda row: _safe_float(row.get("cluster_negative_book_contribution"), 0.0) or 0.0,
        default=None,
    )
    top_missed_group = max(
        recent_missed,
        key=lambda row: _safe_float(row.get("missed_positive_sum"), 0.0) or 0.0,
        default=None,
    )
    cluster_002_recent = next(
        (row for row in recent_cluster_loss if row["cluster_id"] == "cluster_002"),
        None,
    )
    decision = "PASS_PHASE3P_GATE_FAILURE_MONITOR_CREATED"
    summary = {
        "created_at": _now(),
        "decision": decision,
        "scope": "fixed_r3_gate_failure_monitor_no_search_no_retuning",
        "book": BOOK,
        "official_clusters": OFFICIAL_CLUSTERS,
        "r3_liquidity_ratio_lag1_threshold": threshold,
        "recent_oos_worst_loss_cluster": worst_loss_cluster,
        "recent_oos_cluster_002_loss_attribution": cluster_002_recent,
        "recent_oos_top_gate_off_missed_regime": top_missed_group,
        "outputs": {
            "loss_cluster_attribution_csv": str(output_root / "phase3p_gate_on_loss_cluster_attribution.csv"),
            "loss_days_csv": str(output_root / "phase3p_gate_on_loss_days.csv"),
            "missed_return_by_regime_csv": str(output_root / "phase3p_gate_off_missed_return_by_regime.csv"),
            "state_combo_monitor_csv": str(output_root / "phase3p_gate_state_combo_monitor.csv"),
            "summary_json": str(output_root / "phase3p_gate_failure_monitor_summary.json"),
            "summary_md": str(output_root / "PHASE3P_GATE_FAILURE_MONITOR_2026-05-17.md"),
        },
        "not_confirmed": ["production_ready", "live_survival", "minute_execution", "true_capacity"],
    }
    _write_json(output_root / "phase3p_gate_failure_monitor_summary.json", summary)
    md = [
        "# Phase3P Gate Failure Monitor",
        "",
        f"- decision: `{decision}`",
        "- scope: `fixed_r3_gate_failure_monitor_no_search_no_retuning`",
        f"- r3_threshold: `{threshold}`",
        "",
        "## Recent OOS 2026 Findings",
        "",
    ]
    if worst_loss_cluster:
        md.extend(
            [
                "Worst gate-on loss contributor:",
                "",
                f"- cluster: `{worst_loss_cluster['cluster_id']}`",
                f"- negative book contribution on active loss days: `{worst_loss_cluster['cluster_negative_book_contribution']}`",
                f"- share of total loss abs: `{worst_loss_cluster['share_of_total_loss_abs']}`",
                "",
            ]
        )
    if cluster_002_recent:
        md.extend(
            [
                "cluster_002 watch:",
                "",
                f"- negative book contribution: `{cluster_002_recent['cluster_negative_book_contribution']}`",
                f"- share of total loss abs: `{cluster_002_recent['share_of_total_loss_abs']}`",
                f"- mean return on active loss days: `{cluster_002_recent['cluster_mean_return_on_loss_days']}`",
                "",
            ]
        )
    if top_missed_group:
        md.extend(
            [
                "Largest gate-off missed positive regime:",
                "",
                f"- group: `{top_missed_group['group']}`",
                f"- missed positive sum: `{top_missed_group['missed_positive_sum']}`",
                f"- share of missed positives: `{top_missed_group['share_of_all_missed_positive_sum']}`",
                "",
            ]
        )
    md.extend(
        [
            "## Output Tables",
            "",
            "- `phase3p_gate_on_loss_cluster_attribution.csv`",
            "- `phase3p_gate_on_loss_days.csv`",
            "- `phase3p_gate_off_missed_return_by_regime.csv`",
            "- `phase3p_gate_state_combo_monitor.csv`",
            "",
            "## Boundary",
            "",
            "This monitor explains locked gate behavior. It does not tune R3, change cluster membership, or promote any new rule.",
            "",
        ]
    )
    (output_root / "PHASE3P_GATE_FAILURE_MONITOR_2026-05-17.md").write_text("\n".join(md), encoding="utf-8")
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


"""Phase3L-L daily regime-proxy audit for the frozen daily proof book.

This is not true regime replay. It recomputes daily long-short returns for the
frozen Phase3L-K survivor book and buckets those daily returns by deterministic
PIT market-state labels built from lagged market aggregates.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from our_system_phase2.services.market_regime_state import (
    build_pit_market_regime_state_frame,
    summarize_regime_coverage,
)
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH
from our_system_phase2.services.real_market_validation import (
    SIGNAL_CLOCK_AFTER_OPEN,
    _load_recent_quarter_market_panel,
    _signal_evaluation_frame,
    _tradable_daily_ic_spread_turnover_frame,
    _tradable_signal_work_frame,
    evaluate_panel_expression,
)


DEFAULT_BOOK = Path("reports/phase3l_k_daily_proof_book_20260517/phase3l_daily_strong_proof_book.csv")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3l_l_regime_proxy_audit_20260517")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _quantile(values: list[float], q: float) -> float | None:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    pos = (len(clean) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return clean[int(pos)]
    return clean[lo] * (hi - pos) + clean[hi] * (pos - lo)


def _sortino(values: pd.Series) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return None
    downside = clean[clean < 0.0]
    if downside.empty:
        return round(float(clean.mean()), 6)
    downside_std = float(downside.std(ddof=0))
    if not math.isfinite(downside_std) or downside_std <= 1e-12:
        return None
    return round(float(clean.mean() / downside_std * math.sqrt(len(clean))), 6)


def _summarize_returns(values: pd.Series) -> dict[str, Any]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return {
            "day_count": 0,
            "mean_return": None,
            "median_return": None,
            "positive_day_ratio": None,
            "sortino_proxy": None,
            "min_return": None,
            "p10_return": None,
            "p90_return": None,
        }
    clean_list = [float(value) for value in clean]
    return {
        "day_count": int(len(clean)),
        "mean_return": round(float(clean.mean()), 8),
        "median_return": round(float(clean.median()), 8),
        "positive_day_ratio": round(float((clean > 0.0).mean()), 6),
        "sortino_proxy": _sortino(clean),
        "min_return": round(float(clean.min()), 8),
        "p10_return": round(_quantile(clean_list, 0.10) or 0.0, 8),
        "p90_return": round(_quantile(clean_list, 0.90) or 0.0, 8),
    }


def _bucket_labels(values: pd.Series, *, prefix: str) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    labels = pd.Series("unknown", index=numeric.index, dtype=object)
    valid = numeric.dropna()
    if valid.nunique(dropna=True) < 3:
        return labels
    try:
        bucketed = pd.qcut(valid.rank(method="first"), q=3, labels=[f"{prefix}_low", f"{prefix}_mid", f"{prefix}_high"])
    except ValueError:
        return labels
    labels.loc[bucketed.index] = bucketed.astype(str)
    return labels


def _regime_axis_frame(regime_frame: pd.DataFrame) -> pd.DataFrame:
    """Build long-form lagged regime-proxy axes.

    The original PIT label is kept for traceability, but it can collapse to a
    single state under daily limit-density thresholds. Quantile axes provide a
    separate diagnostic view without using future returns.
    """

    base = regime_frame.copy()
    base["date"] = pd.to_datetime(base["date"], errors="coerce")
    axis_columns: list[tuple[str, pd.Series]] = [
        ("pit_regime_label", base.get("pit_regime_label", pd.Series("unknown", index=base.index)).astype(str)),
        ("trend_lag_quantile", _bucket_labels(base.get("trend_mean_lag1", pd.Series(index=base.index, dtype=float)), prefix="trend")),
        ("volatility_lag_quantile", _bucket_labels(base.get("volatility_lag1", pd.Series(index=base.index, dtype=float)), prefix="vol")),
        ("liquidity_lag_quantile", _bucket_labels(base.get("liquidity_ratio_lag1", pd.Series(index=base.index, dtype=float)), prefix="liq")),
        ("limit_density_lag_quantile", _bucket_labels(base.get("limit_density_lag1", pd.Series(index=base.index, dtype=float)), prefix="limit")),
    ]
    rows: list[dict[str, Any]] = []
    for axis, labels in axis_columns:
        for date, label in zip(base["date"], labels):
            if pd.isna(date):
                continue
            rows.append({"date": date, "regime_axis": axis, "regime_bucket": str(label)})
    return pd.DataFrame(rows, columns=["date", "regime_axis", "regime_bucket"])


def _axis_decision(rows: list[dict[str, Any]]) -> dict[str, Any]:
    covered = [row for row in rows if int(row.get("day_count") or 0) > 0 and str(row.get("regime_bucket")) != "unknown"]
    means = [_safe_float(row.get("mean_return")) for row in covered]
    positive_ratios = [_safe_float(row.get("positive_day_ratio")) for row in covered]
    valid_means = [value for value in means if value is not None]
    valid_positive = [value for value in positive_ratios if value is not None]
    positive_bucket_count = sum(1 for value in valid_means if value > 0.0)
    worst = min(covered, key=lambda row: _safe_float(row.get("mean_return"), default=0.0) or 0.0) if covered else None
    abs_by_bucket = [
        abs(_safe_float(row.get("mean_return"), default=0.0) or 0.0) * int(row.get("day_count") or 0)
        for row in covered
    ]
    total_abs = float(sum(abs_by_bucket))
    dominant_share = max(abs_by_bucket) / total_abs if total_abs > 1e-12 and abs_by_bucket else None
    covered_count = len(covered)
    if covered_count < 2:
        decision = "HOLD_INSUFFICIENT_AXIS_COVERAGE"
    elif positive_bucket_count >= max(1, math.ceil(covered_count * 0.5)) and (dominant_share is None or dominant_share <= 0.75):
        decision = "PASS_AXIS_DIVERSIFIED"
    else:
        decision = "HOLD_AXIS_CONCENTRATED_OR_WEAK"
    return {
        "covered_bucket_count": covered_count,
        "positive_bucket_count": int(positive_bucket_count),
        "min_bucket_mean_return": round(float(min(valid_means)), 8) if valid_means else None,
        "min_bucket_positive_day_ratio": round(float(min(valid_positive)), 6) if valid_positive else None,
        "worst_bucket": worst.get("regime_bucket") if worst else None,
        "dominant_axis_return_share": round(float(dominant_share), 6) if dominant_share is not None else None,
        "axis_decision": decision,
    }


def _regime_bucket_rows(
    *,
    survivor: dict[str, str],
    daily: pd.DataFrame,
    regime_axes: pd.DataFrame,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    if daily.empty:
        base = {
            "survivor_uid": survivor.get("survivor_uid"),
            "global_signal_cluster_id": survivor.get("global_signal_cluster_id"),
            "source_cluster_id": survivor.get("source_cluster_id"),
            "source_lane": survivor.get("source_lane"),
            "entry_type": survivor.get("entry_type"),
            "expression": survivor.get("expression"),
            "daily_row_count": 0,
            "regime_bucket_count": 0,
            "covered_regime_bucket_count": 0,
            "positive_regime_bucket_count": 0,
            "min_regime_mean_return": None,
            "min_regime_positive_day_ratio": None,
            "worst_regime_label": None,
            "dominant_regime_return_share": None,
            "axis_pass_count": 0,
            "axis_count": 0,
            "proxy_decision": "HOLD_NO_DAILY_ROWS",
        }
        return base, [], []

    work = daily.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    axes = regime_axes.copy()
    axes["date"] = pd.to_datetime(axes["date"], errors="coerce")
    merged = work.merge(axes, on="date", how="left")
    merged["regime_axis"] = merged["regime_axis"].fillna("missing_axis")
    merged["regime_bucket"] = merged["regime_bucket"].fillna("unknown_missing_regime")

    rows: list[dict[str, Any]] = []
    for (axis, label), group in merged.groupby(["regime_axis", "regime_bucket"], sort=True):
        stats = _summarize_returns(group["long_short_return"])
        rows.append(
            {
                "survivor_uid": survivor.get("survivor_uid"),
                "global_signal_cluster_id": survivor.get("global_signal_cluster_id"),
                "source_cluster_id": survivor.get("source_cluster_id"),
                "source_lane": survivor.get("source_lane"),
                "entry_type": survivor.get("entry_type"),
                "regime_axis": str(axis),
                "regime_bucket": str(label),
                **stats,
            }
        )

    axis_rows: list[dict[str, Any]] = []
    for axis in sorted({str(row.get("regime_axis")) for row in rows}):
        axis_bucket_rows = [row for row in rows if str(row.get("regime_axis")) == axis]
        stats = _axis_decision(axis_bucket_rows)
        axis_rows.append(
            {
                "survivor_uid": survivor.get("survivor_uid"),
                "global_signal_cluster_id": survivor.get("global_signal_cluster_id"),
                "source_cluster_id": survivor.get("source_cluster_id"),
                "source_lane": survivor.get("source_lane"),
                "entry_type": survivor.get("entry_type"),
                "regime_axis": axis,
                **stats,
            }
        )

    pass_axes = [row for row in axis_rows if row.get("axis_decision") == "PASS_AXIS_DIVERSIFIED"]
    usable_axes = [row for row in axis_rows if int(row.get("covered_bucket_count") or 0) >= 2]
    worst_axis = None
    if axis_rows:
        worst_axis = min(axis_rows, key=lambda row: _safe_float(row.get("min_bucket_mean_return"), default=0.0) or 0.0)
    decision = (
        "PASS_REGIME_PROXY_DIVERSIFIED"
        if len(pass_axes) >= 2
        else "HOLD_REGIME_PROXY_CONCENTRATED_OR_WEAK"
        if usable_axes
        else "HOLD_INSUFFICIENT_REGIME_COVERAGE"
    )

    summary = {
        "survivor_uid": survivor.get("survivor_uid"),
        "global_signal_cluster_id": survivor.get("global_signal_cluster_id"),
        "source_cluster_id": survivor.get("source_cluster_id"),
        "source_lane": survivor.get("source_lane"),
        "entry_type": survivor.get("entry_type"),
        "expression": survivor.get("expression"),
        "daily_row_count": int(len(merged)),
        "regime_bucket_count": int(merged[["regime_axis", "regime_bucket"]].drop_duplicates().shape[0]),
        "covered_regime_bucket_count": max([int(row.get("covered_bucket_count") or 0) for row in axis_rows] or [0]),
        "positive_regime_bucket_count": max([int(row.get("positive_bucket_count") or 0) for row in axis_rows] or [0]),
        "min_regime_mean_return": worst_axis.get("min_bucket_mean_return") if worst_axis else None,
        "min_regime_positive_day_ratio": worst_axis.get("min_bucket_positive_day_ratio") if worst_axis else None,
        "worst_regime_label": f"{worst_axis.get('regime_axis')}:{worst_axis.get('worst_bucket')}" if worst_axis else None,
        "dominant_regime_return_share": worst_axis.get("dominant_axis_return_share") if worst_axis else None,
        "axis_count": len(axis_rows),
        "usable_axis_count": len(usable_axes),
        "axis_pass_count": len(pass_axes),
        "axis_decision_distribution": json.dumps(dict(sorted(Counter(str(row.get("axis_decision")) for row in axis_rows).items())), ensure_ascii=False),
        "proxy_decision": decision,
    }
    return summary, rows, axis_rows


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Phase3L-L Regime Proxy Audit",
        "",
        f"- generated_at: {summary['created_at']}",
        f"- decision: `{summary['decision']}`",
        f"- scope: `{summary['scope']}`",
        f"- survivor_count: {summary['survivor_count']}",
        f"- proxy_pass_count: {summary['proxy_pass_count']}",
        f"- proxy_hold_count: {summary['proxy_hold_count']}",
        f"- axis_proxy_note: `{summary.get('axis_proxy_note')}`",
        f"- evaluation_window: {summary['evaluation_start']} to {summary['evaluation_end']}",
        "",
        "## Interpretation",
        "",
        "- This is a lagged daily market-regime proxy audit, not true regime replay.",
        "- Regime labels use market aggregates shifted by one trading day.",
        "- A pass here can reduce concern about single-state dependence, but it does not clear the true regime replay blocker.",
        "",
        "## Regime Coverage",
        "",
        "| regime | days | mean_ew_return | mean_up_ratio | mean_liquidity_ratio | mean_limit_density |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report["regime_coverage"]:
        lines.append(
            "| {pit_regime_label} | {days} | {mean_ew_return} | {mean_up_ratio} | {mean_liquidity_ratio} | {mean_limit_density} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Cluster Summary",
            "",
            "| global_cluster | source_cluster | decision | usable_axes | pass_axes | worst_regime | min_mean | dominant_share | expression |",
            "| --- | --- | --- | ---: | ---: | --- | ---: | ---: | --- |",
        ]
    )
    for row in report["cluster_summary"]:
        expr = str(row.get("expression") or "")
        if len(expr) > 100:
            expr = expr[:97] + "..."
        lines.append(
            "| {global_signal_cluster_id} | {source_cluster_id} | {proxy_decision} | {usable_axis_count} | {axis_pass_count} | {worst_regime_label} | {min_regime_mean_return} | {dominant_regime_return_share} | `{expr}` |".format(
                expr=expr,
                **row,
            )
        )
    lines.extend(
        [
            "",
            "## Remaining Blockers",
            "",
        ]
    )
    for blocker in summary["remaining_blockers"]:
        lines.append(f"- {blocker}")
    lines.append("")
    return "\n".join(lines)


def run(
    *,
    book_path: Path,
    output_root: Path,
    dataset_path: Path,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
    top_bottom_quantile: float,
    min_proxy_pass_count: int,
) -> dict[str, Any]:
    survivors = _read_csv(book_path)
    frame, evaluation_start, evaluation_end = _load_recent_quarter_market_panel(
        dataset_path,
        quarter_window_count=recent_quarter_window_count,
        warmup_days=recent_warmup_days,
    )
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    regime_frame = build_pit_market_regime_state_frame(frame)
    regime_frame = regime_frame[
        (pd.to_datetime(regime_frame["date"], errors="coerce") >= evaluation_start)
        & (pd.to_datetime(regime_frame["date"], errors="coerce") <= evaluation_end)
    ].copy()
    regime_coverage = summarize_regime_coverage(regime_frame)
    regime_axes = _regime_axis_frame(regime_frame)

    expression_cache: dict[str, pd.Series] = {}
    cluster_summary: list[dict[str, Any]] = []
    bucket_rows: list[dict[str, Any]] = []
    axis_summary_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for index, survivor in enumerate(survivors):
        expression = str(survivor.get("expression") or "")
        try:
            signal = evaluate_panel_expression(
                signal_frame,
                expression,
                cache=expression_cache,
                field_lags=signal_clock_report["field_lags"],
            )
            work, _masks = _tradable_signal_work_frame(
                frame,
                signal,
                horizon_days=1,
                feature_lag_days=0,
                evaluation_start_date=evaluation_start,
                evaluation_end_date=evaluation_end,
                field_lags=signal_clock_report["field_lags"],
            )
            daily = _tradable_daily_ic_spread_turnover_frame(work, top_bottom_quantile=top_bottom_quantile)
            cluster, buckets, axis_rows = _regime_bucket_rows(survivor=survivor, daily=daily, regime_axes=regime_axes)
            cluster_summary.append(cluster)
            bucket_rows.extend(buckets)
            axis_summary_rows.extend(axis_rows)
            for row in daily.to_dict("records"):
                out = {
                    "survivor_uid": survivor.get("survivor_uid"),
                    "global_signal_cluster_id": survivor.get("global_signal_cluster_id"),
                    "source_cluster_id": survivor.get("source_cluster_id"),
                    "source_lane": survivor.get("source_lane"),
                    "date": pd.to_datetime(row.get("date")).date().isoformat() if pd.notna(row.get("date")) else None,
                    "window": row.get("window"),
                    "rank_ic": row.get("rank_ic"),
                    "long_short_return": row.get("long_short_return"),
                    "average_one_way_turnover": row.get("average_one_way_turnover"),
                }
                daily_rows.append(out)
        except Exception as exc:
            errors.append(
                {
                    "row_index": index,
                    "survivor_uid": survivor.get("survivor_uid"),
                    "global_signal_cluster_id": survivor.get("global_signal_cluster_id"),
                    "expression": expression,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:500],
                }
            )

    proxy_pass_count = sum(row.get("proxy_decision") == "PASS_REGIME_PROXY_DIVERSIFIED" for row in cluster_summary)
    proxy_hold_count = len(cluster_summary) - proxy_pass_count
    decision = (
        "PASS_PHASE3L_L_REGIME_PROXY_AUDIT_TRUE_REGIME_STILL_BLOCKED"
        if proxy_pass_count >= min_proxy_pass_count and not errors
        else "HOLD_PHASE3L_L_REGIME_PROXY_AUDIT"
    )
    summary = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3l_l_regime_proxy_audit",
        "decision": decision,
        "scope": "daily_lagged_market_regime_proxy_not_true_regime_replay",
        "inputs": {
            "book_path": str(book_path),
            "book_sha256": _sha256(book_path),
            "dataset_path": str(dataset_path),
        },
        "parameters": {
            "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
            "horizon_days": 1,
            "execution_lag_days": 1,
            "top_bottom_quantile": top_bottom_quantile,
            "recent_quarter_window_count": recent_quarter_window_count,
            "recent_warmup_days": recent_warmup_days,
            "min_proxy_pass_count": min_proxy_pass_count,
        },
        "evaluation_start": evaluation_start.date().isoformat(),
        "evaluation_end": evaluation_end.date().isoformat(),
        "survivor_count": len(survivors),
        "evaluated_survivor_count": len(cluster_summary),
        "proxy_pass_count": int(proxy_pass_count),
        "proxy_hold_count": int(proxy_hold_count),
        "error_count": len(errors),
        "proxy_decision_distribution": dict(sorted(Counter(str(row.get("proxy_decision")) for row in cluster_summary).items())),
        "axis_proxy_note": "PIT labels plus lagged trend/volatility/liquidity/limit-density quantile axes; proxy only, not true regime replay.",
        "remaining_blockers": [
            "true_regime_bucket_replay_not_run",
            "minute_execution_capacity_not_run",
            "live_execution_not_confirmed",
        ],
        "outputs": {
            "cluster_summary_csv": str(output_root / "phase3l_l_regime_proxy_cluster_summary.csv"),
            "regime_bucket_csv": str(output_root / "phase3l_l_regime_proxy_bucket_summary.csv"),
            "regime_axis_csv": str(output_root / "phase3l_l_regime_proxy_axis_summary.csv"),
            "daily_returns_csv": str(output_root / "phase3l_l_daily_returns_by_survivor.csv"),
            "report_json": str(output_root / "phase3l_l_regime_proxy_report.json"),
            "report_md": str(output_root / "PHASE3L_L_REGIME_PROXY_AUDIT_2026-05-17.md"),
        },
    }
    report = {
        "summary": summary,
        "regime_coverage": regime_coverage,
        "cluster_summary": cluster_summary,
        "errors": errors,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    _write_csv(output_root / "phase3l_l_regime_proxy_cluster_summary.csv", cluster_summary)
    _write_csv(output_root / "phase3l_l_regime_proxy_bucket_summary.csv", bucket_rows)
    _write_csv(output_root / "phase3l_l_regime_proxy_axis_summary.csv", axis_summary_rows)
    _write_csv(output_root / "phase3l_l_daily_returns_by_survivor.csv", daily_rows)
    _write_csv(output_root / "phase3l_l_regime_proxy_errors.csv", errors)
    _write_json(output_root / "phase3l_l_regime_proxy_report.json", report)
    (output_root / "PHASE3L_L_REGIME_PROXY_AUDIT_2026-05-17.md").write_text(_render_markdown(report), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book", type=Path, default=DEFAULT_BOOK)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--recent-quarter-window-count", type=int, default=4)
    parser.add_argument("--recent-warmup-days", type=int, default=90)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--min-proxy-pass-count", type=int, default=6)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        book_path=args.book,
        output_root=args.output_root,
        dataset_path=args.dataset_path,
        recent_quarter_window_count=args.recent_quarter_window_count,
        recent_warmup_days=args.recent_warmup_days,
        top_bottom_quantile=args.top_bottom_quantile,
        min_proxy_pass_count=args.min_proxy_pass_count,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if str(summary["decision"]).startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())

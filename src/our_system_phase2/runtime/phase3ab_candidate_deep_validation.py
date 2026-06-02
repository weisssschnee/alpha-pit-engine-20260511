"""Deep validation for Phase3AB Stage1 top candidates.

This is a no-search audit. It takes candidates from the Phase3AB aggregate,
rebuilds daily long-only portfolio proxies on a long PIT panel, and reports
time-split, R3-regime, cost, turnover, and liquidity/capacity proxy behavior.
It does not modify X0/R3 or promote any candidate.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.market_regime_state import build_pit_market_regime_state_frame
from our_system_phase2.services.real_market_validation import (
    SIGNAL_CLOCK_AFTER_OPEN,
    _available_market_panel_usecols,
    _prepare_market_panel,
    _signal_evaluation_frame,
    evaluate_panel_expression,
)
from our_system_phase2.services.stock_pit_compact_ensemble import build_stock_pit_compact_top6_daily_portfolio


VERSION = "phase3ab-candidate-deep-validation-v1-2026-05-30"
DEFAULT_INPUT = Path("reports/phase3ab_large_search_aggregate_retry_20260530/phase3ab_top_candidates.csv")
DEFAULT_OUTPUT = Path("reports/phase3ab_candidate_deep_validation_20260530")
DEFAULT_DATASET = Path(r"G:\Project_V7_Rotation\scripts\data\phase3n_stock_tdx_official_20200101_to_20260508_maxopt.parquet")
FALLBACK_DATASET = Path(r"G:\Project_V7_Rotation\scripts\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet")
LOAD_START = pd.Timestamp("2020-01-01")
EVAL_START = pd.Timestamp("2020-07-01")
TRAIN_2025H2_START = pd.Timestamp("2025-07-01")
TRAIN_2025H2_END = pd.Timestamp("2025-12-31")
OOS_2026_START = pd.Timestamp("2026-01-01")
OOS_2026_END = pd.Timestamp("2026-05-08")
COST_BPS_GRID = (0.0, 10.0, 20.0, 30.0, 50.0)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _round(value: Any, digits: int = 6) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


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
            "sharpe": None,
            "sortino": None,
            "hit_rate": None,
            "max_drawdown": None,
            "total_return": None,
            "top1_day_share": None,
            "top3_day_share": None,
        }
    mean = float(clean.mean())
    std = float(clean.std(ddof=0))
    downside = clean[clean < 0.0]
    downside_std = float(downside.std(ddof=0)) if not downside.empty else 0.0
    positive_sum = float(clean[clean > 0.0].sum())
    top_sorted = clean.sort_values(ascending=False)

    def top_share(n: int) -> float | None:
        if positive_sum <= 1e-12:
            return None
        return _round(float(top_sorted.head(n).clip(lower=0.0).sum()) / positive_sum, 6)

    return {
        "days": int(clean.shape[0]),
        "mean_daily": _round(mean, 8),
        "ann_compound": _round((1.0 + mean) ** 252 - 1.0 if mean > -1.0 else None),
        "sharpe": _round(mean / std * math.sqrt(252.0) if std > 1e-12 else None),
        "sortino": _round(mean / downside_std * math.sqrt(252.0) if downside_std > 1e-12 else None),
        "hit_rate": _round((clean > 0.0).mean()),
        "max_drawdown": _max_drawdown(clean),
        "total_return": _round((1.0 + clean).prod() - 1.0, 8),
        "top1_day_share": top_share(1),
        "top3_day_share": top_share(3),
    }


def _load_frame(dataset: Path) -> pd.DataFrame:
    usecols = _available_market_panel_usecols(dataset)
    frame = pd.read_parquet(dataset, columns=usecols)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame[frame["date"] >= LOAD_START].copy()
    return _prepare_market_panel(frame, source_path=dataset)


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


def _build_regime(frame: pd.DataFrame) -> pd.DataFrame:
    cols = ["date", "code", "close", "amount"]
    if "rt_change_pct" in frame.columns:
        cols.append("rt_change_pct")
    regime = build_pit_market_regime_state_frame(frame[cols].copy())
    regime["date"] = pd.to_datetime(regime["date"], errors="coerce")
    train_mask = (regime["date"] >= TRAIN_2025H2_START) & (regime["date"] <= TRAIN_2025H2_END)
    if "liquidity_ratio_lag1" in regime.columns:
        regime["liquidity_bucket"] = _bucket_by_train_thresholds(regime["liquidity_ratio_lag1"], train_mask, "liquidity")
        regime["R3_liquidity_low"] = regime["liquidity_bucket"].eq("liquidity_low")
    else:
        regime["liquidity_bucket"] = "liquidity_unknown"
        regime["R3_liquidity_low"] = False
    keep = ["date", "R3_liquidity_low", "liquidity_bucket"]
    return regime[keep].drop_duplicates("date")


def _select_candidates(rows: list[dict[str, str]], *, top_n: int, max_per_source_lane: int) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    seen_expr: set[str] = set()
    lane_counts: dict[str, int] = {}
    for row in rows:
        expr_hash = str(row.get("expr_hash") or "")
        expression = str(row.get("expression") or "")
        if not expression or expr_hash in seen_expr:
            continue
        lane = str(row.get("source_lane") or "__unknown__")
        if max_per_source_lane > 0 and lane_counts.get(lane, 0) >= max_per_source_lane:
            continue
        selected.append(row)
        seen_expr.add(expr_hash)
        lane_counts[lane] = lane_counts.get(lane, 0) + 1
        if len(selected) >= top_n:
            break
    return selected


def _window_masks(daily: pd.DataFrame) -> dict[str, pd.Series]:
    date = pd.to_datetime(daily["date"], errors="coerce")
    r3 = daily.get("R3_liquidity_low", pd.Series(False, index=daily.index)).fillna(False).astype(bool)
    return {
        "full_2020_2026": (date >= EVAL_START) & (date <= OOS_2026_END),
        "pre_2025": (date >= EVAL_START) & (date <= "2024-12-31"),
        "y2024": (date >= "2024-01-01") & (date <= "2024-12-31"),
        "y2025h1": (date >= "2025-01-01") & (date <= "2025-06-30"),
        "train_2025h2": (date >= TRAIN_2025H2_START) & (date <= TRAIN_2025H2_END),
        "oos_2026_all": (date >= OOS_2026_START) & (date <= OOS_2026_END),
        "oos_2026_r3_on": (date >= OOS_2026_START) & (date <= OOS_2026_END) & r3,
        "oos_2026_r3_off": (date >= OOS_2026_START) & (date <= OOS_2026_END) & ~r3,
    }


def _candidate_daily(
    frame: pd.DataFrame,
    signal_frame: pd.DataFrame,
    field_lags: dict[str, int],
    expression: str,
    *,
    top_bottom_quantile: float,
) -> pd.DataFrame:
    signal = evaluate_panel_expression(signal_frame, expression, cache={}, field_lags=field_lags)
    daily, _masks = build_stock_pit_compact_top6_daily_portfolio(
        frame,
        signal=signal,
        evaluation_start_date=EVAL_START,
        evaluation_end_date=OOS_2026_END,
        horizon_days=1,
        execution_lag_days=1,
        rebalance_frequency_days=1,
        top_bottom_quantile=top_bottom_quantile,
    )
    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
    turnover = pd.to_numeric(daily["average_one_way_turnover"], errors="coerce").fillna(0.0)
    for cost_bps in COST_BPS_GRID:
        daily[f"long_net_{int(cost_bps)}bps"] = pd.to_numeric(daily["long_ret"], errors="coerce") - turnover * (
            float(cost_bps) / 10_000.0
        )
    return daily


def _summarize_candidate(row: dict[str, str], daily: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    metric_rows: list[dict[str, Any]] = []
    stress_rows: list[dict[str, Any]] = []
    for window, mask in _window_masks(daily).items():
        use = daily[mask].copy()
        turnover = pd.to_numeric(use.get("average_one_way_turnover"), errors="coerce")
        base = {
            "candidate_id": row.get("candidate_id"),
            "expr_hash": row.get("expr_hash"),
            "run_label": row.get("run_label"),
            "source_lane": row.get("source_lane"),
            "primitive_family": row.get("primitive_family"),
            "window": window,
            "days": int(mask.sum()),
            "median_turnover": _round(turnover.median()),
            "p90_turnover": _round(turnover.quantile(0.90)),
            "mean_long_entry_amount_median": _round(pd.to_numeric(use.get("long_entry_amount_median"), errors="coerce").mean())
            if "long_entry_amount_median" in use
            else None,
            "p10_long_entry_amount_median": _round(pd.to_numeric(use.get("long_entry_amount_median"), errors="coerce").quantile(0.10))
            if "long_entry_amount_median" in use
            else None,
            "mean_long_max_sector_weight": _round(pd.to_numeric(use.get("long_max_sector_weight"), errors="coerce").mean())
            if "long_max_sector_weight" in use
            else None,
            "expression": row.get("expression"),
        }
        net10 = _metrics(use.get("long_net_10bps", pd.Series(dtype=float)))
        raw = _metrics(use.get("long_ret", pd.Series(dtype=float)))
        metric_rows.append(
            {
                **base,
                **{f"net10_{key}": value for key, value in net10.items()},
                **{f"raw_{key}": value for key, value in raw.items()},
            }
        )
        if window in {"full_2020_2026", "train_2025h2", "oos_2026_all", "oos_2026_r3_on"}:
            for cost_bps in COST_BPS_GRID:
                stress = _metrics(use.get(f"long_net_{int(cost_bps)}bps", pd.Series(dtype=float)))
                stress_rows.append(
                    {
                        "candidate_id": row.get("candidate_id"),
                        "expr_hash": row.get("expr_hash"),
                        "source_lane": row.get("source_lane"),
                        "window": window,
                        "cost_bps": cost_bps,
                        **stress,
                    }
                )
    return metric_rows, stress_rows


def _scoreboard(metric_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_candidate: dict[str, dict[str, dict[str, Any]]] = {}
    for row in metric_rows:
        key = str(row.get("expr_hash") or row.get("candidate_id"))
        by_candidate.setdefault(key, {})[str(row.get("window"))] = row
    rows: list[dict[str, Any]] = []
    for _key, windows in by_candidate.items():
        oos = windows.get("oos_2026_all", {})
        train = windows.get("train_2025h2", {})
        full = windows.get("full_2020_2026", {})
        pre = windows.get("pre_2025", {})
        r3 = windows.get("oos_2026_r3_on", {})
        base = oos or train or full
        oos_sortino = oos.get("net10_sortino")
        train_sortino = train.get("net10_sortino")
        full_sortino = full.get("net10_sortino")
        pre_sortino = pre.get("net10_sortino")
        r3_sortino = r3.get("net10_sortino")
        oos_ann = oos.get("net10_ann_compound")
        oos_dd = oos.get("net10_max_drawdown")
        p90_turnover = oos.get("p90_turnover")
        top3_share = oos.get("net10_top3_day_share")
        amount = oos.get("mean_long_entry_amount_median")
        score = 0.0
        for value, weight in (
            (oos_sortino, 1.0),
            (train_sortino, 0.4),
            (full_sortino, 0.4),
            (pre_sortino, 0.2),
            (r3_sortino, 0.2),
        ):
            if value is not None:
                score += float(value) * weight
        if p90_turnover is not None:
            score -= max(0.0, float(p90_turnover) - 0.35) * 4.0
        if top3_share is not None:
            score -= max(0.0, float(top3_share) - 0.45) * 2.0
        rows.append(
            {
                "candidate_id": base.get("candidate_id"),
                "expr_hash": base.get("expr_hash"),
                "run_label": base.get("run_label"),
                "source_lane": base.get("source_lane"),
                "deep_score": _round(score, 6),
                "oos_2026_net10_ann": oos_ann,
                "oos_2026_net10_sortino": oos_sortino,
                "oos_2026_net10_max_drawdown": oos_dd,
                "oos_2026_p90_turnover": p90_turnover,
                "oos_2026_top3_day_share": top3_share,
                "oos_2026_mean_amount": amount,
                "train_2025h2_net10_sortino": train_sortino,
                "pre_2025_net10_sortino": pre_sortino,
                "full_2020_2026_net10_sortino": full_sortino,
                "r3_on_net10_sortino": r3_sortino,
                "expression": base.get("expression"),
            }
        )
    rows.sort(key=lambda row: (float(row.get("deep_score") or -1e9), float(row.get("oos_2026_net10_sortino") or -1e9)), reverse=True)
    return rows


def _render_markdown(report: dict[str, Any], top_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase3AB Candidate Deep Validation",
        "",
        f"- version: `{report['version']}`",
        f"- input: `{report['input_csv']}`",
        f"- dataset: `{report['dataset']}`",
        f"- selected_candidates: `{report['selected_candidates']}`",
        f"- succeeded: `{report['succeeded']}`",
        f"- failed: `{report['failed']}`",
        "",
        "## Interpretation",
        "",
        "- This is a no-search deep validation audit for Stage1 Phase3AB candidates.",
        "- It is not a promotion decision and does not modify X0/R3.",
        "- Candidates that look strong here still require frozen forward/shadow handling before promotion.",
        "",
        "## Top Deep-Validated Candidates",
        "",
        "| rank | candidate_id | lane | score | oos ann | oos sortino | p90 turnover | top3 share | expr_hash |",
        "|---:|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for idx, row in enumerate(top_rows[:20], start=1):
        lines.append(
            "| {idx} | `{cid}` | {lane} | {score} | {ann} | {sortino} | {turnover} | {top3} | `{expr}` |".format(
                idx=idx,
                cid=row.get("candidate_id", ""),
                lane=str(row.get("source_lane") or "")[:42],
                score="" if row.get("deep_score") is None else row.get("deep_score"),
                ann="" if row.get("oos_2026_net10_ann") is None else row.get("oos_2026_net10_ann"),
                sortino="" if row.get("oos_2026_net10_sortino") is None else row.get("oos_2026_net10_sortino"),
                turnover="" if row.get("oos_2026_p90_turnover") is None else row.get("oos_2026_p90_turnover"),
                top3="" if row.get("oos_2026_top3_day_share") is None else row.get("oos_2026_top3_day_share"),
                expr=row.get("expr_hash", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- scoreboard: `{report['paths']['scoreboard_csv']}`",
            f"- window metrics: `{report['paths']['window_metrics_csv']}`",
            f"- cost stress: `{report['paths']['cost_stress_csv']}`",
            f"- failures: `{report['paths']['failures_csv']}`",
            f"- json: `{report['paths']['json']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def run(
    *,
    input_csv: Path,
    dataset: Path,
    output_root: Path,
    top_n: int,
    max_per_source_lane: int,
    top_bottom_quantile: float,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    rows = _read_csv(input_csv)
    selected = _select_candidates(rows, top_n=top_n, max_per_source_lane=max_per_source_lane)
    frame = _load_frame(dataset)
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    regime = _build_regime(frame)

    metric_rows: list[dict[str, Any]] = []
    stress_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    progress_path = output_root / "phase3ab_deep_validation_progress.json"
    for idx, row in enumerate(selected, start=1):
        progress = {
            "status": "running",
            "current_index": idx,
            "selected_candidates": len(selected),
            "candidate_id": row.get("candidate_id"),
            "expr_hash": row.get("expr_hash"),
        }
        write_json_artifact(progress_path, progress)
        try:
            daily = _candidate_daily(
                frame,
                signal_frame,
                signal_clock_report["field_lags"],
                str(row.get("expression") or ""),
                top_bottom_quantile=top_bottom_quantile,
            )
            daily = daily.merge(regime, on="date", how="left")
            candidate_metric_rows, candidate_stress_rows = _summarize_candidate(row, daily)
            metric_rows.extend(candidate_metric_rows)
            stress_rows.extend(candidate_stress_rows)
        except Exception as exc:  # noqa: BLE001 - audit should continue and record failed formulas.
            failure_rows.append(
                {
                    "candidate_id": row.get("candidate_id"),
                    "expr_hash": row.get("expr_hash"),
                    "source_lane": row.get("source_lane"),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "expression": row.get("expression"),
                }
            )

    scoreboard_rows = _scoreboard(metric_rows)
    paths = {
        "scoreboard_csv": str(output_root / "phase3ab_deep_scoreboard.csv"),
        "window_metrics_csv": str(output_root / "phase3ab_deep_window_metrics.csv"),
        "cost_stress_csv": str(output_root / "phase3ab_deep_cost_stress.csv"),
        "failures_csv": str(output_root / "phase3ab_deep_failures.csv"),
        "json": str(output_root / "phase3ab_candidate_deep_validation.json"),
        "markdown": str(output_root / "PHASE3AB_CANDIDATE_DEEP_VALIDATION_2026-05-30.md"),
    }
    _write_csv(Path(paths["scoreboard_csv"]), scoreboard_rows)
    _write_csv(Path(paths["window_metrics_csv"]), metric_rows)
    _write_csv(Path(paths["cost_stress_csv"]), stress_rows)
    _write_csv(Path(paths["failures_csv"]), failure_rows)
    report = {
        "version": VERSION,
        "scope": "no_search_candidate_deep_validation",
        "input_csv": str(input_csv),
        "dataset": str(dataset),
        "output_root": str(output_root),
        "selected_candidates": len(selected),
        "succeeded": len(scoreboard_rows),
        "failed": len(failure_rows),
        "top_n": int(top_n),
        "max_per_source_lane": int(max_per_source_lane),
        "top_bottom_quantile": float(top_bottom_quantile),
        "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
        "official_x0_r3_policy": "read_only_no_change",
        "paths": paths,
        "top_scoreboard": scoreboard_rows[:30],
    }
    write_json_artifact(Path(paths["json"]), report)
    Path(paths["markdown"]).write_text(_render_markdown(report, scoreboard_rows), encoding="utf-8")
    write_json_artifact(
        progress_path,
        {
            "status": "completed",
            "selected_candidates": len(selected),
            "succeeded": len(scoreboard_rows),
            "failed": len(failure_rows),
            "output_root": str(output_root),
        },
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Deep validate Phase3AB aggregate top candidates.")
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET if DEFAULT_DATASET.exists() else FALLBACK_DATASET)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top-n", type=int, default=80)
    parser.add_argument("--max-per-source-lane", type=int, default=0)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    args = parser.parse_args()
    report = run(
        input_csv=args.input_csv,
        dataset=args.dataset,
        output_root=args.output_root,
        top_n=max(1, int(args.top_n)),
        max_per_source_lane=max(0, int(args.max_per_source_lane)),
        top_bottom_quantile=float(args.top_bottom_quantile),
    )
    print(json.dumps({"status": "ok", "output_root": report["output_root"], "succeeded": report["succeeded"], "failed": report["failed"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

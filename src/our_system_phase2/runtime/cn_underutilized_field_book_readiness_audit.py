from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from our_system_phase2.services.real_market_validation import (
    SIGNAL_CLOCK_AFTER_OPEN,
    _load_recent_quarter_market_panel,
    _signal_evaluation_frame,
    evaluate_panel_expression,
)


DEFAULT_BASELINE_162 = Path("runtime/baselines/cn_discovery_baseline_162_20260601.json")
DEFAULT_QUEUE = Path("runtime/registry_review/cn_underutilized_field_provisional_new_queue_20260601.json")
DEFAULT_DATASET = Path(
    "runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_fundamental_augmented_v2_20260531.parquet"
)
DEFAULT_REPORT_DIR = Path("reports/cn_underutilized_field_book_readiness_20260601")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


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


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _quantile(series: pd.Series, q: float) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return None
    return float(clean.quantile(q))


def _mean(series: pd.Series) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return None
    return float(clean.mean())


def _queue_by_candidate(path: Path) -> dict[str, dict[str, Any]]:
    data = _read_json(path)
    return {str(row.get("candidate_id")): row for row in data.get("queue") or [] if row.get("candidate_id")}


def _new_baseline_rows(path: Path) -> list[dict[str, Any]]:
    data = _read_json(path)
    rows: list[dict[str, Any]] = []
    for row in data.get("deployable_representatives") or []:
        if row.get("registry_source") == "cn_underutilized_field_replay128_provisional_new":
            rows.append(row)
    return rows


def _risk_grade(row: dict[str, Any]) -> str:
    sortino = _safe_float(row.get("strict_cost_adjusted_sortino"))
    turnover = _safe_float(row.get("strict_mean_one_way_turnover"))
    median_amount = _safe_float(row.get("long_selected_median_amount"))
    limit_rate = _safe_float(row.get("long_selected_limit_or_susp_rate"))
    if sortino is None or turnover is None:
        return "diagnostic_missing_replay_metric"
    if sortino >= 1.0 and turnover <= 0.20 and (median_amount or 0.0) >= 50_000_000 and (limit_rate or 0.0) <= 0.05:
        return "book_readiness_candidate"
    if sortino >= 0.0 and turnover <= 0.35 and (limit_rate or 0.0) <= 0.10:
        return "watch_candidate"
    return "research_only_high_risk"


def _expr_field_flags(expression: str) -> dict[str, bool]:
    lower = expression.lower()
    return {
        "uses_fundamental": "$fund_" in lower,
        "uses_amount": "$amount" in lower,
        "uses_volume": "$volume" in lower,
        "uses_turnover_ratio": "$turnover_ratio" in lower,
        "uses_capacity_or_mcap": "market_cap" in lower or "float" in lower or "circulation" in lower,
        "uses_limit_event": "limit" in lower or "seal_" in lower,
    }


def _evaluate_long_side_metrics(
    signal_frame: pd.DataFrame,
    expression: str,
    *,
    field_lags: dict[str, int],
    cache: dict[str, pd.Series],
    selection_quantile: float,
) -> dict[str, Any]:
    signal = evaluate_panel_expression(signal_frame, expression, cache=cache, field_lags=field_lags)
    ranked = signal.groupby(signal_frame["date"]).rank(pct=True)
    selected = ranked >= float(selection_quantile)
    selected_frame = signal_frame.loc[selected.fillna(False)].copy()
    all_dates = signal_frame["date"].nunique()
    selected_dates = selected_frame["date"].nunique() if not selected_frame.empty else 0
    out: dict[str, Any] = {
        "long_selection_quantile": selection_quantile,
        "long_selected_rows": int(len(selected_frame)),
        "long_selected_dates": int(selected_dates),
        "long_selected_date_coverage": round(float(selected_dates / all_dates), 6) if all_dates else 0.0,
    }
    metric_columns = {
        "amount": "long_selected_median_amount",
        "volume": "long_selected_median_volume",
        "final_float_market_cap": "long_selected_median_float_mcap",
        "final_total_market_cap": "long_selected_median_total_mcap",
        "turnover_ratio": "long_selected_median_turnover_ratio",
        "turnover_ratio_real": "long_selected_median_turnover_ratio_real",
    }
    for column, key in metric_columns.items():
        out[key] = _quantile(selected_frame[column], 0.50) if column in selected_frame.columns else None
        out[key.replace("median", "p25")] = _quantile(selected_frame[column], 0.25) if column in selected_frame.columns else None
    limit_susp = pd.Series(False, index=selected_frame.index)
    for column in ("susp", "is_limit_up", "is_limit_down"):
        if column in selected_frame.columns:
            limit_susp = limit_susp | (pd.to_numeric(selected_frame[column], errors="coerce").fillna(0) != 0)
            out[f"long_selected_{column}_rate"] = _mean(pd.to_numeric(selected_frame[column], errors="coerce").fillna(0).clip(0, 1))
        else:
            out[f"long_selected_{column}_rate"] = None
    out["long_selected_limit_or_susp_rate"] = _mean(limit_susp.astype(float)) if not selected_frame.empty else None
    amount = out.get("long_selected_median_amount")
    out["participation_capacity_proxy_2pct_amount"] = float(amount) * 0.02 if amount is not None else None
    return out


def run_audit(
    *,
    baseline_162_path: Path,
    queue_path: Path,
    dataset_path: Path,
    report_dir: Path,
    selection_quantile: float,
    quarter_window_count: int,
    warmup_days: int,
) -> dict[str, Any]:
    queue_by_candidate = _queue_by_candidate(queue_path)
    rows = _new_baseline_rows(baseline_162_path)
    frame, evaluation_start, evaluation_end = _load_recent_quarter_market_panel(
        dataset_path,
        quarter_window_count=quarter_window_count,
        warmup_days=warmup_days,
    )
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    cache: dict[str, pd.Series] = {}
    audit_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for row in rows:
        candidate_id = str(row.get("candidate_id") or "")
        queue = queue_by_candidate.get(candidate_id, {})
        expression = str(row.get("representative_expression") or "")
        base = {
            "registry_entry_id": row.get("registry_entry_id", ""),
            "legacy_cluster_id": row.get("legacy_cluster_id", ""),
            "candidate_id": candidate_id,
            "source_lane": row.get("source_lane", ""),
            "source_generator": row.get("source_generator", ""),
            "factor_lane": row.get("factor_lane", ""),
            "expression": expression,
            "strict_mean_one_way_turnover": _safe_float(queue.get("strict_mean_one_way_turnover")),
            "strict_cost_adjusted_sortino": _safe_float(queue.get("strict_cost_adjusted_sortino")),
            "nearest_existing_registry_corr": _safe_float(row.get("nearest_existing_registry_corr")),
        }
        base.update(_expr_field_flags(expression))
        try:
            base.update(
                _evaluate_long_side_metrics(
                    signal_frame,
                    expression,
                    field_lags=signal_clock_report["field_lags"],
                    cache=cache,
                    selection_quantile=selection_quantile,
                )
            )
        except Exception as exc:
            errors.append({"candidate_id": candidate_id, "error": f"{type(exc).__name__}:{str(exc)[:200]}", "expression": expression})
        base["book_readiness_grade"] = _risk_grade(base)
        audit_rows.append(base)

    report_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(report_dir / "book_readiness_rows.csv", audit_rows)
    _write_csv(report_dir / "book_readiness_errors.csv", errors)
    shortlist = {
        "shortlist_id": "cn_underutilized_field_book_readiness_shortlist_20260601",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_baseline": str(baseline_162_path),
        "core_candidates": [
            row for row in audit_rows if row.get("book_readiness_grade") == "book_readiness_candidate"
        ],
        "watch_candidates": [
            row for row in audit_rows if row.get("book_readiness_grade") == "watch_candidate"
        ],
        "research_only_high_risk": [
            row for row in audit_rows if row.get("book_readiness_grade") == "research_only_high_risk"
        ],
    }
    (report_dir / "book_readiness_shortlist.json").write_text(
        json.dumps(shortlist, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    grade_counts = Counter(str(row.get("book_readiness_grade")) for row in audit_rows)
    source_counts = Counter(str(row.get("source_lane")) for row in audit_rows)
    factor_counts = Counter(str(row.get("factor_lane")) for row in audit_rows)
    payload: dict[str, Any] = {
        "experiment_id": "cn_underutilized_field_book_readiness_20260601",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "decision": "PASS_BOOK_READINESS_AUDIT_READY",
        "scope": "no-replay book-readiness audit for the 13 newly promoted discovery clusters in baseline 162",
        "inputs": {
            "baseline_162_path": str(baseline_162_path),
            "queue_path": str(queue_path),
            "dataset_path": str(dataset_path),
        },
        "signal_clock": signal_clock_report,
        "evaluation_window": {
            "evaluation_start": str(evaluation_start.date()),
            "evaluation_end": str(evaluation_end.date()),
            "quarter_window_count": quarter_window_count,
            "warmup_days": warmup_days,
        },
        "counts": {
            "new_clusters": len(rows),
            "audit_rows": len(audit_rows),
            "errors": len(errors),
            "book_readiness_candidate": grade_counts.get("book_readiness_candidate", 0),
            "watch_candidate": grade_counts.get("watch_candidate", 0),
            "research_only_high_risk": grade_counts.get("research_only_high_risk", 0),
            "diagnostic_missing_replay_metric": grade_counts.get("diagnostic_missing_replay_metric", 0),
        },
        "grade_counts": dict(grade_counts),
        "source_lane_counts": dict(source_counts),
        "factor_lane_counts": dict(factor_counts),
        "metric_summary": {
            "median_strict_turnover": _quantile(pd.Series([row.get("strict_mean_one_way_turnover") for row in audit_rows]), 0.50),
            "p90_strict_turnover": _quantile(pd.Series([row.get("strict_mean_one_way_turnover") for row in audit_rows]), 0.90),
            "median_strict_cost_adjusted_sortino": _quantile(pd.Series([row.get("strict_cost_adjusted_sortino") for row in audit_rows]), 0.50),
            "median_long_selected_amount": _quantile(pd.Series([row.get("long_selected_median_amount") for row in audit_rows]), 0.50),
            "median_long_selected_float_mcap": _quantile(pd.Series([row.get("long_selected_median_float_mcap") for row in audit_rows]), 0.50),
            "median_limit_or_susp_rate": _quantile(pd.Series([row.get("long_selected_limit_or_susp_rate") for row in audit_rows]), 0.50),
        },
        "outputs": {
            "rows_csv": str(report_dir / "book_readiness_rows.csv"),
            "errors_csv": str(report_dir / "book_readiness_errors.csv"),
            "shortlist_json": str(report_dir / "book_readiness_shortlist.json"),
        },
    }
    (report_dir / "cn_underutilized_field_book_readiness.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_markdown(report_dir / "CN_UNDERUTILIZED_FIELD_BOOK_READINESS_2026-06-01.md", payload, audit_rows)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    lines = [
        "# CN Underutilized Field Book Readiness - 2026-06-01",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in payload["counts"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Metric Summary", ""])
    for key, value in payload["metric_summary"].items():
        lines.append(f"- {key}: `{'' if value is None else round(float(value), 6)}`")
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| grade | cluster | factor_lane | turnover | sortino | median_amount | limit_or_susp | expression |",
            "|---|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for row in sorted(rows, key=lambda item: (str(item.get("book_readiness_grade")), -(item.get("strict_cost_adjusted_sortino") or -999))):
        expr = str(row.get("expression") or "").replace("|", "\\|")
        if len(expr) > 80:
            expr = expr[:77] + "..."
        lines.append(
            "| {grade} | {cluster} | {factor} | {turnover} | {sortino} | {amount} | {limit} | `{expr}` |".format(
                grade=row.get("book_readiness_grade", ""),
                cluster=row.get("legacy_cluster_id", ""),
                factor=row.get("factor_lane", ""),
                turnover="" if row.get("strict_mean_one_way_turnover") is None else round(float(row["strict_mean_one_way_turnover"]), 6),
                sortino="" if row.get("strict_cost_adjusted_sortino") is None else round(float(row["strict_cost_adjusted_sortino"]), 6),
                amount="" if row.get("long_selected_median_amount") is None else round(float(row["long_selected_median_amount"]), 2),
                limit="" if row.get("long_selected_limit_or_susp_rate") is None else round(float(row["long_selected_limit_or_susp_rate"]), 6),
                expr=expr,
            )
        )
    lines.extend(["", "## Boundary", "", "This is a no-replay book-readiness screen. It does not prove production readiness or true capacity."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-162-path", type=Path, default=DEFAULT_BASELINE_162)
    parser.add_argument("--queue-path", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--selection-quantile", type=float, default=0.80)
    parser.add_argument("--quarter-window-count", type=int, default=1)
    parser.add_argument("--warmup-days", type=int, default=90)
    args = parser.parse_args()
    payload = run_audit(
        baseline_162_path=args.baseline_162_path,
        queue_path=args.queue_path,
        dataset_path=args.dataset_path,
        report_dir=args.report_dir,
        selection_quantile=args.selection_quantile,
        quarter_window_count=args.quarter_window_count,
        warmup_days=args.warmup_days,
    )
    print(json.dumps({"decision": payload["decision"], "counts": payload["counts"], "metric_summary": payload["metric_summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

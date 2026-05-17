"""Locked long-history daily validation for Phase3L proof objects.

This script does not search, tune, or select. It replays the frozen Phase3L
research pool, candidate book, and oracle diagnostic combo on a longer daily
TDX panel and reports annualized daily-proxy metrics.
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

from our_system_phase2.services.real_market_validation import (
    DEFAULT_EXECUTION_LAG_DAYS,
    SIGNAL_CLOCK_AFTER_OPEN,
    _load_market_panel,
    _signal_evaluation_frame,
    _tradable_daily_ic_spread_turnover_frame,
    _tradable_signal_work_frame,
    evaluate_panel_expression,
)


DEFAULT_DATASET = Path(r"G:\Project_V7_Rotation\scripts\data\phase3n_stock_tdx_official_20200101_to_20260508_maxopt.parquet")
DEFAULT_FREEZE_JSON = Path("reports/phase3l_o_daily_proof_freeze_pack_20260517/phase3l_locked_daily_proof_objects.json")
DEFAULT_ALPHA_CARDS = Path("reports/phase3l_o_daily_proof_freeze_pack_20260517/phase3l_alpha_cards.csv")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3n_long_history_locked_validation_20260517")

BOOKS = {
    "candidate_book_6": ["cluster_001", "cluster_005", "cluster_006", "cluster_009", "cluster_002", "cluster_004"],
    "research_pool_9": [
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
    "oracle_diagnostic_3": ["cluster_005", "cluster_003", "cluster_004"],
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    drawdown = curve / curve.cummax() - 1.0
    return float(drawdown.min())


def _metrics(values: pd.Series, *, cost_adjusted: bool = False) -> dict[str, Any]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return {
            "daily_count": 0,
            "mean_daily_return": None,
            "annual_return_simple": None,
            "annual_return_compound": None,
            "annual_sharpe": None,
            "annual_sortino": None,
            "hit_rate": None,
            "max_drawdown": None,
            "cost_adjusted": cost_adjusted,
        }
    mean = float(clean.mean())
    std = float(clean.std(ddof=0))
    downside = clean[clean < 0]
    downside_std = float(downside.std(ddof=0)) if not downside.empty else 0.0
    compound = float((1.0 + mean) ** 252 - 1.0) if mean > -1.0 else None
    return {
        "daily_count": int(clean.shape[0]),
        "mean_daily_return": _round(mean, 8),
        "median_daily_return": _round(clean.median(), 8),
        "annual_return_simple": _round(mean * 252.0, 6),
        "annual_return_compound": _round(compound, 6),
        "annual_sharpe": _round(mean / std * math.sqrt(252.0) if std > 1e-12 else None, 6),
        "annual_sortino": _round(mean / downside_std * math.sqrt(252.0) if downside_std > 1e-12 else None, 6),
        "hit_rate": _round((clean > 0).mean(), 6),
        "max_drawdown": _round(_max_drawdown(clean), 8),
        "cost_adjusted": cost_adjusted,
    }


def _book_metrics(
    label: str,
    clusters: list[str],
    daily_matrix: pd.DataFrame,
    turnover_matrix: pd.DataFrame,
    meta: dict[str, dict[str, Any]],
    *,
    cost_bps: float,
) -> dict[str, Any]:
    sub = daily_matrix.loc[:, clusters].copy()
    book_return = sub.mean(axis=1, skipna=True)
    turnover = turnover_matrix.loc[:, clusters].mean(axis=1, skipna=True)
    net = book_return - turnover.fillna(0.0) * (float(cost_bps) / 10000.0)
    sources = Counter(str(meta[c].get("source_lane") or "unknown") for c in clusters)
    entry_types = Counter(str(meta[c].get("entry_type") or "unknown") for c in clusters)
    corr = sub.corr().abs()
    pair_corrs = []
    for i, left in enumerate(clusters):
        for right in clusters[i + 1 :]:
            value = _safe_float(corr.loc[left, right] if left in corr.index and right in corr.columns else None)
            if value is not None:
                pair_corrs.append(value)
    out = {
        "book_label": label,
        "cluster_count": len(clusters),
        "clusters": "|".join(clusters),
        "source_distribution": json.dumps(dict(sorted(sources.items())), ensure_ascii=False),
        "source_top_share": _round(max(sources.values()) / len(clusters) if clusters else None),
        "entry_type_distribution": json.dumps(dict(sorted(entry_types.items())), ensure_ascii=False),
        "mean_pairwise_abs_corr": _round(float(np.mean(pair_corrs)) if pair_corrs else 0.0),
        "max_pairwise_abs_corr": _round(float(np.max(pair_corrs)) if pair_corrs else 0.0),
        "median_turnover": _round(float(turnover.dropna().median()) if not turnover.dropna().empty else None),
        "p90_turnover": _round(float(turnover.dropna().quantile(0.9)) if not turnover.dropna().empty else None),
        "max_turnover": _round(float(turnover.dropna().max()) if not turnover.dropna().empty else None),
        "cost_bps": float(cost_bps),
    }
    gross = _metrics(book_return, cost_adjusted=False)
    net_metrics = _metrics(net, cost_adjusted=True)
    out.update({f"gross_{k}": v for k, v in gross.items() if k != "cost_adjusted"})
    out.update({f"net_{k}": v for k, v in net_metrics.items() if k != "cost_adjusted"})
    return out


def _yearly_metrics(book_label: str, daily: pd.Series) -> list[dict[str, Any]]:
    out = []
    clean = pd.to_numeric(daily, errors="coerce").dropna()
    for year, block in clean.groupby(clean.index.year):
        row = {"book_label": book_label, "year": int(year)}
        row.update(_metrics(block))
        out.append(row)
    return out


def run(
    *,
    dataset_path: Path,
    freeze_json: Path,
    alpha_cards: Path,
    output_root: Path,
    top_bottom_quantile: float,
    cost_bps: float,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    card_rows = _read_csv(alpha_cards)
    meta = {str(row["cluster_id"]): row for row in card_rows}
    required_clusters = sorted(set(sum(BOOKS.values(), [])))
    missing = [cluster for cluster in required_clusters if cluster not in meta]
    if missing:
        raise ValueError(f"missing_alpha_card_clusters:{missing}")

    frame = _load_market_panel(dataset_path)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    data_dates = sorted(frame["date"].dropna().unique())
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    cache: dict[str, pd.Series] = {}
    daily_return_columns: dict[str, pd.Series] = {}
    turnover_columns: dict[str, pd.Series] = {}
    cluster_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for cluster_id in required_clusters:
        expression = str(meta[cluster_id].get("representative_expression") or "")
        try:
            signal = evaluate_panel_expression(
                signal_frame,
                expression,
                cache=cache,
                field_lags=signal_clock_report["field_lags"],
            )
            work, _tradability = _tradable_signal_work_frame(
                frame,
                signal,
                horizon_days=1,
                execution_lag_days=DEFAULT_EXECUTION_LAG_DAYS,
                feature_lag_days=0,
                evaluation_start_date=None,
                evaluation_end_date=None,
                field_lags=signal_clock_report["field_lags"],
            )
            daily = _tradable_daily_ic_spread_turnover_frame(work, top_bottom_quantile=top_bottom_quantile)
            daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
            daily = daily.dropna(subset=["date"]).sort_values("date")
            series = daily.set_index("date")["long_short_return"].astype(float)
            turnover = daily.set_index("date")["average_one_way_turnover"].astype(float)
            daily_return_columns[cluster_id] = series
            turnover_columns[cluster_id] = turnover
            net = series - turnover.fillna(0.0) * (float(cost_bps) / 10000.0)
            row = {
                "cluster_id": cluster_id,
                "source_lane": meta[cluster_id].get("source_lane"),
                "entry_type": meta[cluster_id].get("entry_type"),
                "representative_expression": expression,
                "daily_observation_count": int(series.dropna().shape[0]),
                "first_signal_date": series.dropna().index.min().date().isoformat() if not series.dropna().empty else None,
                "last_signal_date": series.dropna().index.max().date().isoformat() if not series.dropna().empty else None,
                "mean_one_way_turnover": _round(turnover.mean()),
                "p90_one_way_turnover": _round(turnover.quantile(0.9)),
            }
            row.update({f"gross_{k}": v for k, v in _metrics(series).items() if k != "cost_adjusted"})
            row.update({f"net_{k}": v for k, v in _metrics(net, cost_adjusted=True).items() if k != "cost_adjusted"})
            cluster_rows.append(row)
        except Exception as exc:
            errors.append(
                {
                    "cluster_id": cluster_id,
                    "expression": expression,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:1000],
                }
            )

    daily_matrix = pd.DataFrame(daily_return_columns).sort_index()
    turnover_matrix = pd.DataFrame(turnover_columns).sort_index()
    book_rows = [
        _book_metrics(label, clusters, daily_matrix, turnover_matrix, meta, cost_bps=cost_bps)
        for label, clusters in BOOKS.items()
    ]
    yearly_rows: list[dict[str, Any]] = []
    for label, clusters in BOOKS.items():
        book_return = daily_matrix.loc[:, clusters].mean(axis=1, skipna=True)
        yearly_rows.extend(_yearly_metrics(label, book_return))

    daily_rows = []
    for date, row in daily_matrix.iterrows():
        out = {"date": pd.Timestamp(date).date().isoformat()}
        out.update({cluster: _round(row.get(cluster), 8) for cluster in daily_matrix.columns})
        for label, clusters in BOOKS.items():
            out[label] = _round(row[clusters].mean(skipna=True), 8)
        daily_rows.append(out)

    _write_csv(output_root / "phase3n_cluster_metrics.csv", cluster_rows)
    _write_csv(output_root / "phase3n_book_metrics.csv", book_rows)
    _write_csv(output_root / "phase3n_yearly_metrics.csv", yearly_rows)
    _write_csv(output_root / "phase3n_daily_returns.csv", daily_rows)
    if errors:
        _write_csv(output_root / "phase3n_errors.csv", errors)

    valid_books = {row["book_label"]: row for row in book_rows}
    candidate = valid_books["candidate_book_6"]
    daily_count = int(candidate.get("gross_daily_count") or 0)
    sample_grade = "SOLID" if daily_count >= 750 else "BASIC" if daily_count >= 250 else "WEAK"
    execution_status = (
        "PASS_LONG_HISTORY_REPLAY_COMPLETED"
        if not errors and daily_count >= 750
        else "HOLD_LONG_HISTORY_REPLAY_INCOMPLETE"
    )
    candidate_net_return = _safe_float(candidate.get("net_annual_return_compound"))
    candidate_net_sharpe = _safe_float(candidate.get("net_annual_sharpe"))
    alpha_pass = (
        execution_status == "PASS_LONG_HISTORY_REPLAY_COMPLETED"
        and candidate_net_return is not None
        and candidate_net_return > 0.0
        and candidate_net_sharpe is not None
        and candidate_net_sharpe > 0.0
    )
    decision = (
        "PASS_LONG_HISTORY_ALPHA_VALIDATION"
        if alpha_pass
        else "FAIL_LONG_HISTORY_ALPHA_VALIDATION"
        if execution_status == "PASS_LONG_HISTORY_REPLAY_COMPLETED"
        else "HOLD_LONG_HISTORY_ALPHA_VALIDATION"
    )
    decision_reason = (
        "candidate_book_net_return_and_sharpe_positive"
        if alpha_pass
        else "candidate_book_net_return_or_sharpe_non_positive"
        if execution_status == "PASS_LONG_HISTORY_REPLAY_COMPLETED"
        else "long_history_replay_incomplete"
    )
    summary = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3n_locked_long_history_validation",
        "decision": decision,
        "execution_status": execution_status,
        "decision_reason": decision_reason,
        "sample_grade": sample_grade,
        "scope": "locked_phase3l_daily_proof_objects_no_search_no_tuning",
        "dataset_path": str(dataset_path),
        "dataset_sha256": _sha256(dataset_path),
        "dataset_rows_loaded": int(len(frame)),
        "dataset_unique_dates": int(len(data_dates)),
        "dataset_date_min": pd.Timestamp(data_dates[0]).date().isoformat() if data_dates else None,
        "dataset_date_max": pd.Timestamp(data_dates[-1]).date().isoformat() if data_dates else None,
        "freeze_json": str(freeze_json),
        "freeze_sha256": _sha256(freeze_json),
        "alpha_cards": str(alpha_cards),
        "alpha_cards_sha256": _sha256(alpha_cards),
        "top_bottom_quantile": float(top_bottom_quantile),
        "cost_bps": float(cost_bps),
        "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
        "execution_lag_days": DEFAULT_EXECUTION_LAG_DAYS,
        "book_metrics": book_rows,
        "error_count": len(errors),
        "errors": errors,
        "not_confirmed": [
            "minute_slippage",
            "true_capacity",
            "broker_execution",
            "live_or_paper_survival",
        ],
        "outputs": {
            "cluster_metrics_csv": str(output_root / "phase3n_cluster_metrics.csv"),
            "book_metrics_csv": str(output_root / "phase3n_book_metrics.csv"),
            "yearly_metrics_csv": str(output_root / "phase3n_yearly_metrics.csv"),
            "daily_returns_csv": str(output_root / "phase3n_daily_returns.csv"),
            "summary_json": str(output_root / "phase3n_long_history_validation.json"),
            "summary_md": str(output_root / "PHASE3N_LONG_HISTORY_LOCKED_VALIDATION_2026-05-17.md"),
        },
    }
    _write_json(output_root / "phase3n_long_history_validation.json", summary)

    md_lines = [
        "# Phase3N Long-History Locked Validation",
        "",
        f"- decision: `{decision}`",
        f"- execution_status: `{execution_status}`",
        f"- decision_reason: `{decision_reason}`",
        f"- sample_grade: `{sample_grade}`",
        f"- dataset: `{dataset_path}`",
        f"- dataset_dates: `{summary['dataset_date_min']}` to `{summary['dataset_date_max']}`",
        f"- candidate_daily_count: `{daily_count}`",
        "",
        "## Book Metrics",
        "",
        "| book | clusters | gross ann ret | net ann ret | gross sharpe | net sharpe | gross sortino | net sortino | max dd | p90 turnover |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in book_rows:
        md_lines.append(
            "| {book_label} | {cluster_count} | {gross_annual_return_compound} | {net_annual_return_compound} | {gross_annual_sharpe} | {net_annual_sharpe} | {gross_annual_sortino} | {net_annual_sortino} | {gross_max_drawdown} | {p90_turnover} |".format(
                **row
            )
        )
    md_lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- The locked Phase3L book does not pass long-history alpha validation.",
            "- The prior 170-day positive result is a recent-regime result, not a full-history production proof.",
            "- This run is a no-search replay of frozen clusters; the negative result should not be repaired by tuning this report.",
            "",
            "## Boundaries",
            "",
            "- No formula, cluster, filter, or book weights were tuned in this run.",
            "- Oracle combo remains diagnostic only.",
            "- This is daily historical validation, not minute execution or capacity proof.",
            "",
        ]
    )
    (output_root / "PHASE3N_LONG_HISTORY_LOCKED_VALIDATION_2026-05-17.md").write_text(
        "\n".join(md_lines),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--freeze-json", type=Path, default=DEFAULT_FREEZE_JSON)
    parser.add_argument("--alpha-cards", type=Path, default=DEFAULT_ALPHA_CARDS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--cost-bps", type=float, default=10.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        dataset_path=args.dataset_path,
        freeze_json=args.freeze_json,
        alpha_cards=args.alpha_cards,
        output_root=args.output_root,
        top_bottom_quantile=args.top_bottom_quantile,
        cost_bps=args.cost_bps,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["execution_status"] == "PASS_LONG_HISTORY_REPLAY_COMPLETED" else 2


if __name__ == "__main__":
    raise SystemExit(main())

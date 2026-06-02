"""No-search book-level marginal audit for newly promoted CN field clusters.

This script consumes the 162 discovery baseline/book-readiness shortlist and
tests whether the six core or thirteen new clusters add value to the locked
X0/R3 daily shadow object. It does not generate candidates, rerun search, or
promote any book.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.runtime.phase3ab_candidate_deep_validation import (
    EVAL_START,
    OOS_2026_END,
    OOS_2026_START,
    SIGNAL_CLOCK_AFTER_OPEN,
    _candidate_daily,
    _metrics,
    _round,
)
from our_system_phase2.runtime.phase3ab_r3_challenger_audit import _build_official_x0_base
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_validation import (
    _available_market_panel_usecols,
    _prepare_market_panel,
    _signal_evaluation_frame,
)


VERSION = "cn-underutilized-field-book-marginal-audit-v1-2026-06-01"
DEFAULT_SHORTLIST = Path("reports/cn_underutilized_field_book_readiness_20260601/book_readiness_shortlist.json")
DEFAULT_DATASET = Path(
    "runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_fundamental_augmented_v2_20260531.parquet"
)
DEFAULT_OUTPUT_ROOT = Path("reports/cn_underutilized_field_book_marginal_audit_20260601")
DEFAULT_R3_GATE_LEDGER = Path("reports/phase3o5_locked_regime_forward_package_20260517/phase3o5_r3_gate_ledger.csv")
LOCAL_X0_DAILY = Path("reports/phase3n_long_history_locked_validation_20260517/phase3n_daily_returns.csv")
MATURE_X0_DAILY = Path(
    r"G:\Project_V7_Rotation\alpha_pit_engine_mature_feature_workspace_20260528\reports\phase3n_long_history_locked_validation_20260517\phase3n_daily_returns.csv"
)
PROJECT_X0_DAILY = Path(
    r"G:\Project_V7_Rotation\alpha_pit_engine_project_20260511\reports\phase3n_long_history_locked_validation_20260517\phase3n_daily_returns.csv"
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


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


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _resolve_x0_daily(path: Path | None) -> Path:
    if path is not None and path.exists():
        return path
    for candidate in (LOCAL_X0_DAILY, MATURE_X0_DAILY, PROJECT_X0_DAILY):
        if candidate.exists():
            return candidate
    raise FileNotFoundError("could not locate phase3n_daily_returns.csv for locked X0/R3")


def _build_x0_base_from_locked_gate(x0_daily_path: Path, gate_ledger_path: Path) -> pd.DataFrame:
    x0 = pd.read_csv(x0_daily_path, parse_dates=["date"])
    gate = pd.read_csv(gate_ledger_path, parse_dates=["date"])
    active_col = "r3_liquidity_low_active"
    if active_col not in gate.columns:
        raise ValueError(f"missing locked gate column: {active_col}")
    base = x0[["date", "candidate_book_6"]].merge(
        gate[["date", active_col]],
        on="date",
        how="left",
    )
    base["date"] = pd.to_datetime(base["date"], errors="coerce")
    base["x0_net10"] = pd.to_numeric(base["candidate_book_6"], errors="coerce").fillna(0.0)
    base["R3_liquidity_low"] = base[active_col].astype(str).str.lower().isin(["true", "1", "1.0"])
    return base[["date", "x0_net10", "R3_liquidity_low"]].dropna(subset=["date"]).copy()


def _load_frame(dataset: Path) -> pd.DataFrame:
    usecols = _available_market_panel_usecols(dataset)
    frame = pd.read_parquet(dataset, columns=usecols)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame[frame["date"] >= EVAL_START].copy()
    return _prepare_market_panel(frame, source_path=dataset)


def _shortlist_rows(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    rows: list[dict[str, Any]] = []
    for bucket, is_core in (("core_candidates", True), ("watch_candidates", False)):
        for row in payload.get(bucket) or []:
            item = dict(row)
            item["shortlist_bucket"] = bucket
            item["is_core_candidate"] = is_core
            item["cluster_id"] = item.get("legacy_cluster_id") or item.get("registry_entry_id") or item.get("candidate_id")
            rows.append(item)
    return rows


def _candidate_series_rows(
    rows: list[dict[str, Any]],
    *,
    frame: pd.DataFrame,
    signal_frame: pd.DataFrame,
    field_lags: dict[str, int],
    top_bottom_quantile: float,
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]]]:
    series_by_cluster: dict[str, pd.Series] = {}
    turnover_by_cluster: dict[str, pd.Series] = {}
    metric_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for row in rows:
        cluster_id = str(row.get("cluster_id") or "")
        expression = str(row.get("expression") or "")
        if not cluster_id or not expression:
            errors.append({"cluster_id": cluster_id, "error": "missing_cluster_or_expression", "expression": expression})
            continue
        try:
            daily = _candidate_daily(
                frame,
                signal_frame,
                field_lags,
                expression,
                top_bottom_quantile=top_bottom_quantile,
            )
        except Exception as exc:  # noqa: BLE001 - audit must keep going.
            errors.append(
                {
                    "cluster_id": cluster_id,
                    "candidate_id": row.get("candidate_id"),
                    "error": f"{type(exc).__name__}:{str(exc)[:300]}",
                    "expression": expression,
                }
            )
            continue
        daily = daily.copy()
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
        daily = daily.dropna(subset=["date"]).sort_values("date")
        returns = pd.to_numeric(daily["long_net_10bps"], errors="coerce").fillna(0.0)
        turnover = pd.to_numeric(daily["average_one_way_turnover"], errors="coerce")
        series_by_cluster[cluster_id] = pd.Series(returns.to_numpy(), index=daily["date"], name=cluster_id)
        turnover_by_cluster[cluster_id] = pd.Series(turnover.to_numpy(), index=daily["date"], name=cluster_id)
        oos_mask = (daily["date"] >= OOS_2026_START) & (daily["date"] <= OOS_2026_END)
        oos_ret = returns.loc[oos_mask]
        oos_turn = turnover.loc[oos_mask]
        metric_rows.append(
            {
                "cluster_id": cluster_id,
                "candidate_id": row.get("candidate_id"),
                "shortlist_bucket": row.get("shortlist_bucket"),
                "is_core_candidate": row.get("is_core_candidate"),
                "source_lane": row.get("source_lane"),
                "source_generator": row.get("source_generator"),
                "factor_lane": row.get("factor_lane"),
                "strict_cost_adjusted_sortino": row.get("strict_cost_adjusted_sortino"),
                "strict_mean_one_way_turnover": row.get("strict_mean_one_way_turnover"),
                "nearest_existing_registry_corr": row.get("nearest_existing_registry_corr"),
                "oos_days": int(oos_ret.shape[0]),
                "oos_median_turnover": _round(oos_turn.median()),
                "oos_p90_turnover": _round(oos_turn.quantile(0.90)),
                **{f"oos_{key}": value for key, value in _metrics(oos_ret).items()},
                "expression": expression,
            }
        )
    if series_by_cluster:
        wide = pd.concat(series_by_cluster.values(), axis=1).sort_index()
    else:
        wide = pd.DataFrame()
    if turnover_by_cluster:
        turn_wide = pd.concat(turnover_by_cluster.values(), axis=1).sort_index()
        for item in metric_rows:
            cid = str(item.get("cluster_id"))
            if cid in turn_wide:
                item["full_median_turnover"] = _round(turn_wide[cid].median())
                item["full_p90_turnover"] = _round(turn_wide[cid].quantile(0.90))
    return wide, metric_rows, errors


def _factor_capped_weights(rows: list[dict[str, Any]], selected_clusters: list[str]) -> dict[str, float]:
    by_cluster = {str(row.get("cluster_id")): row for row in rows}
    source_groups: dict[str, list[str]] = {}
    for cluster in selected_clusters:
        row = by_cluster.get(cluster, {})
        source = str(row.get("source_lane") or "unknown")
        source_groups.setdefault(source, []).append(cluster)
    weights: dict[str, float] = {}
    if not source_groups:
        return weights
    source_weight = 1.0 / len(source_groups)
    for source, source_clusters in source_groups.items():
        factor_groups: dict[str, list[str]] = {}
        for cluster in source_clusters:
            row = by_cluster.get(cluster, {})
            factor = str(row.get("factor_lane") or "unknown")
            factor_groups.setdefault(factor, []).append(cluster)
        factor_weight = source_weight / max(1, len(factor_groups))
        for _factor, factor_clusters in factor_groups.items():
            cluster_weight = factor_weight / max(1, len(factor_clusters))
            for cluster in factor_clusters:
                weights[cluster] = cluster_weight
    total = sum(weights.values())
    if total > 0:
        weights = {key: value / total for key, value in weights.items()}
    return weights


def _weighted_book(wide: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    if wide.empty or not weights:
        return pd.Series(dtype=float)
    columns = [col for col in weights if col in wide.columns]
    if not columns:
        return pd.Series(0.0, index=wide.index)
    weight_sum = sum(weights[col] for col in columns)
    out = sum(wide[col].fillna(0.0) * (weights[col] / weight_sum) for col in columns)
    return pd.Series(out, index=wide.index)


def _corr(left: pd.Series, right: pd.Series) -> float | None:
    joined = pd.DataFrame({"left": left, "right": right}).dropna()
    if len(joined) < 5 or joined["left"].nunique() <= 1 or joined["right"].nunique() <= 1:
        return None
    return _round(joined["left"].corr(joined["right"]))


def _book_row(
    book: str,
    values: pd.Series,
    *,
    x0_r3: pd.Series,
    r3: pd.Series,
    cluster_count: int,
    source_counts: Counter[str] | None = None,
    factor_counts: Counter[str] | None = None,
) -> dict[str, Any]:
    metrics = _metrics(values)
    x0_metrics = _metrics(x0_aligned := x0_r3.reindex(values.index).fillna(0.0))
    active_values = values.loc[r3.reindex(values.index).fillna(False).astype(bool)] if not values.empty else values
    ann_delta = None
    if metrics.get("ann_compound") is not None and x0_metrics.get("ann_compound") is not None:
        ann_delta = _round(float(metrics["ann_compound"]) - float(x0_metrics["ann_compound"]))
    sortino_delta = None
    if metrics.get("sortino") is not None and x0_metrics.get("sortino") is not None:
        sortino_delta = _round(float(metrics["sortino"]) - float(x0_metrics["sortino"]))
    return {
        "book": book,
        "cluster_count": cluster_count,
        "r3_active_days": int(r3.reindex(values.index).fillna(False).astype(bool).sum()) if not values.empty else 0,
        **metrics,
        "active_day_mean": _round(pd.to_numeric(active_values, errors="coerce").mean(), 8) if not active_values.empty else None,
        "corr_to_x0_r3": _corr(values, x0_aligned),
        "delta_ann_vs_x0_r3": ann_delta,
        "delta_sortino_vs_x0_r3": sortino_delta,
        "source_top_share": _round(source_counts.most_common(1)[0][1] / max(1, cluster_count)) if source_counts else None,
        "source_top": source_counts.most_common(1)[0][0] if source_counts else None,
        "source_counts": json.dumps(dict(source_counts or {}), ensure_ascii=False),
        "factor_top_share": _round(factor_counts.most_common(1)[0][1] / max(1, cluster_count)) if factor_counts else None,
        "factor_top": factor_counts.most_common(1)[0][0] if factor_counts else None,
        "factor_counts": json.dumps(dict(factor_counts or {}), ensure_ascii=False),
    }


def _render_markdown(report: dict[str, Any], book_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# CN Underutilized Field Book Marginal Audit - 2026-06-01",
        "",
        f"decision: `{report['decision']}`",
        "",
        "## Scope",
        "",
        "No-search audit. This reads the frozen 162 discovery/book-readiness artifacts and compares new clusters against locked X0/R3.",
        "It does not promote a production book and does not run candidate generation.",
        "",
        "## Book Results",
        "",
        "| book | clusters | ann | sortino | maxDD | corr_to_x0 | delta_ann | delta_sortino |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in book_rows:
        lines.append(
            "| {book} | {clusters} | {ann} | {sortino} | {dd} | {corr} | {dann} | {dsort} |".format(
                book=row.get("book"),
                clusters=row.get("cluster_count"),
                ann=row.get("ann_compound"),
                sortino=row.get("sortino"),
                dd=row.get("max_drawdown"),
                corr=row.get("corr_to_x0_r3"),
                dann=row.get("delta_ann_vs_x0_r3"),
                dsort=row.get("delta_sortino_vs_x0_r3"),
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"- core_new_clusters: `{report['core_cluster_count']}`",
            f"- all_new_clusters: `{report['all_cluster_count']}`",
            f"- evaluation_start: `{report['evaluation_start']}`",
            f"- evaluation_end: `{report['evaluation_end']}`",
            f"- x0_daily_source: `{report['x0_daily_path']}`",
            "",
            "## Boundary",
            "",
            "- Confirms or rejects marginal daily-proxy value only.",
            "- Does not confirm minute execution, real slippage, real capacity, or live survival.",
        ]
    )
    return "\n".join(lines) + "\n"


def run(
    *,
    shortlist_path: Path,
    dataset_path: Path,
    x0_daily_path: Path | None,
    r3_gate_ledger_path: Path,
    output_root: Path,
    top_bottom_quantile: float,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    resolved_x0_daily = _resolve_x0_daily(x0_daily_path)
    rows = _shortlist_rows(shortlist_path)
    core_rows = [row for row in rows if row.get("is_core_candidate")]
    all_clusters = [str(row.get("cluster_id")) for row in rows]
    core_clusters = [str(row.get("cluster_id")) for row in core_rows]

    frame = _load_frame(dataset_path)
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    if r3_gate_ledger_path.exists():
        base = _build_x0_base_from_locked_gate(resolved_x0_daily, r3_gate_ledger_path)
        r3_gate_source = str(r3_gate_ledger_path)
    else:
        base = _build_official_x0_base(dataset_path, resolved_x0_daily)
        r3_gate_source = "rebuilt_from_dataset_fallback"
    base["date"] = pd.to_datetime(base["date"], errors="coerce")
    base = base.dropna(subset=["date"]).sort_values("date").set_index("date")
    r3 = base["R3_liquidity_low"].fillna(False).astype(bool)
    x0_cash = pd.to_numeric(base["x0_net10"], errors="coerce").fillna(0.0)
    x0_r3 = x0_cash.where(r3, 0.0)

    wide, cluster_rows, errors = _candidate_series_rows(
        rows,
        frame=frame,
        signal_frame=signal_frame,
        field_lags=signal_clock_report["field_lags"],
        top_bottom_quantile=top_bottom_quantile,
    )
    wide = wide.reindex(base.index).fillna(0.0)
    oos_index = base.index[(base.index >= OOS_2026_START) & (base.index <= OOS_2026_END)]
    wide_oos = wide.reindex(oos_index).fillna(0.0)
    r3_oos = r3.reindex(oos_index).fillna(False).astype(bool)
    x0_r3_oos = x0_r3.reindex(oos_index).fillna(0.0)
    x0_cash_oos = x0_cash.reindex(oos_index).fillna(0.0)

    core_equal = wide_oos[core_clusters].mean(axis=1) if core_clusters else pd.Series(0.0, index=oos_index)
    all_equal = wide_oos[all_clusters].mean(axis=1) if all_clusters else pd.Series(0.0, index=oos_index)
    all_weights = _factor_capped_weights(rows, all_clusters)
    all_capped = _weighted_book(wide_oos, all_weights)
    core_r3 = core_equal.where(r3_oos, 0.0)
    all_r3 = all_equal.where(r3_oos, 0.0)
    all_capped_r3 = all_capped.where(r3_oos, 0.0)
    blend_core = (((x0_cash_oos * 6.0) + (core_equal * max(1, len(core_clusters)))) / (6.0 + max(1, len(core_clusters)))).where(
        r3_oos,
        0.0,
    )
    blend_core_10pct = ((x0_cash_oos * 0.90) + (core_equal * 0.10)).where(r3_oos, 0.0)

    source_by_cluster = {str(row.get("cluster_id")): str(row.get("source_lane") or "unknown") for row in rows}
    factor_by_cluster = {str(row.get("cluster_id")): str(row.get("factor_lane") or "unknown") for row in rows}

    def counts(clusters: list[str], mapping: dict[str, str]) -> Counter[str]:
        return Counter(mapping.get(cluster, "unknown") for cluster in clusters)

    book_series = {
        "B0_x0_r3": x0_r3_oos,
        "B1_core6_r3_equal": core_r3,
        "B1_core6_ungated_equal": core_equal,
        "B2_x0_plus_core6_r3_equal12": blend_core,
        "B2_x0_plus_core6_r3_10pct_overlay": blend_core_10pct,
        "B3_new13_r3_equal": all_r3,
        "B3_new13_r3_source_factor_capped": all_capped_r3,
        "B3_new13_ungated_equal": all_equal,
    }
    book_rows: list[dict[str, Any]] = []
    for book, series in book_series.items():
        if book.startswith("B0"):
            cluster_count = 6
            sc = None
            fc = None
        elif "core6" in book:
            cluster_count = len(core_clusters)
            sc = counts(core_clusters, source_by_cluster)
            fc = counts(core_clusters, factor_by_cluster)
        elif "new13" in book:
            cluster_count = len(all_clusters)
            sc = counts(all_clusters, source_by_cluster)
            fc = counts(all_clusters, factor_by_cluster)
        else:
            cluster_count = len(core_clusters) + 6
            sc = counts(core_clusters, source_by_cluster)
            fc = counts(core_clusters, factor_by_cluster)
        book_rows.append(_book_row(book, series, x0_r3=x0_r3_oos, r3=r3_oos, cluster_count=cluster_count, source_counts=sc, factor_counts=fc))

    daily = pd.DataFrame({"date": oos_index})
    for book, series in book_series.items():
        daily[book] = series.reindex(oos_index).fillna(0.0).to_numpy()
    daily["R3_liquidity_low"] = r3_oos.to_numpy()

    b0 = next(row for row in book_rows if row["book"] == "B0_x0_r3")
    b2 = next(row for row in book_rows if row["book"] == "B2_x0_plus_core6_r3_equal12")
    b3 = next(row for row in book_rows if row["book"] == "B3_new13_r3_source_factor_capped")
    b2_ann_delta = (b2.get("ann_compound") or 0.0) - (b0.get("ann_compound") or 0.0)
    b2_sortino_delta = (b2.get("sortino") or 0.0) - (b0.get("sortino") or 0.0)
    b2_dd_delta = (b2.get("max_drawdown") or 0.0) - (b0.get("max_drawdown") or 0.0)
    b2_sharpe_delta = (b2.get("sharpe") or 0.0) - (b0.get("sharpe") or 0.0)
    if b2_ann_delta > 0.03 and b2_dd_delta >= -0.02 and b2_sharpe_delta >= -0.25:
        decision = "PASS_CORE6_MARGINAL_OVERLAY_READY_FOR_LOCKED_FORWARD_AUDIT"
    elif (b3.get("ann_compound") or 0.0) > 0.0 and (b3.get("sortino") or 0.0) > 0.0:
        decision = "HOLD_STANDALONE_NEW_FIELD_BOOK_ONLY_NO_X0_PROMOTION"
    else:
        decision = "HOLD_NO_CONFIRMED_BOOK_LEVEL_MARGINAL_VALUE"

    _write_csv(output_root / "book_marginal_metrics.csv", book_rows)
    _write_csv(output_root / "book_marginal_cluster_metrics.csv", cluster_rows)
    _write_csv(output_root / "book_marginal_errors.csv", errors)
    daily.to_csv(output_root / "book_marginal_daily_returns.csv", index=False)
    report = {
        "version": VERSION,
        "decision": decision,
        "scope": "no_search_book_level_marginal_audit",
        "shortlist_path": str(shortlist_path),
        "dataset_path": str(dataset_path),
        "x0_daily_path": str(resolved_x0_daily),
        "r3_gate_source": r3_gate_source,
        "output_root": str(output_root),
        "evaluation_start": oos_index.min().date().isoformat() if len(oos_index) else None,
        "evaluation_end": oos_index.max().date().isoformat() if len(oos_index) else None,
        "oos_days": int(len(oos_index)),
        "r3_active_days": int(r3_oos.sum()),
        "core_cluster_count": len(core_clusters),
        "all_cluster_count": len(all_clusters),
        "cluster_eval_errors": len(errors),
        "book_metrics": book_rows,
        "paths": {
            "book_metrics_csv": str(output_root / "book_marginal_metrics.csv"),
            "cluster_metrics_csv": str(output_root / "book_marginal_cluster_metrics.csv"),
            "daily_returns_csv": str(output_root / "book_marginal_daily_returns.csv"),
            "errors_csv": str(output_root / "book_marginal_errors.csv"),
            "json": str(output_root / "cn_underutilized_field_book_marginal_audit.json"),
            "markdown": str(output_root / "CN_UNDERUTILIZED_FIELD_BOOK_MARGINAL_AUDIT_2026-06-01.md"),
        },
        "boundaries": [
            "does_not_modify_x0_r3",
            "does_not_generate_candidates",
            "does_not_confirm_production_or_minute_execution",
        ],
    }
    write_json_artifact(output_root / "cn_underutilized_field_book_marginal_audit.json", report)
    (output_root / "CN_UNDERUTILIZED_FIELD_BOOK_MARGINAL_AUDIT_2026-06-01.md").write_text(
        _render_markdown(report, book_rows),
        encoding="utf-8",
    )
    decision_path = Path("reports/CN_UNDERUTILIZED_FIELD_BOOK_MARGINAL_DECISION_2026-06-01.md")
    decision_path.write_text(_render_markdown(report, book_rows), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shortlist-path", type=Path, default=DEFAULT_SHORTLIST)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--x0-daily-path", type=Path, default=None)
    parser.add_argument("--r3-gate-ledger-path", type=Path, default=DEFAULT_R3_GATE_LEDGER)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    args = parser.parse_args()
    report = run(
        shortlist_path=args.shortlist_path,
        dataset_path=args.dataset_path,
        x0_daily_path=args.x0_daily_path,
        r3_gate_ledger_path=args.r3_gate_ledger_path,
        output_root=args.output_root,
        top_bottom_quantile=float(args.top_bottom_quantile),
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "decision": report["decision"],
                "output_root": report["output_root"],
                "core_cluster_count": report["core_cluster_count"],
                "all_cluster_count": report["all_cluster_count"],
                "cluster_eval_errors": report["cluster_eval_errors"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

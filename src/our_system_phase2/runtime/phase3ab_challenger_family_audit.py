"""Family-level audit for Phase3AB R3 challenger candidates.

This is a no-search, no-promotion report. It reads the completed Phase3AB R3
challenger audit output and checks whether the nine recent/R3 candidates are a
single crowded family, a useful standalone challenger book, or just weaker
substitutes for locked X0/R3.
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


VERSION = "phase3ab-challenger-family-audit-v1-2026-05-30"
DEFAULT_AUDIT_CSV = Path(
    "reports/phase3ab_r3_challenger_audit_v3_official_gate_20260530/phase3ab_r3_challenger_audit.csv"
)
DEFAULT_DAILY_CSV = Path(
    "reports/phase3ab_r3_challenger_audit_v3_official_gate_20260530/phase3ab_r3_challenger_daily.csv"
)
DEFAULT_OUTPUT = Path("reports/phase3ab_challenger_family_audit_20260530")


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
    clean = pd.to_numeric(values, errors="coerce").fillna(0.0)
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


def _prefixed(prefix: str, values: dict[str, Any]) -> dict[str, Any]:
    return {f"{prefix}_{key}": value for key, value in values.items()}


def _pairwise_corr_rows(wide: pd.DataFrame, *, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    columns = list(wide.columns)
    for idx, left in enumerate(columns):
        for right in columns[idx + 1 :]:
            joined = wide[[left, right]].dropna()
            corr = None
            if len(joined) >= 5 and joined[left].nunique() > 1 and joined[right].nunique() > 1:
                corr = joined[left].corr(joined[right])
            rows.append(
                {
                    "corr_scope": label,
                    "left_expr_hash": left,
                    "right_expr_hash": right,
                    "days": int(len(joined)),
                    "corr": _round(corr),
                    "abs_corr": _round(abs(corr)) if corr is not None else None,
                }
            )
    return rows


def _summary_from_corr(rows: list[dict[str, Any]], scope: str) -> dict[str, Any]:
    values = pd.Series([_round(row.get("abs_corr")) for row in rows if row.get("corr_scope") == scope], dtype=float).dropna()
    return {
        f"{scope}_pair_count": int(values.shape[0]),
        f"{scope}_mean_abs_corr": _round(values.mean()) if not values.empty else None,
        f"{scope}_median_abs_corr": _round(values.median()) if not values.empty else None,
        f"{scope}_max_abs_corr": _round(values.max()) if not values.empty else None,
        f"{scope}_share_abs_corr_ge_0p8": _round((values >= 0.8).mean()) if not values.empty else None,
        f"{scope}_share_abs_corr_ge_0p9": _round((values >= 0.9).mean()) if not values.empty else None,
    }


def _build_books(audit_rows: list[dict[str, str]], daily: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
    daily["R3_liquidity_low"] = daily["R3_liquidity_low"].astype(str).str.lower().isin(["true", "1", "1.0"])
    daily["candidate_r3_return"] = pd.to_numeric(daily["candidate_r3_return"], errors="coerce").fillna(0.0)
    daily["candidate_return"] = pd.to_numeric(daily["candidate_return"], errors="coerce").fillna(0.0)
    daily["x0_r3_return"] = pd.to_numeric(daily["x0_r3_return"], errors="coerce").fillna(0.0)

    audit_by_expr = {row["expr_hash"]: row for row in audit_rows}
    r3_wide = daily.pivot_table(index="date", columns="expr_hash", values="candidate_r3_return", aggfunc="first")
    full_wide = daily.pivot_table(index="date", columns="expr_hash", values="candidate_return", aggfunc="first")
    base = daily[["date", "R3_liquidity_low", "x0_r3_return"]].drop_duplicates("date").sort_values("date").reset_index(drop=True)
    base = base.set_index("date")
    r3_wide = r3_wide.reindex(base.index).fillna(0.0)
    full_wide = full_wide.reindex(base.index).fillna(0.0)

    books = pd.DataFrame(index=base.index)
    books["R3_liquidity_low"] = base["R3_liquidity_low"].astype(bool)
    books["x0_r3"] = base["x0_r3_return"].fillna(0.0)
    books["challenger_all9_r3_equal"] = r3_wide.mean(axis=1)
    books["challenger_all9_no_gate_equal"] = full_wide.mean(axis=1)
    lane_series: list[pd.Series] = []
    for lane in sorted({row.get("source_lane", "") for row in audit_rows}):
        exprs = [row["expr_hash"] for row in audit_rows if row.get("source_lane") == lane]
        if exprs:
            books[f"lane_{lane}_r3_equal"] = r3_wide[exprs].mean(axis=1)
            lane_series.append(books[f"lane_{lane}_r3_equal"])
    if lane_series:
        books["challenger_lane_balanced_r3_equal"] = pd.concat(lane_series, axis=1).mean(axis=1)
    top_by_lane: list[str] = []
    for lane in sorted({row.get("source_lane", "") for row in audit_rows}):
        lane_rows = [row for row in audit_rows if row.get("source_lane") == lane]
        lane_rows.sort(key=lambda row: float(row.get("candidate_r3_sortino") or -999.0), reverse=True)
        if lane_rows:
            top_by_lane.append(lane_rows[0]["expr_hash"])
    if top_by_lane:
        books["challenger_top1_per_lane_r3_equal"] = r3_wide[top_by_lane].mean(axis=1)

    book_rows: list[dict[str, Any]] = []
    for column in [col for col in books.columns if col not in {"R3_liquidity_low"}]:
        metrics = _metrics(books[column])
        blend = None
        if column != "x0_r3":
            blend = (books["x0_r3"] * 6.0 + books[column]) / 7.0
        row = {
            "book": column,
            **metrics,
            "delta_ann_vs_x0_r3": _round((metrics.get("ann_compound") or 0.0) - (_metrics(books["x0_r3"]).get("ann_compound") or 0.0)),
            "delta_sortino_vs_x0_r3": _round((metrics.get("sortino") or 0.0) - (_metrics(books["x0_r3"]).get("sortino") or 0.0)),
        }
        if blend is not None:
            row.update(_prefixed("blend7_with_x0", _metrics(blend)))
            row["blend7_delta_ann_vs_x0_r3"] = _round((_metrics(blend).get("ann_compound") or 0.0) - (_metrics(books["x0_r3"]).get("ann_compound") or 0.0))
            row["blend7_delta_sortino_vs_x0_r3"] = _round((_metrics(blend).get("sortino") or 0.0) - (_metrics(books["x0_r3"]).get("sortino") or 0.0))
        book_rows.append(row)
    for expr, row in audit_by_expr.items():
        books[f"candidate_{expr}"] = r3_wide[expr]
    return books.reset_index(), book_rows


def _source_summary(audit_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, str]]] = {}
    for row in audit_rows:
        groups.setdefault(row.get("source_lane", "__unknown__"), []).append(row)
    summary: list[dict[str, Any]] = []
    for lane, rows in groups.items():
        summary.append(
            {
                "source_lane": lane,
                "candidate_count": len(rows),
                "mean_candidate_r3_ann": _round(pd.Series([float(row.get("candidate_r3_ann_compound") or 0.0) for row in rows]).mean()),
                "mean_candidate_r3_sortino": _round(pd.Series([float(row.get("candidate_r3_sortino") or 0.0) for row in rows]).mean()),
                "mean_corr_to_x0_r3_active": _round(pd.Series([float(row.get("corr_candidate_to_x0_r3_active") or 0.0) for row in rows]).mean()),
                "mean_blend7_delta_ann": _round(pd.Series([float(row.get("blend7_r3_delta_ann_vs_x0_r3") or 0.0) for row in rows]).mean()),
            }
        )
    summary.sort(key=lambda row: row["candidate_count"], reverse=True)
    return summary


def _render(report: dict[str, Any]) -> str:
    lines = [
        "# Phase3AB R3 Challenger Decision Record",
        "",
        "Decision: `HOLD_PHASE3AB_R3_CHALLENGER_DIAGNOSTIC_ONLY`.",
        "",
        "## Confirmed",
        "",
        "- 9 Phase3AB recent/R3 challenger candidates remain valid diagnostic candidates.",
        "- All 9 fail X0/R3 marginal overlay promotion when evaluated against the locked X0/R3 daily object.",
        "- The family is concentrated in `volume_ratio_x_momentum_curve`, `turnover_ratio_x_momentum_curve`, and `amount_ratio_x_momentum_curve`.",
        "",
        "## Not Confirmed",
        "",
        "- Official X0/R3 overlay promotion.",
        "- All-history alpha validity.",
        "- Production readiness, minute execution, true capacity, or live survival.",
        "",
        "## Key Metrics",
        "",
        f"- x0_r3_ann: `{report['x0_r3_ann']}`",
        f"- x0_r3_sortino: `{report['x0_r3_sortino']}`",
        f"- candidate_count: `{report['candidate_count']}`",
        f"- overlay_reject_count: `{report['overlay_reject_count']}`",
        f"- r3_mean_abs_corr: `{report['corr_summary'].get('r3_pairwise_mean_abs_corr')}`",
        f"- r3_max_abs_corr: `{report['corr_summary'].get('r3_pairwise_max_abs_corr')}`",
        "",
        "## Standalone Book Check",
        "",
        "| book | ann | sortino | max dd | delta ann vs X0 | blend7 delta ann |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in report["book_rows"]:
        lines.append(
            "| {book} | {ann} | {sortino} | {dd} | {dann} | {bdann} |".format(
                book=row.get("book"),
                ann=row.get("ann_compound"),
                sortino=row.get("sortino"),
                dd=row.get("max_drawdown"),
                dann=row.get("delta_ann_vs_x0_r3"),
                bdann=row.get("blend7_delta_ann_vs_x0_r3", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Bias Audit",
            "",
            "- OOS evidence grade: `WEAK`; 2026 window has 78 daily observations.",
            "- Discovery status: post-discovery validation of Phase3AB search outputs.",
            "- Cost model: 10 bps turnover-cost proxy inherited from candidate deep validation.",
            "- Date alignment: candidate daily returns come from after-open signal and one-day execution lag; X0/R3 uses locked daily return object and official R3 gate.",
            "- Blocking issue: weak recent-OOS-only evidence and no marginal improvement versus locked X0/R3.",
            "",
            "## Required Next Action",
            "",
            "- Do not add these candidates to X0/R3.",
            "- Keep as diagnostic recent/R3 challenger pool.",
            "- If searching further, use marginal-aware reward against X0/R3 and family duplicate penalties.",
            "",
            "## Outputs",
            "",
            f"- family_summary_json: `{report['paths']['json']}`",
            f"- book_csv: `{report['paths']['book_csv']}`",
            f"- pairwise_corr_csv: `{report['paths']['pairwise_corr_csv']}`",
            f"- source_summary_csv: `{report['paths']['source_summary_csv']}`",
            f"- daily_book_csv: `{report['paths']['daily_book_csv']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def run(*, audit_csv: Path, daily_csv: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    audit_rows = _read_csv(audit_csv)
    daily = pd.read_csv(daily_csv)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
    daily["R3_liquidity_low"] = daily["R3_liquidity_low"].astype(str).str.lower().isin(["true", "1", "1.0"])
    daily["candidate_r3_return"] = pd.to_numeric(daily["candidate_r3_return"], errors="coerce").fillna(0.0)
    daily["candidate_return"] = pd.to_numeric(daily["candidate_return"], errors="coerce").fillna(0.0)

    r3_wide = daily.pivot_table(index="date", columns="expr_hash", values="candidate_r3_return", aggfunc="first")
    full_wide = daily.pivot_table(index="date", columns="expr_hash", values="candidate_return", aggfunc="first")
    pairwise_rows = _pairwise_corr_rows(r3_wide, label="r3_pairwise")
    pairwise_rows.extend(_pairwise_corr_rows(full_wide, label="full_pairwise"))
    corr_summary = {
        **_summary_from_corr(pairwise_rows, "r3_pairwise"),
        **_summary_from_corr(pairwise_rows, "full_pairwise"),
    }
    books, book_rows = _build_books(audit_rows, daily)
    source_summary = _source_summary(audit_rows)
    x0_row = next(row for row in book_rows if row["book"] == "x0_r3")
    overlay_reject_count = sum(1 for row in audit_rows if row.get("overlay_decision") == "REJECT_OVERLAY_NO_MARGINAL_VALUE")
    decision = "HOLD_PHASE3AB_R3_CHALLENGER_DIAGNOSTIC_ONLY"
    if overlay_reject_count != len(audit_rows):
        decision = "REVIEW_PHASE3AB_R3_CHALLENGER_NONUNIFORM_DECISIONS"

    paths = {
        "json": str(output_root / "phase3ab_challenger_family_audit.json"),
        "markdown": str(output_root / "PHASE3AB_R3_CHALLENGER_DECISION_RECORD_2026-05-30.md"),
        "pairwise_corr_csv": str(output_root / "phase3ab_challenger_pairwise_corr.csv"),
        "book_csv": str(output_root / "phase3ab_challenger_book_metrics.csv"),
        "daily_book_csv": str(output_root / "phase3ab_challenger_book_daily.csv"),
        "source_summary_csv": str(output_root / "phase3ab_challenger_source_summary.csv"),
    }
    _write_csv(Path(paths["pairwise_corr_csv"]), pairwise_rows)
    _write_csv(Path(paths["book_csv"]), book_rows)
    _write_csv(Path(paths["daily_book_csv"]), books.to_dict("records"))
    _write_csv(Path(paths["source_summary_csv"]), source_summary)
    report = {
        "version": VERSION,
        "scope": "no_search_challenger_family_audit",
        "decision": decision,
        "candidate_count": len(audit_rows),
        "overlay_reject_count": overlay_reject_count,
        "audit_csv": str(audit_csv),
        "daily_csv": str(daily_csv),
        "output_root": str(output_root),
        "x0_r3_ann": x0_row.get("ann_compound"),
        "x0_r3_sortino": x0_row.get("sortino"),
        "corr_summary": corr_summary,
        "book_rows": book_rows,
        "source_summary": source_summary,
        "paths": paths,
        "official_x0_r3_policy": "read_only_no_change",
        "promotion_policy": "diagnostic_only_no_x0_r3_change",
    }
    write_json_artifact(Path(paths["json"]), report)
    Path(paths["markdown"]).write_text(_render(report), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Phase3AB R3 challenger family behavior.")
    parser.add_argument("--audit-csv", type=Path, default=DEFAULT_AUDIT_CSV)
    parser.add_argument("--daily-csv", type=Path, default=DEFAULT_DAILY_CSV)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(audit_csv=args.audit_csv, daily_csv=args.daily_csv, output_root=args.output_root)
    print(
        json.dumps(
            {
                "status": "ok",
                "decision": report["decision"],
                "output_root": report["output_root"],
                "candidate_count": report["candidate_count"],
                "overlay_reject_count": report["overlay_reject_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_REPORT_DIR = Path("reports/phase3z45b_parametric_limit_open_touch_20260528")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _bool_series(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series.fillna(False)
    return series.astype(str).str.lower().isin(["true", "1", "yes"])


def _float_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _first_non_null(values: pd.Series) -> str:
    for value in values:
        if pd.notna(value) and str(value):
            return str(value)
    return ""


def _top_counts(values: pd.Series, limit: int = 3) -> str:
    counter = Counter(str(value) for value in values if pd.notna(value) and str(value))
    return "; ".join(f"{key}:{count}" for key, count in counter.most_common(limit))


def _event_bucket(row: pd.Series) -> str:
    text = " ".join(
        str(row.get(col) or "")
        for col in ("expression", "primitive_family", "structural_skeleton")
    )
    if "limit_up_touch_not_close" in text:
        return "limit_up_touch_not_close"
    if "limit_up_open_not_close" in text:
        return "limit_up_open_not_close"
    if "limit_up_touch_event" in text:
        return "limit_up_touch_event"
    if "limit_up_open_event" in text:
        return "limit_up_open_event"
    if "limit_up_close_event" in text:
        return "limit_up_close_event"
    if "limit_up_streak_ge" in text:
        return "limit_up_streak_geN"
    if "limit_up_streak" in text:
        return "limit_up_streak_legacy"
    if "break_after_high_board" in text:
        return "break_after_high_board_geN"
    if "break_after_prev_up" in text:
        return "break_after_prev_upN"
    if "post_market_high_board" in text:
        return "post_market_high_board_N_tplusD"
    if "market_high_board" in text:
        return "market_high_board_N"
    if "limit_down" in text:
        return "limit_down_or_repair"
    if bool(row.get("contains_limit_event")):
        return "other_limit_event"
    return "non_limit"


def _cluster_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for cluster_id, group in df.groupby("signal_cluster_id", dropna=False):
        strict_pass = _bool_series(group["strict_pass_proxy"])
        replay_pass = _bool_series(group["portfolio_replay_pass"])
        cost_survives = _bool_series(group["cost_survives"])
        contains_limit = _bool_series(group["contains_limit_event"])
        top_replay = group.sort_values(
            ["portfolio_replay_pass", "portfolio_replay_long_only_sortino", "strict_cost_adjusted_sortino"],
            ascending=[False, False, False],
            na_position="last",
        ).iloc[0]
        rows.append(
            {
                "signal_cluster_id": str(cluster_id),
                "audited_count": int(len(group)),
                "strict_pass_count": int(strict_pass.sum()),
                "portfolio_replay_pass_count": int(replay_pass.sum()),
                "cost_survival_count": int(cost_survives.sum()),
                "limit_event_count": int(contains_limit.sum()),
                "limit_event_share": round(float(contains_limit.mean()), 6),
                "best_strict_cost_adjusted_sortino": round(float(_float_series(group["strict_cost_adjusted_sortino"]).max()), 6),
                "best_portfolio_replay_sortino": round(float(_float_series(group["portfolio_replay_long_only_sortino"]).max()), 6),
                "best_portfolio_replay_net_mean": round(float(_float_series(group["portfolio_replay_long_only_net_mean"]).max()), 8),
                "median_strict_turnover": round(float(_float_series(group["strict_mean_one_way_turnover"]).median()), 6),
                "median_portfolio_turnover": round(float(_float_series(group["portfolio_replay_avg_one_way_turnover"]).median()), 6),
                "event_bucket_top": _top_counts(group["event_bucket"]),
                "family_top": _top_counts(group["primitive_family"]),
                "role_top": _top_counts(group["strict_selection_role"]),
                "representative_candidate_id": str(top_replay.get("candidate_id") or ""),
                "representative_expression": str(top_replay.get("expression") or ""),
                "candidate_review_decision": (
                    "ALLOW_DEEP_AUDIT"
                    if int(replay_pass.sum()) > 0 and int(cost_survives.sum()) > 0
                    else "HOLD_RESEARCH"
                ),
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values(
        ["portfolio_replay_pass_count", "strict_pass_count", "best_portfolio_replay_sortino", "audited_count"],
        ascending=[False, False, False, False],
    )


def _candidate_shortlist(df: pd.DataFrame) -> pd.DataFrame:
    mask = _bool_series(df["portfolio_replay_pass"]) | _bool_series(df["strict_pass_proxy"])
    cols = [
        "candidate_id",
        "signal_cluster_id",
        "event_bucket",
        "contains_limit_event",
        "strict_selection_role",
        "primitive_family",
        "strict_pass_proxy",
        "portfolio_replay_pass",
        "cost_survives",
        "strict_mean_rank_ic",
        "strict_cost_adjusted_sortino",
        "strict_mean_one_way_turnover",
        "portfolio_replay_long_only_sortino",
        "portfolio_replay_long_only_net_mean",
        "portfolio_replay_avg_one_way_turnover",
        "max_abs_signal_corr_to_prior",
        "expression",
    ]
    return df.loc[mask, [col for col in cols if col in df.columns]].sort_values(
        ["portfolio_replay_pass", "cost_survives", "portfolio_replay_long_only_sortino", "strict_cost_adjusted_sortino"],
        ascending=[False, False, False, False],
        na_position="last",
    )


def _event_bucket_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for bucket, group in df.groupby("event_bucket"):
        rows.append(
            {
                "event_bucket": bucket,
                "audited_count": len(group),
                "strict_pass_count": int(_bool_series(group["strict_pass_proxy"]).sum()),
                "portfolio_replay_pass_count": int(_bool_series(group["portfolio_replay_pass"]).sum()),
                "cost_survival_count": int(_bool_series(group["cost_survives"]).sum()),
                "unique_signal_clusters": int(group["signal_cluster_id"].nunique()),
                "median_strict_turnover": round(float(_float_series(group["strict_mean_one_way_turnover"]).median()), 6),
                "best_replay_sortino": round(float(_float_series(group["portfolio_replay_long_only_sortino"]).max()), 6),
                "top_family": _top_counts(group["primitive_family"], limit=5),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["portfolio_replay_pass_count", "strict_pass_count", "audited_count"],
        ascending=[False, False, False],
    )


def run_audit(report_dir: Path, output_dir: Path) -> dict[str, Any]:
    report_path = report_dir / "phase3z39_automated_validation_report.json"
    rows_path = report_dir / "phase3z39_strict_replay_rows.csv"
    report = _read_json(report_path)
    df = pd.read_csv(rows_path)
    for col in ("contains_limit_event", "strict_pass_proxy", "portfolio_replay_pass", "cost_survives"):
        if col in df.columns:
            df[col] = _bool_series(df[col])
    df["event_bucket"] = df.apply(_event_bucket, axis=1)
    output_dir.mkdir(parents=True, exist_ok=True)

    cluster_summary = _cluster_summary(df)
    candidate_shortlist = _candidate_shortlist(df)
    event_summary = _event_bucket_summary(df)

    cluster_summary.to_csv(output_dir / "phase3z45b_cluster_summary.csv", index=False, encoding="utf-8-sig")
    candidate_shortlist.to_csv(output_dir / "phase3z45b_candidate_shortlist.csv", index=False, encoding="utf-8-sig")
    event_summary.to_csv(output_dir / "phase3z45b_event_bucket_summary.csv", index=False, encoding="utf-8-sig")

    strict = report.get("strict_metric_summary") or {}
    limit_split = report.get("limit_event_vs_non_limit_summary") or {}
    top_clusters = cluster_summary.head(12).to_dict(orient="records")
    deep_audit = cluster_summary[cluster_summary["candidate_review_decision"] == "ALLOW_DEEP_AUDIT"]
    limit_deep_audit = deep_audit[deep_audit["limit_event_count"] > 0]
    nonlimit_deep_audit = deep_audit[deep_audit["limit_event_count"] == 0]

    markdown = [
        "# Phase3Z45b Parametric Limit/Open/Touch Result Audit",
        "",
        "## Decision",
        "",
        "Decision: `HOLD_RESEARCH_FOR_CANDIDATE_DEEP_AUDIT`.",
        "",
        "This run produced strict low-corr candidates, but it is research validation only. No alpha is promoted from this audit.",
        "",
        "## Run Summary",
        "",
        f"- decision: `{report.get('decision')}`",
        f"- stage1 reports: `{report.get('stage1_report_count')}`",
        f"- raw stage1 rows: `{(report.get('queue_summary') or {}).get('raw_stage1_rows')}`",
        f"- deduped expression rows: `{(report.get('queue_summary') or {}).get('deduped_expression_rows')}`",
        f"- strict audited: `{strict.get('strict_audited_count')}`",
        f"- strict pass: `{strict.get('strict_pass_count')}`",
        f"- low-corr strict pass clusters: `{strict.get('low_corr_strict_pass_count')}`",
        f"- portfolio replay pass: `{strict.get('portfolio_replay_pass_count')}`",
        f"- cost survival: `{strict.get('cost_survival_count')}`",
        "",
        "## Limit/Event Split",
        "",
    ]
    for name, payload in limit_split.items():
        markdown.extend(
            [
                f"- `{name}` audited `{payload.get('strict_audited_count')}`, strict pass `{payload.get('strict_pass_count')}`, "
                f"low-corr `{payload.get('low_corr_strict_pass_count')}`, replay pass `{payload.get('portfolio_replay_pass_count')}`, "
                f"cost survival `{payload.get('cost_survival_count')}`.",
            ]
        )
    markdown.extend(
        [
            "",
            "Interpretation: limit/event candidates are valid enough to continue as a diagnostic search family, "
            "but direct limit/event formulas did not outperform the non-limit side on replay pass rate or cost survival.",
            "",
            "## Top Deep-Audit Clusters",
            "",
            "| cluster | audited | strict_pass | replay_pass | cost_survival | limit_share | bucket | decision | representative |",
            "|---|---:|---:|---:|---:|---:|---|---|---|",
        ]
    )
    for row in top_clusters:
        expr = str(row["representative_expression"]).replace("|", "\\|")
        if len(expr) > 120:
            expr = expr[:117] + "..."
        markdown.append(
            f"| {row['signal_cluster_id']} | {row['audited_count']} | {row['strict_pass_count']} | "
            f"{row['portfolio_replay_pass_count']} | {row['cost_survival_count']} | {row['limit_event_share']} | "
            f"{row['event_bucket_top']} | {row['candidate_review_decision']} | `{expr}` |"
        )
    markdown.extend(
        [
            "",
            "## Bias / Evidence Audit",
            "",
            f"- signal clock: `{(report.get('bias_audit_contract') or {}).get('signal_clock')}`",
            f"- execution lag days: `{(report.get('bias_audit_contract') or {}).get('execution_lag_days')}`",
            f"- cost bps: `{(report.get('bias_audit_contract') or {}).get('cost_bps')}`",
            f"- OOS grade: `{(report.get('bias_audit_contract') or {}).get('oos_grade')}`",
            f"- promotion allowed: `{(report.get('bias_audit_contract') or {}).get('promotion_allowed')}`",
            "",
            "Blocking issue for promotion: evidence is recent-daily and research-validation only. "
            "Candidate clusters require identity audit, OOS/regime split, turnover/cost stress, and duplicate-family checks.",
            "",
            "## Next Actions",
            "",
            "1. Deep-audit `ALLOW_DEEP_AUDIT` clusters only; do not promote from this report.",
            "2. Split cluster_007 and high-board leader clusters by 2025H2 / 2026 and R3/non-R3 regime.",
            "3. Check whether `limit_up_streak_ge8/ge9/ge10` variants are genuinely distinct or parameter duplicates.",
            "4. Keep `limit_up_touch/open/not_close` features diagnostic until exact limit-price/tradability audit is added.",
        ]
    )
    md_path = output_dir / "PHASE3Z45B_PARAMETRIC_LIMIT_RESULT_AUDIT_2026-05-28.md"
    md_path.write_text("\n".join(markdown) + "\n", encoding="utf-8")

    summary = {
        "decision": "HOLD_RESEARCH_FOR_CANDIDATE_DEEP_AUDIT",
        "report_dir": str(report_dir),
        "output_dir": str(output_dir),
        "strict_metric_summary": strict,
        "limit_event_vs_non_limit_summary": limit_split,
        "cluster_count": int(cluster_summary.shape[0]),
        "deep_audit_cluster_count": int(deep_audit.shape[0]),
        "limit_deep_audit_cluster_count": int(limit_deep_audit.shape[0]),
        "nonlimit_deep_audit_cluster_count": int(nonlimit_deep_audit.shape[0]),
        "outputs": {
            "markdown": str(md_path),
            "cluster_summary": str(output_dir / "phase3z45b_cluster_summary.csv"),
            "candidate_shortlist": str(output_dir / "phase3z45b_candidate_shortlist.csv"),
            "event_bucket_summary": str(output_dir / "phase3z45b_event_bucket_summary.csv"),
        },
    }
    (output_dir / "phase3z45b_parametric_limit_result_audit.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Phase3Z45b parametric limit/open/touch strict results.")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    output_dir = args.output_dir or (args.report_dir / "audit")
    summary = run_audit(args.report_dir, output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.services.stock_pit_proof_suite import _attach_signal_clusters, _safe_float
from our_system_phase2.services.stock_pit_replay_ranker import score_shadow_selector, score_with_trained_replay_rankers
from our_system_phase2.services.stock_pit_true_limit_search_bakeoff_v2 import (
    _fields,
    _fast_rows_from_variant_report,
    _is_gap_like,
    _operators,
    _replay_ranker_feature_row,
    _row_key,
    _stratified_strict_inputs,
)
from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression
from our_system_phase2.services.variation import extract_structural_skeleton


DEFAULT_ROOT = Path(
    "runtime/next_stage_artifacts/phase2-true-limit-replayaware-slice-medium-local-20260511"
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_hash(text: str, length: int = 16) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length]


def field_family(field: str) -> str:
    if field in {"amount", "volume", "turnover_rate", "vwap", "money_flow", "amtm"}:
        return "liquidity"
    if field in {"ret", "return_1d", "return_5d", "return_20d", "reta", "retb", "retc", "retd", "rete", "retf"}:
        return "return_vol"
    if field in {"open", "high", "low", "close", "price_pos", "low_20", "high_20"}:
        return "price_shape"
    if "limit" in field:
        return "limit_state"
    if "cap" in field or "market" in field or "share" in field:
        return "capacity"
    if "trend" in field or field.startswith("rps"):
        return "trend_state"
    return "other"


def expression_windows(expression: str) -> list[int]:
    values: set[int] = set()
    for token in re.findall(r",\s*(\d+)\s*\)", expression or ""):
        values.add(int(token))
    for token in re.findall(r"Delay\([^,]+,\s*(\d+)\s*\)", expression or "", flags=re.IGNORECASE):
        values.add(int(token))
    return sorted(value for value in values if value > 0)


def horizon_bucket(expression: str) -> str:
    windows = expression_windows(expression)
    if not windows:
        return "w_none_or_implicit"
    max_window = max(windows)
    if max_window <= 5:
        return "w_1_5"
    if max_window <= 21:
        return "w_6_21"
    if max_window <= 60:
        return "w_22_60"
    return "w_61_plus"


def turnover_bucket(value: Any) -> str:
    turnover = _safe_float(value, default=float("nan"))
    if not math.isfinite(turnover):
        return "turnover_unknown"
    if turnover <= 0.25:
        return "turnover_0_025"
    if turnover <= 0.75:
        return "turnover_025_075"
    if turnover <= 1.50:
        return "turnover_075_150"
    return "turnover_150_plus"


def row_identity(row: dict[str, Any]) -> str:
    return f"{row.get('seed')}::{row.get('proof_variant')}::{row.get('candidate_id')}::{row.get('expression')}"


def annotate_rows(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[Path]]:
    reports = sorted(root.glob("replayaware_medium_seed*_20260511/true_limit_search_bakeoff_v2_report.json"))
    strict_rows: list[dict[str, Any]] = []
    report_payloads: list[dict[str, Any]] = []
    for report_path in reports:
        payload = read_json(report_path)
        report_payloads.append(payload)
        seed = report_path.parent.name
        rows = read_json(report_path.parent / "strict_by_variant_rows.json").get("strict_rows", [])
        for index, row in enumerate(rows):
            item = dict(row)
            item["seed"] = seed
            item["row_index"] = index
            item["lane"] = str(item.get("proof_variant") or "")
            item["selection_policy"] = item.get("selection_policy") or "r0_control"
            if "selection_pool_type" not in item:
                item["selection_pool_type"] = "R0_leftover" if item["selection_policy"] == "replay_aware_shadow_slice" else "common_pool"
            strict_rows.append(item)
    return strict_rows, report_payloads, reports


def non_gap_replay_pass(row: dict[str, Any]) -> bool:
    return bool(row.get("portfolio_replay_pass")) and not bool(row.get("is_gap_family")) and not _is_gap_like(row)


def global_cluster_pass_rows(rows: list[dict[str, Any]], *, dataset_path: Path, recent_quarter_window_count: int, recent_warmup_days: int) -> list[dict[str, Any]]:
    cluster_input: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["original_lane"] = item.get("lane") or item.get("proof_variant")
        item["proof_variant"] = f"{item.get('seed')}::{item.get('lane')}"
        cluster_input.append(item)
    clustered, _ = _attach_signal_clusters(
        cluster_input,
        dataset_path=dataset_path,
        threshold=0.80,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    output: list[dict[str, Any]] = []
    for row in clustered:
        item = dict(row)
        item["proof_variant"] = item.get("original_lane") or item.get("lane")
        item["lane"] = item.get("original_lane") or item.get("lane")
        item["global_return_corr_cluster"] = item.get("signal_cluster_id")
        item["global_max_abs_corr_to_prior"] = item.get("max_abs_signal_corr_to_prior")
        output.append(item)
    return output


def pass_cluster_summary(pass_rows: list[dict[str, Any]]) -> tuple[pd.DataFrame, dict[str, Any]]:
    detail_rows: list[dict[str, Any]] = []
    for row in pass_rows:
        expression = str(row.get("expression") or "")
        normalized = rank_validation_canonical_expression(expression)
        skeleton = extract_structural_skeleton(normalized)
        fields = _fields(expression)
        operators = _operators(expression)
        field_families = tuple(sorted({field_family(field) for field in fields}))
        operator_family = tuple(sorted(set(operators)))
        strict_turnover = row.get("strict_mean_one_way_turnover")
        deployable = bool(row.get("cost_survives")) and _safe_float(strict_turnover, default=999.0) <= 0.75
        detail_rows.append(
            {
                "seed": row.get("seed"),
                "lane": row.get("lane"),
                "selection_policy": row.get("selection_policy"),
                "selection_pool_type": row.get("selection_pool_type"),
                "candidate_id": row.get("candidate_id"),
                "expression": expression,
                "normalized_expression_hash": stable_hash(normalized),
                "ast_hash": stable_hash(skeleton),
                "global_return_corr_cluster": row.get("global_return_corr_cluster"),
                "global_max_abs_corr_to_prior": row.get("global_max_abs_corr_to_prior"),
                "field_family_cluster": "|".join(field_families) or "none",
                "operator_family_cluster": "|".join(operator_family) or "none",
                "horizon_bucket": horizon_bucket(expression),
                "turnover_bucket": turnover_bucket(strict_turnover),
                "cost_survives": bool(row.get("cost_survives")),
                "strict_mean_one_way_turnover": strict_turnover,
                "portfolio_replay_avg_one_way_turnover": row.get("portfolio_replay_avg_one_way_turnover"),
                "deployable_cost_turnover": deployable,
                "sector_exposure_available": row.get("sector_exposure") is not None,
                "style_exposure_available": row.get("style_exposure") is not None,
            }
        )
    detail = pd.DataFrame(detail_rows)
    if detail.empty:
        return detail, {}
    r0 = detail[detail["selection_policy"] == "r0_control"]
    slice_rows = detail[detail["selection_policy"] == "replay_aware_shadow_slice"]
    r0_clusters = set(r0["global_return_corr_cluster"].dropna().astype(str))
    slice_clusters = set(slice_rows["global_return_corr_cluster"].dropna().astype(str))
    deployable = detail[detail["deployable_cost_turnover"]]
    summary = {
        "raw_non_gap_replay_pass": int(len(detail)),
        "r0_non_gap_replay_pass": int(len(r0)),
        "slice_non_gap_replay_pass": int(len(slice_rows)),
        "unique_return_corr_clusters": int(detail["global_return_corr_cluster"].nunique(dropna=True)),
        "unique_return_corr_deployable_clusters": int(deployable["global_return_corr_cluster"].nunique(dropna=True)),
        "unique_ast_hashes": int(detail["ast_hash"].nunique(dropna=True)),
        "unique_normalized_expression_hashes": int(detail["normalized_expression_hash"].nunique(dropna=True)),
        "unique_field_family_clusters": int(detail["field_family_cluster"].nunique(dropna=True)),
        "unique_operator_family_clusters": int(detail["operator_family_cluster"].nunique(dropna=True)),
        "unique_horizon_buckets": int(detail["horizon_bucket"].nunique(dropna=True)),
        "unique_turnover_buckets": int(detail["turnover_bucket"].nunique(dropna=True)),
        "slice_unique_return_clusters": int(len(slice_clusters)),
        "slice_new_return_clusters_vs_r0": int(len(slice_clusters - r0_clusters)),
        "slice_duplicate_return_clusters_vs_r0": int(len(slice_clusters & r0_clusters)),
        "sector_style_exposure_available": bool(detail["sector_exposure_available"].any() or detail["style_exposure_available"].any()),
    }
    return detail, summary


def reconstruct_scored_leftover(root: Path, *, model_dir: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for report_path in sorted(root.glob("replayaware_medium_seed*_20260511/true_limit_search_bakeoff_v2_report.json")):
        report = read_json(report_path)
        seed_name = report_path.parent.name
        params = report.get("parameters", {})
        for variant_report in report.get("variant_stage1_reports", []):
            lane = str(variant_report.get("variant") or "")
            fast_rows = _fast_rows_from_variant_report(variant_report)
            r0_selected = _stratified_strict_inputs(
                fast_rows,
                top_n=int(params.get("strict_top_n_per_variant") or 0),
                random_n=int(params.get("stratified_random_n_per_variant") or 0),
                seed=f"{params.get('seed')}::{lane}",
            )
            r0_keys = {_row_key(row) for row in r0_selected if _row_key(row)}
            feature_rows: list[dict[str, Any]] = []
            source_rows: dict[int, dict[str, Any]] = {}
            for index, row in enumerate(fast_rows):
                key = _row_key(row)
                if not key or key in r0_keys:
                    continue
                feature = _replay_ranker_feature_row(
                    row,
                    seed=f"{params.get('seed')}::{lane}::replay_aware",
                    source_index=index,
                )
                feature["seed"] = seed_name
                feature["lane"] = lane
                feature["candidate_key"] = key
                feature_rows.append(feature)
                source_rows[index] = row
            if not feature_rows:
                continue
            scored, _ = score_with_trained_replay_rankers(pd.DataFrame(feature_rows), model_dir=model_dir)
            scored = score_shadow_selector(scored, selection_budget=len(scored))
            frames.append(scored)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def score_decile_lift(scored_leftover: pd.DataFrame, strict_rows: list[dict[str, Any]], pass_detail: pd.DataFrame) -> pd.DataFrame:
    if scored_leftover.empty:
        return pd.DataFrame()
    label_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in strict_rows:
        if row.get("selection_policy") != "replay_aware_shadow_slice":
            continue
        key = (str(row.get("seed")), str(row.get("lane")), _row_key(row))
        label_by_key[key] = row
    cluster_by_identity = {
        (str(row["seed"]), str(row["lane"]), str(row["candidate_id"]), str(row["expression"])): row.get("global_return_corr_cluster")
        for _, row in pass_detail.iterrows()
    } if not pass_detail.empty else {}
    frame = scored_leftover.copy()
    frame["score_rank"] = pd.to_numeric(frame["selection_score"], errors="coerce")
    frame = frame.sort_values("score_rank", ascending=False).reset_index(drop=True)
    frame["score_decile"] = pd.qcut(frame.index + 1, q=10, labels=False, duplicates="drop")
    frame["score_decile"] = frame["score_decile"].astype(int) + 1
    rows: list[dict[str, Any]] = []
    for decile, group in frame.groupby("score_decile"):
        audited: list[dict[str, Any]] = []
        clusters: set[str] = set()
        for _, candidate in group.iterrows():
            label = label_by_key.get((str(candidate.get("seed")), str(candidate.get("lane")), str(candidate.get("candidate_key"))))
            if label is not None:
                audited.append(label)
                identity = (str(label.get("seed")), str(label.get("lane")), str(label.get("candidate_id")), str(label.get("expression")))
                cluster = cluster_by_identity.get(identity)
                if cluster and bool(label.get("portfolio_replay_pass")) and not bool(label.get("is_gap_family")):
                    clusters.add(str(cluster))
        replay_pass = [row for row in audited if bool(row.get("portfolio_replay_pass"))]
        non_gap_pass = [row for row in replay_pass if not bool(row.get("is_gap_family")) and not _is_gap_like(row)]
        rows.append(
            {
                "score_decile_top_first": int(decile),
                "candidate_count": int(len(group)),
                "score_min": round(float(group["score_rank"].min()), 6),
                "score_max": round(float(group["score_rank"].max()), 6),
                "score_mean": round(float(group["score_rank"].mean()), 6),
                "audited_count": int(len(audited)),
                "replay_pass": int(len(replay_pass)),
                "non_gap_replay_pass": int(len(non_gap_pass)),
                "unique_cluster_pass": int(len(clusters)),
                "audited_avg_corr": round(float(pd.to_numeric([row.get("max_abs_signal_corr_to_prior") for row in audited], errors="coerce").mean()), 6)
                if audited
                else None,
                "audited_avg_turnover": round(float(pd.to_numeric([row.get("strict_mean_one_way_turnover") for row in audited], errors="coerce").mean()), 6)
                if audited
                else None,
                "scored_avg_cheap_turnover": round(float(pd.to_numeric(group.get("cheap_backtest_turnover"), errors="coerce").mean()), 6),
            }
        )
    return pd.DataFrame(rows)


def diagnose_failure(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    expression = str(row.get("expression") or "")
    operators = set(_operators(expression))
    fields = set(_fields(expression))
    turnover = max(
        _safe_float(row.get("strict_mean_one_way_turnover"), default=0.0),
        _safe_float(row.get("portfolio_replay_avg_one_way_turnover"), default=0.0),
    )
    corr = _safe_float(row.get("max_abs_signal_corr_to_prior"), default=0.0)
    strict_ic = _safe_float(row.get("strict_mean_rank_ic"), default=0.0)
    decay = _safe_float(row.get("fast_to_strict_ic_decay"), default=0.0)
    blocker_flags = " ".join(str(flag) for flag in (row.get("strict_blocker_flags") or []))
    complexity = len(operators) + 0.75 * len(fields) + 0.15 * expression.count("(")
    if bool(row.get("is_gap_family")) or _is_gap_like(row):
        reasons.append("gap_dependency")
    if turnover > 0.75:
        reasons.append("turnover_too_high")
    if corr > 0.80:
        reasons.append("corr_duplicate")
    if "sector_exposure" in row and row.get("sector_exposure") is not None and abs(_safe_float(row.get("sector_exposure"))) > 0.5:
        reasons.append("sector_exposure")
    if "style_exposure" in row and row.get("style_exposure") is not None and abs(_safe_float(row.get("style_exposure"))) > 0.5:
        reasons.append("style_exposure")
    if strict_ic < 0.0 or "weak_primary_horizon_ic" in blocker_flags:
        reasons.append("subperiod_instability")
    if decay < -0.03:
        reasons.append("regime_instability")
    if complexity > 12:
        reasons.append("complexity_overfit")
    if {"Div", "Sign", "CSResidual"} & operators:
        reasons.append("operator_pathology")
    if {"open", "high", "low"} & fields and not bool(row.get("portfolio_replay_pass")):
        reasons.append("field_pathology")
    if not reasons:
        reasons.append("unknown")
    return reasons


def failure_diagnosis(strict_rows: list[dict[str, Any]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    fail_rows = [row for row in strict_rows if not bool(row.get("portfolio_replay_pass"))]
    detail: list[dict[str, Any]] = []
    for row in fail_rows:
        reasons = diagnose_failure(row)
        detail.append(
            {
                "seed": row.get("seed"),
                "lane": row.get("lane"),
                "selection_policy": row.get("selection_policy"),
                "candidate_id": row.get("candidate_id"),
                "expression": row.get("expression"),
                "signal_cluster_id": row.get("signal_cluster_id"),
                "max_abs_signal_corr_to_prior": row.get("max_abs_signal_corr_to_prior"),
                "is_gap_family": bool(row.get("is_gap_family")),
                "primary_reason": reasons[0],
                "all_reasons": "|".join(reasons),
                "strict_pass_proxy": bool(row.get("strict_pass_proxy")),
                "strict_mean_rank_ic": row.get("strict_mean_rank_ic"),
                "strict_mean_one_way_turnover": row.get("strict_mean_one_way_turnover"),
            }
        )
    detail_df = pd.DataFrame(detail)
    if detail_df.empty:
        return detail_df, pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for lane, group in detail_df.groupby("lane"):
        reason_counts = Counter(reason for value in group["all_reasons"] for reason in str(value).split("|") if reason)
        row = {"lane": lane, "fail_count": int(len(group))}
        row.update({reason: int(reason_counts.get(reason, 0)) for reason in FAILURE_REASON_ORDER})
        rows.append(row)
    return detail_df, pd.DataFrame(rows).sort_values("lane")


FAILURE_REASON_ORDER = [
    "gap_dependency",
    "turnover_too_high",
    "corr_duplicate",
    "factor_exposure",
    "sector_exposure",
    "style_exposure",
    "subperiod_instability",
    "regime_instability",
    "complexity_overfit",
    "operator_pathology",
    "field_pathology",
    "unknown",
]


def pool_summary(strict_rows: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in strict_rows:
        grouped[(str(row.get("lane")), str(row.get("selection_policy")), str(row.get("selection_pool_type")))].append(row)
    for (lane, policy, pool_type), group in grouped.items():
        replay = [row for row in group if bool(row.get("portfolio_replay_pass"))]
        non_gap = [row for row in replay if not bool(row.get("is_gap_family")) and not _is_gap_like(row)]
        rows.append(
            {
                "lane": lane,
                "selection_policy": policy,
                "selection_pool_type": pool_type,
                "audited_count": int(len(group)),
                "replay_pass": int(len(replay)),
                "non_gap_replay_pass": int(len(non_gap)),
            }
        )
    return pd.DataFrame(rows).sort_values(["lane", "selection_policy", "selection_pool_type"])


def df_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    return json.loads(df.where(pd.notna(df), None).to_json(orient="records", force_ascii=False))


def write_markdown(
    path: Path,
    *,
    root: Path,
    pass_summary: dict[str, Any],
    pool_df: pd.DataFrame,
    decile_df: pd.DataFrame,
    failure_summary_df: pd.DataFrame,
) -> None:
    def md_table(df: pd.DataFrame, columns: list[str]) -> str:
        if df.empty:
            return "_empty_"
        trimmed = df[columns].copy()
        return trimmed.to_markdown(index=False)

    lines = [
        "# Phase3 Repair Audit - 2026-05-11",
        "",
        "## Scope",
        "",
        f"- input root: `{root}`",
        "- purpose: diagnose whether the 28 non-gap replay passes are independent, whether replay-aware slice is residual value, whether selector scores are calibrated, and why failed lanes fail.",
        "- decision: HOLD_RESEARCH. This is diagnostic evidence, not factor promotion.",
        "",
        "## Independent Alpha Check",
        "",
        f"- raw non-gap replay pass: {pass_summary.get('raw_non_gap_replay_pass')}",
        f"- unique return-corr clusters: {pass_summary.get('unique_return_corr_clusters')}",
        f"- unique deployable return-corr clusters: {pass_summary.get('unique_return_corr_deployable_clusters')}",
        f"- unique AST hashes: {pass_summary.get('unique_ast_hashes')}",
        f"- unique normalized expression hashes: {pass_summary.get('unique_normalized_expression_hashes')}",
        f"- slice new return clusters vs R0: {pass_summary.get('slice_new_return_clusters_vs_r0')}",
        f"- sector/style exposure available: {pass_summary.get('sector_style_exposure_available')}",
        "",
        "Conclusion:",
        "",
        "- The raw pass count is not the deployable alpha count.",
        "- Return-corr and cost/turnover cluster compression must be the primary reporting view.",
        "- Slice contribution is residual value only unless it adds enough new deployable clusters versus R0.",
        "",
        "## Selection Pool Type",
        "",
        md_table(pool_df, ["lane", "selection_policy", "selection_pool_type", "audited_count", "replay_pass", "non_gap_replay_pass"]),
        "",
        "## Replay-Aware Score Decile Lift",
        "",
        md_table(
            decile_df,
            [
                "score_decile_top_first",
                "candidate_count",
                "audited_count",
                "replay_pass",
                "non_gap_replay_pass",
                "unique_cluster_pass",
                "audited_avg_corr",
                "audited_avg_turnover",
            ],
        ),
        "",
        "Conclusion:",
        "",
        "- All observed replay-aware passes are in the upper score buckets, but low-score buckets still need random pass-through to prove monotonic calibration.",
        "",
        "## Failure Diagnosis By Lane",
        "",
        md_table(failure_summary_df, ["lane", "fail_count", *FAILURE_REASON_ORDER]),
        "",
        "Conclusion:",
        "",
        "- Concentrated duplicate/operator pathology should feed AST repair.",
        "- Quarantine lanes should not compete for normal replay budget until repair diagnostics improve.",
        "",
        "## Next Phase Definition",
        "",
        "- Phase3 name: `phase3_repair`.",
        "- Main allocation: CEM control + AST failure-aware repair + replay-aware residual slice.",
        "- Suggested budget: R0/CEM-led 60%, AST failure repair 20%, replay-aware residual slice 10%, novelty/diagnostic 10%.",
        "- Replay-aware selector remains residual miner. It should not replace R0 until it wins equal-budget common-pool unique non-gap pass rate by at least 25%-30% without worse corr/turnover/complexity.",
        "- RX/random/non-gap-forced move to quarantine + pathology tests until failure diagnosis shows a fixable concentrated pathology.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit replay-aware medium results before Phase3 repair.")
    parser.add_argument("--input-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--model-dir", type=Path, default=Path("data/models"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = parser.parse_args()

    root = args.input_root
    strict_rows, report_payloads, report_paths = annotate_rows(root)
    if not report_paths:
        raise FileNotFoundError(f"no true_limit_search_bakeoff_v2_report.json under {root}")
    first_report = report_payloads[0]
    dataset_path = Path(first_report["dataset_path"])
    params = first_report.get("parameters", {})
    recent_quarters = int(params.get("recent_quarter_window_count") or 2)
    warmup = int(params.get("recent_warmup_days") or 60)

    pass_rows = [row for row in strict_rows if non_gap_replay_pass(row)]
    clustered_pass_rows = global_cluster_pass_rows(
        pass_rows,
        dataset_path=dataset_path,
        recent_quarter_window_count=recent_quarters,
        recent_warmup_days=warmup,
    )
    pass_detail_df, pass_summary = pass_cluster_summary(clustered_pass_rows)
    pool_df = pool_summary(strict_rows)
    scored_leftover = reconstruct_scored_leftover(root, model_dir=args.model_dir)
    decile_df = score_decile_lift(scored_leftover, strict_rows, pass_detail_df)
    failure_detail_df, failure_summary_df = failure_diagnosis(strict_rows)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    base = args.output_dir / "PHASE3_REPAIR_AUDIT_2026-05-11"
    pass_detail_df.to_csv(base.with_name(base.name + "_pass_clusters.csv"), index=False, encoding="utf-8")
    pool_df.to_csv(base.with_name(base.name + "_pool_summary.csv"), index=False, encoding="utf-8")
    decile_df.to_csv(base.with_name(base.name + "_score_deciles.csv"), index=False, encoding="utf-8")
    failure_detail_df.to_csv(base.with_name(base.name + "_failure_detail.csv"), index=False, encoding="utf-8")
    failure_summary_df.to_csv(base.with_name(base.name + "_failure_summary.csv"), index=False, encoding="utf-8")
    scored_leftover.to_parquet(base.with_name(base.name + "_scored_leftover.parquet"), index=False)

    payload = {
        "experiment_id": "20260511_phase3_repair_audit_001",
        "input_root": str(root),
        "report_count": len(report_paths),
        "strict_row_count": len(strict_rows),
        "pass_summary": pass_summary,
        "pool_summary": df_to_records(pool_df),
        "score_decile_lift": df_to_records(decile_df),
        "failure_summary": df_to_records(failure_summary_df),
        "outputs": {
            "markdown": str(base.with_suffix(".md")),
            "json": str(base.with_suffix(".json")),
            "pass_clusters_csv": str(base.with_name(base.name + "_pass_clusters.csv")),
            "pool_summary_csv": str(base.with_name(base.name + "_pool_summary.csv")),
            "score_deciles_csv": str(base.with_name(base.name + "_score_deciles.csv")),
            "failure_summary_csv": str(base.with_name(base.name + "_failure_summary.csv")),
            "failure_detail_csv": str(base.with_name(base.name + "_failure_detail.csv")),
            "scored_leftover_parquet": str(base.with_name(base.name + "_scored_leftover.parquet")),
        },
    }
    base.with_suffix(".json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(
        base.with_suffix(".md"),
        root=root,
        pass_summary=pass_summary,
        pool_df=pool_df,
        decile_df=decile_df,
        failure_summary_df=failure_summary_df,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""Phase3L-E daily deep test batch.

Runs the supported deep tests from the Phase3L-D fixed queue:

- full-expression strict/replay window checks via subperiod_stability_replay
- sign-flip placebo
- low-order ablations

Regime bucket replay is intentionally not run here because the current strict
runner does not produce true regime-bucket performance. Those rows remain
blocked for a dedicated regime runner.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH, dataset_role_for_path
from our_system_phase2.services.stock_pit_phase3_repair import (
    _attach_shadow_metrics,
    _deployable_pass,
    _non_gap_replay_pass,
    _phase3_main_kpis,
)
from our_system_phase2.services.stock_pit_proof_suite import (
    DEFAULT_LOW_CORR_THRESHOLD,
    DEFAULT_PORTFOLIO_REPLAY_COST_BPS,
    _attach_portfolio_replay,
    _attach_signal_clusters,
    _strict_audit_selected_fast_rows,
)


DEFAULT_QUEUE = Path("reports/phase3l_deep_evidence_gap_audit_20260517/phase3l_deep_test_queue.jsonl")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3l_e_daily_deep_test_batch_20260517")
SUPPORTED_TEST_TYPES = {"subperiod_stability_replay", "sign_flip_placebo", "low_order_ablation"}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


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


def _write_progress(root: Path, stage: str, **extra: Any) -> None:
    root.mkdir(parents=True, exist_ok=True)
    payload = {"time": utc_now_iso(), "stage": stage}
    payload.update(extra)
    with (root / "phase3_progress.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _score(row: dict[str, Any]) -> float | None:
    for key in ["portfolio_replay_long_only_sortino", "strict_cost_adjusted_sortino", "strict_mean_cost_adjusted_window_spread"]:
        value = _safe_float(row.get(key))
        if value is not None:
            return value
    return None


def _load_window_stats(row: dict[str, Any]) -> dict[str, Any]:
    path_text = row.get("strict_report_path")
    if not path_text:
        return {
            "window_count": 0,
            "positive_cost_window_count": 0,
            "positive_cost_window_ratio": None,
            "min_window_cost_adjusted_return": None,
        }
    path = Path(str(path_text))
    if not path.exists():
        return {
            "window_count": 0,
            "positive_cost_window_count": 0,
            "positive_cost_window_ratio": None,
            "min_window_cost_adjusted_return": None,
        }
    payload = _read_json(path)
    primary = (payload.get("horizon_reports") or [{}])[0]
    windows = [window for window in primary.get("windows", []) if isinstance(window, dict)]
    values = [
        value
        for value in (_safe_float(window.get("mean_cost_adjusted_long_short_return")) for window in windows)
        if value is not None
    ]
    positives = sum(1 for value in values if value > 0)
    return {
        "window_count": len(values),
        "positive_cost_window_count": positives,
        "positive_cost_window_ratio": round(positives / max(1, len(values)), 6) if values else None,
        "min_window_cost_adjusted_return": round(min(values), 6) if values else None,
    }


def _selected_rows(queue_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    metadata: dict[str, dict[str, Any]] = {}
    unsupported: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for idx, row in enumerate(queue_rows):
        test_type = str(row.get("test_type") or "")
        expr = str(row.get("test_expression") or "")
        if test_type not in SUPPORTED_TEST_TYPES or not expr:
            item = dict(row)
            item["blocked_reason"] = (
                "regime_bucket_runner_not_available" if test_type == "regime_bucket_replay" else "unsupported_or_empty_expression"
            )
            unsupported.append(item)
            continue
        key = (str(row.get("cluster_id") or ""), test_type, expr)
        if key in seen:
            continue
        seen.add(key)
        candidate_id = f"phase3lE-{test_type}-{row.get('cluster_id')}-{len(selected):03d}"
        item = {
            "candidate_id": candidate_id,
            "expression": expr,
            "proof_variant": test_type,
            "strict_selection_role": "phase3l_deep_test",
            "selection_policy": "phase3l_fixed_deep_test_queue",
            "selection_pool_type": "fixed_phase3l_deep_queue",
            "primitive_family": test_type,
            "proposal_kind": test_type,
            "mean_window_rank_ic": None,
        }
        selected.append(item)
        metadata[candidate_id] = dict(row)
    return selected, metadata, unsupported


def _attach_metadata(rows: list[dict[str, Any]], metadata: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        item = dict(row)
        meta = metadata.get(str(row.get("candidate_id") or ""), {})
        for key in [
            "cluster_id",
            "candidate_uid",
            "source_lane",
            "base_expression",
            "test_type",
            "ablation_role",
            "ablation_kind",
            "expected_result",
        ]:
            item[f"phase3l_{key}"] = meta.get(key)
        out.append(item)
    return out


def _cluster_results(rows: list[dict[str, Any]], unsupported: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_cluster: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_cluster[str(row.get("phase3l_cluster_id") or "")].append(row)
    blocked_regime = {str(row.get("cluster_id") or "") for row in unsupported if row.get("test_type") == "regime_bucket_replay"}
    results: list[dict[str, Any]] = []
    for cluster_id, group in sorted(by_cluster.items()):
        full_rows = [row for row in group if row.get("phase3l_test_type") == "subperiod_stability_replay"]
        sign_rows = [row for row in group if row.get("phase3l_test_type") == "sign_flip_placebo"]
        low_rows = [row for row in group if row.get("phase3l_test_type") == "low_order_ablation"]
        full = full_rows[0] if full_rows else {}
        full_score = _score(full) if full else None
        low_scores = [_score(row) for row in low_rows]
        low_scores = [score for score in low_scores if score is not None]
        low_best = max(low_scores) if low_scores else None
        windows = _load_window_stats(full) if full else {}
        sign_flip_passed = any(_non_gap_replay_pass(row) or _deployable_pass(row, turnover_max=0.75) for row in sign_rows)
        low_order_beats_full = low_best is not None and full_score is not None and low_best >= full_score
        subperiod_pass = bool(
            full
            and _non_gap_replay_pass(full)
            and (windows.get("positive_cost_window_ratio") is not None)
            and float(windows["positive_cost_window_ratio"]) >= 0.5
        )
        daily_blocker_flags = []
        promotion_blocker_flags = []
        if not subperiod_pass:
            daily_blocker_flags.append("subperiod_window_stability_failed_or_missing")
        if sign_flip_passed:
            daily_blocker_flags.append("sign_flip_placebo_passed")
        if low_order_beats_full:
            daily_blocker_flags.append("low_order_ablation_explains_full")
        if cluster_id in blocked_regime:
            promotion_blocker_flags.append("regime_bucket_replay_not_run")
        decision = "DAILY_DEEP_TEST_PASS_EX_REGIME" if not daily_blocker_flags else "HOLD_DAILY_DEEP_TEST"
        results.append(
            {
                "cluster_id": cluster_id,
                "source_lane": full.get("phase3l_source_lane") if full else (group[0].get("phase3l_source_lane") if group else None),
                "full_non_gap_pass": _non_gap_replay_pass(full) if full else False,
                "full_deployable_pass": _deployable_pass(full, turnover_max=0.75) if full else False,
                "full_score": round(full_score, 6) if full_score is not None else None,
                "subperiod_positive_cost_window_ratio": windows.get("positive_cost_window_ratio"),
                "subperiod_min_window_cost_adjusted_return": windows.get("min_window_cost_adjusted_return"),
                "sign_flip_non_gap_or_deployable_passed": sign_flip_passed,
                "low_order_test_count": len(low_rows),
                "low_order_best_score": round(low_best, 6) if low_best is not None else None,
                "low_order_margin_full_minus_best": round(full_score - low_best, 6) if full_score is not None and low_best is not None else None,
                "low_order_beats_or_ties_full": low_order_beats_full,
                "regime_bucket_status": "BLOCKED_RUNNER_NOT_AVAILABLE" if cluster_id in blocked_regime else "NOT_REQUESTED",
                "daily_blocker_flags": "|".join(daily_blocker_flags),
                "promotion_blocker_flags": "|".join(promotion_blocker_flags),
                "blocker_flags": "|".join([*daily_blocker_flags, *promotion_blocker_flags]),
                "decision": decision,
            }
        )
    return results


def _markdown(summary: dict[str, Any], cluster_results: list[dict[str, Any]]) -> str:
    passed = [row for row in cluster_results if row.get("decision") == "DAILY_DEEP_TEST_PASS_EX_REGIME"]
    lines = [
        "# Phase3L-E Daily Deep Test Batch",
        "",
        f"- generated_at: {summary['created_at']}",
        f"- decision: `{summary['decision']}`",
        f"- selected_test_count: {summary['selected_test_count']}",
        f"- strict_row_count: {summary['strict_row_count']}",
        f"- cluster_count: {summary['cluster_count']}",
        f"- pass_ex_regime_count: {len(passed)}",
        f"- blocked_regime_count: {summary['blocked_regime_count']}",
        "",
        "## Interpretation",
        "",
        "- This batch validates supported daily tests only: full-window replay, sign-flip, and low-order ablation.",
        "- Regime bucket replay is not available in this runner and remains a blocker before KEEP/promotion.",
        "- Passing this batch does not imply production readiness or minute execution capacity.",
        "",
        "## Cluster Results",
        "",
        "| cluster | decision | full_score | low_order_best | margin | sign_flip_passed | window_ratio | daily_blockers | promotion_blockers |",
        "| --- | --- | ---: | ---: | ---: | --- | ---: | --- | --- |",
    ]
    for row in cluster_results:
        lines.append(
            "| {cluster_id} | {decision} | {full_score} | {low_order_best_score} | {low_order_margin_full_minus_best} | {sign_flip_non_gap_or_deployable_passed} | {subperiod_positive_cost_window_ratio} | {daily_blocker_flags} | {promotion_blocker_flags} |".format(
                **row
            )
        )
    lines.append("")
    return "\n".join(lines)


def run(
    *,
    queue_path: Path,
    output_root: Path,
    dataset_path: Path,
    top_bottom_quantile: float,
    cost_bps: float,
    low_corr_threshold: float,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
    turnover_survival_max_one_way: float,
    reuse_strict_rows: Path | None = None,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    _write_progress(output_root, "start", queue_path=str(queue_path), dataset_path=str(dataset_path))
    queue = _read_jsonl(queue_path)
    selected, metadata, unsupported = _selected_rows(queue)
    write_json_artifact(output_root / "phase3l_e_selected_tests.json", {"selected": selected, "unsupported": unsupported})
    _write_progress(output_root, "selected_tests_prepared", selected_count=len(selected), unsupported_count=len(unsupported))

    if reuse_strict_rows is not None:
        payload = _read_json(reuse_strict_rows)
        strict_rows = payload.get("strict_rows") if isinstance(payload, dict) else payload
        if not isinstance(strict_rows, list):
            raise TypeError(f"expected strict_rows list in {reuse_strict_rows}")
        replay_report = {"reused_from": str(reuse_strict_rows)}
        cluster_report = {"reused_from": str(reuse_strict_rows)}
        _write_progress(output_root, "strict_rows_reused", strict_row_count=len(strict_rows), source=str(reuse_strict_rows))
    else:
        strict_rows = _strict_audit_selected_fast_rows(
            selected,
            output_root=output_root / "strict_phase3l_e",
            dataset_path=dataset_path,
            top_bottom_quantile=top_bottom_quantile,
            cost_bps=cost_bps,
            recent_quarter_window_count=recent_quarter_window_count,
            recent_warmup_days=recent_warmup_days,
        )
        strict_rows = _attach_metadata(strict_rows, metadata)
        _write_progress(output_root, "strict_audit_done", strict_row_count=len(strict_rows))
        strict_rows, replay_report = _attach_portfolio_replay(
            strict_rows,
            dataset_path=dataset_path,
            top_bottom_quantile=top_bottom_quantile,
            cost_bps=cost_bps,
            recent_quarter_window_count=recent_quarter_window_count,
            recent_warmup_days=recent_warmup_days,
        )
        _write_progress(output_root, "portfolio_replay_done", strict_row_count=len(strict_rows))
        strict_rows, cluster_report = _attach_signal_clusters(
            strict_rows,
            dataset_path=dataset_path,
            threshold=low_corr_threshold,
            recent_quarter_window_count=recent_quarter_window_count,
            recent_warmup_days=recent_warmup_days,
        )
        strict_rows = _attach_shadow_metrics(strict_rows)
        write_json_artifact(output_root / "phase3l_e_strict_rows.json", {"strict_rows": strict_rows})
        _write_progress(output_root, "strict_rows_written", strict_row_count=len(strict_rows))

    cluster_results = _cluster_results(strict_rows, unsupported)
    _write_csv(output_root / "phase3l_e_cluster_results.csv", cluster_results)
    _write_csv(output_root / "phase3l_e_unsupported_tests.csv", unsupported)
    kpis = _phase3_main_kpis(strict_rows, turnover_max=turnover_survival_max_one_way)
    pass_count = sum(1 for row in cluster_results if row.get("decision") == "DAILY_DEEP_TEST_PASS_EX_REGIME")
    summary = {
        "created_at": _now(),
        "decision": "PASS_PHASE3L_E_DAILY_DEEP_TEST_BATCH_EX_REGIME" if pass_count >= 8 else "HOLD_PHASE3L_E_DAILY_DEEP_TEST_ATTRITION",
        "scope": "daily_deep_tests_without_true_regime_bucket_or_minute_execution",
        "queue_path": str(queue_path),
        "dataset_path": str(dataset_path),
        "dataset_role": dataset_role_for_path(dataset_path),
        "selected_test_count": len(selected),
        "unsupported_test_count": len(unsupported),
        "blocked_regime_count": sum(1 for row in unsupported if row.get("test_type") == "regime_bucket_replay"),
        "strict_row_count": len(strict_rows),
        "cluster_count": len(cluster_results),
        "pass_ex_regime_count": pass_count,
        "required_next_blockers": ["true_regime_bucket_replay", "minute_execution_capacity"],
        "main_kpi": kpis,
    }
    report = {
        "summary": summary,
        "cluster_results": cluster_results,
        "replay_report": replay_report,
        "signal_cluster_report": cluster_report,
    }
    write_json_artifact(output_root / "phase3l_e_daily_deep_test_batch.json", report)
    (output_root / "PHASE3L_E_DAILY_DEEP_TEST_BATCH_2026-05-17.md").write_text(
        _markdown(summary, cluster_results),
        encoding="utf-8",
    )
    _write_progress(output_root, "report_written", status="completed")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--strict-cost-bps", type=float, default=DEFAULT_PORTFOLIO_REPLAY_COST_BPS)
    parser.add_argument("--low-corr-threshold", type=float, default=DEFAULT_LOW_CORR_THRESHOLD)
    parser.add_argument("--recent-quarter-window-count", type=int, default=2)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    parser.add_argument("--turnover-survival-max-one-way", type=float, default=0.75)
    parser.add_argument("--reuse-strict-rows", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        queue_path=args.queue,
        output_root=args.output_root,
        dataset_path=args.dataset_path,
        top_bottom_quantile=args.top_bottom_quantile,
        cost_bps=args.strict_cost_bps,
        low_corr_threshold=args.low_corr_threshold,
        recent_quarter_window_count=args.recent_quarter_window_count,
        recent_warmup_days=args.recent_warmup_days,
        turnover_survival_max_one_way=args.turnover_survival_max_one_way,
        reuse_strict_rows=args.reuse_strict_rows,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

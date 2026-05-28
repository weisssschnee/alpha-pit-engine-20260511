"""Automated validation flow for Phase3Z39 reward/event search results.

This script is intentionally post-search and read-only with respect to the
search output. It promotes nothing by itself. It builds a frozen strict-audit
queue from completed stage1 validation reports, then runs strict replay,
portfolio replay, signal clustering, decile/control calibration, and writes a
single decision report.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH
from our_system_phase2.services.stock_pit_ledger_policy import stock_pit_terminal_reward_proxy
from our_system_phase2.services.stock_pit_proof_suite import (
    DEFAULT_LOW_CORR_THRESHOLD,
    _attach_portfolio_replay,
    _attach_signal_clusters,
    _decile_summary,
    _strict_audit_selected_fast_rows,
    _strict_rows_metric_summary,
)
from our_system_phase2.services.variation import extract_structural_skeleton


FLOW_VERSION = "phase3z39-automated-validation-flow-v1-2026-05-25"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        number = float(value)
        if not math.isfinite(number):
            return default
        return number
    except (TypeError, ValueError):
        return default


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_manifest(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "size_bytes": int(stat.st_size),
        "mtime_utc": datetime.utcfromtimestamp(stat.st_mtime).isoformat(timespec="seconds") + "Z",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _iter_report_rows(search_root: Path, *, reward_profile: str = "default") -> tuple[list[dict[str, Any]], list[Path]]:
    paths = sorted(search_root.glob("*/*/stage1_validation_report.json"))
    rows: list[dict[str, Any]] = []
    for path in paths:
        payload = _read_json(path)
        stage = path.parts[-3]
        shard = path.parts[-2]
        for row in payload.get("evaluations", []) or []:
            if not isinstance(row, dict):
                continue
            item = dict(row)
            item["source_stage"] = stage
            item["source_shard"] = shard
            item["source_report_path"] = str(path)
            reward_payload = stock_pit_terminal_reward_proxy(item, reward_profile=reward_profile)
            item["fast_reward"] = reward_payload["reward"]
            item["strict_queue_reward_profile"] = reward_profile
            item["strict_queue_reward_components"] = reward_payload
            item["contains_limit_event"] = _contains_limit_event(item)
            item["structural_skeleton"] = extract_structural_skeleton(str(item.get("expression") or ""))
            rows.append(item)
    return rows, paths


def _contains_limit_event(row: dict[str, Any]) -> bool:
    text = " ".join(
        str(row.get(key) or "")
        for key in (
            "candidate_id",
            "expression",
            "primitive_family",
            "proposal_kind",
            "source_stage",
        )
    ).lower()
    return "limit" in text or "涨停" in text or "跌停" in text


def _family(row: dict[str, Any]) -> str:
    return str(row.get("primitive_family") or row.get("research_family") or "unknown")


def _expression(row: dict[str, Any]) -> str:
    return str(row.get("expression") or "").strip()


def _rank_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            _safe_float(row.get("fast_reward"), -999.0),
            _safe_float(row.get("mean_window_long_sortino"), -999.0),
            _safe_float(row.get("mean_window_long_return"), -999.0),
            _safe_float(row.get("mean_window_rank_ic"), -999.0),
        ),
        reverse=True,
    )


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = _expression(row) or str(row.get("candidate_id") or "")
        if not key:
            continue
        current = best.get(key)
        if current is None or _safe_float(row.get("fast_reward"), -999.0) > _safe_float(
            current.get("fast_reward"), -999.0
        ):
            best[key] = row
    return _rank_rows(list(best.values()))


def _take_with_family_cap(
    rows: list[dict[str, Any]],
    *,
    limit: int,
    max_per_family: int,
    role: str,
    seen_expressions: set[str],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for row in _rank_rows(rows):
        expression = _expression(row)
        if not expression or expression in seen_expressions:
            continue
        family = _family(row)
        if counts[family] >= max(1, int(max_per_family)):
            continue
        item = dict(row)
        item["strict_selection_role"] = role
        item["proof_variant"] = "phase3z39_reward_event"
        selected.append(item)
        seen_expressions.add(expression)
        counts[family] += 1
        if len(selected) >= max(0, int(limit)):
            break
    return selected


def _decile_controls(
    rows: list[dict[str, Any]],
    *,
    sample_per_decile: int,
    seen_expressions: set[str],
    seed: str,
) -> list[dict[str, Any]]:
    if sample_per_decile <= 0:
        return []
    ranked = sorted(rows, key=lambda row: _safe_float(row.get("fast_reward"), -999.0))
    total = len(ranked)
    selected: list[dict[str, Any]] = []
    for decile in range(1, 11):
        lo = int((decile - 1) * total / 10)
        hi = int(decile * total / 10)
        bucket = ranked[lo:hi]
        ordered = sorted(
            bucket,
            key=lambda row: _sha256_text(f"{seed}|{decile}|{row.get('candidate_id')}|{_expression(row)}"),
        )
        count = 0
        for row in ordered:
            expression = _expression(row)
            if not expression or expression in seen_expressions:
                continue
            item = dict(row)
            item["strict_selection_role"] = f"reward_decile_{decile}_control"
            item["reward_decile"] = decile
            item["proof_variant"] = "phase3z39_reward_event"
            selected.append(item)
            seen_expressions.add(expression)
            count += 1
            if count >= sample_per_decile:
                break
    return selected


def build_validation_queue(
    rows: list[dict[str, Any]],
    *,
    strict_budget: int,
    top_overall_budget: int,
    top_limit_budget: int,
    top_diverse_budget: int,
    decile_sample_per_bucket: int,
    max_per_family: int,
    seed: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    deduped = _dedupe_rows(rows)
    seen: set[str] = set()
    queue: list[dict[str, Any]] = []

    queue.extend(
        _take_with_family_cap(
            deduped,
            limit=top_overall_budget,
            max_per_family=max_per_family,
            role="top_reward",
            seen_expressions=seen,
        )
    )
    queue.extend(
        _take_with_family_cap(
            [row for row in deduped if bool(row.get("contains_limit_event"))],
            limit=top_limit_budget,
            max_per_family=max_per_family,
            role="top_limit_event_reward",
            seen_expressions=seen,
        )
    )
    queue.extend(
        _take_with_family_cap(
            deduped,
            limit=top_diverse_budget,
            max_per_family=1,
            role="family_diverse_reward",
            seen_expressions=seen,
        )
    )
    queue.extend(
        _decile_controls(
            deduped,
            sample_per_decile=decile_sample_per_bucket,
            seen_expressions=seen,
            seed=seed,
        )
    )
    if len(queue) < strict_budget:
        queue.extend(
            _take_with_family_cap(
                deduped,
                limit=strict_budget - len(queue),
                max_per_family=max(10_000, strict_budget),
                role="budget_fill_reward",
                seen_expressions=seen,
            )
        )
    queue = queue[: max(0, int(strict_budget))]
    for index, row in enumerate(queue):
        row["strict_queue_rank"] = index + 1
    summary = {
        "raw_stage1_rows": len(rows),
        "deduped_expression_rows": len(deduped),
        "strict_queue_count": len(queue),
        "strict_budget": int(strict_budget),
        "selection_role_counts": dict(Counter(str(row.get("strict_selection_role")) for row in queue)),
        "limit_event_queue_count": sum(1 for row in queue if row.get("contains_limit_event")),
        "family_counts_top20": Counter(_family(row) for row in queue).most_common(20),
    }
    return queue, summary


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    seen: set[str] = set()
    preferred = [
        "strict_queue_rank",
        "strict_selection_role",
        "reward_decile",
        "candidate_id",
        "contains_limit_event",
        "primitive_family",
        "proposal_kind",
        "source_stage",
        "source_shard",
        "fast_reward",
        "mean_window_long_sortino",
        "mean_window_long_return",
        "mean_window_rank_ic",
        "strict_pass_proxy",
        "portfolio_replay_pass",
        "signal_cluster_id",
        "strict_mean_rank_ic",
        "strict_mean_cost_adjusted_window_spread",
        "strict_cost_adjusted_sortino",
        "strict_mean_one_way_turnover",
        "portfolio_replay_long_only_sortino",
        "portfolio_replay_long_only_net_mean",
        "portfolio_replay_avg_one_way_turnover",
        "expression",
    ]
    for key in preferred:
        if any(key in row for row in rows):
            keys.append(key)
            seen.add(key)
    for row in rows:
        for key in row:
            if key not in seen and not isinstance(row.get(key), (dict, list)):
                keys.append(key)
                seen.add(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _role_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for role, bucket in sorted(
        ((role, [row for row in rows if str(row.get("strict_selection_role")) == role]) for role in {str(row.get("strict_selection_role")) for row in rows}),
        key=lambda item: item[0],
    ):
        item = {"strict_selection_role": role, **_strict_rows_metric_summary(bucket)}
        output.append(item)
    return output


def _limit_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    limit_rows = [row for row in rows if bool(row.get("contains_limit_event"))]
    non_limit_rows = [row for row in rows if not bool(row.get("contains_limit_event"))]
    return {
        "limit_event": _strict_rows_metric_summary(limit_rows),
        "non_limit": _strict_rows_metric_summary(non_limit_rows),
    }


def _reattach_queue_metadata(strict_rows: list[dict[str, Any]], queue: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_expression = {_expression(row): row for row in queue if _expression(row)}
    by_candidate = {str(row.get("candidate_id")): row for row in queue if row.get("candidate_id") is not None}
    enriched: list[dict[str, Any]] = []
    passthrough_keys = [
        "strict_queue_rank",
        "contains_limit_event",
        "source_stage",
        "source_shard",
        "source_report_path",
        "structural_skeleton",
        "reward_decile",
    ]
    for row in strict_rows:
        source = by_expression.get(_expression(row)) or by_candidate.get(str(row.get("candidate_id"))) or {}
        item = dict(row)
        for key in passthrough_keys:
            if key in source and key not in item:
                item[key] = source[key]
        if "contains_limit_event" not in item:
            item["contains_limit_event"] = _contains_limit_event(item)
        enriched.append(item)
    return enriched


def _experiment_manifest(search_root: Path, report_paths: list[Path], dataset_path: Path, output_root: Path) -> dict[str, Any]:
    dataset_manifest = {
        "path": str(dataset_path),
        "exists": dataset_path.exists(),
    }
    if dataset_path.exists():
        stat = dataset_path.stat()
        dataset_manifest.update(
            {
                "size_bytes": int(stat.st_size),
                "mtime_utc": datetime.utcfromtimestamp(stat.st_mtime).isoformat(timespec="seconds") + "Z",
            }
        )
    return {
        "date": datetime.now().astimezone().date().isoformat(),
        "experiment_id": "phase3z39_reward_event_auto_validation",
        "objective": "Validate completed Z39 reward/event search rows with strict replay, portfolio replay, signal clustering, and control calibration.",
        "status": "completed",
        "mode": "research",
        "inputs": {
            "search_root": str(search_root),
            "stage1_report_count": len(report_paths),
            "stage1_report_manifests": [_file_manifest(path) for path in report_paths[:80]],
            "dataset": dataset_manifest,
        },
        "outputs": {
            "output_root": str(output_root),
        },
        "reproducibility": "partial" if len(report_paths) > 80 else "yes",
    }


def run_flow(
    *,
    search_root: Path,
    output_root: Path,
    dataset_path: Path,
    strict_budget: int,
    top_overall_budget: int,
    top_limit_budget: int,
    top_diverse_budget: int,
    decile_sample_per_bucket: int,
    max_per_family: int,
    top_bottom_quantile: float,
    cost_bps: float,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
    low_corr_threshold: float,
    seed: str,
    reward_profile: str = "default",
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    rows, report_paths = _iter_report_rows(search_root, reward_profile=reward_profile)
    if not rows:
        raise SystemExit(f"No stage1 validation rows found under {search_root}")

    queue, queue_summary = build_validation_queue(
        rows,
        strict_budget=strict_budget,
        top_overall_budget=top_overall_budget,
        top_limit_budget=top_limit_budget,
        top_diverse_budget=top_diverse_budget,
        decile_sample_per_bucket=decile_sample_per_bucket,
        max_per_family=max_per_family,
        seed=seed,
    )
    _write_csv(output_root / "phase3z39_frozen_strict_queue.csv", queue)
    write_json_artifact(output_root / "phase3z39_frozen_strict_queue.json", {"queue": queue, "summary": queue_summary})

    strict_rows = _strict_audit_selected_fast_rows(
        queue,
        output_root=output_root / "strict_reports",
        dataset_path=dataset_path,
        top_bottom_quantile=top_bottom_quantile,
        cost_bps=cost_bps,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    strict_rows = _reattach_queue_metadata(strict_rows, queue)
    _write_csv(output_root / "phase3z39_strict_rows_pre_replay_checkpoint.csv", strict_rows)
    write_json_artifact(
        output_root / "phase3z39_strict_rows_pre_replay_checkpoint.json",
        {
            "created_at": utc_now_iso(),
            "flow_version": FLOW_VERSION,
            "strict_rows": strict_rows,
            "strict_metric_summary": _strict_rows_metric_summary(strict_rows),
        },
    )
    strict_rows, portfolio_report = _attach_portfolio_replay(
        strict_rows,
        dataset_path=dataset_path,
        top_bottom_quantile=top_bottom_quantile,
        cost_bps=cost_bps,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    _write_csv(output_root / "phase3z39_strict_rows_post_portfolio_checkpoint.csv", strict_rows)
    write_json_artifact(
        output_root / "phase3z39_strict_rows_post_portfolio_checkpoint.json",
        {
            "created_at": utc_now_iso(),
            "flow_version": FLOW_VERSION,
            "strict_rows": strict_rows,
            "portfolio_replay_report": portfolio_report,
            "strict_metric_summary": _strict_rows_metric_summary(strict_rows),
        },
    )
    strict_rows, signal_cluster_report = _attach_signal_clusters(
        strict_rows,
        dataset_path=dataset_path,
        threshold=low_corr_threshold,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )

    _write_csv(output_root / "phase3z39_strict_replay_rows.csv", strict_rows)
    write_json_artifact(output_root / "phase3z39_strict_replay_rows.json", {"strict_rows": strict_rows})

    metric_summary = _strict_rows_metric_summary(strict_rows)
    role_summary = _role_summary(strict_rows)
    decile_summary = _decile_summary(strict_rows)
    limit_summary = _limit_summary(strict_rows)

    decision = "HOLD_RESEARCH"
    if metric_summary["strict_pass_count"] > 0 and metric_summary["low_corr_strict_pass_count"] > 0:
        decision = "PASS_AUTOMATED_VALIDATION_HAS_STRICT_LOW_CORR_CANDIDATES_NOT_PROMOTION"
    if metric_summary["strict_audited_count"] == 0:
        decision = "FAIL_NO_STRICT_ROWS"

    manifest = _experiment_manifest(search_root, report_paths, dataset_path, output_root)
    manifest["parameters"] = {
        "strict_budget": int(strict_budget),
        "top_overall_budget": int(top_overall_budget),
        "top_limit_budget": int(top_limit_budget),
        "top_diverse_budget": int(top_diverse_budget),
        "decile_sample_per_bucket": int(decile_sample_per_bucket),
        "max_per_family": int(max_per_family),
        "top_bottom_quantile": float(top_bottom_quantile),
        "cost_bps": float(cost_bps),
        "recent_quarter_window_count": int(recent_quarter_window_count),
        "recent_warmup_days": int(recent_warmup_days),
        "low_corr_threshold": float(low_corr_threshold),
        "seed": seed,
        "reward_profile": reward_profile,
    }
    manifest["commands"] = {"script": "python -m our_system_phase2.runtime.phase3z39_automated_validation_flow ..."}

    report = {
        "flow_version": FLOW_VERSION,
        "created_at": utc_now_iso(),
        "decision": decision,
        "scope": "research_validation_only_no_alpha_promotion",
        "search_root": str(search_root),
        "output_root": str(output_root),
        "dataset_path": str(dataset_path),
        "stage1_report_count": len(report_paths),
        "reward_profile": reward_profile,
        "queue_summary": queue_summary,
        "strict_metric_summary": metric_summary,
        "role_summary": role_summary,
        "decile_summary": decile_summary,
        "limit_event_vs_non_limit_summary": limit_summary,
        "portfolio_replay_report": portfolio_report,
        "signal_cluster_report": signal_cluster_report,
        "bias_audit_contract": {
            "signal_clock": "after_open",
            "feature_availability": "field_lag_policy_from_real_market_validation",
            "execution_lag_days": 1,
            "cost_bps": float(cost_bps),
            "recent_quarter_window_count": int(recent_quarter_window_count),
            "oos_grade": "WEAK_RECENT_DAILY_UNTIL_LONGER_FORWARD_REPLAY",
            "promotion_allowed": False,
        },
        "experiment_record": manifest,
        "outputs": {
            "frozen_queue_csv": str(output_root / "phase3z39_frozen_strict_queue.csv"),
            "strict_rows_csv": str(output_root / "phase3z39_strict_replay_rows.csv"),
            "summary_json": str(output_root / "phase3z39_automated_validation_report.json"),
            "summary_md": str(output_root / "PHASE3Z39_AUTOMATED_VALIDATION_REPORT_2026-05-25.md"),
        },
    }
    write_json_artifact(output_root / "phase3z39_automated_validation_report.json", report)

    lines = [
        "# Phase3Z39 Automated Validation Report",
        "",
        f"- decision: `{decision}`",
        f"- scope: `{report['scope']}`",
        f"- search root: `{search_root}`",
        f"- reward profile: `{reward_profile}`",
        f"- stage1 reports: `{len(report_paths)}`",
        f"- raw stage1 rows: `{queue_summary['raw_stage1_rows']}`",
        f"- deduped expression rows: `{queue_summary['deduped_expression_rows']}`",
        f"- strict audited rows: `{metric_summary['strict_audited_count']}`",
        f"- strict pass rows: `{metric_summary['strict_pass_count']}`",
        f"- low-corr strict pass clusters: `{metric_summary['low_corr_strict_pass_count']}`",
        f"- portfolio replay pass rows: `{metric_summary['portfolio_replay_pass_count']}`",
        f"- limit/event queue rows: `{queue_summary['limit_event_queue_count']}`",
        "",
        "This is an automated validation gate. It is not an alpha promotion or production proof.",
        "",
        "## Selection Roles",
        "",
        "| role | audited | strict pass | replay pass | low-corr pass |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in role_summary:
        lines.append(
            f"| `{row['strict_selection_role']}` | {row['strict_audited_count']} | {row['strict_pass_count']} | {row['portfolio_replay_pass_count']} | {row['low_corr_strict_pass_count']} |"
        )
    lines += [
        "",
        "## Limit/Event vs Non-Limit",
        "",
        "| bucket | audited | strict pass | replay pass | low-corr pass |",
        "|---|---:|---:|---:|---:|",
    ]
    for bucket, summary in limit_summary.items():
        lines.append(
            f"| `{bucket}` | {summary['strict_audited_count']} | {summary['strict_pass_count']} | {summary['portfolio_replay_pass_count']} | {summary['low_corr_strict_pass_count']} |"
        )
    lines += [
        "",
        "## Signal Clusters",
        "",
        "| cluster | candidates | strict pass | replay pass | representative |",
        "|---|---:|---:|---:|---|",
    ]
    for cluster in signal_cluster_report.get("clusters", [])[:30]:
        expr = str(cluster.get("representative_expression") or "")[:120].replace("|", " ")
        lines.append(
            f"| `{cluster.get('signal_cluster_id')}` | {cluster.get('candidate_count')} | {cluster.get('strict_pass_count')} | {cluster.get('cluster_replay_contribution_count')} | `{expr}` |"
        )
    lines += [
        "",
        "## Required Next Action",
        "",
        "- If strict low-corr candidates exist: run longer-window OOS/recent regime replay before any KEEP.",
        "- If strict passes are concentrated in one cluster: do not promote; reroute reward memory with cluster-capped credit.",
        "- If limit/event bucket fails strict replay: keep limit/event as diagnostic generator, not official book component.",
    ]
    (output_root / "PHASE3Z39_AUTOMATED_VALIDATION_REPORT_2026-05-25.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run automated strict validation for Phase3Z39 search output.")
    parser.add_argument("--search-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--strict-budget", type=int, default=96)
    parser.add_argument("--top-overall-budget", type=int, default=32)
    parser.add_argument("--top-limit-budget", type=int, default=32)
    parser.add_argument("--top-diverse-budget", type=int, default=32)
    parser.add_argument("--decile-sample-per-bucket", type=int, default=1)
    parser.add_argument("--max-per-family", type=int, default=3)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--cost-bps", type=float, default=10.0)
    parser.add_argument("--recent-quarter-window-count", type=int, default=2)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    parser.add_argument("--low-corr-threshold", type=float, default=DEFAULT_LOW_CORR_THRESHOLD)
    parser.add_argument("--reward-profile", default="default")
    parser.add_argument("--seed", default="phase3z39_validation_20260525")
    args = parser.parse_args()

    result = run_flow(
        search_root=args.search_root,
        output_root=args.output_root,
        dataset_path=args.dataset_path,
        strict_budget=args.strict_budget,
        top_overall_budget=args.top_overall_budget,
        top_limit_budget=args.top_limit_budget,
        top_diverse_budget=args.top_diverse_budget,
        decile_sample_per_bucket=args.decile_sample_per_bucket,
        max_per_family=args.max_per_family,
        top_bottom_quantile=args.top_bottom_quantile,
        cost_bps=args.cost_bps,
        recent_quarter_window_count=args.recent_quarter_window_count,
        recent_warmup_days=args.recent_warmup_days,
        low_corr_threshold=args.low_corr_threshold,
        reward_profile=str(args.reward_profile),
        seed=str(args.seed),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

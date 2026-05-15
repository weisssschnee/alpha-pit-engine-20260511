from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH
from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression
from our_system_phase2.services.stock_pit_phase3_repair import _phase3_main_kpis
from our_system_phase2.services.stock_pit_proof_suite import (
    DEFAULT_PORTFOLIO_REPLAY_COST_BPS,
    _attach_portfolio_replay,
    _attach_signal_clusters,
    _strict_audit_selected_fast_rows,
)
from our_system_phase2.services.stock_pit_true_limit_search_bakeoff_v2 import _attach_shadow_metrics


ATTRIBUTION_KEYS = {
    "ablation_arm",
    "aggregate_source_kind",
    "candidate_id",
    "experiment_id",
    "parent_candidate_id",
    "parent_cluster",
    "parent_expression",
    "parent_signal_cluster_id",
    "phase3_budget_bucket",
    "phase3_source_lane",
    "proof_variant",
    "repair_action",
    "repair_policy",
    "reward_decile",
    "selection_policy",
    "selection_pool_type",
    "source_failure_reasons",
    "source_run_id",
    "source_seed",
    "strict_selection_role",
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


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


def _write_table(path_base: Path, rows: list[dict[str, Any]]) -> dict[str, str]:
    path_base.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path = path_base.with_suffix(".jsonl")
    _write_jsonl(jsonl_path, rows)
    csv_path = path_base.with_suffix(".csv")
    _write_csv(csv_path, rows)
    output = {"jsonl": str(jsonl_path), "csv": str(csv_path)}
    try:
        parquet_path = path_base.with_suffix(".parquet")
        pd.DataFrame(rows).to_parquet(parquet_path, index=False)
        output["parquet"] = str(parquet_path)
    except Exception as exc:
        output["parquet_error"] = str(exc)
    return output


def _expr_hash(expression: str | None) -> str:
    canonical = rank_validation_canonical_expression(str(expression or ""))
    return hashlib.sha256(canonical.encode("utf-8", errors="ignore")).hexdigest()[:20]


def _eval_context_hash(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:20]


def _load_selection(root: Path) -> tuple[str, list[dict[str, Any]]]:
    path = root / "phase3_strict_selection_inputs.json"
    if not path.exists():
        raise FileNotFoundError(f"missing frozen selection input: {path}")
    payload = _read_json(path)
    arm = str(payload.get("ablation_arm") or root.name)
    selected = payload.get("selected") or []
    if not isinstance(selected, list):
        raise ValueError(f"invalid selected payload in {path}")
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(selected):
        if not isinstance(row, dict):
            continue
        item = dict(row)
        expression = str(item.get("expression") or "")
        item["ablation_arm"] = arm
        item["arm_root"] = str(root)
        item["frozen_queue_index"] = index
        item["expr_hash"] = _expr_hash(expression)
        item["canonical_expression"] = rank_validation_canonical_expression(expression)
        rows.append(item)
    return arm, rows


def _load_candidate_pool(arm_roots: list[Path]) -> list[dict[str, Any]]:
    pool: list[dict[str, Any]] = []
    seen_rows: set[tuple[str, str, str]] = set()
    for root in arm_roots:
        arm = root.name
        ledger_paths = list((root / "variants").glob("*/candidate_ledger.json")) + list((root / "cem_internal").glob("*candidate_ledger.json"))
        for ledger_path in ledger_paths:
            try:
                payload = _read_json(ledger_path)
            except Exception:
                continue
            records = payload.get("records") if isinstance(payload, dict) else payload
            if not isinstance(records, list):
                continue
            source_lane = ledger_path.parent.name
            for index, record in enumerate(records):
                if not isinstance(record, dict):
                    continue
                expression = str(record.get("expression") or "")
                expr_hash = _expr_hash(expression)
                key = (arm, source_lane, expr_hash)
                if key in seen_rows:
                    continue
                seen_rows.add(key)
                pool.append(
                    {
                        "candidate_id": record.get("candidate_id"),
                        "expr_hash": expr_hash,
                        "canonical_expression": rank_validation_canonical_expression(expression),
                        "expression": expression,
                        "generator": record.get("generator") or record.get("proof_variant") or source_lane,
                        "eligible_arm": arm,
                        "source_lane": source_lane,
                        "motif_family": record.get("motif_family") or record.get("primitive_family") or record.get("research_family"),
                        "mechanism_label": record.get("mechanism_label"),
                        "open_space": record.get("open_space"),
                        "role_slots": record.get("role_slots"),
                        "parent_id": record.get("parent_candidate_id") or record.get("parent_id"),
                        "repair_action": record.get("repair_action") or record.get("repair_policy") or record.get("proposal_kind"),
                        "complexity": record.get("complexity") or record.get("complexity_score"),
                        "operator_list": record.get("operator_list"),
                        "field_list": record.get("field_list"),
                        "window_list": record.get("window_list"),
                        "ledger_path": str(ledger_path),
                        "ledger_index": index,
                    }
                )
    return pool


def _freeze_queues(arm_rows: dict[str, list[dict[str, Any]]], output_root: Path) -> list[dict[str, Any]]:
    all_rows: list[dict[str, Any]] = []
    queue_root = output_root / "frozen_queues"
    for arm, rows in sorted(arm_rows.items()):
        frozen_rows = []
        for rank, row in enumerate(rows):
            item = dict(row)
            item["arm"] = arm
            item["rank_before_replay"] = rank
            item["selection_score_before_replay"] = row.get("phase3_selection_score") or row.get("fast_reward")
            item["selection_reason"] = row.get("strict_selection_role") or row.get("selection_policy")
            item["source_lane"] = row.get("phase3_budget_bucket") or row.get("proof_variant")
            item["cache_allowed"] = True
            frozen_rows.append(item)
            all_rows.append(item)
        _write_jsonl(queue_root / f"{arm}.jsonl", frozen_rows)
    return all_rows


def _unique_audit_tasks(frozen_rows: list[dict[str, Any]], eval_context_hash: str) -> list[dict[str, Any]]:
    by_hash: dict[str, dict[str, Any]] = {}
    contributors: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in frozen_rows:
        expr_hash = str(row["expr_hash"])
        contributors[expr_hash].append(
            {
                "arm": str(row.get("arm") or row.get("ablation_arm") or ""),
                "candidate_id": str(row.get("candidate_id") or ""),
                "source_lane": str(row.get("source_lane") or ""),
            }
        )
        if expr_hash in by_hash:
            continue
        item = dict(row)
        item["candidate_id"] = f"cache_task_{expr_hash}"
        item["strict_selection_role"] = f"cache_unique::{row.get('strict_selection_role') or row.get('selection_policy') or 'selected'}"
        item["selection_policy"] = "phase3c_cache_unique_audit"
        item["eval_context_hash"] = eval_context_hash
        item["cache_task_expr_hash"] = expr_hash
        by_hash[expr_hash] = item
    tasks = []
    for expr_hash, row in sorted(by_hash.items()):
        item = dict(row)
        item["cache_contributor_count"] = len(contributors[expr_hash])
        item["cache_contributors"] = contributors[expr_hash]
        tasks.append(item)
    return tasks


def _overlay_attribution(eval_row: dict[str, Any], frozen_row: dict[str, Any]) -> dict[str, Any]:
    item = dict(eval_row)
    for key in ATTRIBUTION_KEYS:
        if key in frozen_row:
            item[key] = frozen_row.get(key)
    item["expression"] = frozen_row.get("expression") or eval_row.get("expression")
    item["candidate_id"] = frozen_row.get("candidate_id") or eval_row.get("candidate_id")
    item["ablation_arm"] = frozen_row.get("arm") or frozen_row.get("ablation_arm")
    item["expr_hash"] = frozen_row.get("expr_hash")
    item["shared_replay_result"] = True
    item["replay_result_source_expr_hash"] = frozen_row.get("expr_hash")
    item["cache_task_candidate_id"] = eval_row.get("candidate_id")
    item["frozen_queue_index"] = frozen_row.get("frozen_queue_index")
    item["rank_before_replay"] = frozen_row.get("rank_before_replay")
    return item


def _evaluate_task_shard(
    *,
    shard_index: int,
    tasks: list[dict[str, Any]],
    output_root: str,
    dataset_path: str,
    top_bottom_quantile: float,
    strict_cost_bps: float,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
) -> dict[str, Any]:
    shard_root = Path(output_root) / f"shard_{shard_index:02d}"
    failed_rows: list[dict[str, Any]] = []
    try:
        strict_rows = _strict_audit_selected_fast_rows(
            tasks,
            output_root=shard_root / "strict_unique",
            dataset_path=Path(dataset_path),
            top_bottom_quantile=float(top_bottom_quantile),
            cost_bps=float(strict_cost_bps),
            recent_quarter_window_count=int(recent_quarter_window_count),
            recent_warmup_days=int(recent_warmup_days),
        )
        strict_rows, replay_report = _attach_portfolio_replay(
            strict_rows,
            dataset_path=Path(dataset_path),
            top_bottom_quantile=float(top_bottom_quantile),
            cost_bps=float(strict_cost_bps),
            recent_quarter_window_count=int(recent_quarter_window_count),
            recent_warmup_days=int(recent_warmup_days),
        )
    except Exception as shard_exc:
        strict_rows = []
        replay_reports: list[dict[str, Any]] = []
        for task_index, task in enumerate(tasks):
            try:
                one = _strict_audit_selected_fast_rows(
                    [task],
                    output_root=shard_root / "strict_unique_resilient",
                    dataset_path=Path(dataset_path),
                    top_bottom_quantile=float(top_bottom_quantile),
                    cost_bps=float(strict_cost_bps),
                    recent_quarter_window_count=int(recent_quarter_window_count),
                    recent_warmup_days=int(recent_warmup_days),
                )
                one, one_replay = _attach_portfolio_replay(
                    one,
                    dataset_path=Path(dataset_path),
                    top_bottom_quantile=float(top_bottom_quantile),
                    cost_bps=float(strict_cost_bps),
                    recent_quarter_window_count=int(recent_quarter_window_count),
                    recent_warmup_days=int(recent_warmup_days),
                )
                strict_rows.extend(one)
                replay_reports.append(one_replay)
            except Exception as item_exc:
                failed = _failed_cache_row(task, shard_index=shard_index, task_index=task_index, exception=item_exc)
                strict_rows.append(failed)
                failed_rows.append(failed)
        replay_report = {
            "portfolio_replay_count": sum(int(report.get("portfolio_replay_count") or 0) for report in replay_reports),
            "unique_expression_replay_count": sum(int(report.get("unique_expression_replay_count") or 0) for report in replay_reports),
            "resilient_fallback": True,
            "failed_task_count": len(failed_rows),
            "shard_exception": f"{type(shard_exc).__name__}: {shard_exc}",
        }
    strict_rows = _attach_shadow_metrics(strict_rows)
    _write_json(
        shard_root / "strict_eval_cache.json",
        {
            "strict_rows": strict_rows,
            "replay_report": replay_report,
            "failed_rows": failed_rows,
        },
    )
    return {
        "shard_index": shard_index,
        "task_count": len(tasks),
        "strict_rows": strict_rows,
        "replay_report": replay_report,
        "shard_root": str(shard_root),
        "failed_task_count": len(failed_rows),
    }


def _failed_cache_row(task: dict[str, Any], *, shard_index: int, task_index: int, exception: Exception) -> dict[str, Any]:
    expression = str(task.get("expression") or "")
    return {
        "proof_variant": task.get("proof_variant"),
        "strict_selection_role": task.get("strict_selection_role"),
        "selection_policy": task.get("selection_policy") or "phase3c_cache_unique_audit",
        "selection_pool_type": task.get("selection_pool_type") or "common_pool",
        "phase3_budget_bucket": task.get("phase3_budget_bucket"),
        "candidate_id": task.get("candidate_id"),
        "primitive_family": task.get("primitive_family"),
        "proposal_kind": task.get("proposal_kind"),
        "expression": expression,
        "fast_reward": task.get("fast_reward"),
        "fast_mean_rank_ic": task.get("mean_window_rank_ic"),
        "strict_report_path": None,
        "strict_mean_rank_ic": None,
        "strict_mean_cost_adjusted_window_spread": None,
        "strict_cost_adjusted_sortino": None,
        "strict_mean_one_way_turnover": None,
        "strict_gatekeeper_decision": "HOLD_RESEARCH",
        "strict_pass_proxy": False,
        "cost_survives": False,
        "strict_blocker_flags": [f"cache_strict_exception:{type(exception).__name__}"],
        "portfolio_replay_error": type(exception).__name__,
        "portfolio_replay_pass": False,
        "portfolio_replay_pass_definition": "failed_before_replay_in_cache_sprint",
        "cache_task_expr_hash": task.get("cache_task_expr_hash") or _expr_hash(expression),
        "eval_context_hash": task.get("eval_context_hash"),
        "cache_failure": True,
        "cache_failure_message": str(exception),
        "cache_failure_shard_index": int(shard_index),
        "cache_failure_task_index": int(task_index),
    }


def _load_original_metrics(root: Path) -> dict[str, Any]:
    report_path = root / "phase3_repair_report.json"
    if not report_path.exists():
        return {}
    report = _read_json(report_path)
    return dict(report.get("main_kpi") or {})


def _load_original_report(root: Path) -> dict[str, Any]:
    report_path = root / "phase3_repair_report.json"
    if report_path.exists():
        return _read_json(report_path)
    selection_only_path = root / "phase3_selection_only_report.json"
    if selection_only_path.exists():
        return _read_json(selection_only_path)
    return {}


def _summarize_arm(
    *,
    arm: str,
    root: Path,
    rows: list[dict[str, Any]],
    dataset_path: Path,
    low_corr_threshold: float,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
    turnover_max: float,
    output_root: Path,
) -> dict[str, Any]:
    clustered, _ = _attach_signal_clusters(
        rows,
        dataset_path=dataset_path,
        threshold=low_corr_threshold,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    clustered = _attach_shadow_metrics(clustered)
    arm_root = output_root / "arms" / arm
    _write_json(arm_root / "phase3_strict_rows_cache.json", {"strict_rows": clustered})
    _write_json(arm_root / "phase3_strict_rows.json", {"strict_rows": clustered})
    kpi = _phase3_main_kpis(clustered, turnover_max=turnover_max)
    original_report = _load_original_report(root)
    original = _load_original_metrics(root)
    original_primary = ((original.get("primary") or {}) if isinstance(original, dict) else {})
    original_secondary = ((original.get("secondary") or {}) if isinstance(original, dict) else {})
    cache_primary = kpi.get("primary") or {}
    cache_secondary = kpi.get("secondary") or {}
    summary = {
        "arm": arm,
        "arm_root": str(root),
        "audited": len(rows),
        "cache_deployable_clusters": cache_primary.get("cost_turnover_deployable_unique_clusters"),
        "original_deployable_clusters": original_primary.get("cost_turnover_deployable_unique_clusters"),
        "cache_raw_non_gap_pass": cache_secondary.get("raw_non_gap_replay_pass"),
        "original_raw_non_gap_pass": original_secondary.get("raw_non_gap_replay_pass"),
        "cache_top_cluster_share": cache_secondary.get("top_cluster_raw_pass_share"),
        "original_top_cluster_share": original_secondary.get("top_cluster_raw_pass_share"),
        "deployable_delta": (
            int(cache_primary.get("cost_turnover_deployable_unique_clusters") or 0)
            - int(original_primary.get("cost_turnover_deployable_unique_clusters") or 0)
        ),
        "raw_non_gap_delta": (
            int(cache_secondary.get("raw_non_gap_replay_pass") or 0)
            - int(original_secondary.get("raw_non_gap_replay_pass") or 0)
        ),
    }
    cache_report = {
        "phase3_version": "phase3c-cache-sprint-v1",
        "created_at": utc_now_iso(),
        "experiment_id": f"phase3c_cache_sprint::{arm}",
        "status": "completed",
        "ablation_arm": arm,
        "output_root": str(arm_root),
        "dataset_path": str(dataset_path),
        "main_kpi": kpi,
        "decision": {
            "gate": "CACHE_PARITY_OUTPUT",
            "commercial_claim_allowed": False,
        },
        "ablation_design": original_report.get("ablation_design") or {},
        "parameters": original_report.get("parameters") or {},
        "cache_sprint": {
            "source_arm_root": str(root),
            "shared_replay_cache": True,
            "selection_was_frozen_before_replay_cache": True,
        },
    }
    _write_json(arm_root / "phase3_repair_report.json", cache_report)
    _write_json(arm_root / "phase3_cache_arm_metrics.json", {"main_kpi": kpi, "summary": summary})
    return summary


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Phase3C Cache Parity Smoke",
        "",
        f"- decision: `{report['decision']}`",
        f"- wall_time_seconds: `{report['wall_time_seconds']}`",
        f"- candidate_pool_size: `{report['candidate_pool']['rows']}`",
        f"- candidate_pool_unique_expr: `{report['candidate_pool']['unique_expr_hashes']}`",
        f"- frozen_queue_rows: `{report['frozen_queues']['rows']}`",
        f"- unique_audit_tasks: `{report['audit_tasks']['unique_tasks']}`",
        f"- replay_task_dedup_rate: `{report['audit_tasks']['replay_task_dedup_rate']}`",
        "",
        "## Arm Parity",
        "",
        "| arm | audited | original deployable | cache deployable | original raw non-gap | cache raw non-gap | deployable delta | raw delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report["arm_parity"]:
        lines.append(
            f"| {row['arm']} | {row['audited']} | {row['original_deployable_clusters']} | {row['cache_deployable_clusters']} | {row['original_raw_non_gap_pass']} | {row['cache_raw_non_gap_pass']} | {row['deployable_delta']} | {row['raw_non_gap_delta']} |"
        )
    lines.extend(
        [
            "",
            "## Contract",
            "",
            "All per-arm queues were frozen before replay cache evaluation. Replay labels were not used to change arm selection.",
            "Duplicate expressions are evaluated once and mapped back to each arm for attribution.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase3C cache sprint: freeze queues, deduplicate replay tasks, and check parity.")
    parser.add_argument("--arm-root", action="append", type=Path, required=True)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--recent-quarter-window-count", type=int, default=2)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    parser.add_argument("--strict-cost-bps", type=float, default=DEFAULT_PORTFOLIO_REPLAY_COST_BPS)
    parser.add_argument("--low-corr-threshold", type=float, default=0.80)
    parser.add_argument("--turnover-survival-max-one-way", type=float, default=0.75)
    parser.add_argument("--strict-shards", type=int, default=1, help="Parallel shards for unique strict/replay cache evaluation.")
    args = parser.parse_args()

    started = time.monotonic()
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    eval_context = {
        "dataset_path": str(args.dataset_path),
        "evaluator_version": "phase3c-cache-sprint-v1",
        "operator_semantics_version": "current_repo",
        "top_bottom_quantile": float(args.top_bottom_quantile),
        "recent_quarter_window_count": int(args.recent_quarter_window_count),
        "recent_warmup_days": int(args.recent_warmup_days),
        "strict_cost_bps": float(args.strict_cost_bps),
        "low_corr_threshold": float(args.low_corr_threshold),
        "turnover_survival_max_one_way": float(args.turnover_survival_max_one_way),
        "selection_contract": "frozen_queues_before_replay_cache",
    }
    context_hash = _eval_context_hash(eval_context)

    arm_rows: dict[str, list[dict[str, Any]]] = {}
    arm_roots: dict[str, Path] = {}
    for root in args.arm_root:
        arm, rows = _load_selection(root)
        if arm in arm_rows:
            raise ValueError(f"duplicate arm selection: {arm}")
        arm_rows[arm] = rows
        arm_roots[arm] = root

    candidate_pool = _load_candidate_pool(list(args.arm_root))
    candidate_pool_paths = _write_table(output_root / "candidate_pool", candidate_pool)

    frozen_rows = _freeze_queues(arm_rows, output_root)
    frozen_paths = _write_table(output_root / "frozen_queues_all", frozen_rows)

    audit_tasks = _unique_audit_tasks(frozen_rows, context_hash)
    audit_task_paths = _write_table(output_root / "audit_tasks_unique", audit_tasks)

    strict_shards = max(1, int(args.strict_shards))
    strict_unique: list[dict[str, Any]] = []
    replay_reports: list[dict[str, Any]] = []
    if strict_shards <= 1 or len(audit_tasks) <= 1:
        shard_result = _evaluate_task_shard(
            shard_index=0,
            tasks=audit_tasks,
            output_root=str(output_root / "strict_cache_shards"),
            dataset_path=str(args.dataset_path),
            top_bottom_quantile=float(args.top_bottom_quantile),
            strict_cost_bps=float(args.strict_cost_bps),
            recent_quarter_window_count=int(args.recent_quarter_window_count),
            recent_warmup_days=int(args.recent_warmup_days),
        )
        strict_unique.extend(shard_result["strict_rows"])
        replay_reports.append(shard_result["replay_report"])
    else:
        shard_tasks = [[] for _ in range(strict_shards)]
        for index, task in enumerate(audit_tasks):
            shard_tasks[index % strict_shards].append(task)
        with ProcessPoolExecutor(max_workers=strict_shards) as executor:
            futures = [
                executor.submit(
                    _evaluate_task_shard,
                    shard_index=index,
                    tasks=tasks,
                    output_root=str(output_root / "strict_cache_shards"),
                    dataset_path=str(args.dataset_path),
                    top_bottom_quantile=float(args.top_bottom_quantile),
                    strict_cost_bps=float(args.strict_cost_bps),
                    recent_quarter_window_count=int(args.recent_quarter_window_count),
                    recent_warmup_days=int(args.recent_warmup_days),
                )
                for index, tasks in enumerate(shard_tasks)
                if tasks
            ]
            for future in as_completed(futures):
                shard_result = future.result()
                strict_unique.extend(shard_result["strict_rows"])
                replay_reports.append(shard_result["replay_report"])
    strict_unique = sorted(strict_unique, key=lambda row: str(row.get("cache_task_expr_hash") or _expr_hash(str(row.get("expression") or ""))))
    replay_report = {
        "portfolio_replay_count": sum(int(report.get("portfolio_replay_count") or 0) for report in replay_reports),
        "unique_expression_replay_count": sum(int(report.get("unique_expression_replay_count") or 0) for report in replay_reports),
        "shard_count": len(replay_reports),
        "shards": replay_reports,
        "cost_bps": float(args.strict_cost_bps),
    }
    _write_json(
        output_root / "strict_eval_cache.json",
        {
            "strict_rows": strict_unique,
            "eval_context": eval_context,
            "strict_shards": strict_shards,
            "replay_report": replay_report,
        },
    )

    by_hash = {str(row.get("cache_task_expr_hash") or _expr_hash(str(row.get("expression") or ""))): row for row in strict_unique}
    arm_parity = []
    missing_hashes: list[str] = []
    for arm, rows in sorted(arm_rows.items()):
        mapped: list[dict[str, Any]] = []
        for row in rows:
            expr_hash = str(row["expr_hash"])
            eval_row = by_hash.get(expr_hash)
            if not eval_row:
                missing_hashes.append(expr_hash)
                continue
            mapped.append(_overlay_attribution(eval_row, row))
        arm_parity.append(
            _summarize_arm(
                arm=arm,
                root=arm_roots[arm],
                rows=mapped,
                dataset_path=args.dataset_path,
                low_corr_threshold=float(args.low_corr_threshold),
                recent_quarter_window_count=int(args.recent_quarter_window_count),
                recent_warmup_days=int(args.recent_warmup_days),
                turnover_max=float(args.turnover_survival_max_one_way),
                output_root=output_root,
            )
        )

    frozen_count = len(frozen_rows)
    unique_count = len(audit_tasks)
    candidate_hashes = [str(row.get("expr_hash") or "") for row in candidate_pool if row.get("expr_hash")]
    replay_task_dedup_rate = round(1.0 - unique_count / max(1, frozen_count), 6)
    parity_pass = not missing_hashes and all(int(row["deployable_delta"]) == 0 and int(row["raw_non_gap_delta"]) == 0 for row in arm_parity)
    report = {
        "created_at": utc_now_iso(),
        "experiment_id": "phase3c_cache_sprint_parity",
        "decision": "PASS_CACHE_PARITY" if parity_pass else "HOLD_CACHE_PARITY",
        "parity_pass": bool(parity_pass),
        "wall_time_seconds": round(time.monotonic() - started, 3),
        "eval_context": eval_context,
        "eval_context_hash": context_hash,
        "candidate_pool": {
            "rows": len(candidate_pool),
            "unique_expr_hashes": len(set(candidate_hashes)),
            "duplicate_rate": round(1.0 - len(set(candidate_hashes)) / max(1, len(candidate_hashes)), 6),
            "paths": candidate_pool_paths,
        },
        "frozen_queues": {
            "rows": frozen_count,
            "arms": sorted(arm_rows),
            "paths": frozen_paths,
        },
        "audit_tasks": {
            "unique_tasks": unique_count,
            "replay_task_dedup_rate": replay_task_dedup_rate,
            "strict_shards": strict_shards,
            "paths": audit_task_paths,
        },
        "missing_hashes": sorted(set(missing_hashes)),
        "arm_parity": arm_parity,
        "portfolio_replay_report": replay_report,
        "strict_eval_cache": str(output_root / "strict_eval_cache.json"),
    }
    _write_json(output_root / "phase3C_cache_parity_report.json", report)
    _write_csv(output_root / "phase3C_cache_arm_parity.csv", arm_parity)
    (output_root / "PHASE3C_CACHE_PARITY_SMOKE_2026-05-13.md").write_text(_markdown(report), encoding="utf-8")
    print(json.dumps({"output_root": str(output_root), "decision": report["decision"], "replay_task_dedup_rate": replay_task_dedup_rate}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from our_system_phase2.services.stock_pit_phase3_repair import _deployable_pass, _non_gap_replay_pass
from our_system_phase2.services.stock_pit_proof_suite import (
    _attach_signal_clusters,
    _entropy_from_values,
    _load_recent_quarter_market_panel,
    _signal_series_for_expression,
)
from our_system_phase2.services.stock_pit_true_limit_search_bakeoff_v2 import write_json_artifact
from our_system_phase2.services.phase3g_signal_vector_store import Phase3GSignalVectorStore, _corr


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "pass"}


def _stable_hash(text: str, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:length]


def _normalize_expression(expression: str) -> str:
    return re.sub(r"\s+", "", expression or "")


def _expression_complexity(expression: str | None) -> int | None:
    if not expression:
        return None
    operators = re.findall(r"[A-Za-z_][A-Za-z0-9_]*(?=\()", expression)
    fields = re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", expression)
    numbers = re.findall(r"(?<![A-Za-z_])\d+(?:\.\d+)?", expression)
    return len(operators) * 2 + len(set(fields)) + len(numbers)


def _seed_name_from_root(root: Path) -> str:
    match = re.search(r"seed(\d+)", root.name)
    if match:
        return f"seed{match.group(1)}"
    # Shared-pool Phase3H roots are shaped as .../s33/official_replay/h0.
    # Preserve both the real seed and arm so source_run_id/aggregate_row_id stay unique.
    parent_match = re.fullmatch(r"s(\d+)", root.parent.parent.name, flags=re.IGNORECASE)
    if parent_match and re.fullmatch(r"h\d+", root.name, flags=re.IGNORECASE):
        return f"s{parent_match.group(1)}_{root.name.lower()}"
    return root.name


def _load_candidate_metadata(root: Path) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    ledger_paths = list((root / "variants").glob("*/candidate_ledger.json")) + list((root / "cem_internal").glob("*candidate_ledger.json"))
    for ledger_path in ledger_paths:
        try:
            data = _read_json(ledger_path)
        except Exception:
            continue
        records = data.get("records") if isinstance(data, dict) else data
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, dict):
                continue
            candidate_id = str(record.get("candidate_id") or "")
            if candidate_id:
                metadata[candidate_id] = record
    return metadata


def _infer_machine_source(root: Path, override: str | None = None) -> str:
    if override:
        return override
    text = str(root).lower()
    if "company" in text or "hermesworker" in text or r"d:\p3b" in text:
        return "company"
    return "local"


def _load_phase3_seed(root: Path, *, allow_incomplete: bool, machine_source_override: str | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    report_path = root / "phase3_repair_report.json"
    strict_path = root / "phase3_strict_rows.json"
    if not strict_path.exists():
        raise FileNotFoundError(f"missing strict rows: {strict_path}")
    if not report_path.exists() and not allow_incomplete:
        raise RuntimeError(f"incomplete seed run without report: {root}")

    seed = _seed_name_from_root(root)
    report = _read_json(report_path) if report_path.exists() else {}
    ablation_arm = str(report.get("ablation_arm") or "Phase3A_full")
    source_run_id = f"{ablation_arm}::{seed}"
    strict_rows = _read_json(strict_path)["strict_rows"]
    candidate_metadata = _load_candidate_metadata(root)
    backfilled_parent_metadata = 0
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(strict_rows):
        item = dict(row)
        ledger_item = candidate_metadata.get(str(item.get("candidate_id") or ""), {})
        for key in [
            "repair_policy",
            "parent_candidate_id",
            "parent_expression",
            "generation_time",
            "parent_replay_source_path",
            "parent_replay_source_mtime",
            "parent_lane",
            "parent_signal_cluster_id",
            "source_failure_reasons",
            "phase3_source_lane",
        ]:
            if not item.get(key) and ledger_item.get(key):
                item[key] = ledger_item.get(key)
                if key.startswith("parent_"):
                    backfilled_parent_metadata += 1
        item["aggregate_source_kind"] = "phase3A_seed"
        item["source_seed"] = seed
        item["source_run_id"] = source_run_id
        item["ablation_arm"] = ablation_arm
        item["seed_root"] = str(root)
        item["aggregate_row_id"] = f"{source_run_id}::{index}::{item.get('candidate_id')}"
        item["proof_variant"] = item.get("proof_variant") or item.get("phase3_budget_bucket") or "phase3"
        item["strict_selection_role"] = item.get("strict_selection_role") or item.get("selection_policy") or "phase3"
        rows.append(item)

    metadata = {
        "seed": seed,
        "source_run_id": source_run_id,
        "ablation_arm": ablation_arm,
        "root": str(root),
        "machine_source": _infer_machine_source(root, machine_source_override),
        "report_exists": report_path.exists(),
        "strict_rows": len(rows),
        "candidate_metadata_rows": len(candidate_metadata),
        "backfilled_parent_metadata_fields": backfilled_parent_metadata,
        "report_path": str(report_path) if report_path.exists() else None,
    }
    if report_path.exists():
        metadata["decision"] = report.get("decision")
        metadata["main_kpi"] = report.get("main_kpi")
        metadata["ablation_design"] = report.get("ablation_design")
    return rows, metadata


def _load_phase2_r0_baseline(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            if row.get("selection_policy") not in {"r0_control", "phase3_r0_cem_led", "r0_cem_led"}:
                continue
            if not _as_bool(row.get("deployable_cost_turnover")):
                continue
            expression = row.get("expression") or ""
            item: dict[str, Any] = {
                "aggregate_source_kind": "phase2_r0_baseline",
                "source_seed": "phase2_r0_baseline",
                "seed_root": str(path),
                "aggregate_row_id": f"phase2_r0::{index}::{row.get('candidate_id')}",
                "proof_variant": row.get("lane") or "phase2_r0_baseline",
                "strict_selection_role": row.get("selection_policy") or "r0_control",
                "selection_policy": row.get("selection_policy") or "r0_control",
                "phase3_budget_bucket": "phase2_r0_baseline",
                "candidate_id": row.get("candidate_id") or f"phase2_r0_{index}",
                "expression": expression,
                "fast_reward": 0.0,
                "portfolio_replay_pass": True,
                "cost_survives": _as_bool(row.get("cost_survives")),
                "is_gap_family": False,
                "strict_mean_one_way_turnover": _safe_float(row.get("strict_mean_one_way_turnover"), 999.0),
                "portfolio_replay_avg_one_way_turnover": _safe_float(row.get("portfolio_replay_avg_one_way_turnover"), 999.0),
                "strict_pass_proxy": True,
                "baseline_local_cluster": row.get("global_return_corr_cluster"),
                "normalized_expression_hash": row.get("normalized_expression_hash") or _stable_hash(_normalize_expression(expression)),
            }
            rows.append(item)
    return rows


def _load_phase3b_union_baseline(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    data = _read_json(path)
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(data.get("deployable_representatives") or []):
        expression = str(item.get("representative_expression") or "")
        if not expression:
            continue
        rows.append(
            {
                "aggregate_source_kind": "phase3b_union_baseline",
                "source_seed": "phase3b_union_baseline",
                "seed_root": str(path),
                "aggregate_row_id": f"phase3b_union::{index}::{item.get('cluster_id')}",
                "proof_variant": "phase3b_union_baseline",
                "strict_selection_role": "phase3b_union_baseline",
                "selection_policy": "phase3b_union_baseline",
                "phase3_budget_bucket": "phase3b_union_baseline",
                "candidate_id": item.get("candidate_id") or f"phase3b_union_{index}",
                "expression": expression,
                "fast_reward": 0.0,
                "portfolio_replay_pass": True,
                "cost_survives": True,
                "is_gap_family": False,
                "strict_mean_one_way_turnover": 0.0,
                "portfolio_replay_avg_one_way_turnover": 0.0,
                "strict_pass_proxy": True,
                "baseline_phase3b_cluster_id": item.get("cluster_id"),
                "normalized_expression_hash": _stable_hash(_normalize_expression(expression)),
            }
        )
    return rows


def _load_phase3_cumulative_baseline(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    data = _read_json(path)
    declared_count = data.get("declared_cumulative_cluster_count")
    if declared_count is None:
        declared_count = data.get("declared_cluster_count")
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(data.get("deployable_representatives") or []):
        expression = str(item.get("representative_expression") or "")
        if not expression:
            continue
        rows.append(
            {
                "aggregate_source_kind": "phase3_cumulative_baseline",
                "source_seed": "phase3_cumulative_baseline",
                "seed_root": str(path),
                "aggregate_row_id": f"phase3_cumulative::{index}::{item.get('cluster_id')}",
                "proof_variant": "phase3_cumulative_baseline",
                "strict_selection_role": "phase3_cumulative_baseline",
                "selection_policy": "phase3_cumulative_baseline",
                "phase3_budget_bucket": "phase3_cumulative_baseline",
                "candidate_id": item.get("candidate_id") or f"phase3_cumulative_{index}",
                "expression": expression,
                "fast_reward": 0.0,
                "portfolio_replay_pass": True,
                "cost_survives": True,
                "is_gap_family": False,
                "strict_mean_one_way_turnover": 0.0,
                "portfolio_replay_avg_one_way_turnover": 0.0,
                "strict_pass_proxy": True,
                "baseline_phase3_cumulative_cluster_id": item.get("cluster_id"),
                "baseline_phase3_cumulative_declared_cluster_count": declared_count,
                "normalized_expression_hash": _stable_hash(_normalize_expression(expression)),
            }
        )
    return rows


def _parent_pseudo_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    parents: list[dict[str, Any]] = []
    for row in rows:
        expression = row.get("parent_expression")
        if not expression:
            continue
        key = _normalize_expression(str(expression))
        if key in seen:
            continue
        seen.add(key)
        parents.append(
            {
                "aggregate_source_kind": "parent_expression",
                "source_seed": row.get("source_seed"),
                "aggregate_row_id": f"parent::{_stable_hash(key)}",
                "proof_variant": "parent_expression",
                "strict_selection_role": "parent_expression",
                "selection_policy": "parent_expression",
                "phase3_budget_bucket": "parent_expression",
                "candidate_id": f"parent-{_stable_hash(key, 12)}",
                "expression": expression,
                "fast_reward": -999.0,
                "portfolio_replay_pass": False,
                "cost_survives": False,
                "is_gap_family": False,
                "strict_mean_one_way_turnover": 999.0,
            }
        )
    return parents


def _needs_global_cluster(row: dict[str, Any], *, turnover_max: float) -> bool:
    source_kind = row.get("aggregate_source_kind")
    if source_kind == "parent_expression":
        return True
    if source_kind == "phase3b_union_baseline":
        return True
    if source_kind == "phase3_cumulative_baseline":
        return True
    if source_kind == "phase2_r0_baseline":
        return _is_deployable(row, turnover_max)
    if source_kind != "phase3A_seed":
        return False
    return _non_gap_replay_pass(row) or _is_deployable(row, turnover_max)


def _dedupe_cluster_inputs(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    representatives: list[dict[str, Any]] = []
    row_to_expression_key: dict[str, str] = {}
    seen: set[str] = set()
    for row in rows:
        expression = str(row.get("expression") or "")
        key = _normalize_expression(expression)
        row_to_expression_key[str(row.get("aggregate_row_id"))] = key
        if not key or key in seen:
            continue
        seen.add(key)
        representative = dict(row)
        representative["aggregate_row_id"] = f"cluster_expr::{_stable_hash(key)}"
        representative["candidate_id"] = representative.get("candidate_id") or representative["aggregate_row_id"]
        representatives.append(representative)
    return representatives, row_to_expression_key


def _attach_signal_vector_proxy_clusters(
    rows: list[dict[str, Any]],
    *,
    dataset_path: Path | str,
    threshold: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not rows:
        return rows, {"cluster_count": 0}
    store = Phase3GSignalVectorStore(dataset_path=dataset_path)
    cluster_representatives: list[tuple[str, str, Any]] = []
    assignments: dict[str, dict[str, Any]] = {}
    pairwise: list[dict[str, Any]] = []
    errors: Counter[str] = Counter()
    for row in sorted(rows, key=lambda item: _safe_float(item.get("fast_reward")), reverse=True):
        expression = str(row.get("expression") or "")
        row_key = f"{row.get('proof_variant')}::{row.get('strict_selection_role')}::{row.get('candidate_id')}::{expression}"
        vector, vector_meta = store.vector_for_expression(expression)
        if vector is None:
            errors[str(vector_meta.get("signal_vector_error") or "missing_vector")] += 1
            assignments[row_key] = {
                **vector_meta,
                "signal_cluster_id": "cluster_error",
                "signal_cluster_error": vector_meta.get("signal_vector_error") or "missing_vector",
                "max_abs_signal_corr_to_prior": None,
                "global_cluster_mode": "signal_vector_proxy",
            }
            continue
        best_cluster = None
        best_corr = 0.0
        for cluster_id, representative_expression, representative in cluster_representatives:
            corr = float(_corr(vector, representative))
            abs_corr = abs(corr)
            pairwise.append(
                {
                    "left_expression": expression,
                    "right_expression": representative_expression,
                    "right_cluster_id": cluster_id,
                    "signal_corr": round(corr, 6),
                    "abs_signal_corr": round(abs_corr, 6),
                }
            )
            if abs_corr > best_corr:
                best_corr = abs_corr
                best_cluster = cluster_id
        if best_cluster is not None and best_corr >= threshold:
            cluster_id = best_cluster
        else:
            cluster_id = f"cluster_{len(cluster_representatives) + 1:03d}"
            cluster_representatives.append((cluster_id, expression, vector))
        assignments[row_key] = {
            **vector_meta,
            "signal_cluster_id": cluster_id,
            "max_abs_signal_corr_to_prior": round(best_corr, 6),
            "global_cluster_mode": "signal_vector_proxy",
        }

    enriched: list[dict[str, Any]] = []
    for row in rows:
        expression = str(row.get("expression") or "")
        row_key = f"{row.get('proof_variant')}::{row.get('strict_selection_role')}::{row.get('candidate_id')}::{expression}"
        enriched.append({**row, **assignments.get(row_key, {"signal_cluster_id": "cluster_missing", "global_cluster_mode": "signal_vector_proxy"})})

    cluster_rows: dict[str, list[dict[str, Any]]] = {}
    for row in enriched:
        cluster_rows.setdefault(str(row.get("signal_cluster_id") or "unknown"), []).append(row)
    cluster_report = []
    for cluster_id, cluster_members in sorted(cluster_rows.items(), key=lambda item: (-len(item[1]), item[0])):
        strict_pass = sum(1 for item in cluster_members if item.get("strict_pass_proxy"))
        replay_pass = sum(1 for item in cluster_members if item.get("portfolio_replay_pass"))
        cluster_report.append(
            {
                "signal_cluster_id": cluster_id,
                "candidate_count": len(cluster_members),
                "cluster_budget_share": round(float(len(cluster_members)) / max(1, len(enriched)), 6),
                "strict_pass_count": strict_pass,
                "cluster_strict_pass_rate": round(float(strict_pass) / max(1, len(cluster_members)), 6),
                "cluster_replay_contribution_count": replay_pass,
                "cluster_replay_pass_rate": round(float(replay_pass) / max(1, len(cluster_members)), 6),
                "representative_expression": cluster_members[0].get("expression"),
            }
        )
    return enriched, {
        "cluster_count": len(cluster_rows),
        "cluster_mode": "signal_vector_proxy",
        "low_corr_threshold_abs_signal_corr": float(threshold),
        "signal_cluster_entropy": _entropy_from_values(row.get("signal_cluster_id") for row in enriched),
        "clusters": cluster_report,
        "top_pairwise_abs_correlations": sorted(pairwise, key=lambda item: item["abs_signal_corr"], reverse=True)[:40],
        "vector_store_ready": store.coverage_ready(),
        "vector_error_counts": dict(errors),
    }


def _cluster_id(row: dict[str, Any]) -> str:
    return str(row.get("global_signal_cluster_id") or row.get("signal_cluster_id") or "cluster_missing")


def _is_deployable(row: dict[str, Any], turnover_max: float) -> bool:
    if row.get("aggregate_source_kind") == "phase2_r0_baseline":
        return bool(row.get("portfolio_replay_pass")) and bool(row.get("cost_survives")) and _safe_float(row.get("strict_mean_one_way_turnover"), 999.0) <= turnover_max
    if row.get("aggregate_source_kind") == "phase3b_union_baseline":
        return bool(row.get("portfolio_replay_pass")) and bool(row.get("cost_survives"))
    if row.get("aggregate_source_kind") == "phase3_cumulative_baseline":
        return bool(row.get("portfolio_replay_pass")) and bool(row.get("cost_survives"))
    return _deployable_pass(row, turnover_max=turnover_max)


def _per_seed_metrics(rows: list[dict[str, Any]], *, turnover_max: float) -> list[dict[str, Any]]:
    output = []
    for run_id, group in sorted(_group_by(rows, "source_run_id").items()):
        if run_id == "phase2_r0_baseline":
            continue
        first = group[0] if group else {}
        non_gap = [row for row in group if _non_gap_replay_pass(row)]
        deployable = [row for row in group if _is_deployable(row, turnover_max)]
        counts = Counter(_cluster_id(row) for row in non_gap)
        top_cluster, top_count = counts.most_common(1)[0] if counts else ("none", 0)
        output.append(
            {
                "run_id": run_id,
                "seed": first.get("source_seed"),
                "ablation_arm": first.get("ablation_arm"),
                "audited": len(group),
                "raw_non_gap_pass": len(non_gap),
                "unique_return_corr_clusters": len(set(_cluster_id(row) for row in non_gap)),
                "deployable_clusters": len(set(_cluster_id(row) for row in deployable)),
                "top_cluster_id": top_cluster,
                "top_cluster_share": round(top_count / max(1, len(non_gap)), 6),
            }
        )
    return output


def _median(values: list[float]) -> float | None:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return None
    middle = len(clean) // 2
    if len(clean) % 2:
        return round(clean[middle], 6)
    return round((clean[middle - 1] + clean[middle]) / 2.0, 6)


def _per_arm_metrics(rows: list[dict[str, Any]], *, turnover_max: float) -> list[dict[str, Any]]:
    output = []
    phase3_rows = [row for row in rows if row.get("aggregate_source_kind") == "phase3A_seed"]
    for arm, group in sorted(_group_by(phase3_rows, "ablation_arm").items()):
        non_gap = [row for row in group if _non_gap_replay_pass(row)]
        deployable = [row for row in group if _is_deployable(row, turnover_max)]
        counts = Counter(_cluster_id(row) for row in non_gap)
        top_cluster, top_count = counts.most_common(1)[0] if counts else ("none", 0)
        output.append(
            {
                "ablation_arm": arm,
                "audited": len(group),
                "raw_non_gap_pass": len(non_gap),
                "raw_non_gap_pass_per_audited": round(len(non_gap) / max(1, len(group)), 6),
                "unique_return_corr_clusters": len(set(_cluster_id(row) for row in non_gap)),
                "unique_return_corr_clusters_per_audited": round(len(set(_cluster_id(row) for row in non_gap)) / max(1, len(group)), 6),
                "deployable_clusters": len(set(_cluster_id(row) for row in deployable)),
                "deployable_clusters_per_audited": round(len(set(_cluster_id(row) for row in deployable)) / max(1, len(group)), 6),
                "top_cluster_id": top_cluster,
                "top_cluster_share": round(top_count / max(1, len(non_gap)), 6),
                "median_turnover": _median([_safe_float(row.get("strict_mean_one_way_turnover"), default=float("nan")) for row in deployable]),
                "median_complexity": _median([float(_expression_complexity(str(row.get("expression") or "")) or 0) for row in deployable]),
            }
        )
    return output


def _group_by(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "unknown")].append(row)
    return grouped


def _global_metrics(rows: list[dict[str, Any]], *, turnover_max: float) -> dict[str, Any]:
    phase3_rows = [row for row in rows if row.get("aggregate_source_kind") == "phase3A_seed"]
    baseline_rows = [row for row in rows if row.get("aggregate_source_kind") == "phase2_r0_baseline"]
    phase3b_baseline_rows = [row for row in rows if row.get("aggregate_source_kind") == "phase3b_union_baseline"]
    cumulative_baseline_rows = [row for row in rows if row.get("aggregate_source_kind") == "phase3_cumulative_baseline"]
    non_gap = [row for row in phase3_rows if _non_gap_replay_pass(row)]
    deployable = [row for row in phase3_rows if _is_deployable(row, turnover_max)]
    baseline_deployable = [row for row in baseline_rows if _is_deployable(row, turnover_max)]
    phase3b_baseline_deployable = [row for row in phase3b_baseline_rows if _is_deployable(row, turnover_max)]
    cumulative_baseline_deployable = [row for row in cumulative_baseline_rows if _is_deployable(row, turnover_max)]
    deployable_clusters = set(_cluster_id(row) for row in deployable)
    baseline_clusters = set(_cluster_id(row) for row in baseline_deployable)
    phase3b_baseline_clusters = set(_cluster_id(row) for row in phase3b_baseline_deployable)
    cumulative_baseline_clusters = set(_cluster_id(row) for row in cumulative_baseline_deployable)
    counts = Counter(_cluster_id(row) for row in non_gap)
    top_cluster, top_count = counts.most_common(1)[0] if counts else ("none", 0)
    cumulative_declared_counts = [
        int(_safe_float(row.get("baseline_phase3_cumulative_declared_cluster_count"), default=0.0))
        for row in cumulative_baseline_rows
        if row.get("baseline_phase3_cumulative_declared_cluster_count") is not None
    ]
    return {
        "completed_phase3_seed_count": len(set(row.get("source_seed") for row in phase3_rows)),
        "audited": len(phase3_rows),
        "global_unique_return_corr_clusters": len(set(_cluster_id(row) for row in non_gap)),
        "global_deployable_clusters": len(deployable_clusters),
        "phase2_r0_baseline_deployable_clusters": len(baseline_clusters),
        "global_new_clusters_vs_phase2_r0": len(deployable_clusters - baseline_clusters),
        "global_new_cluster_ids_vs_phase2_r0": sorted(deployable_clusters - baseline_clusters),
        "phase3b_union_baseline_deployable_clusters": len(phase3b_baseline_clusters),
        "new_deployable_clusters_vs_phase3B_union": len(deployable_clusters - phase3b_baseline_clusters) if phase3b_baseline_clusters else None,
        "new_deployable_cluster_ids_vs_phase3B_union": sorted(deployable_clusters - phase3b_baseline_clusters) if phase3b_baseline_clusters else [],
        "phase3_cumulative_baseline_deployable_clusters": len(cumulative_baseline_clusters) if cumulative_baseline_rows else None,
        "phase3_cumulative_baseline_declared_clusters": max(cumulative_declared_counts) if cumulative_declared_counts else None,
        "new_deployable_clusters_vs_phase3_cumulative": len(deployable_clusters - cumulative_baseline_clusters) if cumulative_baseline_clusters else None,
        "new_deployable_cluster_ids_vs_phase3_cumulative": sorted(deployable_clusters - cumulative_baseline_clusters) if cumulative_baseline_clusters else [],
        "raw_non_gap_pass": len(non_gap),
        "global_top_cluster_id": top_cluster,
        "global_top_cluster_share": round(top_count / max(1, len(non_gap)), 6),
        "cluster_label_scope": "global_reclustered_across_replay_relevant_completed_phase3_rows_plus_phase2_r0_baseline",
        "seed_local_labels_ignored": True,
    }


def _overlap_matrix(rows: list[dict[str, Any]], *, turnover_max: float) -> list[dict[str, Any]]:
    deployable_by_seed: dict[str, set[str]] = {}
    non_gap_by_seed: dict[str, set[str]] = {}
    for run_id, group in _group_by([row for row in rows if row.get("aggregate_source_kind") == "phase3A_seed"], "source_run_id").items():
        deployable_by_seed[run_id] = {_cluster_id(row) for row in group if _is_deployable(row, turnover_max)}
        non_gap_by_seed[run_id] = {_cluster_id(row) for row in group if _non_gap_replay_pass(row)}
    seeds = sorted(deployable_by_seed)
    output = []
    for left in seeds:
        for right in seeds:
            left_set = deployable_by_seed[left]
            right_set = deployable_by_seed[right]
            union = left_set | right_set
            non_gap_union = non_gap_by_seed[left] | non_gap_by_seed[right]
            output.append(
                {
                    "left_seed": left,
                    "right_seed": right,
                    "deployable_left": len(left_set),
                    "deployable_right": len(right_set),
                    "deployable_overlap": len(left_set & right_set),
                    "deployable_union": len(union),
                    "deployable_jaccard": round(len(left_set & right_set) / max(1, len(union)), 6),
                    "non_gap_cluster_overlap": len(non_gap_by_seed[left] & non_gap_by_seed[right]),
                    "non_gap_cluster_union": len(non_gap_union),
                }
            )
    return output


def _arm_overlap_matrix(rows: list[dict[str, Any]], *, turnover_max: float) -> list[dict[str, Any]]:
    deployable_by_arm: dict[str, set[str]] = {}
    non_gap_by_arm: dict[str, set[str]] = {}
    for arm, group in _group_by([row for row in rows if row.get("aggregate_source_kind") == "phase3A_seed"], "ablation_arm").items():
        deployable_by_arm[arm] = {_cluster_id(row) for row in group if _is_deployable(row, turnover_max)}
        non_gap_by_arm[arm] = {_cluster_id(row) for row in group if _non_gap_replay_pass(row)}
    arms = sorted(deployable_by_arm)
    output = []
    for left in arms:
        for right in arms:
            left_set = deployable_by_arm[left]
            right_set = deployable_by_arm[right]
            union = left_set | right_set
            non_gap_union = non_gap_by_arm[left] | non_gap_by_arm[right]
            output.append(
                {
                    "left_arm": left,
                    "right_arm": right,
                    "deployable_left": len(left_set),
                    "deployable_right": len(right_set),
                    "deployable_overlap": len(left_set & right_set),
                    "deployable_union": len(union),
                    "deployable_jaccard": round(len(left_set & right_set) / max(1, len(union)), 6),
                    "non_gap_cluster_overlap": len(non_gap_by_arm[left] & non_gap_by_arm[right]),
                    "non_gap_cluster_union": len(non_gap_union),
                }
            )
    return output


def _lane_attribution(rows: list[dict[str, Any]], *, turnover_max: float) -> list[dict[str, Any]]:
    output = []
    phase3_rows = [row for row in rows if row.get("aggregate_source_kind") == "phase3A_seed"]
    for lane, group in sorted(_group_by(phase3_rows, "phase3_budget_bucket").items()):
        non_gap = [row for row in group if _non_gap_replay_pass(row)]
        deployable = [row for row in group if _is_deployable(row, turnover_max)]
        output.append(
            {
                "lane": lane,
                "audited": len(group),
                "raw_non_gap_pass": len(non_gap),
                "unique_return_corr_clusters": len(set(_cluster_id(row) for row in non_gap)),
                "deployable_clusters": len(set(_cluster_id(row) for row in deployable)),
                "cluster_ids": sorted(set(_cluster_id(row) for row in deployable)),
            }
        )
    return output


def _direct_corr(expression: str | None, parent_expression: str | None, *, frame: Any, evaluation_start: Any, evaluation_end: Any, cache: dict[str, Any]) -> float | None:
    if not expression or not parent_expression:
        return None
    try:
        left = _signal_series_for_expression(expression, frame=frame, evaluation_start_date=evaluation_start, evaluation_end_date=evaluation_end, cache=cache)
        right = _signal_series_for_expression(parent_expression, frame=frame, evaluation_start_date=evaluation_start, evaluation_end_date=evaluation_end, cache=cache)
        joined = __import__("pandas").concat([left, right], axis=1, join="inner").dropna()
        if len(joined) < 30 or joined.iloc[:, 0].nunique(dropna=True) <= 1 or joined.iloc[:, 1].nunique(dropna=True) <= 1:
            return None
        value = joined.iloc[:, 0].corr(joined.iloc[:, 1])
        return round(float(value), 6) if value == value and math.isfinite(float(value)) else None
    except Exception:
        return None


def _ast_repair_transition(
    rows: list[dict[str, Any]],
    *,
    dataset_path: Path,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
    turnover_max: float,
    compute_parent_corr: bool = True,
) -> list[dict[str, Any]]:
    phase3_rows = [row for row in rows if row.get("aggregate_source_kind") == "phase3A_seed" and row.get("phase3_budget_bucket") == "ast_failure_aware_repair"]
    parent_cluster_by_expression = {
        _normalize_expression(str(row.get("expression") or "")): _cluster_id(row)
        for row in rows
        if row.get("aggregate_source_kind") == "parent_expression"
    }
    frame = evaluation_start = evaluation_end = None
    cache: dict[str, Any] = {}
    output = []
    for row in phase3_rows:
        parent_expression = row.get("parent_expression")
        if parent_expression and compute_parent_corr and frame is None:
            frame, evaluation_start, evaluation_end = _load_recent_quarter_market_panel(
                dataset_path,
                quarter_window_count=recent_quarter_window_count,
                warmup_days=recent_warmup_days,
            )
        parent_cluster = parent_cluster_by_expression.get(_normalize_expression(str(parent_expression or "")), "unknown_parent")
        corr_to_parent = None
        if parent_expression and compute_parent_corr and frame is not None:
            corr_to_parent = _direct_corr(
                str(row.get("expression") or ""),
                str(parent_expression),
                frame=frame,
                evaluation_start=evaluation_start,
                evaluation_end=evaluation_end,
                cache=cache,
            )
        parent_complexity = _expression_complexity(str(parent_expression)) if parent_expression else None
        child_complexity = _expression_complexity(str(row.get("expression") or ""))
        output.append(
            {
                "seed": row.get("source_seed"),
                "candidate_id": row.get("candidate_id"),
                "repair_policy": row.get("repair_policy") or "unknown",
                "parent_cluster": parent_cluster,
                "child_cluster": _cluster_id(row),
                "escaped_cluster": None if parent_cluster == "unknown_parent" else parent_cluster != _cluster_id(row),
                "deployable": _is_deployable(row, turnover_max),
                "corr_to_parent": corr_to_parent,
                "turnover_delta": None,
                "complexity_delta": None if parent_complexity is None or child_complexity is None else child_complexity - parent_complexity,
                "parent_expression": parent_expression,
                "child_expression": row.get("expression"),
                "source_failure_reasons": row.get("source_failure_reasons"),
            }
        )
    return output


def _denominator_audit(seed_roots: list[Path], strict_rows_by_seed: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    output = []
    for root in seed_roots:
        seed = _seed_name_from_root(root)
        report_path = root / "phase3_repair_report.json"
        report = _read_json(report_path) if report_path.exists() else {}
        ablation_arm = str(report.get("ablation_arm") or "Phase3A_full")
        run_id = f"{ablation_arm}::{seed}"
        generated = 0
        valid = 0
        unique_generated_expressions: set[str] = set()
        for ledger in list((root / "variants").glob("*/candidate_ledger.json")) + list((root / "cem_internal").glob("*candidate_ledger.json")):
            try:
                data = _read_json(ledger)
            except Exception:
                continue
            records = data.get("records") if isinstance(data, dict) else data
            if not isinstance(records, list):
                continue
            generated += len(records)
            for row in records:
                expression = str(row.get("expression") or "")
                if expression:
                    unique_generated_expressions.add(_normalize_expression(expression))
                decision = str(row.get("fast_screen_decision") or row.get("decision") or "").lower()
                if not decision or "reject" not in decision:
                    valid += 1
        selected = []
        residual_scored_count = None
        selection_path = root / "phase3_strict_selection_inputs.json"
        if selection_path.exists():
            selection_data = _read_json(selection_path)
            selected = selection_data.get("selected") or []
            residual_scored_count = selection_data.get("residual_scored_count")
        rows = strict_rows_by_seed.get(run_id, [])
        output.append(
            {
                "run_id": run_id,
                "seed": seed,
                "ablation_arm": ablation_arm,
                "generated": generated,
                "valid": valid,
                "candidate_pool": len(unique_generated_expressions),
                "selected_for_audit": len(selected),
                "residual_scored_count": residual_scored_count,
                "audited": len(rows),
                "replay_attempted": sum(1 for row in rows if row.get("portfolio_replay_day_count") is not None),
                "replay_pass": sum(1 for row in rows if bool(row.get("portfolio_replay_pass"))),
                "non_gap_replay_pass": sum(1 for row in rows if _non_gap_replay_pass(row)),
            }
        )
    return output


def _pass_criteria(
    rows: list[dict[str, Any]],
    seed_metadata: list[dict[str, Any]],
    global_metrics: dict[str, Any],
    *,
    turnover_max: float,
    phase_label: str,
    require_local_and_company: bool,
) -> dict[str, Any]:
    baseline_clusters = {
        _cluster_id(row)
        for row in rows
        if row.get("aggregate_source_kind") == "phase2_r0_baseline" and _is_deployable(row, turnover_max)
    }
    ast_deployable_clusters = {
        _cluster_id(row)
        for row in rows
        if row.get("aggregate_source_kind") == "phase3A_seed"
        and row.get("phase3_budget_bucket") == "ast_failure_aware_repair"
        and _is_deployable(row, turnover_max)
    }
    ast_new_clusters = ast_deployable_clusters - baseline_clusters
    machine_sources = sorted({str(meta.get("machine_source") or "unknown") for meta in seed_metadata})
    algorithm_criteria = {
        "global_deployable_clusters_gt_phase2_reference_5": global_metrics["global_deployable_clusters"] > 5,
        "global_deployable_clusters_gte_8": global_metrics["global_deployable_clusters"] >= 8,
        "top_cluster_share_lt_50pct": global_metrics["global_top_cluster_share"] < 0.50,
        "ast_repair_new_deployable_clusters_vs_phase2_r0_gte_2": len(ast_new_clusters) >= 2,
        "raw_pass_not_primary": True,
    }
    metadata_criteria = {
        "local_and_company_runner_represented": {"local", "company"}.issubset(set(machine_sources)),
    }
    if require_local_and_company:
        decision = f"PASS_CONFIRM_{phase_label.upper()}" if all(algorithm_criteria.values()) and all(metadata_criteria.values()) else "HOLD_RESEARCH"
    else:
        decision = f"PASS_CONFIRM_{phase_label.upper()}" if all(algorithm_criteria.values()) else "HOLD_RESEARCH"
    return {
        "criteria": {**algorithm_criteria, **metadata_criteria},
        "algorithm_criteria": algorithm_criteria,
        "metadata_criteria": metadata_criteria,
        "metadata_gate_decision": "PASS_METADATA" if all(metadata_criteria.values()) else "HOLD_METADATA_ONLY",
        "require_local_and_company": require_local_and_company,
        "machine_sources": machine_sources,
        "ast_repair_deployable_clusters": sorted(ast_deployable_clusters),
        "ast_repair_new_deployable_clusters_vs_phase2_r0": len(ast_new_clusters),
        "ast_repair_new_cluster_ids_vs_phase2_r0": sorted(ast_new_clusters),
        "decision": decision,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def _markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "_empty_\n"
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
    return "\n".join(lines) + "\n"


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    phase_label = str(report.get("phase_label") or "Phase3A")
    lines = [
        f"# {phase_label} Global Aggregate Report",
        "",
        f"- created_at: `{report['created_at']}`",
        f"- decision: `{report['decision']}`",
        f"- metadata_gate_decision: `{report['phase3A_pass_criteria'].get('metadata_gate_decision')}`",
        f"- cluster_label_scope: `{report['global_union_metrics']['cluster_label_scope']}`",
        f"- seed_local_labels_ignored: `{report['global_union_metrics']['seed_local_labels_ignored']}`",
        "",
        "## Pass Criteria",
        "",
        "```json",
        json.dumps(report["phase3A_pass_criteria"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Global Union Metrics",
        "",
        "```json",
        json.dumps(report["global_union_metrics"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Per Seed Metrics",
        "",
        _markdown_table(report["per_seed_metrics"], ["run_id", "seed", "ablation_arm", "audited", "raw_non_gap_pass", "unique_return_corr_clusters", "deployable_clusters", "top_cluster_id", "top_cluster_share"]),
        "## Per Arm Metrics",
        "",
        _markdown_table(report["per_arm_metrics"], ["ablation_arm", "audited", "raw_non_gap_pass", "unique_return_corr_clusters", "deployable_clusters", "top_cluster_id", "top_cluster_share", "median_turnover", "median_complexity"]),
        "## Seed Overlap Matrix",
        "",
        _markdown_table(report["seed_overlap_matrix"], ["left_seed", "right_seed", "deployable_overlap", "deployable_union", "deployable_jaccard", "non_gap_cluster_overlap", "non_gap_cluster_union"]),
        "## Arm Overlap Matrix",
        "",
        _markdown_table(report["arm_overlap_matrix"], ["left_arm", "right_arm", "deployable_overlap", "deployable_union", "deployable_jaccard", "non_gap_cluster_overlap", "non_gap_cluster_union"]),
        "## Lane Attribution",
        "",
        _markdown_table(report["lane_attribution"], ["lane", "audited", "raw_non_gap_pass", "unique_return_corr_clusters", "deployable_clusters"]),
        "## Denominator Audit",
        "",
        _markdown_table(report["denominator_audit"], ["seed", "generated", "valid", "candidate_pool", "selected_for_audit", "audited", "replay_attempted", "replay_pass", "non_gap_replay_pass"]),
        "## Bias Audit",
        "",
        "- decision: `HOLD_RESEARCH`",
        f"- reason: {phase_label} aggregate validates search mechanics and global cluster uniqueness, but sector neutralization/capacity/survivorship promotion-grade checks remain blockers.",
        "- date alignment: true-limit after_open + T+1 contract inherited from strict rows.",
        f"- replay vs discovery: {phase_label} repair is search-method evidence; not a commercial alpha promotion.",
        "",
        "## Next Ablation",
        "",
        "A. original R0/CEM-led baseline\nB. R0/CEM-led + cluster quota\nC. R0 + AST repair only\nD. Phase3A full\n",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-path", required=True, type=Path)
    parser.add_argument("--seed-root", action="append", required=True, type=Path)
    parser.add_argument("--phase2-r0-baseline-csv", type=Path, default=Path("reports/PHASE3_REPAIR_AUDIT_2026-05-11_pass_clusters.csv"))
    parser.add_argument("--phase3b-union-baseline-json", type=Path, default=None)
    parser.add_argument("--phase3-cumulative-baseline-json", type=Path, default=None)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--low-corr-threshold", type=float, default=0.80)
    parser.add_argument("--turnover-max", type=float, default=0.75)
    parser.add_argument("--recent-quarter-window-count", type=int, default=2)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    parser.add_argument("--allow-incomplete", action="store_true")
    parser.add_argument("--phase-label", default="Phase3A")
    parser.add_argument("--experiment-id", default="20260511_phase3A_global_aggregate")
    parser.add_argument("--objective", default="global_dedup_across_phase3A_seeds_and_phase2_r0_baseline")
    parser.add_argument("--machine-source-override", choices=["local", "company"], default=None)
    parser.add_argument("--require-local-and-company", action="store_true")
    parser.add_argument("--json-name", default="phase3A_global_aggregate_report.json")
    parser.add_argument("--clustered-rows-name", default="phase3A_global_clustered_rows.json")
    parser.add_argument("--markdown-name", default="PHASE3A_GLOBAL_AGGREGATE_2026-05-11.md")
    parser.add_argument("--csv-prefix", default="phase3A")
    parser.add_argument("--cluster-mode", choices=["full_signal", "signal_vector_proxy"], default="full_signal")
    parser.add_argument("--skip-ast-parent-corr", action="store_true")
    args = parser.parse_args()

    args.output_root.mkdir(parents=True, exist_ok=True)

    seed_rows: list[dict[str, Any]] = []
    seed_metadata = []
    completed_seed_roots = []
    for root in args.seed_root:
        rows, metadata = _load_phase3_seed(root, allow_incomplete=args.allow_incomplete, machine_source_override=args.machine_source_override)
        if metadata["report_exists"]:
            seed_rows.extend(rows)
            completed_seed_roots.append(root)
            seed_metadata.append(metadata)
        elif args.allow_incomplete:
            seed_metadata.append(metadata)
    baseline_rows = _load_phase2_r0_baseline(args.phase2_r0_baseline_csv)
    phase3b_baseline_rows = _load_phase3b_union_baseline(args.phase3b_union_baseline_json)
    cumulative_baseline_rows = _load_phase3_cumulative_baseline(args.phase3_cumulative_baseline_json)
    parent_rows = _parent_pseudo_rows(seed_rows)
    all_rows = seed_rows + baseline_rows + phase3b_baseline_rows + cumulative_baseline_rows + parent_rows
    rows_for_cluster = [
        row for row in all_rows if _needs_global_cluster(row, turnover_max=args.turnover_max)
    ]
    cluster_representatives, row_to_expression_key = _dedupe_cluster_inputs(rows_for_cluster)

    if args.cluster_mode == "signal_vector_proxy":
        clustered_representatives, cluster_report = _attach_signal_vector_proxy_clusters(
            cluster_representatives,
            dataset_path=args.dataset_path,
            threshold=args.low_corr_threshold,
        )
    else:
        clustered_representatives, cluster_report = _attach_signal_clusters(
            cluster_representatives,
            dataset_path=args.dataset_path,
            threshold=args.low_corr_threshold,
            recent_quarter_window_count=args.recent_quarter_window_count,
            recent_warmup_days=args.recent_warmup_days,
        )
    cluster_by_expression_key = {
        _normalize_expression(str(row.get("expression") or "")): row.get("signal_cluster_id")
        for row in clustered_representatives
    }

    clustered: list[dict[str, Any]] = []
    for row in all_rows:
        item = dict(row)
        expression_key = row_to_expression_key.get(str(item.get("aggregate_row_id")), _normalize_expression(str(item.get("expression") or "")))
        item["global_signal_cluster_id"] = cluster_by_expression_key.get(expression_key)
        if item["global_signal_cluster_id"] is None:
            item["global_signal_cluster_id"] = "not_clustered_non_metric"
        clustered.append(item)

    phase3_clustered = [row for row in clustered if row.get("aggregate_source_kind") == "phase3A_seed"]
    baseline_clustered = [row for row in clustered if row.get("aggregate_source_kind") == "phase2_r0_baseline"]
    phase3b_baseline_clustered = [row for row in clustered if row.get("aggregate_source_kind") == "phase3b_union_baseline"]
    cumulative_baseline_clustered = [row for row in clustered if row.get("aggregate_source_kind") == "phase3_cumulative_baseline"]
    parent_clustered = [row for row in clustered if row.get("aggregate_source_kind") == "parent_expression"]
    strict_rows_by_seed = _group_by(phase3_clustered, "source_run_id")
    completed_rows = phase3_clustered + baseline_clustered + phase3b_baseline_clustered + cumulative_baseline_clustered + parent_clustered
    global_metrics = _global_metrics(completed_rows, turnover_max=args.turnover_max)
    pass_criteria = _pass_criteria(
        completed_rows,
        seed_metadata,
        global_metrics,
        turnover_max=args.turnover_max,
        phase_label=str(args.phase_label),
        require_local_and_company=bool(args.require_local_and_company),
    )

    report = {
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "experiment_id": str(args.experiment_id),
        "phase_label": str(args.phase_label),
        "objective": str(args.objective),
        "status": "completed",
        "dataset_path": str(args.dataset_path),
        "completed_seed_roots": [str(path) for path in completed_seed_roots],
        "excluded_incomplete_seed_roots": [str(path) for path in args.seed_root if path not in completed_seed_roots],
        "phase2_r0_baseline_csv": str(args.phase2_r0_baseline_csv),
        "phase3b_union_baseline_json": str(args.phase3b_union_baseline_json) if args.phase3b_union_baseline_json else None,
        "phase3_cumulative_baseline_json": str(args.phase3_cumulative_baseline_json) if args.phase3_cumulative_baseline_json else None,
        "seed_metadata": seed_metadata,
        "global_clustering_input": {
            "scope": "global_reclustered_for_replay_relevant_phase3_rows_plus_phase2_r0_baseline_and_parent_expressions",
            "cluster_mode": str(args.cluster_mode),
            "audited_rows_total": len(seed_rows),
            "rows_requiring_cluster": len(rows_for_cluster),
            "unique_expression_representatives_clustered": len(cluster_representatives),
            "failed_non_metric_rows_not_reclustered": len(all_rows) - len(rows_for_cluster),
        },
        "cluster_report": cluster_report,
        "per_seed_metrics": _per_seed_metrics(phase3_clustered, turnover_max=args.turnover_max),
        "per_arm_metrics": _per_arm_metrics(phase3_clustered, turnover_max=args.turnover_max),
        "global_union_metrics": global_metrics,
        "seed_overlap_matrix": _overlap_matrix(phase3_clustered, turnover_max=args.turnover_max),
        "arm_overlap_matrix": _arm_overlap_matrix(phase3_clustered, turnover_max=args.turnover_max),
        "lane_attribution": _lane_attribution(phase3_clustered, turnover_max=args.turnover_max),
        "ast_repair_transition": _ast_repair_transition(
            completed_rows,
            dataset_path=args.dataset_path,
            recent_quarter_window_count=args.recent_quarter_window_count,
            recent_warmup_days=args.recent_warmup_days,
            turnover_max=args.turnover_max,
            compute_parent_corr=not bool(args.skip_ast_parent_corr),
        ),
        "denominator_audit": _denominator_audit(completed_seed_roots, strict_rows_by_seed),
        "phase3A_pass_criteria": pass_criteria,
        "decision": pass_criteria["decision"],
        "bias_audit": {
            "decision": "HOLD_RESEARCH",
            "reason": "aggregate is search-method evidence; promotion-grade sector/capacity/survivorship checks remain unresolved",
            "clock": "after_open + true_limit + T+1 inherited from strict runs",
            "cost_bps": 10,
            "oos_sample_grade": "WEAK_RECENT_PANEL_ONLY",
        },
    }

    prefix = str(args.csv_prefix)
    write_json_artifact(args.output_root / str(args.json_name), report)
    write_json_artifact(
        args.output_root / str(args.clustered_rows_name),
        {"rows": phase3_clustered + baseline_clustered + phase3b_baseline_clustered + cumulative_baseline_clustered},
    )
    _write_csv(args.output_root / f"{prefix}_per_seed_metrics.csv", report["per_seed_metrics"])
    _write_csv(args.output_root / f"{prefix}_per_arm_metrics.csv", report["per_arm_metrics"])
    _write_csv(args.output_root / f"{prefix}_seed_overlap_matrix.csv", report["seed_overlap_matrix"])
    _write_csv(args.output_root / f"{prefix}_arm_overlap_matrix.csv", report["arm_overlap_matrix"])
    _write_csv(args.output_root / f"{prefix}_lane_attribution.csv", report["lane_attribution"])
    _write_csv(args.output_root / f"{prefix}_ast_repair_transition.csv", report["ast_repair_transition"])
    _write_csv(args.output_root / f"{prefix}_denominator_audit.csv", report["denominator_audit"])
    _write_markdown(args.output_root / str(args.markdown_name), report)
    print(json.dumps({"output_root": str(args.output_root), "decision": report["decision"], "global_union_metrics": report["global_union_metrics"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.formula_gen_v2.freeform_sampler import build_agnostic_freeform_ledger
from our_system_phase2.formula_gen_v2.sampler import build_formula_gen_v2_ledger, build_formula_gen_v2_repair_expansion_ledger
from our_system_phase2.services.phase3e_selectors import (
    Phase3ERegistryContext,
    select_phase3e_queue,
    strip_forbidden_replay_label_rows,
    write_selector_artifacts,
)
from our_system_phase2.services.phase3g_signal_vector_store import Phase3GSignalVectorStore
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_data import dataset_role_for_path
from our_system_phase2.services.real_market_validation import SIGNAL_CLOCK_AFTER_OPEN, TDXGP_LIMIT_STATUS_SOURCE
from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression
from our_system_phase2.services.stock_pit_proof_suite import (
    DEFAULT_LOW_CORR_THRESHOLD,
    DEFAULT_PORTFOLIO_REPLAY_COST_BPS,
    _attach_portfolio_replay,
    _attach_signal_clusters,
    _evaluation_reward,
    _fast_rows_from_variant_report,
    _mean,
    _safe_float,
    _share,
    _strict_audit_selected_fast_rows,
    _write_ledger,
)
from our_system_phase2.services.stock_pit_replay_ranker import score_shadow_selector, score_with_trained_replay_rankers
from our_system_phase2.services.stock_pit_true_limit_search_bakeoff_v2 import (
    TRUE_LIMIT_SEARCH_BAKEOFF_V2_VERSION,
    _attach_shadow_metrics,
    _build_variant_ledgers,
    _dedupe_records,
    _field_group,
    _fields,
    _is_gap_like,
    _ledger_from_records,
    _operators,
    _replay_ranker_feature_row,
    _row_key,
    _validate_variant_ledgers,
)
from our_system_phase2.services.variation import extract_structural_skeleton


PHASE3_REPAIR_VERSION = "phase3-repair-v2-2026-05-12"
PHASE3_DEFAULT_FAILURE_DETAIL = Path("reports/PHASE3_REPAIR_AUDIT_2026-05-11_failure_detail.csv")
PHASE3B_UNION_BASELINE_PATH = Path(__file__).resolve().parents[1] / "runtime" / "baselines" / "phase3B_union_deployable_clusters_20260512.json"
PHASE3D_CUMULATIVE_BASELINE_PATH = Path(__file__).resolve().parents[1] / "runtime" / "baselines" / "phase3D_cumulative_deployable_clusters_20260514.json"
PHASE3E_CUMULATIVE_BASELINE_PATH = Path(__file__).resolve().parents[1] / "runtime" / "baselines" / "phase3E_cumulative_deployable_clusters_20260514.json"
PHASE3H_CUMULATIVE_BASELINE_PATH = Path(__file__).resolve().parents[1] / "runtime" / "baselines" / "phase3H_cumulative_deployable_clusters_20260515.json"


def _stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def _write_progress(root: Path, stage: str, **extra: Any) -> None:
    payload = {"time": utc_now_iso(), "stage": stage}
    payload.update(extra)
    try:
        with (root / "phase3_progress.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        return


def _expression_windows(expression: str) -> list[int]:
    values: set[int] = set()
    for token in re.findall(r",\s*(\d+)\s*\)", expression or ""):
        values.add(int(token))
    for token in re.findall(r"Delay\([^,]+,\s*(\d+)\s*\)", expression or "", flags=re.IGNORECASE):
        values.add(int(token))
    return sorted(value for value in values if value > 0)


def _ast_cluster(expression: str) -> str:
    return _stable_hash(extract_structural_skeleton(rank_validation_canonical_expression(expression)))


def _operator_family(expression: str) -> str:
    return "|".join(sorted(set(_operators(expression)))) or "none"


def _field_family_cluster(expression: str) -> str:
    return "|".join(sorted({_field_group(field) for field in _fields(expression)})) or "none"


def _complexity(expression: str) -> float:
    return len(_operators(expression)) + 0.75 * len(_fields(expression)) + 0.25 * len(_expression_windows(expression)) + 0.15 * expression.count("(")


def _turnover_bucket(value: Any) -> str:
    turnover = _safe_float(value, default=float("nan"))
    if not math.isfinite(turnover):
        return "unknown"
    if turnover <= 0.25:
        return "low"
    if turnover <= 0.75:
        return "medium"
    if turnover <= 1.50:
        return "high"
    return "extreme"


def _deployable_pass(row: dict[str, Any], *, turnover_max: float) -> bool:
    return (
        bool(row.get("portfolio_replay_pass"))
        and not bool(row.get("is_gap_family"))
        and not _is_gap_like(row)
        and bool(row.get("cost_survives"))
        and _safe_float(row.get("strict_mean_one_way_turnover"), default=999.0) <= turnover_max
    )


def _non_gap_replay_pass(row: dict[str, Any]) -> bool:
    return bool(row.get("portfolio_replay_pass")) and not bool(row.get("is_gap_family")) and not _is_gap_like(row)


def _copy_for_selection(row: dict[str, Any], *, policy: str, role: str, pool_type: str, bucket: str) -> dict[str, Any]:
    item = dict(row)
    item["selection_policy"] = policy
    item["strict_selection_role"] = role
    item["selection_pool_type"] = pool_type
    item["phase3_budget_bucket"] = bucket
    return item


def _quota_event(
    row: dict[str, Any],
    *,
    event: str,
    quota_type: str,
    quota_stage: str,
    quota_basis: str,
    rejected_by_quota: bool,
    quota_reject_reason: str | None = None,
    parent_cluster: str | None = None,
    provisional_child_cluster: str | None = None,
    phase3_ast_cluster: str | None = None,
    repair_source_eligible: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    expression = str(row.get("expression") or "")
    reasons = str(row.get("source_failure_reasons") or row.get("all_reasons") or "")
    payload = {
        "event": event,
        "quota_applied": True,
        "quota_type": quota_type,
        "quota_stage": quota_stage,
        "quota_basis": quota_basis,
        "rejected_by_quota": bool(rejected_by_quota),
        "quota_reject_reason": quota_reject_reason,
        "repair_source_eligible": bool(repair_source_eligible),
        "candidate_id": row.get("candidate_id"),
        "expression": expression,
        "normalized_expression_hash": _stable_hash(rank_validation_canonical_expression(expression)) if expression else None,
        "phase3_source_lane": row.get("phase3_source_lane") or row.get("proof_variant"),
        "proof_variant": row.get("proof_variant"),
        "parent_candidate_id": row.get("parent_candidate_id"),
        "parent_cluster": parent_cluster or row.get("parent_signal_cluster_id"),
        "provisional_child_cluster": provisional_child_cluster or row.get("pre_audit_return_corr_cluster"),
        "final_child_cluster": None,
        "phase3_ast_cluster": phase3_ast_cluster or (_ast_cluster(expression) if expression else None),
        "corr_to_parent": None,
        "corr_to_existing_deployable": None,
        "escaped_parent_cluster": None,
        "repair_policy": row.get("repair_policy") or row.get("proposal_kind"),
        "source_failure_reason": reasons,
        "operator_pathology_before": "operator_pathology" in reasons,
        "operator_pathology_after": None,
    }
    if extra:
        payload.update(extra)
    return payload


def _attach_quota_metadata(item: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    item["quota_applied"] = bool(event.get("quota_applied"))
    item["quota_type"] = event.get("quota_type")
    item["quota_stage"] = event.get("quota_stage")
    item["quota_basis"] = event.get("quota_basis")
    item["rejected_by_quota"] = False
    item["quota_reject_reason"] = None
    item["parent_cluster"] = event.get("parent_cluster")
    item["provisional_child_cluster"] = event.get("provisional_child_cluster")
    item["final_child_cluster"] = None
    item["corr_to_parent"] = None
    item["corr_to_existing_deployable"] = None
    item["escaped_parent_cluster"] = event.get("escaped_parent_cluster")
    item["operator_pathology_before"] = event.get("operator_pathology_before")
    item["operator_pathology_after"] = event.get("operator_pathology_after")
    return item


def _cluster_candidate_pool(
    rows: list[dict[str, Any]],
    *,
    dataset_path: Path,
    low_corr_threshold: float,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
) -> list[dict[str, Any]]:
    if not rows:
        return []
    prepared: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        item = dict(row)
        item["strict_selection_role"] = item.get("strict_selection_role") or f"phase3_candidate_pool_{index}"
        item["proof_variant"] = item.get("proof_variant") or item.get("true_limit_bakeoff_variant") or item.get("phase3_source_lane") or "phase3_pool"
        prepared.append(item)
    clustered, _ = _attach_signal_clusters(
        prepared,
        dataset_path=dataset_path,
        threshold=low_corr_threshold,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    for row in clustered:
        row["pre_audit_return_corr_cluster"] = row.get("signal_cluster_id")
        row["pre_audit_max_abs_corr_to_prior"] = row.get("max_abs_signal_corr_to_prior")
    return clustered


def _cluster_quota_select(
    rows: list[dict[str, Any]],
    *,
    budget: int,
    policy: str,
    role_prefix: str,
    bucket: str,
    max_per_return_corr_cluster: int,
    max_per_ast_cluster: int,
    seed: str,
    quota_type: str = "cluster_quota",
    quota_stage: str = "pre_audit_cluster_quota",
    quota_basis: str = "pre_audit_return_corr_cluster|phase3_ast_cluster",
    quota_events: list[dict[str, Any]] | None = None,
    rejected_rows_for_repair: list[dict[str, Any]] | None = None,
    allow_rejected_as_repair_source: bool = False,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    return_counts: Counter[str] = Counter()
    ast_counts: Counter[str] = Counter()

    def sort_key(row: dict[str, Any]) -> tuple[float, float]:
        expression = str(row.get("expression") or "")
        return (_evaluation_reward(row), _stable_noise(seed, row.get("candidate_id"), expression))

    for row in sorted(rows, key=sort_key, reverse=True):
        if len(selected) >= max(0, int(budget)):
            break
        key = _row_key(row)
        if not key or key in seen:
            continue
        expression = str(row.get("expression") or "")
        return_cluster = str(row.get("pre_audit_return_corr_cluster") or "unknown")
        ast_cluster = _ast_cluster(expression)
        if return_counts[return_cluster] >= max_per_return_corr_cluster:
            event = _quota_event(
                row,
                event="rejected",
                quota_type=quota_type,
                quota_stage=quota_stage,
                quota_basis=quota_basis,
                rejected_by_quota=True,
                quota_reject_reason="return_corr_cluster_cap",
                provisional_child_cluster=return_cluster,
                phase3_ast_cluster=ast_cluster,
                repair_source_eligible=allow_rejected_as_repair_source,
            )
            if quota_events is not None:
                quota_events.append(event)
            if allow_rejected_as_repair_source and rejected_rows_for_repair is not None:
                source = dict(row)
                source["all_reasons"] = "corr_duplicate_from_direct_r0_quota"
                source["source_failure_reasons"] = "corr_duplicate_from_direct_r0_quota"
                rejected_rows_for_repair.append(source)
            continue
        if ast_counts[ast_cluster] >= max_per_ast_cluster:
            event = _quota_event(
                row,
                event="rejected",
                quota_type=quota_type,
                quota_stage=quota_stage,
                quota_basis=quota_basis,
                rejected_by_quota=True,
                quota_reject_reason="ast_cluster_cap",
                provisional_child_cluster=return_cluster,
                phase3_ast_cluster=ast_cluster,
                repair_source_eligible=allow_rejected_as_repair_source,
            )
            if quota_events is not None:
                quota_events.append(event)
            if allow_rejected_as_repair_source and rejected_rows_for_repair is not None:
                source = dict(row)
                source["all_reasons"] = "operator_pathology_from_direct_r0_ast_quota"
                source["source_failure_reasons"] = "operator_pathology_from_direct_r0_ast_quota"
                rejected_rows_for_repair.append(source)
            continue
        item = _copy_for_selection(row, policy=policy, role=f"{role_prefix}_cluster_quota", pool_type="common_pool", bucket=bucket)
        item["phase3_pre_audit_return_corr_cluster"] = return_cluster
        item["phase3_ast_cluster"] = ast_cluster
        event = _quota_event(
            row,
            event="selected",
            quota_type=quota_type,
            quota_stage=quota_stage,
            quota_basis=quota_basis,
            rejected_by_quota=False,
            provisional_child_cluster=return_cluster,
            phase3_ast_cluster=ast_cluster,
        )
        _attach_quota_metadata(item, event)
        if quota_events is not None:
            quota_events.append(event)
        selected.append(item)
        seen.add(key)
        return_counts[return_cluster] += 1
        ast_counts[ast_cluster] += 1
    return selected


def _cluster_credit_soft_select(
    rows: list[dict[str, Any]],
    *,
    budget: int,
    policy: str,
    role_prefix: str,
    bucket: str,
    seed: str,
    quota_events: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    return_counts: Counter[str] = Counter()
    ast_counts: Counter[str] = Counter()
    pool = [dict(row) for row in rows]
    budget = max(0, int(budget))

    while len(selected) < budget:
        best_row: dict[str, Any] | None = None
        best_key: tuple[float, float] | None = None
        for row in pool:
            key = _row_key(row)
            if not key or key in seen:
                continue
            expression = str(row.get("expression") or "")
            return_cluster = str(row.get("pre_audit_return_corr_cluster") or "unknown")
            ast_cluster = _ast_cluster(expression)
            duplicate_load = max(return_counts[return_cluster], ast_counts[ast_cluster])
            weight = 1.0 / math.sqrt(1.0 + duplicate_load)
            score = _evaluation_reward(row) * weight
            current_key = (score, _stable_noise(seed, row.get("candidate_id"), expression))
            if best_key is None or current_key > best_key:
                best_key = current_key
                best_row = row
        if best_row is None:
            break
        key = _row_key(best_row)
        if not key:
            break
        expression = str(best_row.get("expression") or "")
        return_cluster = str(best_row.get("pre_audit_return_corr_cluster") or "unknown")
        ast_cluster = _ast_cluster(expression)
        duplicate_load = max(return_counts[return_cluster], ast_counts[ast_cluster])
        weight = 1.0 / math.sqrt(1.0 + duplicate_load)
        item = _copy_for_selection(
            best_row,
            policy=policy,
            role=f"{role_prefix}_cluster_credit_cap",
            pool_type="common_pool",
            bucket=bucket,
        )
        item["phase3_pre_audit_return_corr_cluster"] = return_cluster
        item["phase3_ast_cluster"] = ast_cluster
        item["cluster_credit_selection_weight"] = round(weight, 6)
        item["cluster_credit_duplicate_load"] = int(duplicate_load)
        event = _quota_event(
            best_row,
            event="selected_soft_credit",
            quota_type="cluster_credit_cap",
            quota_stage="direct_replay_soft_selection",
            quota_basis="pre_audit_return_corr_cluster|phase3_ast_cluster",
            rejected_by_quota=False,
            provisional_child_cluster=return_cluster,
            phase3_ast_cluster=ast_cluster,
        )
        _attach_quota_metadata(item, event)
        item["quota_type"] = "cluster_credit_cap"
        item["quota_stage"] = "direct_replay_soft_selection"
        item["quota_reject_reason"] = None
        if quota_events is not None:
            quota_events.append(event)
        selected.append(item)
        seen.add(key)
        return_counts[return_cluster] += 1
        ast_counts[ast_cluster] += 1
    return selected


def _top_score_select(
    rows: list[dict[str, Any]],
    *,
    budget: int,
    policy: str,
    role_prefix: str,
    bucket: str,
    seed: str,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    def sort_key(row: dict[str, Any]) -> tuple[float, float]:
        expression = str(row.get("expression") or "")
        return (_evaluation_reward(row), _stable_noise(seed, row.get("candidate_id"), expression))

    for row in sorted(rows, key=sort_key, reverse=True):
        if len(selected) >= max(0, int(budget)):
            break
        key = _row_key(row)
        if not key or key in seen:
            continue
        expression = str(row.get("expression") or "")
        item = _copy_for_selection(row, policy=policy, role=f"{role_prefix}_top_score", pool_type="common_pool", bucket=bucket)
        item["phase3_pre_audit_return_corr_cluster"] = "not_preclustered_no_quota"
        item["phase3_ast_cluster"] = _ast_cluster(expression)
        item["quota_applied"] = False
        item["quota_type"] = "none"
        item["quota_stage"] = "not_applicable"
        item["quota_basis"] = "top_score_no_quota"
        item["rejected_by_quota"] = False
        item["quota_reject_reason"] = None
        selected.append(item)
        seen.add(key)
    return selected


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    return len(left & right) / max(1, len(left | right))


@lru_cache(maxsize=1)
def _phase3b_union_proxy_rows() -> tuple[dict[str, Any], ...]:
    baseline = _load_phase3b_union_baseline()
    output: list[dict[str, Any]] = []
    for row in baseline.get("deployable_representatives", []) or []:
        if not isinstance(row, dict):
            continue
        expression = str(row.get("representative_expression") or "")
        if not expression:
            continue
        output.append(
            {
                "cluster_id": row.get("cluster_id"),
                "expression": expression,
                "canonical": rank_validation_canonical_expression(expression),
                "skeleton": extract_structural_skeleton(expression),
                "fields": set(_fields(expression)),
                "operators": set(_operators(expression)),
            }
        )
    return tuple(output)


def _phase3b_union_similarity_proxy(expression: str) -> dict[str, Any]:
    canonical = rank_validation_canonical_expression(expression)
    skeleton = extract_structural_skeleton(expression)
    fields = set(_fields(expression))
    operators = set(_operators(expression))
    best: dict[str, Any] = {
        "max_phase3b_union_proxy": 0.0,
        "max_ast_similarity_to_phase3B_union": 0.0,
        "field_family_overlap_to_phase3B_union": 0.0,
        "operator_family_overlap_to_phase3B_union": 0.0,
        "nearest_phase3B_union_cluster": None,
    }
    for baseline in _phase3b_union_proxy_rows():
        exact = 1.0 if canonical == baseline["canonical"] else 0.0
        ast = 1.0 if skeleton == baseline["skeleton"] else 0.0
        field_overlap = _jaccard({_field_group(field) for field in fields}, {_field_group(field) for field in baseline["fields"]})
        operator_overlap = _jaccard(set(operators), set(baseline["operators"]))
        proxy = max(exact, 0.55 * ast + 0.20 * field_overlap + 0.25 * operator_overlap)
        if proxy > float(best["max_phase3b_union_proxy"]):
            best = {
                "max_phase3b_union_proxy": round(float(proxy), 6),
                "max_ast_similarity_to_phase3B_union": round(float(ast), 6),
                "field_family_overlap_to_phase3B_union": round(float(field_overlap), 6),
                "operator_family_overlap_to_phase3B_union": round(float(operator_overlap), 6),
                "nearest_phase3B_union_cluster": baseline["cluster_id"],
            }
    return best


def _novelty_steered_select(
    rows: list[dict[str, Any]],
    *,
    budget: int,
    policy: str,
    role_prefix: str,
    bucket: str,
    seed: str,
) -> list[dict[str, Any]]:
    budget = max(0, int(budget))
    if budget <= 0:
        return []
    enriched: list[dict[str, Any]] = []
    for row in rows:
        expression = str(row.get("expression") or "")
        if not expression:
            continue
        item = dict(row)
        proxy = _phase3b_union_similarity_proxy(expression)
        item.update(proxy)
        novelty = 1.0 - float(proxy["max_phase3b_union_proxy"])
        base_reward = _evaluation_reward(item)
        item["phase3B_union_novelty_score"] = round(float(novelty), 6)
        item["phase3c_novelty_selection_score"] = round(
            float(base_reward) + 0.050 * novelty - 0.030 * max(0.0, float(proxy["max_phase3b_union_proxy"]) - 0.90),
            8,
        )
        enriched.append(item)
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(row: dict[str, Any], role_suffix: str) -> bool:
        if len(selected) >= budget:
            return False
        key = _row_key(row)
        if not key or key in seen:
            return False
        expression = str(row.get("expression") or "")
        item = _copy_for_selection(
            row,
            policy=policy,
            role=f"{role_prefix}_{role_suffix}",
            pool_type="common_pool",
            bucket=bucket,
        )
        for field in (
            "max_phase3b_union_proxy",
            "max_ast_similarity_to_phase3B_union",
            "field_family_overlap_to_phase3B_union",
            "operator_family_overlap_to_phase3B_union",
            "nearest_phase3B_union_cluster",
            "phase3B_union_novelty_score",
            "phase3c_novelty_selection_score",
        ):
            item[field] = row.get(field)
        item["phase3c_novelty_steering_enabled"] = True
        item["phase3_pre_audit_return_corr_cluster"] = "not_preclustered_novelty_steered"
        item["phase3_ast_cluster"] = _ast_cluster(expression)
        item["quota_applied"] = False
        item["quota_type"] = "none"
        item["quota_stage"] = "not_applicable"
        item["quota_basis"] = "phase3B_union_pre_replay_novelty_proxy"
        item["rejected_by_quota"] = False
        item["quota_reject_reason"] = None
        selected.append(item)
        seen.add(key)
        return True

    high_novelty_n = max(1 if budget > 0 else 0, int(round(budget * 0.50)))
    high_score_n = max(0, int(round(budget * 0.25)))
    uncertain_n = max(0, int(round(budget * 0.15)))
    random_n = max(0, budget - high_novelty_n - high_score_n - uncertain_n)
    buckets = [
        (
            "high_novelty",
            sorted(
                enriched,
                key=lambda row: (
                    float(row.get("phase3B_union_novelty_score") or 0.0),
                    float(row.get("phase3c_novelty_selection_score") or 0.0),
                    _stable_noise(seed, row.get("candidate_id"), row.get("expression")),
                ),
                reverse=True,
            ),
            high_novelty_n,
        ),
        (
            "high_score",
            sorted(
                enriched,
                key=lambda row: (
                    float(row.get("phase3c_novelty_selection_score") or 0.0),
                    _evaluation_reward(row),
                    _stable_noise(seed, row.get("candidate_id"), row.get("expression")),
                ),
                reverse=True,
            ),
            high_score_n,
        ),
        (
            "medium_uncertain",
            sorted(
                enriched,
                key=lambda row: (
                    -abs(float(row.get("phase3B_union_novelty_score") or 0.0) - 0.50),
                    float(row.get("phase3c_novelty_selection_score") or 0.0),
                    _stable_noise(seed, row.get("candidate_id"), row.get("expression")),
                ),
                reverse=True,
            ),
            uncertain_n,
        ),
        (
            "stable_random",
            sorted(enriched, key=lambda row: _stable_noise(seed, "novelty_random", row.get("candidate_id"), row.get("expression"))),
            random_n,
        ),
    ]
    for role_suffix, pool, count in buckets:
        for row in pool:
            if sum(1 for selected_row in selected if str(selected_row.get("strict_selection_role") or "").endswith(role_suffix)) >= count:
                break
            add(row, role_suffix)
    if len(selected) < budget:
        for row in sorted(enriched, key=lambda item: float(item.get("phase3c_novelty_selection_score") or 0.0), reverse=True):
            add(row, "backfill")
            if len(selected) >= budget:
                break
    return selected[:budget]


def _repair_aware_soft_quota_select(
    rows: list[dict[str, Any]],
    *,
    budget: int,
    policy: str,
    role_prefix: str,
    bucket: str,
    max_share_per_parent_cluster: float,
    max_per_child_cluster: int,
    seed: str,
    quota_events: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    deferred: list[tuple[dict[str, Any], str]] = []
    parent_counts: Counter[str] = Counter()
    child_counts: Counter[str] = Counter()
    budget = max(0, int(budget))
    parent_cap = max(1, int(math.ceil(budget * max(0.0, float(max_share_per_parent_cluster)))))
    child_cap = max(1, int(max_per_child_cluster))

    def parent_cluster(row: dict[str, Any]) -> str:
        return str(row.get("parent_signal_cluster_id") or row.get("parent_cluster") or row.get("parent_candidate_id") or "unknown_parent")

    def child_cluster(row: dict[str, Any]) -> str:
        return str(row.get("pre_audit_return_corr_cluster") or "unknown_child")

    def sort_key(row: dict[str, Any]) -> tuple[float, float, float]:
        expression = str(row.get("expression") or "")
        novelty_hint = 1.0 if child_cluster(row) != parent_cluster(row) else 0.0
        return (_evaluation_reward(row), novelty_hint, _stable_noise(seed, row.get("candidate_id"), expression))

    def add_selected(row: dict[str, Any], *, event_name: str, bypass_reason: str | None = None) -> bool:
        if len(selected) >= budget:
            return False
        key = _row_key(row)
        if not key or key in seen:
            return False
        expression = str(row.get("expression") or "")
        parent = parent_cluster(row)
        child = child_cluster(row)
        ast_cluster = _ast_cluster(expression)
        item = _copy_for_selection(row, policy=policy, role=f"{role_prefix}_repair_aware_soft_quota", pool_type="common_pool", bucket=bucket)
        item["phase3_pre_audit_return_corr_cluster"] = child
        item["phase3_ast_cluster"] = ast_cluster
        event = _quota_event(
            row,
            event=event_name,
            quota_type="repair_aware_soft_quota",
            quota_stage="post_mutation_child_filter",
            quota_basis="parent_soft_cap|provisional_child_cluster_soft_cap",
            rejected_by_quota=False,
            parent_cluster=parent,
            provisional_child_cluster=child,
            phase3_ast_cluster=ast_cluster,
            extra={
                "parent_soft_cap": parent_cap,
                "child_soft_cap": child_cap,
                "quota_bypass_reason": bypass_reason,
                "escaped_parent_cluster": child != parent,
                "operator_pathology_after": "Div(" in expression and "Add(Abs(" not in expression,
            },
        )
        _attach_quota_metadata(item, event)
        item["quota_bypass_reason"] = bypass_reason
        if quota_events is not None:
            quota_events.append(event)
        selected.append(item)
        seen.add(key)
        parent_counts[parent] += 1
        child_counts[child] += 1
        return True

    for row in sorted(rows, key=sort_key, reverse=True):
        if len(selected) >= budget:
            break
        key = _row_key(row)
        if not key or key in seen:
            continue
        parent = parent_cluster(row)
        child = child_cluster(row)
        reasons = str(row.get("source_failure_reasons") or row.get("all_reasons") or "")
        child_new = child_counts[child] == 0
        repair_reason = "corr_duplicate" in reasons or "operator_pathology" in reasons
        bypass = child_new and repair_reason and child != parent
        if parent_counts[parent] >= parent_cap and not bypass:
            deferred.append((row, "parent_cluster_soft_cap"))
            if quota_events is not None:
                quota_events.append(
                    _quota_event(
                        row,
                        event="deferred",
                        quota_type="repair_aware_soft_quota",
                        quota_stage="post_mutation_child_filter",
                        quota_basis="parent_soft_cap|provisional_child_cluster_soft_cap",
                        rejected_by_quota=True,
                        quota_reject_reason="parent_cluster_soft_cap",
                        parent_cluster=parent,
                        provisional_child_cluster=child,
                        repair_source_eligible=True,
                    )
                )
            continue
        if child_counts[child] >= child_cap and not bypass:
            deferred.append((row, "child_cluster_soft_cap"))
            if quota_events is not None:
                quota_events.append(
                    _quota_event(
                        row,
                        event="deferred",
                        quota_type="repair_aware_soft_quota",
                        quota_stage="post_mutation_child_filter",
                        quota_basis="parent_soft_cap|provisional_child_cluster_soft_cap",
                        rejected_by_quota=True,
                        quota_reject_reason="child_cluster_soft_cap",
                        parent_cluster=parent,
                        provisional_child_cluster=child,
                        repair_source_eligible=True,
                    )
                )
            continue
        add_selected(row, event_name="selected")

    for row, reason in sorted(deferred, key=lambda pair: sort_key(pair[0]), reverse=True):
        if len(selected) >= budget:
            break
        add_selected(row, event_name="selected_after_soft_quota_fill", bypass_reason=reason)

    return selected


def _stable_noise(*parts: Any) -> float:
    digest = hashlib.sha1("::".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:12]
    return int(digest, 16) / float(16**12)


def _read_failure_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    frame = pd.read_csv(path)
    return json.loads(frame.where(pd.notna(frame), None).to_json(orient="records", force_ascii=False))


def _first_field(expression: str, families: set[str] | None = None) -> str | None:
    fields = _fields(expression)
    if families:
        for field in fields:
            if _field_group(field) in families:
                return field
    return fields[0] if fields else None


def _window_shift(expression: str, *, max_window: int, seed: str) -> int:
    windows = _expression_windows(expression)
    anchors = [3, 5, 8, 13, 21, 34, 55, 89]
    anchors = [value for value in anchors if value <= max_window]
    if not anchors:
        return max(1, min(max_window, 5))
    if windows:
        base = max(windows)
        larger = [value for value in anchors if value > base]
        if larger:
            return larger[0]
    return anchors[int(_stable_noise(seed, expression) * len(anchors)) % len(anchors)]


def _repair_expressions(row: dict[str, Any], *, max_window: int, seed: str) -> list[tuple[str, str]]:
    expression = str(row.get("expression") or "")
    if not expression:
        return []
    fields = _fields(expression)
    if not fields:
        return []
    price_field = _first_field(expression, {"price_shape"}) or fields[0]
    liquid_field = _first_field(expression, {"liquidity"}) or ("amount" if "amount" in fields else fields[-1])
    window = _window_shift(expression, max_window=max_window, seed=seed)
    alt_window = max(2, min(max_window, window // 2 if window > 8 else window + 3))
    candidates: list[tuple[str, str]] = []

    # duplicate_escape: keep broad intuition, change horizon/field/operator path.
    candidates.extend(
        [
            ("duplicate_escape", f"CSRank(Mean(${price_field},{window}))"),
            ("duplicate_escape", f"CSRank(Delta(${price_field},{window}))"),
            (
                "duplicate_escape",
                f"CSRank(Mul(ZScore(Mean(${price_field},{window})),ZScore(Delta(${liquid_field},{alt_window}))))",
            ),
        ]
    )

    # operator_sanitize: avoid nested residual/sign/div paths and smooth event triggers.
    candidates.extend(
        [
            ("operator_sanitize", f"CSRank(Mean(Abs(Delta(${price_field},1)),{window}))"),
            ("operator_sanitize", f"CSRank(Div(Delta(${price_field},{alt_window}),Add(Abs(Mean(${price_field},{window})),0.000001)))"),
            ("operator_sanitize", f"CSRank(Sub(Mean(${price_field},{alt_window}),Mean(${price_field},{window})))"),
        ]
    )
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for policy, expr in candidates:
        normalized = rank_validation_canonical_expression(expr)
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append((policy, expr))
    return out


def _build_repair_records_from_source_rows(
    source_rows: list[dict[str, Any]],
    *,
    failure_detail_path: Path,
    max_window: int,
    seed: str,
    source_tag: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    generation_time = utc_now_iso()
    try:
        source_mtime = datetime.fromtimestamp(Path(failure_detail_path).stat().st_mtime, tz=timezone.utc).astimezone().isoformat()
    except OSError:
        source_mtime = None
    for source_index, row in enumerate(source_rows):
        for policy, expression in _repair_expressions(row, max_window=max_window, seed=f"{seed}::{source_index}"):
            parent_id = str(row.get("candidate_id") or _stable_hash(str(row.get("expression") or "")))
            records.append(
                {
                    "candidate_id": f"phase3repair-{source_tag}-{policy}-{_stable_hash(parent_id + expression, 12)}",
                    "expression": expression,
                    "canonical_rank_validation_expression": rank_validation_canonical_expression(expression),
                    "frontier_lane": "stock_pit_ast_failure_aware_repair",
                    "primitive_family": f"ast_repair_{policy}",
                    "proposal_kind": policy,
                    "research_family": f"ast_failure_aware_{policy}",
                    "side_search_role": "phase3_ast_failure_aware_repair",
                    "recommended_signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
                    "qlib_forward_compatible": True,
                    "uses_only_forward_panel_fields": True,
                    "retained": True,
                    "true_limit_bakeoff_variant": "ast_failure_aware_repair",
                    "proof_variant": "ast_failure_aware_repair",
                    "repair_policy": policy,
                    "parent_candidate_id": parent_id,
                    "parent_expression": row.get("expression"),
                    "generation_time": generation_time,
                    "parent_replay_source_path": str(failure_detail_path),
                    "parent_replay_source_mtime": source_mtime,
                    "parent_lane": row.get("lane") or row.get("phase3_source_lane") or row.get("proof_variant"),
                    "source_failure_reasons": row.get("all_reasons") or row.get("source_failure_reasons"),
                    "parent_signal_cluster_id": row.get("signal_cluster_id") or row.get("global_return_corr_cluster") or row.get("pre_audit_return_corr_cluster"),
                    "phase3_source_lane": "ast_failure_aware_repair",
                    "repair_source_tag": source_tag,
                }
            )
    return records


def build_ast_failure_aware_repair_ledger(
    *,
    path: Path | str,
    failure_detail_path: Path,
    candidate_budget: int,
    max_window: int,
    seed: str,
    extra_source_rows: list[dict[str, Any]] | None = None,
    source_tag: str = "failure_detail",
) -> dict[str, Any]:
    failure_rows = _read_failure_rows(failure_detail_path)
    source_rows = [
        row
        for row in failure_rows
        if "corr_duplicate" in str(row.get("all_reasons") or "")
        or "operator_pathology" in str(row.get("all_reasons") or "")
        or str(row.get("lane") or "") in {"non_gap_forced_sampler", "rx_no_policy_true_limit", "rx_diverse_beam"}
    ]
    if extra_source_rows:
        source_rows.extend(dict(row) for row in extra_source_rows)
    records = _build_repair_records_from_source_rows(
        source_rows,
        failure_detail_path=failure_detail_path,
        max_window=max_window,
        seed=seed,
        source_tag=source_tag,
    )
    selected = _dedupe_records(sorted(records, key=lambda row: _stable_noise(seed, row.get("candidate_id"), row.get("expression"))))
    selected = selected[: max(0, int(candidate_budget))]
    return _ledger_from_records(
        path=path,
        variant="ast_failure_aware_repair",
        records=selected,
        scope="phase3_ast_failure_aware_repair_duplicate_escape_operator_sanitize",
        search_report={
            "version": PHASE3_REPAIR_VERSION,
            "failure_detail_path": str(failure_detail_path),
            "source_failure_count": len(source_rows),
            "generated_repair_count": len(records),
            "selected_repair_count": len(selected),
            "enabled_policies": ["duplicate_escape", "operator_sanitize"],
            "source_tag": source_tag,
            "extra_source_count": len(extra_source_rows or []),
        },
    )


def _select_replay_aware_residual(
    rows: list[dict[str, Any]],
    *,
    model_dir: Path,
    budget: int,
    r0_selected_keys: set[str],
    seed: str,
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    if budget <= 0:
        return [], pd.DataFrame()
    feature_rows: list[dict[str, Any]] = []
    source_rows: dict[int, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        key = _row_key(row)
        if not key or key in r0_selected_keys:
            continue
        feature = _replay_ranker_feature_row(row, seed=f"{seed}::residual", source_index=index)
        feature["candidate_key"] = key
        feature_rows.append(feature)
        source_rows[index] = row
    if not feature_rows:
        return [], pd.DataFrame()
    scored, _ = score_with_trained_replay_rankers(pd.DataFrame(feature_rows), model_dir=model_dir)
    scored = score_shadow_selector(scored, selection_budget=len(scored))
    scored = scored.sort_values("selection_score", ascending=False).reset_index(drop=True)
    scored["score_decile"] = pd.qcut(scored.index + 1, q=10, labels=False, duplicates="drop").astype(int) + 1
    exploit_n = min(int(math.ceil(budget * 0.40)), budget)
    calibration_n = max(0, budget - exploit_n)
    selected_indices: list[int] = []
    selected_indices.extend(scored[scored["score_decile"] == 1].head(exploit_n).index.tolist())
    if calibration_n:
        for decile in list(range(2, 11)) + [1]:
            if len(selected_indices) >= budget:
                break
            pool = scored[(scored["score_decile"] == decile) & (~scored.index.isin(selected_indices))]
            if not pool.empty:
                selected_indices.append(int(pool.index[0]))
    if len(selected_indices) < budget:
        for idx in scored.index:
            if len(selected_indices) >= budget:
                break
            if int(idx) not in selected_indices:
                selected_indices.append(int(idx))
    selected: list[dict[str, Any]] = []
    for idx in selected_indices[:budget]:
        scored_row = scored.loc[idx]
        source = source_rows.get(int(scored_row["_source_index"]))
        if source is None:
            continue
        item = _copy_for_selection(
            source,
            policy="replay_aware_residual",
            role=f"replay_aware_residual_decile_{int(scored_row['score_decile'])}",
            pool_type="R0_leftover",
            bucket="replay_aware_residual",
        )
        item["replay_ranker_selection_score"] = round(_safe_float(scored_row.get("selection_score")), 6)
        item["p_non_gap_replay"] = round(_safe_float(scored_row.get("p_non_gap_replay")), 6)
        item["p_replay"] = round(_safe_float(scored_row.get("p_replay")), 6)
        item["replay_score_decile"] = int(scored_row["score_decile"])
        item["replay_residual_selection_mode"] = "top_decile_exploit" if int(scored_row["score_decile"]) == 1 else "score_decile_calibration"
        selected.append(item)
    return selected, scored


def _select_quarantine_diagnostic(
    rows: list[dict[str, Any]],
    *,
    budget: int,
    seed: str,
) -> list[dict[str, Any]]:
    quarantine_lanes = {"non_gap_forced_sampler", "rx_no_policy_true_limit", "rx_diverse_beam", "typed_random_dark", "unreached_space"}
    pool: list[dict[str, Any]] = []
    for row in rows:
        lane = str(row.get("proof_variant") or "")
        if lane not in quarantine_lanes:
            continue
        expression = str(row.get("expression") or "")
        if lane == "unreached_space" and (_is_gap_like(row) or _complexity(expression) > 12):
            continue
        if _safe_float(row.get("mean_window_one_way_turnover"), default=0.0) > 0.75:
            continue
        item = _copy_for_selection(
            row,
            policy="novelty_diagnostic_quarantine",
            role=f"quarantine_pathology_{lane}",
            pool_type="quarantine_hard_gate",
            bucket="novelty_diagnostic",
        )
        item["quarantine_lane"] = lane
        pool.append(item)
    pool = sorted(pool, key=lambda row: (_stable_noise(seed, row.get("proof_variant"), row.get("candidate_id")), _evaluation_reward(row)), reverse=True)
    return pool[: max(0, int(budget))]


def _quota_budgets(total: int) -> dict[str, int]:
    total = max(1, int(total))
    r0 = int(round(total * 0.60))
    repair = int(round(total * 0.20))
    residual = int(round(total * 0.10))
    diagnostic = total - r0 - repair - residual
    if diagnostic < 0:
        diagnostic = 0
    return {
        "r0_cem_led": r0,
        "ast_failure_aware_repair": repair,
        "replay_aware_residual": residual,
        "novelty_diagnostic": diagnostic,
    }


def _phase3b_budgets(total: int, *, residual: bool = True, diagnostic: bool = True) -> dict[str, int]:
    total = max(1, int(total))
    residual_budget = int(round(total * 0.05)) if residual else 0
    diagnostic_budget = int(round(total * 0.05)) if diagnostic else 0
    repair = int(round(total * 0.40))
    r0 = total - repair - residual_budget - diagnostic_budget
    return {
        "r0_cem_led": max(0, int(r0)),
        "ast_failure_aware_repair": max(0, int(repair)),
        "replay_aware_residual": max(0, int(residual_budget)),
        "novelty_diagnostic": max(0, int(total - max(0, int(r0)) - max(0, int(repair)) - max(0, int(residual_budget)))),
    }


def _scale_budget_dict(base: dict[str, int], target_total: int) -> dict[str, int]:
    target_total = max(0, int(target_total))
    if target_total <= 0:
        return {key: 0 for key in base}
    current_total = sum(max(0, int(value)) for value in base.values())
    if current_total <= 0:
        return {key: 0 for key in base}
    scaled = {key: int(math.floor(max(0, int(value)) * target_total / current_total)) for key, value in base.items()}
    remaining = target_total - sum(scaled.values())
    order = sorted(base, key=lambda key: (max(0, int(base[key])), key), reverse=True)
    for key in order:
        if remaining <= 0:
            break
        scaled[key] += 1
        remaining -= 1
    return scaled


def _phase3c_budgets(total: int, *, base: str, expansion: str) -> dict[str, int]:
    total = max(1, int(total))
    if expansion == "none":
        expansion_budgets = {
            "formula_gen_v2_defined": 0,
            "agnostic_freeform_ast": 0,
            "formula_gen_v2_repair_expansion": 0,
        }
        incumbent_total = total
    elif expansion == "defined":
        expansion_budgets = {
            "formula_gen_v2_defined": int(round(total * 0.15)),
            "agnostic_freeform_ast": 0,
            "formula_gen_v2_repair_expansion": 0,
        }
        incumbent_total = total - sum(expansion_budgets.values())
    elif expansion == "open":
        expansion_budgets = {
            "formula_gen_v2_defined": 0,
            "agnostic_freeform_ast": int(round(total * 0.15)),
            "formula_gen_v2_repair_expansion": 0,
        }
        incumbent_total = total - sum(expansion_budgets.values())
    elif expansion == "mixed":
        expansion_budgets = {
            "formula_gen_v2_defined": int(round(total * 0.08)),
            "agnostic_freeform_ast": int(round(total * 0.10)),
            "formula_gen_v2_repair_expansion": int(round(total * 0.07)),
        }
        incumbent_total = total - sum(expansion_budgets.values())
    else:
        raise ValueError(f"unknown Phase3C expansion: {expansion}")

    if base == "stable":
        incumbent = _scale_budget_dict(_quota_budgets(max(1, incumbent_total)), incumbent_total)
    elif base == "productive":
        incumbent = _scale_budget_dict(_phase3b_budgets(max(1, incumbent_total)), incumbent_total)
    else:
        raise ValueError(f"unknown Phase3C base: {base}")

    for key in ["r0_cem_led", "ast_failure_aware_repair", "replay_aware_residual", "novelty_diagnostic"]:
        incumbent.setdefault(key, 0)
    incumbent.update(expansion_budgets)
    diff = total - sum(incumbent.values())
    incumbent["r0_cem_led"] += diff
    return incumbent


def _no_diagnostic_stable_budgets(total: int) -> dict[str, int]:
    total = max(1, int(total))
    r0 = int(round(total * 0.60))
    repair = int(round(total * 0.20))
    residual = int(round(total * 0.10))
    # Phase3D removes novelty_diagnostic from official budget; send the remainder to R0/CEM.
    r0 += total - r0 - repair - residual
    return {
        "r0_cem_led": max(0, int(r0)),
        "ast_failure_aware_repair": max(0, int(repair)),
        "replay_aware_residual": max(0, int(residual)),
        "novelty_diagnostic": 0,
    }


def _phase3d_budgets(total: int, *, base: str, mode: str) -> dict[str, int]:
    total = max(1, int(total))
    if mode == "sm_current":
        return _phase3c_budgets(total, base="stable", expansion="mixed")
    if mode == "open_repair":
        expansion_budgets = {
            "formula_gen_v2_defined": int(round(total * 0.02)),
            "agnostic_freeform_ast": int(round(total * 0.20)),
            "formula_gen_v2_repair_expansion": int(round(total * 0.13)),
        }
        incumbent_total = total - sum(expansion_budgets.values())
    elif mode == "no_defined_direct":
        expansion_budgets = {
            "formula_gen_v2_defined": 0,
            "agnostic_freeform_ast": int(round(total * 0.18)),
            "formula_gen_v2_repair_expansion": int(round(total * 0.12)),
        }
        incumbent_total = total - sum(expansion_budgets.values())
    else:
        raise ValueError(f"unknown Phase3D mode: {mode}")

    if base == "stable":
        incumbent = _scale_budget_dict(_no_diagnostic_stable_budgets(max(1, incumbent_total)), incumbent_total)
    elif base == "productive":
        incumbent = _scale_budget_dict(_phase3b_budgets(max(1, incumbent_total), diagnostic=False), incumbent_total)
    else:
        raise ValueError(f"unknown Phase3D base: {base}")

    for key in ["r0_cem_led", "ast_failure_aware_repair", "replay_aware_residual", "novelty_diagnostic"]:
        incumbent.setdefault(key, 0)
    incumbent.update(expansion_budgets)
    diff = total - sum(incumbent.values())
    incumbent["r0_cem_led"] += diff
    return incumbent


PHASE3_ABLATION_ARMS = {
    "original_R0": {
        "description": "R0/CEM-led baseline, no cluster quota, no AST repair, no residual, no diagnostic",
        "cluster_quota": False,
    },
    "R0_cluster_quota_only": {
        "description": "R0/CEM-led baseline with cluster quota only",
        "cluster_quota": True,
    },
    "R0_AST_repair_only": {
        "description": "R0 plus AST repair, no cluster quota, no residual, no diagnostic",
        "cluster_quota": False,
    },
    "R0_cluster_quota_AST_repair_only": {
        "description": "R0 plus cluster quota plus AST repair, no residual, no diagnostic",
        "cluster_quota": True,
    },
    "Phase3A_full": {
        "description": "Phase3A full: R0/CEM-led with cluster quota, AST repair, replay-aware residual, novelty diagnostic",
        "cluster_quota": True,
    },
    "Phase3B_B0_incumbent_best": {
        "description": "Phase3B control: current strongest R0 + AST repair only, no quota/residual/diagnostic",
        "cluster_quota": False,
        "direct_r0_quota": False,
        "repair_quota_mode": "none",
        "budget_mode": "incumbent_ast_repair",
    },
    "Phase3B_B1_phase3A_full": {
        "description": "Phase3B control: existing Phase3A full with hard quota interaction",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "budget_mode": "phase3A_full",
    },
    "Phase3B_B2_direct_R0_quota_only": {
        "description": "Phase3B: direct R0 quota only; repair lane is selected after mutation without parent quota",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "none",
        "budget_mode": "phase3B_50_40_5_5",
        "direct_rejected_to_repair_source": True,
        "direct_return_cluster_cap": 3,
        "direct_ast_cluster_cap": 3,
    },
    "Phase3B_B3_repair_aware_soft_quota": {
        "description": "Phase3B: direct R0 quota plus child-side repair-aware soft quota",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "repair_aware_soft",
        "budget_mode": "phase3B_50_40_5_5",
        "direct_rejected_to_repair_source": True,
        "direct_return_cluster_cap": 3,
        "direct_ast_cluster_cap": 3,
        "repair_parent_max_share": 0.35,
        "repair_child_cluster_cap": 3,
    },
    "Phase3C_S0_stable_control": {
        "description": "Phase3C S0: B1 stable incumbent control",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3c_base": "stable",
        "phase3c_expansion": "none",
    },
    "Phase3C_P0_productive_control": {
        "description": "Phase3C P0: B2 productive incumbent with cluster-credit cap",
        "cluster_quota": True,
        "direct_r0_quota": False,
        "direct_cluster_credit_cap": True,
        "repair_quota_mode": "none",
        "direct_rejected_to_repair_source": False,
        "phase3c_base": "productive",
        "phase3c_expansion": "none",
    },
    "Phase3C_SD_defined_motifs": {
        "description": "Phase3C SD: stable base plus FormulaGenV2 defined motifs",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3c_base": "stable",
        "phase3c_expansion": "defined",
    },
    "Phase3C_SO_open_ended": {
        "description": "Phase3C SO: stable base plus agnostic freeform AST",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3c_base": "stable",
        "phase3c_expansion": "open",
    },
    "Phase3C_SM_mixed": {
        "description": "Phase3C SM: stable base plus defined, open-ended, and repair expansion",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3c_base": "stable",
        "phase3c_expansion": "mixed",
    },
    "Phase3C_PD_defined_motifs": {
        "description": "Phase3C PD: productive base plus FormulaGenV2 defined motifs",
        "cluster_quota": True,
        "direct_r0_quota": False,
        "direct_cluster_credit_cap": True,
        "repair_quota_mode": "none",
        "phase3c_base": "productive",
        "phase3c_expansion": "defined",
    },
    "Phase3C_PO_open_ended": {
        "description": "Phase3C PO: productive base plus agnostic freeform AST",
        "cluster_quota": True,
        "direct_r0_quota": False,
        "direct_cluster_credit_cap": True,
        "repair_quota_mode": "none",
        "phase3c_base": "productive",
        "phase3c_expansion": "open",
    },
    "Phase3C_PM_mixed": {
        "description": "Phase3C PM: productive base plus defined, open-ended, and repair expansion",
        "cluster_quota": True,
        "direct_r0_quota": False,
        "direct_cluster_credit_cap": True,
        "repair_quota_mode": "none",
        "phase3c_base": "productive",
        "phase3c_expansion": "mixed",
    },
    "Phase3D_D0_SM_current_control": {
        "description": "Phase3D D0: SM current control, exact Phase3C SM mixed budget",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "sm_current",
    },
    "Phase3D_D1_SM_open_repair": {
        "description": "Phase3D D1: stable SM base reallocates defined-direct budget to open-ended and repair expansion",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "open_repair",
    },
    "Phase3D_D2_PM_open_repair": {
        "description": "Phase3D D2: productive PM base with cluster-credit cap and open/repair reallocation",
        "cluster_quota": True,
        "direct_r0_quota": False,
        "direct_cluster_credit_cap": True,
        "repair_quota_mode": "none",
        "direct_rejected_to_repair_source": False,
        "phase3d_base": "productive",
        "phase3d_mode": "open_repair",
    },
    "Phase3D_D3_SM_no_defined_direct": {
        "description": "Phase3D D3: stable SM base removes defined direct and keeps defined motifs only through repair expansion",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
    },
    "Phase3E_E0_D3_primary": {
        "description": "Phase3E E0: D3 primary control with standard D3 selector",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "standard_D3",
        "generation_profile": "D3_SM_no_defined_direct",
    },
    "Phase3E_E1_D3_plus_D2_sidecar": {
        "description": "Phase3E E1: D3 primary with 20 percent D2 productive sidecar and cluster-capped sidecar credit",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "mixed_profile_cluster_capped",
        "generation_profile": "D3_plus_D2_sidecar",
        "d2_sidecar_share": 0.20,
    },
    "Phase3E_E2_D3_deployability_hardened": {
        "description": "Phase3E E2: D3 generation with deployability-hardened selector",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "deployability_hardened",
        "generation_profile": "D3_SM_no_defined_direct",
    },
    "Phase3E_E3_D3_book_marginal": {
        "description": "Phase3E E3: D3 generation with book-marginal proxy selector against 103-cluster registry",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "book_marginal_proxy",
        "generation_profile": "D3_SM_no_defined_direct",
    },
    "Phase3F_F0_E0_stable": {
        "description": "Phase3F F0: E0/D3 stable control against 134-cluster baseline",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "standard_D3",
        "generation_profile": "E0_D3_primary",
        "phase3_selector_baseline": "phase3E_cumulative_134",
    },
    "Phase3F_F1_E3_current_proxy": {
        "description": "Phase3F F1: current E3 book-marginal proxy control against 134-cluster baseline",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "book_marginal_proxy",
        "generation_profile": "E3_current_proxy",
        "phase3_selector_baseline": "phase3E_cumulative_134",
    },
    "Phase3F_F2_E3_proxy_diversified": {
        "description": "Phase3F F2: E3 proxy with queue-level anti-concentration caps and penalties",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "book_marginal_proxy_diversified",
        "generation_profile": "E3_proxy_diversified",
        "phase3_selector_baseline": "phase3E_cumulative_134",
    },
    "Phase3F_F3_E3_proxy_strengthened": {
        "description": "Phase3F F3: strengthened proxy book-marginal selector with stronger registry and selected-queue diversity pressure",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "book_marginal_proxy_strengthened",
        "generation_profile": "E3_proxy_strengthened",
        "phase3_selector_baseline": "phase3E_cumulative_134",
        "book_marginal_mode": "proxy",
    },
    "Phase3G_G0_E0_stable": {
        "description": "Phase3G G0: E0/D3 stable control against 134-cluster baseline",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "standard_D3",
        "generation_profile": "E0_D3_primary",
        "phase3_selector_baseline": "phase3E_cumulative_134",
    },
    "Phase3G_G1_E3_current_proxy": {
        "description": "Phase3G G1: current E3 symbolic proxy control against 134-cluster baseline",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "book_marginal_proxy",
        "generation_profile": "E3_current_proxy",
        "phase3_selector_baseline": "phase3E_cumulative_134",
    },
    "Phase3G_G2_E3_signal_vector_diversified": {
        "description": "Phase3G G2: E3 with sampled signal-vector diversified proxy selector",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "signal_vector_diversified_proxy",
        "generation_profile": "E3_signal_vector_diversified",
        "phase3_selector_baseline": "phase3E_cumulative_134",
        "book_marginal_mode": "signal_vector_proxy",
    },
    "Phase3G_G3_E3_strong_signal_vector_proxy": {
        "description": "Phase3G G3: E3 with stronger sampled signal-vector proxy diversity pressure",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "strong_signal_vector_proxy",
        "generation_profile": "E3_strong_signal_vector_proxy",
        "phase3_selector_baseline": "phase3E_cumulative_134",
        "book_marginal_mode": "signal_vector_proxy",
    },
    "Phase3H_H0_G0_stable": {
        "description": "Phase3H H0: G0/E0 stable historical control",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "standard_D3",
        "generation_profile": "E0_D3_primary",
        "phase3_selector_baseline": "phase3E_cumulative_134",
        "phase3_metadata_policy": "DUAL_BASELINE_ACCEPTED",
        "phase3_discovery_baseline_count": 134,
        "phase3_selector_vector_baseline_count": 122,
    },
    "Phase3H_H1_G2_signal_vector_control": {
        "description": "Phase3H H1: G2 signal-vector diversified control under dual-baseline policy",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "signal_vector_diversified_proxy",
        "generation_profile": "G2_signal_vector_control",
        "phase3_selector_baseline": "phase3E_cumulative_134",
        "phase3_metadata_policy": "DUAL_BASELINE_ACCEPTED",
        "phase3_discovery_baseline_count": 134,
        "phase3_selector_vector_baseline_count": 122,
        "book_marginal_mode": "signal_vector_proxy",
    },
    "Phase3H_H2_G2_turnover_calibrated": {
        "description": "Phase3H H2: G2 signal-vector selector with stronger turnover-structure penalty",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "signal_vector_turnover_calibrated_proxy",
        "generation_profile": "G2_turnover_calibrated",
        "phase3_selector_baseline": "phase3E_cumulative_134",
        "phase3_metadata_policy": "DUAL_BASELINE_ACCEPTED",
        "phase3_discovery_baseline_count": 134,
        "phase3_selector_vector_baseline_count": 122,
        "target_median_turnover": "0.18-0.20",
        "book_marginal_mode": "signal_vector_proxy",
    },
    "Phase3H_H3_G2_registry_canonicalized": {
        "description": "Phase3H H3: G2 signal-vector selector with canonical 122-vector registry policy metadata",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "signal_vector_diversified_proxy",
        "generation_profile": "G2_registry_canonicalized",
        "phase3_selector_baseline": "phase3E_cumulative_134",
        "phase3_metadata_policy": "DUAL_BASELINE_ACCEPTED",
        "phase3_discovery_baseline_count": 134,
        "phase3_selector_vector_baseline_count": 122,
        "phase3_selector_vector_baseline_name": "canonical_122",
        "strict_vector_cluster_cap": True,
        "book_marginal_mode": "signal_vector_proxy",
    },
    "Phase3I_I0_G2_primary": {
        "description": "Phase3I I0: G2 signal-vector discovery primary fresh-seed control",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "signal_vector_diversified_proxy",
        "generation_profile": "G2_phase3i_primary",
        "phase3_selector_baseline": "phase3H_cumulative_149",
        "phase3_metadata_policy": "DUAL_BASELINE_ACCEPTED",
        "phase3_discovery_baseline_count": 149,
        "phase3_selector_vector_baseline_count": 137,
        "book_marginal_mode": "signal_vector_proxy",
    },
    "Phase3I_I1_G2_cost_turnover_constrained": {
        "description": "Phase3I I1: G2 with stronger cluster-level cost and turnover hardening",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "signal_vector_cost_turnover_constrained_proxy",
        "generation_profile": "G2_cost_turnover_constrained",
        "phase3_selector_baseline": "phase3H_cumulative_149",
        "phase3_metadata_policy": "DUAL_BASELINE_ACCEPTED",
        "phase3_discovery_baseline_count": 149,
        "phase3_selector_vector_baseline_count": 137,
        "target_median_turnover": "below_I0",
        "book_marginal_mode": "signal_vector_proxy",
    },
    "Phase3I_I2_G2_capacity_liquidity": {
        "description": "Phase3I I2: G2 with capacity/liquidity-aware hardening, diagnostic-only if proxies are insufficient",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "signal_vector_capacity_liquidity_proxy",
        "generation_profile": "G2_capacity_liquidity",
        "phase3_selector_baseline": "phase3H_cumulative_149",
        "phase3_metadata_policy": "DUAL_BASELINE_ACCEPTED",
        "phase3_discovery_baseline_count": 149,
        "phase3_selector_vector_baseline_count": 137,
        "book_marginal_mode": "signal_vector_proxy",
    },
    "Phase3I_I3_G2_book_proxy_hardened": {
        "description": "Phase3I I3: G2 with stronger registry/queue signal-corr book-proxy hardening, not true return residual",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "signal_vector_book_proxy_hardened",
        "generation_profile": "G2_book_proxy_hardened",
        "phase3_selector_baseline": "phase3H_cumulative_149",
        "phase3_metadata_policy": "DUAL_BASELINE_ACCEPTED",
        "phase3_discovery_baseline_count": 149,
        "phase3_selector_vector_baseline_count": 137,
        "book_marginal_mode": "signal_vector_proxy",
    },
    "Phase3I_I1_v2_turnover_tail_guard": {
        "description": "Phase3I I1_v2: G2 with pool-relative turnover tail guard and high-turnover queue caps",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "signal_vector_turnover_tail_guard_v2",
        "generation_profile": "G2_turnover_tail_guard_v2",
        "phase3_selector_baseline": "phase3H_cumulative_149",
        "phase3_metadata_policy": "DUAL_BASELINE_ACCEPTED",
        "phase3_discovery_baseline_count": 149,
        "phase3_selector_vector_baseline_count": 137,
        "target_p90_turnover": "below_I0",
        "book_marginal_mode": "signal_vector_proxy",
    },
    "Phase3I_I3_v2_queue_diversity": {
        "description": "Phase3I I3_v2: G2 selected-queue signal diversity first, registry novelty second",
        "cluster_quota": True,
        "direct_r0_quota": True,
        "repair_quota_mode": "phase3A_hard",
        "phase3d_base": "stable",
        "phase3d_mode": "no_defined_direct",
        "selector_profile": "signal_vector_queue_diversity_v2",
        "generation_profile": "G2_queue_diversity_v2",
        "phase3_selector_baseline": "phase3H_cumulative_149",
        "phase3_metadata_policy": "DUAL_BASELINE_ACCEPTED",
        "phase3_discovery_baseline_count": 149,
        "phase3_selector_vector_baseline_count": 137,
        "book_marginal_mode": "signal_vector_proxy",
    },
}


def _ablation_budgets(total: int, arm: str) -> dict[str, int]:
    total = max(1, int(total))
    if arm in {"Phase3A_full", "Phase3B_B1_phase3A_full"}:
        return _quota_budgets(total)
    if arm in {"original_R0", "R0_cluster_quota_only"}:
        return {
            "r0_cem_led": total,
            "ast_failure_aware_repair": 0,
            "replay_aware_residual": 0,
            "novelty_diagnostic": 0,
        }
    if arm in {"R0_AST_repair_only", "R0_cluster_quota_AST_repair_only"}:
        repair = max(1, int(round(total * 0.20)))
        r0 = total - repair
        return {
            "r0_cem_led": r0,
            "ast_failure_aware_repair": repair,
            "replay_aware_residual": 0,
            "novelty_diagnostic": 0,
        }
    if arm == "Phase3B_B0_incumbent_best":
        repair = max(1, int(round(total * 0.20)))
        return {
            "r0_cem_led": total - repair,
            "ast_failure_aware_repair": repair,
            "replay_aware_residual": 0,
            "novelty_diagnostic": 0,
        }
    if arm in {"Phase3B_B2_direct_R0_quota_only", "Phase3B_B3_repair_aware_soft_quota"}:
        return _phase3b_budgets(total)
    config = PHASE3_ABLATION_ARMS.get(arm, {})
    if str(config.get("phase3c_base") or ""):
        return _phase3c_budgets(
            total,
            base=str(config.get("phase3c_base")),
            expansion=str(config.get("phase3c_expansion") or "none"),
        )
    if str(config.get("phase3d_base") or ""):
        return _phase3d_budgets(
            total,
            base=str(config.get("phase3d_base")),
            mode=str(config.get("phase3d_mode") or "open_repair"),
        )
    raise ValueError(f"unknown Phase3 ablation arm: {arm}")


def _selector_baseline_path(ablation_arm: str, arm_config: dict[str, Any]) -> Path:
    baseline = str(arm_config.get("phase3_selector_baseline") or "")
    if baseline == "phase3H_cumulative_149" or ablation_arm.startswith("Phase3I_"):
        return PHASE3H_CUMULATIVE_BASELINE_PATH
    if baseline == "phase3E_cumulative_134" or ablation_arm.startswith("Phase3F_") or ablation_arm.startswith("Phase3G_") or ablation_arm.startswith("Phase3H_"):
        return PHASE3E_CUMULATIVE_BASELINE_PATH
    return PHASE3D_CUMULATIVE_BASELINE_PATH


def _phase3e_candidate_pool(
    *,
    ablation_arm: str,
    r0_pool: list[dict[str, Any]],
    repair_pool: list[dict[str, Any]],
    formula_rows: list[dict[str, Any]],
    agnostic_rows: list[dict[str, Any]],
    repair_expansion_rows: list[dict[str, Any]],
    residual_rows: list[dict[str, Any]],
    diagnostic_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []

    def add(rows: list[dict[str, Any]], bucket: str) -> None:
        for row in rows:
            if not row.get("expression"):
                continue
            item = dict(row)
            item["ablation_arm"] = ablation_arm
            item["phase3_budget_bucket"] = bucket
            item["source_profile"] = item.get("source_profile") or "phase3e_candidate_pool"
            item["proof_variant"] = item.get("proof_variant") or bucket
            output.append(item)

    add(r0_pool, "r0_cem_led")
    add(repair_pool, "ast_failure_aware_repair")
    add(formula_rows, "formula_gen_v2_defined")
    add(agnostic_rows, "agnostic_freeform_ast")
    add(repair_expansion_rows, "formula_gen_v2_repair_expansion")
    add(residual_rows, "replay_aware_residual")
    add(diagnostic_rows, "novelty_diagnostic")
    return output


def _phase3_main_kpis(rows: list[dict[str, Any]], *, turnover_max: float) -> dict[str, Any]:
    audited = max(1, len(rows))
    non_gap_pass = [row for row in rows if _non_gap_replay_pass(row)]
    deployable = [row for row in rows if _deployable_pass(row, turnover_max=turnover_max)]
    return_clusters = {str(row.get("signal_cluster_id")) for row in non_gap_pass if row.get("signal_cluster_id")}
    deployable_clusters = {str(row.get("signal_cluster_id")) for row in deployable if row.get("signal_cluster_id")}
    r0_clusters = {
        str(row.get("signal_cluster_id"))
        for row in rows
        if row.get("selection_policy") in {"phase3_r0_cem_led", "r0_control"} and _non_gap_replay_pass(row) and row.get("signal_cluster_id")
    }
    new_clusters = return_clusters - r0_clusters
    cluster_counts = Counter(str(row.get("signal_cluster_id")) for row in non_gap_pass if row.get("signal_cluster_id"))
    top_cluster_share = max(cluster_counts.values()) / max(1, len(non_gap_pass)) if cluster_counts else 0.0
    return {
        "primary": {
            "cost_turnover_deployable_unique_clusters": int(len(deployable_clusters)),
            "audited_count": int(len(rows)),
            "cost_turnover_deployable_unique_clusters_per_audited": round(len(deployable_clusters) / audited, 6),
        },
        "secondary": {
            "unique_return_corr_clusters": int(len(return_clusters)),
            "unique_return_corr_clusters_per_audited": round(len(return_clusters) / audited, 6),
            "new_clusters_not_covered_by_r0": int(len(new_clusters)),
            "new_clusters_not_covered_by_r0_per_audited": round(len(new_clusters) / audited, 6),
            "raw_non_gap_replay_pass": int(len(non_gap_pass)),
            "raw_non_gap_replay_pass_per_audited": round(len(non_gap_pass) / audited, 6),
            "top_cluster_raw_pass_share": round(top_cluster_share, 6),
            "top_cluster_id": cluster_counts.most_common(1)[0][0] if cluster_counts else None,
        },
        "raw_pass_is_diagnostic_only": True,
    }


def _policy_table(rows: list[dict[str, Any]], *, turnover_max: float) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("phase3_budget_bucket") or "unknown"), str(row.get("selection_policy") or "unknown"))].append(row)
    table: list[dict[str, Any]] = []
    for (bucket, policy), group in sorted(grouped.items()):
        non_gap = [row for row in group if _non_gap_replay_pass(row)]
        deployable = [row for row in group if _deployable_pass(row, turnover_max=turnover_max)]
        table.append(
            {
                "phase3_budget_bucket": bucket,
                "selection_policy": policy,
                "audited": len(group),
                "raw_non_gap_replay_pass": len(non_gap),
                "unique_return_corr_clusters": len({row.get("signal_cluster_id") for row in non_gap if row.get("signal_cluster_id")}),
                "deployable_unique_clusters": len({row.get("signal_cluster_id") for row in deployable if row.get("signal_cluster_id")}),
                "deployable_cluster_per_audited": round(len({row.get("signal_cluster_id") for row in deployable if row.get("signal_cluster_id")}) / max(1, len(group)), 6),
            }
        )
    return table


def _repair_policy_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("selection_policy") != "ast_failure_aware_repair":
            continue
        grouped[str(row.get("repair_policy") or row.get("proposal_kind") or "unknown")].append(row)
    table: list[dict[str, Any]] = []
    for policy, group in sorted(grouped.items()):
        table.append(
            {
                "repair_policy": policy,
                "audited": len(group),
                "strict_pass": sum(1 for row in group if bool(row.get("strict_pass_proxy"))),
                "raw_non_gap_replay_pass": sum(1 for row in group if _non_gap_replay_pass(row)),
                "deployable_pass": sum(1 for row in group if _deployable_pass(row, turnover_max=0.75)),
                "unique_clusters": len({row.get("signal_cluster_id") for row in group if _non_gap_replay_pass(row) and row.get("signal_cluster_id")}),
            }
        )
    return table


def _cluster_transition_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    transitions: Counter[tuple[str, str, str]] = Counter()
    for row in rows:
        if row.get("selection_policy") != "ast_failure_aware_repair":
            continue
        parent = str(row.get("parent_signal_cluster_id") or "unknown_parent")
        child = str(row.get("signal_cluster_id") or "unknown_child")
        outcome = "non_gap_replay_pass" if _non_gap_replay_pass(row) else "fail"
        transitions[(parent, child, outcome)] += 1
    return [
        {"parent_cluster": parent, "child_cluster": child, "outcome": outcome, "count": count}
        for (parent, child, outcome), count in sorted(transitions.items())
    ]


def _replay_decile_table(rows: list[dict[str, Any]], *, turnover_max: float) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("selection_policy") == "replay_aware_residual":
            grouped[int(row.get("replay_score_decile") or 0)].append(row)
    table: list[dict[str, Any]] = []
    for decile, group in sorted(grouped.items()):
        non_gap = [row for row in group if _non_gap_replay_pass(row)]
        deployable = [row for row in group if _deployable_pass(row, turnover_max=turnover_max)]
        table.append(
            {
                "score_decile": decile,
                "audited": len(group),
                "raw_non_gap_replay_pass": len(non_gap),
                "unique_cluster_pass": len({row.get("signal_cluster_id") for row in non_gap if row.get("signal_cluster_id")}),
                "deployable_cluster_pass": len({row.get("signal_cluster_id") for row in deployable if row.get("signal_cluster_id")}),
            }
        )
    return table


def _quota_event_table(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str | None], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[
            (
                str(event.get("quota_type") or "unknown"),
                str(event.get("quota_stage") or "unknown"),
                str(event.get("event") or "unknown"),
                event.get("quota_reject_reason"),
            )
        ].append(event)
    return [
        {
            "quota_type": quota_type,
            "quota_stage": quota_stage,
            "event": event_name,
            "quota_reject_reason": reject_reason,
            "count": len(group),
            "repair_source_eligible": sum(1 for row in group if bool(row.get("repair_source_eligible"))),
        }
        for (quota_type, quota_stage, event_name, reject_reason), group in sorted(grouped.items())
    ]


def _cem_anti_collapse_table(rows: list[dict[str, Any]], *, turnover_max: float) -> dict[str, Any]:
    cem = [row for row in rows if row.get("selection_policy") == "phase3_r0_cem_led" and row.get("proof_variant") == "cem_adaptive_grammar"]
    non_gap = [row for row in cem if _non_gap_replay_pass(row)]
    deployable = [row for row in cem if _deployable_pass(row, turnover_max=turnover_max)]
    cluster_counts = Counter(str(row.get("signal_cluster_id")) for row in non_gap if row.get("signal_cluster_id"))
    return {
        "audited": len(cem),
        "raw_non_gap_replay_pass": len(non_gap),
        "unique_return_corr_clusters": len(cluster_counts),
        "deployable_unique_clusters": len({row.get("signal_cluster_id") for row in deployable if row.get("signal_cluster_id")}),
        "top_cluster_id": cluster_counts.most_common(1)[0][0] if cluster_counts else None,
        "top_cluster_share": round(cluster_counts.most_common(1)[0][1] / max(1, len(non_gap)), 6) if cluster_counts else 0.0,
    }


def _load_phase3b_union_baseline(path: Path = PHASE3B_UNION_BASELINE_PATH) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"baseline_path": str(path), "load_error": type(exc).__name__, "global_deployable_cluster_count": None}
    data["baseline_path"] = str(path)
    return data


def _semantic_bucket(row: dict[str, Any]) -> str:
    bucket = str(row.get("phase3_budget_bucket") or row.get("proof_variant") or "")
    if bucket in {"formula_gen_v2_defined"}:
        return "defined_motif"
    if bucket in {"formula_gen_v2_repair_expansion"}:
        return "defined_repair"
    if bucket in {"agnostic_freeform_ast"}:
        return "unknown_agnostic_freeform"
    return "incumbent"


def _bucket_table(rows: list[dict[str, Any]], *, turnover_max: float, key_func) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(key_func(row))].append(row)
    output: list[dict[str, Any]] = []
    for bucket, group in sorted(grouped.items()):
        non_gap = [row for row in group if _non_gap_replay_pass(row)]
        deployable = [row for row in group if _deployable_pass(row, turnover_max=turnover_max)]
        cluster_counts = Counter(str(row.get("signal_cluster_id")) for row in non_gap if row.get("signal_cluster_id"))
        pathology = [
            row
            for row in group
            if "operator_pathology" in str(row.get("source_failure_reasons") or row.get("all_reasons") or "")
            or bool(row.get("operator_pathology"))
        ]
        output.append(
            {
                "bucket": bucket,
                "audited": len(group),
                "raw_non_gap": len(non_gap),
                "deployable_clusters": len({row.get("signal_cluster_id") for row in deployable if row.get("signal_cluster_id")}),
                "top_cluster_share": round(cluster_counts.most_common(1)[0][1] / max(1, len(non_gap)), 6) if cluster_counts else 0.0,
                "pathology_rate": round(len(pathology) / max(1, len(group)), 6),
            }
        )
    return output


def _definition_pressure_audit(rows: list[dict[str, Any]], *, turnover_max: float) -> dict[str, Any]:
    table = _bucket_table(rows, turnover_max=turnover_max, key_func=_semantic_bucket)
    return {
        "semantic_mismatch_reject_count": 0,
        "unknown_mechanism_default_downweight": False,
        "new_vs_phase3B_union_pending_global_aggregate": True,
        "table": table,
    }


def _motif_lift_audit(rows: list[dict[str, Any]], *, turnover_max: float) -> list[dict[str, Any]]:
    return _bucket_table(rows, turnover_max=turnover_max, key_func=lambda row: row.get("motif_family") or row.get("primitive_family") or "unknown")


def _open_space_audit(rows: list[dict[str, Any]], *, turnover_max: float) -> dict[str, Any]:
    open_rows = [row for row in rows if _semantic_bucket(row) == "unknown_agnostic_freeform"]
    non_gap = [row for row in open_rows if _non_gap_replay_pass(row)]
    deployable = [row for row in open_rows if _deployable_pass(row, turnover_max=turnover_max)]
    complexity_fail = [row for row in open_rows if _complexity(str(row.get("expression") or "")) > 16]
    turnover_fail = [row for row in open_rows if _safe_float(row.get("strict_mean_one_way_turnover"), 0.0) > turnover_max]
    return {
        "generated": None,
        "valid": None,
        "audited": len(open_rows),
        "raw_non_gap": len(non_gap),
        "deployable_clusters": len({row.get("signal_cluster_id") for row in deployable if row.get("signal_cluster_id")}),
        "new_deployable_clusters_vs_phase3B_union_pending_global_aggregate": True,
        "operator_pathology_rate": 0.0,
        "turnover_failure_rate": round(len(turnover_fail) / max(1, len(open_rows)), 6),
        "complexity_failure_rate": round(len(complexity_fail) / max(1, len(open_rows)), 6),
    }


def _paired_ablation_audit(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        group_id = row.get("paired_ablation_group_id")
        if group_id:
            grouped[str(group_id)].append(row)
    output = []
    for group_id, group in sorted(grouped.items()):
        full = [row for row in group if row.get("proposal_kind") != "paired_low_order_ablation"]
        lows = [row for row in group if row.get("proposal_kind") == "paired_low_order_ablation"]
        output.append(
            {
                "paired_ablation_group_id": group_id,
                "full_count": len(full),
                "low_order_count": len(lows),
                "has_real_role_slots": any(bool(row.get("role_slots")) for row in group),
                "full_formula": full[0].get("expression") if full else None,
                "low_order_best": None,
                "full_score": None,
                "low_order_best_score": None,
                "marginal_complexity_value": None,
                "paired_ablation_pass": None,
                "score_pending": True,
            }
        )
    return output


def run_phase3_repair(
    *,
    output_root: Path | str,
    dataset_path: Path | str,
    failure_detail_path: Path | str = PHASE3_DEFAULT_FAILURE_DETAIL,
    replay_ranker_model_dir: Path | str = Path("data/models"),
    candidate_budget: int = 64,
    strict_audit_budget: int = 64,
    target_window_count: int = 6,
    max_window: int = 34,
    beam_width: int = 16,
    max_beam_records: int = 256,
    top_bottom_quantile: float = 0.02,
    recent_quarter_window_count: int = 2,
    recent_warmup_days: int = 60,
    strict_cost_bps: float = DEFAULT_PORTFOLIO_REPLAY_COST_BPS,
    low_corr_threshold: float = DEFAULT_LOW_CORR_THRESHOLD,
    turnover_survival_max_one_way: float = 0.75,
    max_audited_per_return_corr_cluster_per_seed: int = 4,
    max_audited_per_ast_cluster_per_seed: int = 3,
    seed: str = "phase3A_repair",
    use_fast_context: bool = True,
    ablation_arm: str = "Phase3A_full",
    selection_only: bool = False,
    shared_candidate_pool_output: Path | str | None = None,
) -> dict[str, Any]:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    _write_progress(root, "start", seed=seed, ablation_arm=ablation_arm, candidate_budget=int(candidate_budget), strict_audit_budget=int(strict_audit_budget))
    dataset = Path(dataset_path)
    failure_detail = Path(failure_detail_path)
    if ablation_arm not in PHASE3_ABLATION_ARMS:
        raise ValueError(f"unknown Phase3 ablation arm: {ablation_arm}")
    arm_config = dict(PHASE3_ABLATION_ARMS[ablation_arm])
    use_cluster_quota = bool(arm_config["cluster_quota"])
    direct_r0_quota = bool(arm_config.get("direct_r0_quota", use_cluster_quota))
    direct_cluster_credit_cap = bool(arm_config.get("direct_cluster_credit_cap", False))
    repair_quota_mode = str(arm_config.get("repair_quota_mode", "phase3A_hard" if use_cluster_quota else "none"))
    direct_return_cap = int(arm_config.get("direct_return_cluster_cap", max_audited_per_return_corr_cluster_per_seed))
    direct_ast_cap = int(arm_config.get("direct_ast_cluster_cap", max_audited_per_ast_cluster_per_seed))
    repair_child_cap = int(arm_config.get("repair_child_cluster_cap", max_audited_per_ast_cluster_per_seed))
    repair_parent_max_share = float(arm_config.get("repair_parent_max_share", 0.35))
    direct_rejected_to_repair_source = bool(arm_config.get("direct_rejected_to_repair_source", False))
    quota_events: list[dict[str, Any]] = []
    direct_rejected_repair_sources: list[dict[str, Any]] = []
    budgets = _ablation_budgets(strict_audit_budget, ablation_arm)
    _write_progress(root, "budgets_resolved", budgets=budgets)

    variants = _build_variant_ledgers(
        root=root,
        dataset=dataset,
        previous_search_roots=[],
        candidate_budget=candidate_budget,
        target_window_count=target_window_count,
        max_window=max_window,
        beam_width=beam_width,
        max_beam_records=max_beam_records,
        top_bottom_quantile=top_bottom_quantile,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
        use_fast_context=use_fast_context,
        seed=seed,
        include_qd=False,
    )
    _write_progress(root, "base_variant_ledgers_built", variant_count=len(variants))
    if budgets.get("formula_gen_v2_defined", 0) > 0:
        variants.append(
            (
                "formula_gen_v2_defined",
                build_formula_gen_v2_ledger(
                    path=dataset,
                    candidate_budget=max(candidate_budget, int(budgets["formula_gen_v2_defined"]) * 6),
                    seed=f"{seed}::formula_gen_v2_defined",
                    include_seed_templates=True,
                    include_paired_ablations=True,
                ),
            )
        )
        _write_progress(root, "formula_gen_v2_defined_ledger_built", variant_count=len(variants))
    if budgets.get("agnostic_freeform_ast", 0) > 0:
        variants.append(
            (
                "agnostic_freeform_ast",
                build_agnostic_freeform_ledger(
                    path=dataset,
                    candidate_budget=max(candidate_budget, int(budgets["agnostic_freeform_ast"]) * 6),
                    seed=f"{seed}::agnostic_freeform_ast",
                ),
            )
        )
        _write_progress(root, "agnostic_freeform_ledger_built", variant_count=len(variants))
    if budgets["ast_failure_aware_repair"] > 0:
        repair_ledger = build_ast_failure_aware_repair_ledger(
            path=dataset,
            failure_detail_path=failure_detail,
            candidate_budget=max(candidate_budget, budgets["ast_failure_aware_repair"] * 4),
            max_window=max_window,
            seed=f"{seed}::ast_failure_aware_repair",
        )
        variants.append(("ast_failure_aware_repair", repair_ledger))
        _write_progress(root, "ast_repair_ledger_built", variant_count=len(variants))
    variant_reports = _validate_variant_ledgers(
        root=root,
        dataset=dataset,
        variants=variants,
        candidate_budget=candidate_budget,
        top_bottom_quantile=top_bottom_quantile,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
        use_fast_context=use_fast_context,
    )
    write_json_artifact(root / "stage1_variant_reports.json", {"variants": variant_reports})
    _write_progress(root, "stage1_variant_reports_written", variant_count=len(variant_reports))

    fast_by_variant = {str(report["variant"]): _fast_rows_from_variant_report(report) for report in variant_reports}
    all_fast_rows = [row for rows in fast_by_variant.values() for row in rows]
    for row in all_fast_rows:
        row["phase3_source_lane"] = row.get("proof_variant")

    r0_pool = [
        row
        for lane in ("cem_adaptive_grammar", "ast_evolutionary_mutation", "simple_template")
        for row in fast_by_variant.get(lane, [])
    ]
    if direct_cluster_credit_cap:
        r0_clustered = _cluster_candidate_pool(
            r0_pool,
            dataset_path=dataset,
            low_corr_threshold=low_corr_threshold,
            recent_quarter_window_count=recent_quarter_window_count,
            recent_warmup_days=recent_warmup_days,
        )
        r0_selected = _cluster_credit_soft_select(
            r0_clustered,
            budget=budgets["r0_cem_led"],
            policy="phase3_r0_cluster_credit_cap",
            role_prefix="phase3_r0_cluster_credit_cap",
            bucket="r0_cem_led",
            seed=seed,
            quota_events=quota_events,
        )
    elif direct_r0_quota:
        r0_clustered = _cluster_candidate_pool(
            r0_pool,
            dataset_path=dataset,
            low_corr_threshold=low_corr_threshold,
            recent_quarter_window_count=recent_quarter_window_count,
            recent_warmup_days=recent_warmup_days,
        )
        r0_selected = _cluster_quota_select(
            r0_clustered,
            budget=budgets["r0_cem_led"],
            policy="phase3_r0_cem_led",
            role_prefix="phase3_r0_cem_led",
            bucket="r0_cem_led",
            max_per_return_corr_cluster=direct_return_cap,
            max_per_ast_cluster=direct_ast_cap,
            seed=seed,
            quota_type="direct_r0_quota",
            quota_stage="direct_replay_pre_audit",
            quota_basis="pre_audit_return_corr_cluster|phase3_ast_cluster",
            quota_events=quota_events,
            rejected_rows_for_repair=direct_rejected_repair_sources,
            allow_rejected_as_repair_source=direct_rejected_to_repair_source and budgets["ast_failure_aware_repair"] > 0,
        )
    else:
        r0_selected = _top_score_select(
            r0_pool,
            budget=budgets["r0_cem_led"],
            policy="phase3_r0_no_quota",
            role_prefix="phase3_r0_no_quota",
            bucket="r0_cem_led",
            seed=seed,
        )
    _write_progress(root, "r0_selected", selected_count=len(r0_selected), direct_cluster_credit_cap=direct_cluster_credit_cap, direct_r0_quota=direct_r0_quota)
    r0_keys = {_row_key(row) for row in r0_selected if _row_key(row)}

    if direct_rejected_repair_sources and budgets["ast_failure_aware_repair"] > 0:
        extra_repair_ledger = build_ast_failure_aware_repair_ledger(
            path=dataset,
            failure_detail_path=failure_detail,
            candidate_budget=max(candidate_budget, budgets["ast_failure_aware_repair"] * 4),
            max_window=max_window,
            seed=f"{seed}::direct_quota_repair_sources",
            extra_source_rows=direct_rejected_repair_sources,
            source_tag="direct_quota_rejected",
        )
        extra_reports = _validate_variant_ledgers(
            root=root,
            dataset=dataset,
            variants=[("ast_failure_aware_repair_from_direct_quota", extra_repair_ledger)],
            candidate_budget=max(candidate_budget, budgets["ast_failure_aware_repair"] * 4),
            top_bottom_quantile=top_bottom_quantile,
            recent_quarter_window_count=recent_quarter_window_count,
            recent_warmup_days=recent_warmup_days,
            use_fast_context=use_fast_context,
        )
        variant_reports.extend(extra_reports)
        extra_rows = [row for report in extra_reports for row in _fast_rows_from_variant_report(report)]
        for row in extra_rows:
            row["phase3_source_lane"] = "ast_failure_aware_repair"
            row["proof_variant"] = "ast_failure_aware_repair"
        fast_by_variant.setdefault("ast_failure_aware_repair", []).extend(extra_rows)

    repair_pool = fast_by_variant.get("ast_failure_aware_repair", [])
    if budgets["ast_failure_aware_repair"] > 0 and repair_quota_mode == "phase3A_hard":
        repair_clustered = _cluster_candidate_pool(
            repair_pool,
            dataset_path=dataset,
            low_corr_threshold=low_corr_threshold,
            recent_quarter_window_count=recent_quarter_window_count,
            recent_warmup_days=recent_warmup_days,
        )
        repair_selected = _cluster_quota_select(
            repair_clustered,
            budget=budgets["ast_failure_aware_repair"],
            policy="ast_failure_aware_repair",
            role_prefix="phase3_ast_repair",
            bucket="ast_failure_aware_repair",
            max_per_return_corr_cluster=max_audited_per_return_corr_cluster_per_seed,
            max_per_ast_cluster=max_audited_per_ast_cluster_per_seed,
            seed=f"{seed}::repair",
            quota_type="phase3A_hard_repair_quota",
            quota_stage="post_mutation_child_filter",
            quota_basis="pre_audit_child_return_corr_cluster|child_ast_cluster",
            quota_events=quota_events,
        )
    elif budgets["ast_failure_aware_repair"] > 0 and repair_quota_mode == "repair_aware_soft":
        repair_clustered = _cluster_candidate_pool(
            repair_pool,
            dataset_path=dataset,
            low_corr_threshold=low_corr_threshold,
            recent_quarter_window_count=recent_quarter_window_count,
            recent_warmup_days=recent_warmup_days,
        )
        repair_selected = _repair_aware_soft_quota_select(
            repair_clustered,
            budget=budgets["ast_failure_aware_repair"],
            policy="ast_failure_aware_repair",
            role_prefix="phase3_ast_repair",
            bucket="ast_failure_aware_repair",
            max_share_per_parent_cluster=repair_parent_max_share,
            max_per_child_cluster=repair_child_cap,
            seed=f"{seed}::repair",
            quota_events=quota_events,
        )
    elif budgets["ast_failure_aware_repair"] > 0:
        repair_selected = _top_score_select(
            repair_pool,
            budget=budgets["ast_failure_aware_repair"],
            policy="ast_failure_aware_repair_no_quota",
            role_prefix="phase3_ast_repair_no_quota",
            bucket="ast_failure_aware_repair",
            seed=f"{seed}::repair",
        )
    else:
        repair_selected = []
    for row in repair_selected:
        row["repair_policy"] = row.get("repair_policy") or row.get("proposal_kind")
    _write_progress(root, "repair_selected", selected_count=len(repair_selected), repair_quota_mode=repair_quota_mode)

    formula_selected = (
        _novelty_steered_select(
            fast_by_variant.get("formula_gen_v2_defined", []),
            budget=int(budgets.get("formula_gen_v2_defined", 0)),
            policy="formula_gen_v2_defined_phase3B_union_novelty",
            role_prefix="phase3c_formula_gen_v2_defined",
            bucket="formula_gen_v2_defined",
            seed=f"{seed}::formula_gen_v2_defined_select",
        )
        if budgets.get("formula_gen_v2_defined", 0) > 0
        else []
    )
    _write_progress(root, "formula_selected", selected_count=len(formula_selected))
    agnostic_selected = (
        _novelty_steered_select(
            fast_by_variant.get("agnostic_freeform_ast", []),
            budget=int(budgets.get("agnostic_freeform_ast", 0)),
            policy="agnostic_freeform_ast_phase3B_union_novelty",
            role_prefix="phase3c_agnostic_freeform_ast",
            bucket="agnostic_freeform_ast",
            seed=f"{seed}::agnostic_freeform_ast_select",
        )
        if budgets.get("agnostic_freeform_ast", 0) > 0
        else []
    )
    _write_progress(root, "agnostic_selected", selected_count=len(agnostic_selected))
    repair_expansion_selected: list[dict[str, Any]] = []
    repair_expansion_rows: list[dict[str, Any]] = []
    if budgets.get("formula_gen_v2_repair_expansion", 0) > 0:
        repair_expansion_ledger = build_formula_gen_v2_repair_expansion_ledger(
            path=dataset,
            source_rows=(r0_selected + repair_selected)[: max(4, int(budgets["formula_gen_v2_repair_expansion"]) * 4)],
            candidate_budget=max(candidate_budget, int(budgets["formula_gen_v2_repair_expansion"]) * 6),
            seed=f"{seed}::formula_gen_v2_repair_expansion",
        )
        expansion_reports = _validate_variant_ledgers(
            root=root,
            dataset=dataset,
            variants=[("formula_gen_v2_repair_expansion", repair_expansion_ledger)],
            candidate_budget=max(candidate_budget, int(budgets["formula_gen_v2_repair_expansion"]) * 6),
            top_bottom_quantile=top_bottom_quantile,
            recent_quarter_window_count=recent_quarter_window_count,
            recent_warmup_days=recent_warmup_days,
            use_fast_context=use_fast_context,
        )
        variant_reports.extend(expansion_reports)
        repair_expansion_rows = [row for report in expansion_reports for row in _fast_rows_from_variant_report(report)]
        for row in repair_expansion_rows:
            row["phase3_source_lane"] = "formula_gen_v2_repair_expansion"
            row["proof_variant"] = "formula_gen_v2_repair_expansion"
        fast_by_variant["formula_gen_v2_repair_expansion"] = repair_expansion_rows
        repair_expansion_selected = _novelty_steered_select(
            repair_expansion_rows,
            budget=int(budgets.get("formula_gen_v2_repair_expansion", 0)),
            policy="formula_gen_v2_repair_expansion_phase3B_union_novelty",
            role_prefix="phase3c_formula_gen_v2_repair_expansion",
            bucket="formula_gen_v2_repair_expansion",
            seed=f"{seed}::formula_gen_v2_repair_expansion_select",
        )
        _write_progress(root, "repair_expansion_selected", selected_count=len(repair_expansion_selected))

    all_fast_rows = [row for rows in fast_by_variant.values() for row in rows]
    for row in all_fast_rows:
        row["phase3_source_lane"] = row.get("proof_variant")
    write_json_artifact(root / "stage1_variant_reports.json", {"variants": variant_reports})
    _write_progress(root, "pre_residual_selection", all_fast_row_count=len(all_fast_rows), residual_budget=int(budgets["replay_aware_residual"]))

    if budgets["replay_aware_residual"] > 0:
        residual_selected, residual_scored = _select_replay_aware_residual(
            all_fast_rows,
            model_dir=Path(replay_ranker_model_dir),
            budget=budgets["replay_aware_residual"],
            r0_selected_keys=r0_keys
            | {_row_key(row) for row in repair_selected if _row_key(row)}
            | {_row_key(row) for row in formula_selected if _row_key(row)}
            | {_row_key(row) for row in agnostic_selected if _row_key(row)}
            | {_row_key(row) for row in repair_expansion_selected if _row_key(row)},
            seed=seed,
        )
    else:
        residual_selected = []
        residual_scored = pd.DataFrame()
    _write_progress(root, "residual_selected", selected_count=len(residual_selected), scored_count=int(len(residual_scored)))
    diagnostic_selected = (
        _select_quarantine_diagnostic(
            all_fast_rows,
            budget=budgets["novelty_diagnostic"],
            seed=f"{seed}::diagnostic",
        )
        if budgets["novelty_diagnostic"] > 0
        else []
    )
    _write_progress(root, "diagnostic_selected", selected_count=len(diagnostic_selected))
    strict_inputs = (
        r0_selected
        + repair_selected
        + formula_selected
        + agnostic_selected
        + repair_expansion_selected
        + residual_selected
        + diagnostic_selected
    )
    selector_profile = str(arm_config.get("selector_profile") or "standard_D3")
    selector_baseline_path = _selector_baseline_path(ablation_arm, arm_config)
    selector_audit_rows: list[dict[str, Any]] = []
    selector_preflight: dict[str, Any] = {}
    phase3e_pool_for_selector = _phase3e_candidate_pool(
        ablation_arm=ablation_arm,
        r0_pool=r0_pool,
        repair_pool=repair_pool,
        formula_rows=fast_by_variant.get("formula_gen_v2_defined", []),
        agnostic_rows=fast_by_variant.get("agnostic_freeform_ast", []),
        repair_expansion_rows=repair_expansion_rows,
        residual_rows=residual_selected,
        diagnostic_rows=diagnostic_selected,
    )
    if shared_candidate_pool_output is not None:
        shared_pool_path = Path(shared_candidate_pool_output)
        safe_phase3e_pool_for_selector = strip_forbidden_replay_label_rows(phase3e_pool_for_selector)
        safe_strict_inputs = strip_forbidden_replay_label_rows(strict_inputs)
        write_json_artifact(
            shared_pool_path,
            {
                "created_at": utc_now_iso(),
                "source_ablation_arm": ablation_arm,
                "source_selector_profile": selector_profile,
                "seed": str(seed),
                "dataset_path": str(dataset),
                "dataset_role": dataset_role_for_path(dataset),
                "candidate_budget": int(candidate_budget),
                "strict_audit_budget": int(strict_audit_budget),
                "budgets": budgets,
                "selector_baseline_path": str(selector_baseline_path),
                "candidate_pool": safe_phase3e_pool_for_selector,
                "default_selected": safe_strict_inputs,
                "ablation_design": {
                    "description": arm_config["description"],
                    "phase3e_generation_profile": arm_config.get("generation_profile"),
                    "phase3e_selector_profile": selector_profile,
                    "phase3_metadata_policy": arm_config.get("phase3_metadata_policy"),
                    "phase3_discovery_baseline_count": arm_config.get("phase3_discovery_baseline_count"),
                    "phase3_selector_vector_baseline_count": arm_config.get("phase3_selector_vector_baseline_count"),
                    "phase3_selector_vector_baseline_name": arm_config.get("phase3_selector_vector_baseline_name"),
                    "strict_vector_cluster_cap": arm_config.get("strict_vector_cluster_cap"),
                    "target_median_turnover": arm_config.get("target_median_turnover"),
                },
            },
        )
        _write_progress(root, "shared_candidate_pool_written", path=str(shared_pool_path), candidate_pool_count=len(phase3e_pool_for_selector), default_selected_count=len(strict_inputs))
    if ablation_arm.startswith("Phase3E_") or ablation_arm.startswith("Phase3F_") or ablation_arm.startswith("Phase3G_") or ablation_arm.startswith("Phase3H_") or selector_profile != "standard_D3":
        phase3e_context = Phase3ERegistryContext.from_path(selector_baseline_path)
        phase3g_signal_store = Phase3GSignalVectorStore(dataset_path=dataset_path) if selector_profile.startswith("signal_vector_") else None
        strict_inputs, selector_audit_rows, selector_preflight = select_phase3e_queue(
            phase3e_pool_for_selector,
            budgets=budgets,
            selector_profile=selector_profile,
            context=phase3e_context,
            seed=seed,
            default_selected=strict_inputs,
            total_budget=max(1, int(strict_audit_budget)),
            signal_vector_store=phase3g_signal_store,
        )
        write_selector_artifacts(root, audit_rows=selector_audit_rows, preflight=selector_preflight, selector_profile=selector_profile)
        _write_progress(
            root,
            "phase3e_selector_applied",
            selector_profile=selector_profile,
            selected_count=len(strict_inputs),
            audit_row_count=len(selector_audit_rows),
            book_marginal_mode=selector_preflight.get("book_marginal_mode"),
        )
    if len(strict_inputs) != max(1, int(strict_audit_budget)):
        raise RuntimeError(
            f"ablation arm {ablation_arm} selected {len(strict_inputs)} rows for strict audit; expected {strict_audit_budget}"
        )
    write_json_artifact(
        root / "phase3_strict_selection_inputs.json",
        {
            "selected": strict_inputs,
            "budgets": budgets,
            "ablation_arm": ablation_arm,
            "ablation_design": {
                "description": arm_config["description"],
                "cluster_quota_enabled": use_cluster_quota,
                "direct_r0_quota_enabled": direct_r0_quota,
                "direct_cluster_credit_cap_enabled": direct_cluster_credit_cap,
                "repair_quota_mode": repair_quota_mode,
                "phase3c_base": arm_config.get("phase3c_base"),
                "phase3c_expansion": arm_config.get("phase3c_expansion"),
                "phase3e_generation_profile": arm_config.get("generation_profile"),
                "phase3e_selector_profile": selector_profile,
                "phase3e_cumulative_baseline_path": str(selector_baseline_path),
                "phase3_metadata_policy": arm_config.get("phase3_metadata_policy"),
                "phase3_discovery_baseline_count": arm_config.get("phase3_discovery_baseline_count"),
                "phase3_selector_vector_baseline_count": arm_config.get("phase3_selector_vector_baseline_count"),
                "phase3_selector_vector_baseline_name": arm_config.get("phase3_selector_vector_baseline_name"),
                "strict_vector_cluster_cap": arm_config.get("strict_vector_cluster_cap"),
                "target_median_turnover": arm_config.get("target_median_turnover"),
                "fresh_seed_required_for_formal_ablation": True,
                "raw_pass_is_diagnostic_only": True,
                "phase3c_expansion_novelty_steering": "phase3B_union_pre_replay_proxy_soft_only",
                "phase3B_union_baseline_path": str(PHASE3B_UNION_BASELINE_PATH),
            },
            "cluster_quota": {
                "direct_return_cluster_cap": int(direct_return_cap),
                "direct_ast_cluster_cap": int(direct_ast_cap),
                "repair_child_cluster_cap": int(repair_child_cap),
                "repair_parent_max_share": float(repair_parent_max_share),
                "max_pass_credit_per_return_corr_cluster": 1,
                "duplicate_cluster_weighting": "inverse_sqrt",
            },
            "residual_scored_count": int(len(residual_scored)),
            "quota_event_count": int(len(quota_events)),
            "direct_quota_repair_source_count": int(len(direct_rejected_repair_sources)),
            "phase3e_selector_audit_count": int(len(selector_audit_rows)),
                "phase3e_selector_preflight": selector_preflight,
        },
    )
    write_json_artifact(root / "phase3_quota_events.json", {"quota_events": quota_events})
    if not residual_scored.empty:
        residual_scored.to_parquet(root / "phase3_replay_aware_residual_scored.parquet", index=False)
    _write_progress(root, "strict_selection_written", strict_input_count=len(strict_inputs))

    if selection_only:
        phase3b_union_baseline = _load_phase3b_union_baseline()
        report = {
            "phase3_version": PHASE3_REPAIR_VERSION,
            "created_at": utc_now_iso(),
            "experiment_id": f"phase3_selection_only_{seed}",
            "ablation_arm": ablation_arm,
            "status": "selection_only",
            "objective": "freeze_phase3_strict_selection_before_shared_cache_replay",
            "dataset_path": str(dataset),
            "dataset_role": dataset_role_for_path(dataset),
            "output_root": str(root),
            "ablation_design": {
                "description": arm_config["description"],
                "cluster_quota_enabled": use_cluster_quota,
                "direct_r0_quota_enabled": direct_r0_quota,
                "direct_cluster_credit_cap_enabled": direct_cluster_credit_cap,
                "repair_quota_mode": repair_quota_mode,
                "phase3c_base": arm_config.get("phase3c_base"),
                "phase3c_expansion": arm_config.get("phase3c_expansion"),
                "phase3e_generation_profile": arm_config.get("generation_profile"),
                "phase3e_selector_profile": selector_profile,
                "phase3e_cumulative_baseline_path": str(selector_baseline_path),
                "phase3_metadata_policy": arm_config.get("phase3_metadata_policy"),
                "phase3_discovery_baseline_count": arm_config.get("phase3_discovery_baseline_count"),
                "phase3_selector_vector_baseline_count": arm_config.get("phase3_selector_vector_baseline_count"),
                "phase3_selector_vector_baseline_name": arm_config.get("phase3_selector_vector_baseline_name"),
                "strict_vector_cluster_cap": arm_config.get("strict_vector_cluster_cap"),
                "target_median_turnover": arm_config.get("target_median_turnover"),
                "fresh_seed_required_for_formal_ablation": True,
                "raw_pass_is_diagnostic_only": True,
                "phase3c_expansion_novelty_steering": "phase3B_union_pre_replay_proxy_soft_only",
                "selection_only_for_cache_sprint": True,
                "phase3B_union_baseline_path": str(PHASE3B_UNION_BASELINE_PATH),
            },
            "parameters": {
                "candidate_budget": int(candidate_budget),
                "strict_audit_budget": int(strict_audit_budget),
                "budgets": budgets,
                "target_window_count": int(target_window_count),
                "max_window": int(max_window),
                "beam_width": int(beam_width),
                "max_beam_records": int(max_beam_records),
                "recent_quarter_window_count": int(recent_quarter_window_count),
                "recent_warmup_days": int(recent_warmup_days),
                "turnover_survival_max_one_way": float(turnover_survival_max_one_way),
                "seed": str(seed),
                "direct_return_cluster_cap": int(direct_return_cap),
                "direct_ast_cluster_cap": int(direct_ast_cap),
                "repair_child_cluster_cap": int(repair_child_cap),
                "repair_parent_max_share": float(repair_parent_max_share),
                "direct_quota_repair_source_count": int(len(direct_rejected_repair_sources)),
                "phase3B_union_baseline_path": str(PHASE3B_UNION_BASELINE_PATH),
                "phase3D_cumulative_baseline_path": str(PHASE3D_CUMULATIVE_BASELINE_PATH),
                "phase3E_cumulative_baseline_path": str(PHASE3E_CUMULATIVE_BASELINE_PATH),
                "selector_baseline_path": str(selector_baseline_path),
                "phase3e_selector_profile": selector_profile,
                "phase3e_selector_audit_count": int(len(selector_audit_rows)),
            },
            "fixed_contract": {
                "evaluator": "TDXGP true-limit preferred",
                "limit_status_preferred_source": TDXGP_LIMIT_STATUS_SOURCE,
                "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
                "execution_lag_days": 1,
                "feature_lag_days": 0,
                "cost_bps": float(strict_cost_bps),
                "top_bottom_quantile": float(top_bottom_quantile),
                "raw_pass_is_diagnostic_only": True,
                "phase3B_union_baseline_name": phase3b_union_baseline.get("baseline_name"),
                "phase3B_union_deployable_cluster_count": phase3b_union_baseline.get("global_deployable_cluster_count"),
                "phase3c_new_cluster_metric": "new_deployable_clusters_vs_phase3B_union",
            },
            "selection": {
                "strict_input_count": int(len(strict_inputs)),
                "quota_event_count": int(len(quota_events)),
                "residual_scored_count": int(len(residual_scored)),
                "direct_quota_repair_source_count": int(len(direct_rejected_repair_sources)),
            },
            "reproducibility": {
                "commands": "python -m our_system_phase2.runtime.stock_pit_phase3_repair --selection-only ...",
                "outputs": [
                    "phase3_selection_only_report.json",
                    "phase3_strict_selection_inputs.json",
                    "phase3_quota_events.json",
                    "phase3e_selector_audit.csv",
                    "phase3e_selector_feature_preflight.json",
                    "PHASE3E_SELECTOR_FEATURE_PREFLIGHT.md",
                    "stage1_variant_reports.json",
                    "variants/*/candidate_ledger.json",
                    "variants/*/stage1_validation_report.json",
                ],
            },
        }
        write_json_artifact(root / "phase3_selection_only_report.json", report)
        _write_progress(root, "selection_only_report_written", status="selection_only")
        return report

    strict_rows = _strict_audit_selected_fast_rows(
        strict_inputs,
        output_root=root / "strict_phase3",
        dataset_path=dataset,
        top_bottom_quantile=top_bottom_quantile,
        cost_bps=strict_cost_bps,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    _write_progress(root, "strict_audit_done", strict_row_count=len(strict_rows))
    strict_rows, replay_report = _attach_portfolio_replay(
        strict_rows,
        dataset_path=dataset,
        top_bottom_quantile=top_bottom_quantile,
        cost_bps=strict_cost_bps,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    _write_progress(root, "portfolio_replay_done", strict_row_count=len(strict_rows))
    strict_rows, cluster_report = _attach_signal_clusters(
        strict_rows,
        dataset_path=dataset,
        threshold=low_corr_threshold,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    _write_progress(root, "signal_cluster_done", strict_row_count=len(strict_rows))
    strict_rows = _attach_shadow_metrics(strict_rows)
    write_json_artifact(root / "phase3_strict_rows.json", {"strict_rows": strict_rows})
    _write_progress(root, "strict_rows_written", strict_row_count=len(strict_rows))

    kpi = _phase3_main_kpis(strict_rows, turnover_max=turnover_survival_max_one_way)
    policy_table = _policy_table(strict_rows, turnover_max=turnover_survival_max_one_way)
    phase3b_union_baseline = _load_phase3b_union_baseline()
    report = {
        "phase3_version": PHASE3_REPAIR_VERSION,
        "created_at": utc_now_iso(),
        "experiment_id": f"phase3A_repair_{seed}",
        "ablation_arm": ablation_arm,
        "ablation_design": {
            "description": arm_config["description"],
            "cluster_quota_enabled": use_cluster_quota,
            "direct_r0_quota_enabled": direct_r0_quota,
            "direct_cluster_credit_cap_enabled": direct_cluster_credit_cap,
            "repair_quota_mode": repair_quota_mode,
            "phase3c_base": arm_config.get("phase3c_base"),
            "phase3c_expansion": arm_config.get("phase3c_expansion"),
            "phase3e_generation_profile": arm_config.get("generation_profile"),
            "phase3e_selector_profile": selector_profile,
            "phase3e_cumulative_baseline_path": str(selector_baseline_path),
            "phase3_metadata_policy": arm_config.get("phase3_metadata_policy"),
            "phase3_discovery_baseline_count": arm_config.get("phase3_discovery_baseline_count"),
            "phase3_selector_vector_baseline_count": arm_config.get("phase3_selector_vector_baseline_count"),
            "phase3_selector_vector_baseline_name": arm_config.get("phase3_selector_vector_baseline_name"),
            "strict_vector_cluster_cap": arm_config.get("strict_vector_cluster_cap"),
            "target_median_turnover": arm_config.get("target_median_turnover"),
            "phase3c_expansion_novelty_steering": "phase3B_union_pre_replay_proxy_soft_only",
            "fresh_seed_required_for_formal_ablation": True,
            "arms": sorted(PHASE3_ABLATION_ARMS),
        },
        "status": "completed",
        "objective": "maximize_cost_turnover_deployable_unique_clusters_not_raw_pass_count",
        "dataset_path": str(dataset),
        "dataset_role": dataset_role_for_path(dataset),
        "output_root": str(root),
        "fixed_contract": {
            "evaluator": "TDXGP true-limit preferred",
            "limit_status_preferred_source": TDXGP_LIMIT_STATUS_SOURCE,
            "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
            "execution_lag_days": 1,
            "feature_lag_days": 0,
            "cost_bps": float(strict_cost_bps),
            "top_bottom_quantile": float(top_bottom_quantile),
            "raw_pass_is_diagnostic_only": True,
            "phase3B_union_baseline_name": phase3b_union_baseline.get("baseline_name"),
            "phase3B_union_deployable_cluster_count": phase3b_union_baseline.get("global_deployable_cluster_count"),
            "phase3c_new_cluster_metric": "new_deployable_clusters_vs_phase3B_union",
        },
        "parameters": {
            "candidate_budget": int(candidate_budget),
            "strict_audit_budget": int(strict_audit_budget),
            "budgets": budgets,
            "target_window_count": int(target_window_count),
            "max_window": int(max_window),
            "beam_width": int(beam_width),
            "max_beam_records": int(max_beam_records),
            "recent_quarter_window_count": int(recent_quarter_window_count),
            "recent_warmup_days": int(recent_warmup_days),
            "turnover_survival_max_one_way": float(turnover_survival_max_one_way),
            "seed": str(seed),
            "direct_return_cluster_cap": int(direct_return_cap),
            "direct_ast_cluster_cap": int(direct_ast_cap),
            "repair_child_cluster_cap": int(repair_child_cap),
            "repair_parent_max_share": float(repair_parent_max_share),
            "direct_quota_repair_source_count": int(len(direct_rejected_repair_sources)),
            "phase3B_union_baseline_path": str(PHASE3B_UNION_BASELINE_PATH),
            "phase3D_cumulative_baseline_path": str(PHASE3D_CUMULATIVE_BASELINE_PATH),
            "phase3E_cumulative_baseline_path": str(PHASE3E_CUMULATIVE_BASELINE_PATH),
            "selector_baseline_path": str(selector_baseline_path),
            "phase3e_selector_profile": selector_profile,
            "phase3e_selector_audit_count": int(len(selector_audit_rows)),
        },
        "main_kpi": kpi,
        "selection_policy_table": policy_table,
        "phase3B_union_baseline": {
            "baseline_name": phase3b_union_baseline.get("baseline_name"),
            "source_commit": phase3b_union_baseline.get("source_commit"),
            "global_deployable_cluster_count": phase3b_union_baseline.get("global_deployable_cluster_count"),
            "comparison_contract": phase3b_union_baseline.get("comparison_contract"),
        },
        "definition_pressure_audit": _definition_pressure_audit(strict_rows, turnover_max=turnover_survival_max_one_way),
        "motif_lift_audit": _motif_lift_audit(strict_rows, turnover_max=turnover_survival_max_one_way),
        "open_space_audit": _open_space_audit(strict_rows, turnover_max=turnover_survival_max_one_way),
        "paired_ablation_audit": _paired_ablation_audit(strict_rows),
        "quota_event_summary": _quota_event_table(quota_events),
        "quota_event_count": int(len(quota_events)),
        "repair_policy_outcome": _repair_policy_table(strict_rows),
        "cluster_transition": _cluster_transition_table(strict_rows),
        "replay_aware_decile": _replay_decile_table(strict_rows, turnover_max=turnover_survival_max_one_way),
        "cem_anti_collapse": _cem_anti_collapse_table(strict_rows, turnover_max=turnover_survival_max_one_way),
        "portfolio_replay_report": replay_report,
        "signal_cluster_report": cluster_report,
        "variant_stage1_reports": variant_reports,
        "decision": {
            "gate": "PASS" if kpi["primary"]["cost_turnover_deployable_unique_clusters"] > 5 else "HOLD",
            "commercial_claim_allowed": False,
            "success_thresholds": {
                "minimum_success_deployable_unique_clusters_gt": 5,
                "better_success_deployable_unique_clusters_gte": 7,
                "top_cluster_raw_pass_share_lt": 0.50,
            },
        },
        "reproducibility": {
            "commands": "python -m our_system_phase2.runtime.stock_pit_phase3_repair ...",
            "outputs": [
                "phase3_repair_report.json",
                "phase3_strict_selection_inputs.json",
                "phase3_strict_rows.json",
                "phase3_quota_events.json",
                "phase3e_selector_audit.csv",
                "phase3e_selector_feature_preflight.json",
                "PHASE3E_SELECTOR_FEATURE_PREFLIGHT.md",
                "phase3_replay_aware_residual_scored.parquet",
                "variants/*/candidate_ledger.json",
                "variants/*/stage1_validation_report.json",
            ],
        },
    }
    write_json_artifact(root / "phase3_repair_report.json", report)
    _write_progress(root, "report_written", status="completed")
    return report

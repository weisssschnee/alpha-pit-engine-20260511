from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from our_system_phase2.domain.models import utc_now_iso
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


def _stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


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
    raise ValueError(f"unknown Phase3 ablation arm: {arm}")


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
) -> dict[str, Any]:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    dataset = Path(dataset_path)
    failure_detail = Path(failure_detail_path)
    if ablation_arm not in PHASE3_ABLATION_ARMS:
        raise ValueError(f"unknown Phase3 ablation arm: {ablation_arm}")
    arm_config = dict(PHASE3_ABLATION_ARMS[ablation_arm])
    use_cluster_quota = bool(arm_config["cluster_quota"])
    direct_r0_quota = bool(arm_config.get("direct_r0_quota", use_cluster_quota))
    repair_quota_mode = str(arm_config.get("repair_quota_mode", "phase3A_hard" if use_cluster_quota else "none"))
    direct_return_cap = int(arm_config.get("direct_return_cluster_cap", max_audited_per_return_corr_cluster_per_seed))
    direct_ast_cap = int(arm_config.get("direct_ast_cluster_cap", max_audited_per_ast_cluster_per_seed))
    repair_child_cap = int(arm_config.get("repair_child_cluster_cap", max_audited_per_ast_cluster_per_seed))
    repair_parent_max_share = float(arm_config.get("repair_parent_max_share", 0.35))
    direct_rejected_to_repair_source = bool(arm_config.get("direct_rejected_to_repair_source", False))
    quota_events: list[dict[str, Any]] = []
    direct_rejected_repair_sources: list[dict[str, Any]] = []
    budgets = _ablation_budgets(strict_audit_budget, ablation_arm)

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
    if budgets["ast_failure_aware_repair"] > 0:
        repair_ledger = build_ast_failure_aware_repair_ledger(
            path=dataset,
            failure_detail_path=failure_detail,
            candidate_budget=max(candidate_budget, budgets["ast_failure_aware_repair"] * 4),
            max_window=max_window,
            seed=f"{seed}::ast_failure_aware_repair",
        )
        variants.append(("ast_failure_aware_repair", repair_ledger))
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

    fast_by_variant = {str(report["variant"]): _fast_rows_from_variant_report(report) for report in variant_reports}
    all_fast_rows = [row for rows in fast_by_variant.values() for row in rows]
    for row in all_fast_rows:
        row["phase3_source_lane"] = row.get("proof_variant")

    r0_pool = [
        row
        for lane in ("cem_adaptive_grammar", "ast_evolutionary_mutation", "simple_template")
        for row in fast_by_variant.get(lane, [])
    ]
    if direct_r0_quota:
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

    all_fast_rows = [row for rows in fast_by_variant.values() for row in rows]
    for row in all_fast_rows:
        row["phase3_source_lane"] = row.get("proof_variant")
    write_json_artifact(root / "stage1_variant_reports.json", {"variants": variant_reports})

    if budgets["replay_aware_residual"] > 0:
        residual_selected, residual_scored = _select_replay_aware_residual(
            all_fast_rows,
            model_dir=Path(replay_ranker_model_dir),
            budget=budgets["replay_aware_residual"],
            r0_selected_keys=r0_keys | {_row_key(row) for row in repair_selected if _row_key(row)},
            seed=seed,
        )
    else:
        residual_selected = []
        residual_scored = pd.DataFrame()
    diagnostic_selected = (
        _select_quarantine_diagnostic(
            all_fast_rows,
            budget=budgets["novelty_diagnostic"],
            seed=f"{seed}::diagnostic",
        )
        if budgets["novelty_diagnostic"] > 0
        else []
    )
    strict_inputs = r0_selected + repair_selected + residual_selected + diagnostic_selected
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
                "repair_quota_mode": repair_quota_mode,
                "fresh_seed_required_for_formal_ablation": True,
                "raw_pass_is_diagnostic_only": True,
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
        },
    )
    write_json_artifact(root / "phase3_quota_events.json", {"quota_events": quota_events})
    if not residual_scored.empty:
        residual_scored.to_parquet(root / "phase3_replay_aware_residual_scored.parquet", index=False)

    strict_rows = _strict_audit_selected_fast_rows(
        strict_inputs,
        output_root=root / "strict_phase3",
        dataset_path=dataset,
        top_bottom_quantile=top_bottom_quantile,
        cost_bps=strict_cost_bps,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    strict_rows, replay_report = _attach_portfolio_replay(
        strict_rows,
        dataset_path=dataset,
        top_bottom_quantile=top_bottom_quantile,
        cost_bps=strict_cost_bps,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    strict_rows, cluster_report = _attach_signal_clusters(
        strict_rows,
        dataset_path=dataset,
        threshold=low_corr_threshold,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
    )
    strict_rows = _attach_shadow_metrics(strict_rows)
    write_json_artifact(root / "phase3_strict_rows.json", {"strict_rows": strict_rows})

    kpi = _phase3_main_kpis(strict_rows, turnover_max=turnover_survival_max_one_way)
    policy_table = _policy_table(strict_rows, turnover_max=turnover_survival_max_one_way)
    report = {
        "phase3_version": PHASE3_REPAIR_VERSION,
        "created_at": utc_now_iso(),
        "experiment_id": f"phase3A_repair_{seed}",
        "ablation_arm": ablation_arm,
        "ablation_design": {
            "description": arm_config["description"],
            "cluster_quota_enabled": use_cluster_quota,
            "direct_r0_quota_enabled": direct_r0_quota,
            "repair_quota_mode": repair_quota_mode,
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
        },
        "main_kpi": kpi,
        "selection_policy_table": policy_table,
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
                "phase3_replay_aware_residual_scored.parquet",
                "variants/*/candidate_ledger.json",
                "variants/*/stage1_validation_report.json",
            ],
        },
    }
    write_json_artifact(root / "phase3_repair_report.json", report)
    return report

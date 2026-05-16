from __future__ import annotations

import math
from typing import Any


PHASE3G_VECTOR_SELECTOR_VERSION = "phase3g-signal-vector-selector-v1-2026-05-14"
PHASE3G_SIGNAL_VECTOR_SELECTOR_PROFILES = {
    "signal_vector_diversified_proxy",
    "signal_vector_turnover_calibrated_proxy",
    "signal_vector_cost_turnover_constrained_proxy",
    "signal_vector_turnover_tail_guard_v2",
    "signal_vector_capacity_liquidity_proxy",
    "signal_vector_book_proxy_hardened",
    "signal_vector_queue_diversity_v2",
    "strong_signal_vector_proxy",
}


def is_signal_vector_selector(selector_profile: str) -> bool:
    return selector_profile in PHASE3G_SIGNAL_VECTOR_SELECTOR_PROFILES


def signal_vector_book_marginal_mode(selector_profile: str) -> str:
    return "signal_vector_proxy" if is_signal_vector_selector(selector_profile) else ""


def selected_count(selected_rows: list[dict[str, Any]], field: str, value: Any) -> int:
    if value is None or value == "":
        return 0
    return sum(1 for row in selected_rows if str(row.get(field) or "") == str(value))


def threshold_penalty(value: float | None, threshold: float | None) -> float:
    if value is None or threshold is None or threshold <= 0:
        return 0.0
    return max(0.0, float(value) / float(threshold) - 1.0)


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _count_turnover_bucket(selected_rows: list[dict[str, Any]], threshold: float | None) -> int:
    if threshold is None:
        return 0
    count = 0
    for row in selected_rows:
        value = _safe_float(row.get("turnover_proxy"))
        if value is not None and value > threshold:
            count += 1
    return count


def score_signal_vector_selector(
    selector_profile: str,
    features: dict[str, Any],
    thresholds: Any,
    *,
    selected_rows: list[dict[str, Any]],
    base_e3_score: float,
) -> tuple[float, bool, str, dict[str, Any]]:
    strengthened = selector_profile == "strong_signal_vector_proxy"
    turnover_calibrated = selector_profile == "signal_vector_turnover_calibrated_proxy"
    cost_turnover_constrained = selector_profile == "signal_vector_cost_turnover_constrained_proxy"
    turnover_tail_guard_v2 = selector_profile == "signal_vector_turnover_tail_guard_v2"
    capacity_liquidity = selector_profile == "signal_vector_capacity_liquidity_proxy"
    book_proxy_hardened = selector_profile == "signal_vector_book_proxy_hardened"
    queue_diversity_v2 = selector_profile == "signal_vector_queue_diversity_v2"
    known_cluster = str(features.get("known_signal_cluster_id") or "")
    provisional_cluster = str(features.get("provisional_signal_cluster_id") or "")
    source_lane = str(features.get("source_lane") or "")
    source_lane_cluster = f"{source_lane}|{provisional_cluster}"
    known_count = selected_count(selected_rows, "known_signal_cluster_id", known_cluster)
    provisional_count = selected_count(selected_rows, "provisional_signal_cluster_id", provisional_cluster)
    source_lane_count = selected_count(selected_rows, "source_lane_signal_cluster_id", source_lane_cluster)

    cap_reasons = []
    if known_cluster:
        if known_cluster in {"cluster_001", "cluster_003"}:
            limit = 1 if strengthened else 2
            if known_count >= limit:
                cap_reasons.append(f"{known_cluster}_signal_cap")
        else:
            limit = 2 if strengthened else 3
            if known_count >= limit:
                cap_reasons.append("known_signal_cluster_cap")
    if provisional_cluster:
        limit = 3 if strengthened or queue_diversity_v2 else 4
        if provisional_count >= limit:
            cap_reasons.append("provisional_signal_cluster_cap")
    if source_lane_cluster:
        # Keep this as a real cap, but do not let the strong profile underfill
        # small candidate pools solely because multiple lanes discover the same
        # high-confidence signal bucket.
        limit = 2
        if source_lane_count >= limit:
            cap_reasons.append("source_lane_signal_cluster_cap")

    novelty = 1.0 - float(features.get("max_corr_to_134_signal_vector") or 0.0)
    selected_corr = float(features.get("max_corr_to_selected_queue_signal") or 0.0)
    known_penalty = math.sqrt(float(known_count)) if known_cluster else 0.0
    provisional_penalty = math.sqrt(float(provisional_count)) if provisional_cluster else 0.0
    source_lane_penalty = math.sqrt(float(source_lane_count)) if source_lane_cluster else 0.0
    cluster_special_penalty = 0.0
    if known_cluster in {"cluster_001", "cluster_003"}:
        cluster_special_penalty = 2.0 * math.sqrt(float(known_count + 1))
    turnover_penalty = threshold_penalty(features.get("turnover_proxy"), getattr(thresholds, "turnover_p90", None))
    turnover_structure_penalty = float(features.get("turnover_structure_risk") or 0.0)
    turnover_value = _safe_float(features.get("turnover_proxy"))
    pool_turnover_p80 = _safe_float(features.get("selector_pool_turnover_p80"))
    pool_turnover_p90 = _safe_float(features.get("selector_pool_turnover_p90"))
    pool_turnover_p95 = _safe_float(features.get("selector_pool_turnover_p95"))
    selector_total_budget = int(float(features.get("selector_total_budget") or 64))
    high_turnover_p80_count = _count_turnover_bucket(selected_rows, pool_turnover_p80)
    high_turnover_p90_count = _count_turnover_bucket(selected_rows, pool_turnover_p90)
    turnover_tail_penalty = 0.0
    if turnover_value is not None:
        if pool_turnover_p80 is not None and turnover_value > pool_turnover_p80:
            turnover_tail_penalty += 1.0
        if pool_turnover_p90 is not None and turnover_value > pool_turnover_p90:
            turnover_tail_penalty += 2.0
        if pool_turnover_p95 is not None and turnover_value > pool_turnover_p95:
            turnover_tail_penalty += 4.0
    if turnover_tail_guard_v2 and turnover_value is not None:
        max_p80 = max(1, int(math.floor(selector_total_budget * 0.20)))
        max_p90 = max(1, int(math.floor(selector_total_budget * 0.08)))
        if pool_turnover_p95 is not None and turnover_value > pool_turnover_p95:
            cap_reasons.append("turnover_gt_pool_p95")
        if pool_turnover_p80 is not None and turnover_value > pool_turnover_p80 and high_turnover_p80_count >= max_p80:
            cap_reasons.append("turnover_pool_p80_queue_share_cap")
        if pool_turnover_p90 is not None and turnover_value > pool_turnover_p90 and high_turnover_p90_count >= max_p90:
            cap_reasons.append("turnover_pool_p90_queue_share_cap")
    complexity_penalty = threshold_penalty(float(features.get("complexity_score") or 0.0), getattr(thresholds, "complexity_p90", None))
    liquidity_proxy = float(features.get("liquidity_proxy") or 0.0)
    capacity_proxy = float(features.get("capacity_proxy") or 0.0)
    liquidity_penalty = 1.0 / max(1.0, math.log1p(max(0.0, liquidity_proxy)))
    capacity_penalty = 1.0 / max(1.0, math.log1p(max(0.0, capacity_proxy)))
    registry_symbolic_corr = float(features.get("max_corr_to_103_registry") or 0.0)

    if strengthened:
        score = (
            float(base_e3_score)
            + 0.65 * novelty
            - 1.20 * selected_corr
            - 0.70 * known_penalty
            - 0.65 * provisional_penalty
            - 0.55 * source_lane_penalty
            - 0.35 * turnover_penalty
            - 0.75 * turnover_structure_penalty
            - 0.20 * complexity_penalty
            - 0.45 * cluster_special_penalty
        )
    elif turnover_tail_guard_v2:
        score = (
            float(base_e3_score)
            + 0.40 * novelty
            - 0.95 * selected_corr
            - 0.60 * known_penalty
            - 0.50 * provisional_penalty
            - 0.40 * source_lane_penalty
            - 2.75 * turnover_tail_penalty
            - 1.25 * turnover_penalty
            - 1.60 * turnover_structure_penalty
            - 0.20 * complexity_penalty
            - 0.30 * cluster_special_penalty
        )
    elif turnover_calibrated:
        score = (
            float(base_e3_score)
            + 0.45 * novelty
            - 0.95 * selected_corr
            - 0.60 * known_penalty
            - 0.50 * provisional_penalty
            - 0.40 * source_lane_penalty
            - 0.45 * turnover_penalty
            - 1.10 * turnover_structure_penalty
            - 0.20 * complexity_penalty
            - 0.30 * cluster_special_penalty
        )
    elif cost_turnover_constrained:
        score = (
            float(base_e3_score)
            + 0.40 * novelty
            - 0.95 * selected_corr
            - 0.60 * known_penalty
            - 0.50 * provisional_penalty
            - 0.40 * source_lane_penalty
            - 0.75 * turnover_penalty
            - 1.45 * turnover_structure_penalty
            - 0.20 * complexity_penalty
            - 0.30 * cluster_special_penalty
        )
    elif capacity_liquidity:
        score = (
            float(base_e3_score)
            + 0.42 * novelty
            - 0.95 * selected_corr
            - 0.58 * known_penalty
            - 0.48 * provisional_penalty
            - 0.40 * source_lane_penalty
            - 0.35 * turnover_penalty
            - 0.70 * turnover_structure_penalty
            - 0.25 * liquidity_penalty
            - 0.25 * capacity_penalty
            - 0.18 * complexity_penalty
            - 0.30 * cluster_special_penalty
        )
    elif book_proxy_hardened:
        score = (
            float(base_e3_score)
            + 0.35 * novelty
            - 1.10 * selected_corr
            - 0.55 * registry_symbolic_corr
            - 0.65 * known_penalty
            - 0.55 * provisional_penalty
            - 0.45 * source_lane_penalty
            - 0.45 * turnover_penalty
            - 0.85 * turnover_structure_penalty
            - 0.20 * complexity_penalty
            - 0.32 * cluster_special_penalty
        )
    elif queue_diversity_v2:
        if selected_corr >= 0.95 and len(selected_rows) >= 8:
            cap_reasons.append("selected_queue_signal_corr_cap")
        score = (
            0.60 * float(base_e3_score)
            + 0.40 * novelty
            - 2.10 * selected_corr
            - 0.80 * known_penalty
            - 0.80 * provisional_penalty
            - 0.60 * source_lane_penalty
            - 0.35 * turnover_penalty
            - 0.65 * turnover_structure_penalty
            - 0.20 * complexity_penalty
            - 0.40 * cluster_special_penalty
        )
    else:
        score = (
            float(base_e3_score)
            + 0.45 * novelty
            - 0.95 * selected_corr
            - 0.60 * known_penalty
            - 0.50 * provisional_penalty
            - 0.40 * source_lane_penalty
            - 0.30 * turnover_penalty
            - 0.65 * turnover_structure_penalty
            - 0.20 * complexity_penalty
            - 0.30 * cluster_special_penalty
        )
    details = {
        "base_e3_score": round(float(base_e3_score), 8),
        "source_lane_signal_cluster_id": source_lane_cluster,
        "known_signal_cluster_count_before_pick": known_count,
        "provisional_signal_cluster_count_before_pick": provisional_count,
        "source_lane_signal_cluster_count_before_pick": source_lane_count,
        "vector_diversity_penalty": round(float(selected_corr), 6),
        "known_signal_cluster_penalty": round(float(known_penalty), 6),
        "provisional_signal_cluster_penalty": round(float(provisional_penalty), 6),
        "source_lane_signal_cluster_penalty": round(float(source_lane_penalty), 6),
        "cluster_001_signal_penalty": round(float(cluster_special_penalty if known_cluster == "cluster_001" else 0.0), 6),
        "cluster_003_signal_penalty": round(float(cluster_special_penalty if known_cluster == "cluster_003" else 0.0), 6),
        "turnover_penalty": round(float(turnover_penalty), 6),
        "turnover_structure_penalty": round(float(turnover_structure_penalty), 6),
        "selector_pool_turnover_p80": round(float(pool_turnover_p80), 6) if pool_turnover_p80 is not None else "",
        "selector_pool_turnover_p90": round(float(pool_turnover_p90), 6) if pool_turnover_p90 is not None else "",
        "selector_pool_turnover_p95": round(float(pool_turnover_p95), 6) if pool_turnover_p95 is not None else "",
        "high_turnover_p80_count_before_pick": high_turnover_p80_count,
        "high_turnover_p90_count_before_pick": high_turnover_p90_count,
        "turnover_tail_penalty": round(float(turnover_tail_penalty), 6),
        "liquidity_proxy": round(float(liquidity_proxy), 6),
        "capacity_proxy": round(float(capacity_proxy), 6),
        "liquidity_penalty": round(float(liquidity_penalty), 6),
        "capacity_penalty": round(float(capacity_penalty), 6),
        "registry_symbolic_corr_penalty": round(float(registry_symbolic_corr), 6),
        "complexity_penalty": round(float(complexity_penalty), 6),
        "cap_reject_reason": "|".join(cap_reasons),
        "selector_mode": selector_profile,
        "book_marginal_mode": "signal_vector_proxy",
    }
    hard_pass = not cap_reasons and not bool(features.get("operator_pathology_flag"))
    reject_reason = "|".join(cap_reasons or (["operator_pathology"] if bool(features.get("operator_pathology_flag")) else []))
    return round(score, 8), hard_pass, reject_reason, details

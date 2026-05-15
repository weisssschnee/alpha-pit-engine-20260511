from __future__ import annotations

import math
from typing import Any


PHASE3G_VECTOR_SELECTOR_VERSION = "phase3g-signal-vector-selector-v1-2026-05-14"
PHASE3G_SIGNAL_VECTOR_SELECTOR_PROFILES = {
    "signal_vector_diversified_proxy",
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


def score_signal_vector_selector(
    selector_profile: str,
    features: dict[str, Any],
    thresholds: Any,
    *,
    selected_rows: list[dict[str, Any]],
    base_e3_score: float,
) -> tuple[float, bool, str, dict[str, Any]]:
    strengthened = selector_profile == "strong_signal_vector_proxy"
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
        limit = 3 if strengthened else 4
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
    complexity_penalty = threshold_penalty(float(features.get("complexity_score") or 0.0), getattr(thresholds, "complexity_p90", None))

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
        "complexity_penalty": round(float(complexity_penalty), 6),
        "cap_reject_reason": "|".join(cap_reasons),
        "selector_mode": "signal_vector_diversified_proxy",
        "book_marginal_mode": "signal_vector_proxy",
    }
    hard_pass = not cap_reasons and not bool(features.get("operator_pathology_flag"))
    reject_reason = "|".join(cap_reasons or (["operator_pathology"] if bool(features.get("operator_pathology_flag")) else []))
    return round(score, 8), hard_pass, reject_reason, details

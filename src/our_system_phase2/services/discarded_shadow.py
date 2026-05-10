from __future__ import annotations

from statistics import mean
from typing import Any

from our_system_phase2.domain.models import CandidateRecord, utc_now_iso
from our_system_phase2.services.edge_reality import evaluate_edge_reality


def _discard_reason(record: CandidateRecord) -> str:
    if record.retained:
        return "retained"
    metadata = record.metadata or {}
    if metadata.get("level0_rejected"):
        return "surrogate_level0_rejected_then_archive_discarded"
    if metadata.get("level1_rejected"):
        return "short_ic_level1_rejected_then_archive_discarded"
    if metadata.get("level2_rejected"):
        return "regime_level2_rejected_then_archive_discarded"
    return "archive_dominance_or_cell_replacement"


def _rank_key(item: dict[str, Any]) -> tuple[bool, float, float, float]:
    return (
        bool(item["passes_reality_proxy"]),
        float(item["net_edge_score"]),
        float(item["activity_proxy"]),
        float(item["liquidity_proxy"]),
    )


def build_discarded_space_shadow_report(
    *,
    run_id: str,
    records: list[CandidateRecord],
    sample_limit: int = 32,
) -> dict[str, Any]:
    """Build a report-only shadow archive over generated candidates rejected by the archive.

    This intentionally does not modify archive retention. Its job is to preserve
    evidence for the reverse experiment: whether a behavior-dominance discard
    might still look more tradeable under the friction-aware edge proxy.
    """
    generated = [record for record in records if record.round_index > 0]
    retained = [record for record in generated if record.retained]
    discarded = [record for record in generated if not record.retained]

    retained_evaluations = [evaluate_edge_reality(record) for record in retained]
    discarded_evaluations = []
    for record in discarded:
        discarded_evaluations.append(
            {
                **evaluate_edge_reality(record),
                "discard_reason": _discard_reason(record),
                "candidate_label": record.label,
                "ic_max": record.ic_max,
                "ic_positive_coverage": record.ic_positive_coverage,
            }
        )

    retained_best = max((item["net_edge_score"] for item in retained_evaluations), default=None)
    discarded_best = max((item["net_edge_score"] for item in discarded_evaluations), default=None)
    ranked_discarded = sorted(discarded_evaluations, key=_rank_key, reverse=True)
    top_discarded = ranked_discarded[:sample_limit]

    shadow_cell_index: dict[str, dict[str, Any]] = {}
    for item in ranked_discarded:
        cell = str(item["archive_cell"])
        if cell not in shadow_cell_index:
            shadow_cell_index[cell] = item

    counterfactual_hits = [
        item
        for item in top_discarded
        if item["passes_reality_proxy"] or (retained_best is not None and item["net_edge_score"] > retained_best)
    ]

    lane_counts: dict[str, dict[str, Any]] = {}
    for item in discarded_evaluations:
        lane = str(item["frontier_lane"])
        current = lane_counts.setdefault(
            lane,
            {
                "discarded_count": 0,
                "reality_proxy_pass_count": 0,
                "best_net_edge_score": None,
            },
        )
        current["discarded_count"] += 1
        current["reality_proxy_pass_count"] += 1 if item["passes_reality_proxy"] else 0
        best = current["best_net_edge_score"]
        if best is None or item["net_edge_score"] > best:
            current["best_net_edge_score"] = item["net_edge_score"]

    if counterfactual_hits:
        recommendation = "review_archive_dominance_against_edge_proxy_before_tightening_filters"
    elif any(item["passes_reality_proxy"] for item in discarded_evaluations):
        recommendation = "monitor_discarded_reality_proxy_passes_without_changing_retention"
    else:
        recommendation = "no_discarded_edge_proxy_found_in_sample"

    return {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "scope": "report_only_shadow_archive_does_not_change_archive_retention",
        "question": "could archive-discarded candidates contain stronger edge-reality proxies than retained candidates",
        "does_not_change_archive_retention": True,
        "not_claiming_tradable_alpha": True,
        "generated_candidate_count": len(generated),
        "retained_candidate_count": len(retained),
        "discarded_candidate_count": len(discarded),
        "sample_limit": sample_limit,
        "shadow_archive_cell_count": len(shadow_cell_index),
        "retained_best_net_edge_score": retained_best,
        "discarded_best_net_edge_score": discarded_best,
        "retained_mean_net_edge_score": round(mean(item["net_edge_score"] for item in retained_evaluations), 6)
        if retained_evaluations
        else None,
        "discarded_mean_net_edge_score": round(mean(item["net_edge_score"] for item in discarded_evaluations), 6)
        if discarded_evaluations
        else None,
        "discarded_reality_proxy_pass_count": sum(1 for item in discarded_evaluations if item["passes_reality_proxy"]),
        "counterfactual_hit_count_in_sample": len(counterfactual_hits),
        "counterfactual_hit_rule": "discarded passes reality proxy or beats retained best net_edge_score",
        "lane_counts": lane_counts,
        "recommendation": recommendation,
        "top_discarded_candidates": top_discarded,
        "shadow_archive_by_cell": list(shadow_cell_index.values())[:sample_limit],
        "counterfactual_hits": counterfactual_hits,
    }

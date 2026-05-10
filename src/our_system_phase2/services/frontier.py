from __future__ import annotations

from statistics import mean

from our_system_phase2.domain.models import CandidateRecord
from our_system_phase2.services.fingerprint import fingerprint_distance


FRONTIER_LANES = (
    "score_frontier",
    "novelty_frontier",
    "uncertainty_frontier",
    "bridge_frontier",
)


def classify_frontiers(archive: list[CandidateRecord], *, limit: int = 2) -> dict[str, list[CandidateRecord]]:
    if not archive:
        return {lane: [] for lane in FRONTIER_LANES}
    lane_limit = max(1, min(len(archive), int(limit)))
    sparse_scores = {}
    for record in archive:
        peer_distances = [
            fingerprint_distance(record.fingerprint, other.fingerprint)
            for other in archive
            if other.candidate_id != record.candidate_id
        ]
        sparse_scores[record.candidate_id] = round(mean(peer_distances), 6) if peer_distances else 1.0
    score_frontier = sorted(archive, key=lambda item: item.ic_max, reverse=True)[:lane_limit]
    novelty_frontier = sorted(archive, key=lambda item: sparse_scores[item.candidate_id], reverse=True)[:lane_limit]
    uncertainty_frontier = sorted(archive, key=lambda item: item.surrogate_uncertainty, reverse=True)[:lane_limit]
    bridge_frontier = sorted(
        archive,
        key=lambda item: (
            sparse_scores[item.candidate_id],
            item.fingerprint["predictive_of_regime_change"],
            item.fingerprint["size_tilt"],
        ),
        reverse=True,
    )[:lane_limit]
    return {
        "score_frontier": score_frontier,
        "novelty_frontier": novelty_frontier,
        "uncertainty_frontier": uncertainty_frontier,
        "bridge_frontier": bridge_frontier,
    }


def select_lane_parents(
    frontier_records: list[CandidateRecord],
    *,
    lane: str,
    allocation: int,
    revisit_counts: dict[str, int] | None = None,
) -> list[CandidateRecord]:
    if allocation <= 0 or not frontier_records:
        return []
    usage = revisit_counts or {}
    indexed = list(enumerate(frontier_records))
    if lane == "score_frontier":
        ranked = indexed
    else:
        ranked = sorted(
            indexed,
            key=lambda item: (
                usage.get(item[1].candidate_id, 0),
                item[0],
            ),
        )
    return [record for _, record in ranked[:allocation]]

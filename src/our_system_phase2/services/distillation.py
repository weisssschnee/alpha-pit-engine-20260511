from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from our_system_phase2.domain.models import CandidateRecord
from our_system_phase2.services.variation import extract_structural_skeleton


@dataclass(slots=True)
class StructuralInsight:
    motifs: list[dict[str, Any]]
    param_priors: dict[str, Any]
    behavioral_gaps: list[str]


def _extract_windows(expression: str) -> list[int]:
    values: list[int] = []
    token = ""
    for char in expression:
        if char.isdigit():
            token += char
        elif token:
            values.append(int(token))
            token = ""
    if token:
        values.append(int(token))
    return values


def distill_archive(archive: list[CandidateRecord], *, min_support: int = 2) -> StructuralInsight:
    retained = [record for record in archive if record.retained]
    motif_counts = Counter(extract_structural_skeleton(record.expression) for record in retained)
    motifs = [
        {"skeleton": skeleton, "support": count}
        for skeleton, count in motif_counts.most_common()
        if count >= min_support
    ]
    windows = [window for record in retained for window in _extract_windows(record.expression)]
    param_priors = {
        "window_values": sorted(set(windows)),
        "preferred_window": sorted(windows)[len(windows) // 2] if windows else None,
    }
    occupied = {record.archive_cell for record in retained}
    candidate_cells = {
        "high_momentum|high_size|transition|high_vol|trend",
        "high_momentum|low_size|transition|high_vol|mean_revert",
        "low_momentum|high_size|stable|low_vol|trend",
        "low_momentum|low_size|transition|high_vol|mean_revert",
    }
    behavioral_gaps = sorted(candidate_cells - occupied)
    return StructuralInsight(motifs=motifs, param_priors=param_priors, behavioral_gaps=behavioral_gaps)


def insight_to_artifact(insight: StructuralInsight) -> dict[str, Any]:
    return {
        "motifs": insight.motifs,
        "param_priors": insight.param_priors,
        "behavioral_gaps": insight.behavioral_gaps,
        "feeds_action_generator": True,
        "uses_archive_retained_records_only": True,
    }

from __future__ import annotations

from typing import Any

from our_system_phase2.domain.models import CandidateRecord


LABEL_PRIORITY = {
    "robust": 3,
    "regime_conditional": 2,
    "weak": 1,
}


def dominance_tuple(record: CandidateRecord) -> tuple[float, float, int, float]:
    return (
        float(record.ic_max),
        float(record.ic_positive_coverage),
        LABEL_PRIORITY.get(record.label, 0),
        float(record.oos_stability),
    )


def dominates(candidate: CandidateRecord, incumbent: CandidateRecord) -> bool:
    return dominance_tuple(candidate) > dominance_tuple(incumbent)


class PrototypeArchive:
    def __init__(self) -> None:
        self.records: list[CandidateRecord] = []
        self.cell_index: dict[str, CandidateRecord] = {}
        self.refined_cell_index: dict[str, CandidateRecord] = {}
        self.audit_log: list[dict[str, Any]] = []

    def update(self, candidate: CandidateRecord) -> CandidateRecord:
        incumbent = self.cell_index.get(candidate.archive_cell)
        refined_cell = (
            candidate.metadata.get("adaptive_archive_cell")
            if isinstance(candidate.metadata, dict)
            else None
        )
        refined_incumbent = self.refined_cell_index.get(str(refined_cell)) if refined_cell else None
        decision = {
            "candidate_id": candidate.candidate_id,
            "archive_cell": candidate.archive_cell,
            "adaptive_archive_cell": refined_cell,
            "candidate_dominance": {
                "ic_max": candidate.ic_max,
                "ic_positive_coverage": candidate.ic_positive_coverage,
                "oos_ic": candidate.oos_ic,
                "label": candidate.label,
                "oos_stability": candidate.oos_stability,
            },
            "used_scalar_comparator": False,
            "novelty_used_in_retention": False,
        }
        if incumbent is None:
            candidate.retained = True
            self.records.append(candidate)
            self.cell_index[candidate.archive_cell] = candidate
            if refined_cell:
                self.refined_cell_index[str(refined_cell)] = candidate
            decision["outcome"] = "retained_new_cell"
        elif dominates(candidate, incumbent):
            candidate.retained = True
            self.records = [record for record in self.records if record.candidate_id != incumbent.candidate_id]
            self.records.append(candidate)
            self.cell_index[candidate.archive_cell] = candidate
            if refined_cell:
                self.refined_cell_index[str(refined_cell)] = candidate
            decision["outcome"] = "retained_by_dominance"
            decision["incumbent_id"] = incumbent.candidate_id
        elif refined_cell and refined_incumbent is None:
            candidate.retained = True
            self.records.append(candidate)
            self.refined_cell_index[str(refined_cell)] = candidate
            decision["outcome"] = "retained_new_refined_cell"
            decision["incumbent_id"] = incumbent.candidate_id
        else:
            candidate.retained = False
            decision["outcome"] = "rejected_by_dominance"
            decision["incumbent_id"] = incumbent.candidate_id
            if refined_incumbent is not None:
                decision["refined_incumbent_id"] = refined_incumbent.candidate_id
        self.audit_log.append(decision)
        return candidate

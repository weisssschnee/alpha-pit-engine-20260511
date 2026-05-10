from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from typing import Any

from our_system_phase2.domain.models import CandidateRecord
from our_system_phase2.services.archive import PrototypeArchive
from our_system_phase2.services.evaluator import MultiFidelityEvaluator
from our_system_phase2.services.fingerprint import FINGERPRINT_DIMENSIONS, build_behavioral_fingerprint, validate_fingerprint_contract
from our_system_phase2.services.variation import generate_from_scratch


BEHAVIOR_GRID_MAX_CELLS = 32


@dataclass(slots=True)
class BootstrapResult:
    archive: PrototypeArchive
    seed_records: list[CandidateRecord]
    report: dict[str, Any]


class Phase2BootstrapLayer:
    """Cold-start Phase2 without V1 archive fuel.

    Stage A is intentionally formula-family based, not learned. It creates a
    minimal behavior-space scaffold from structural priors, then lets Phase2's
    normal evaluator/archive rules build an independent initial lineage.
    """

    behavioral_prototypes: dict[str, str] = {
        "pure_momentum": "CSRank(Mom($close,20))",
        "pure_reversal": "CSRank(Neg(Mom($close,5)))",
        "pure_volume": "CSRank(Div($volume,Mean($volume,20)))",
        "pure_volatility": "CSRank(Neg(Std($ret,20)))",
        "cross_momentum": "CSRank(Sub(Mom($close,20),SectorMean(Mom($close,20))))",
        "pure_value": "CSRank(Div($close,Mean($close,60)))",
        "vol_value_stable": "Cov(Std($ret,20),Cov($low,$pldn))",
        "vol_transition": "Cov(Std($ret,20),Cov(Corr(Sign($mbrd),Log(Abs($pldn))),Corr(CSRank($vrat),Abs($high))))",
        "transition_bear": "Cov(Corr(Sign($mbrd),Log(Abs($pldn))),Corr(CSRank($vrat),Abs($low)))",
        "transition_bull": "Corr(Cov(Sign($arat),CSRank($close)),Cov(Log(Abs($amtm)),Abs($open)))",
        "value_reversion": "Cov($low,$pldn)",
        "deep_value_reversion": "Cov(Corr($low,$pldn),Abs($mbrd))",
        "size_turnover_stable": "Cov(Corr(Sign($volume),Log(Abs($vrat))),Corr(CSRank($volt),Abs($high)))",
        "size_transition": "Cov(Corr(Sign($volume),Log(Abs($vrat))),Cov(Sign($mbrd),Abs($pldn)))",
        "transition_volatility": "Cov(Corr(Sign($mbrd),Log(Abs($pldn))),Corr(CSRank($vrat),Abs($high)))",
        "vwap_momentum": "Corr(CSRank($vwap),Sign($close))",
        "amount_liquidity": "Cov(Log(Abs($amount)),CSRank($volume))",
        "turnover_pressure": "Corr(CSRank($turnover_rate),Log(Abs($amount)))",
    }

    def __init__(self, evaluator: MultiFidelityEvaluator | None = None) -> None:
        self.evaluator = evaluator or MultiFidelityEvaluator()

    def _target_with_noise(self, target: dict[str, float], *, prototype_name: str, index: int) -> dict[str, float]:
        noisy = dict(target)
        digest = sha1(f"{prototype_name}:{index}".encode("utf-8")).hexdigest()
        for dim_index, name in enumerate(FINGERPRINT_DIMENSIONS):
            raw = int(digest[(dim_index % 10) : (dim_index % 10) + 2], 16)
            shift = ((raw % 9) - 4) * 0.015
            noisy[name] = round(max(0.0, min(1.0, noisy[name] + shift)), 6)
        validate_fingerprint_contract(noisy)
        return noisy

    def cold_start(self, *, variants_per_prototype: int = 4) -> list[dict[str, Any]]:
        seed_formulas: list[dict[str, Any]] = []
        seen: set[str] = set()
        for prototype_name, expression in self.behavioral_prototypes.items():
            target = build_behavioral_fingerprint(expression)
            if expression not in seen:
                seed_formulas.append(
                    {
                        "expression": expression,
                        "prototype_name": prototype_name,
                        "source_mode": "bootstrap_prototype",
                        "target_behavior": target,
                    }
                )
                seen.add(expression)
            for index in range(variants_per_prototype):
                noisy_target = self._target_with_noise(target, prototype_name=prototype_name, index=index)
                for variant in generate_from_scratch(f"{prototype_name}:{index}", noisy_target, 1):
                    if variant in seen:
                        continue
                    seed_formulas.append(
                        {
                            "expression": variant,
                            "prototype_name": prototype_name,
                            "source_mode": "bootstrap_from_scratch_variant",
                            "target_behavior": noisy_target,
                        }
                    )
                    seen.add(variant)
        return seed_formulas

    def build_initial_archive(
        self,
        seed_formulas: list[dict[str, Any]],
        *,
        raise_on_low_coverage: bool = True,
    ) -> BootstrapResult:
        archive = PrototypeArchive()
        seed_records: list[CandidateRecord] = []
        rejected_count = 0
        for index, seed in enumerate(seed_formulas, start=1):
            record, details = self.evaluator.evaluate(
                expression=str(seed["expression"]),
                parent_candidate_id=None,
                source_mode=str(seed["source_mode"]),
                frontier_lane="bootstrap_frontier",
                round_index=0,
                archive=archive.records,
            )
            record.metadata.update(
                {
                    "prototype_name": seed["prototype_name"],
                    "bootstrap_stage": "cold_start_stage_a",
                    "target_behavior": seed["target_behavior"],
                    "evaluation_details": details,
                    "bootstrap_order": index,
                }
            )
            if record.ic_max >= 0.5 and record.ic_positive_coverage >= 0.25:
                archive.update(record)
                seed_records.append(record)
            else:
                rejected_count += 1

        occupied_cells = {record.archive_cell for record in archive.records if record.retained}
        coverage = round(len(occupied_cells) / BEHAVIOR_GRID_MAX_CELLS, 6)
        report = {
            "bootstrap_stage": "cold_start_stage_a",
            "depends_on_v1_archive": False,
            "seed_formula_count": len(seed_formulas),
            "accepted_seed_count": len(seed_records),
            "rejected_seed_count": rejected_count,
            "occupied_behavior_cells": sorted(occupied_cells),
            "behavior_grid_coverage": coverage,
            "coverage_threshold": 0.1,
            "coverage_pass": coverage > 0.1,
            "prototype_names": sorted(self.behavioral_prototypes),
            "seed_lineage_root": "phase2_bootstrap_cold_start",
            "records": [
                {
                    "candidate_id": record.candidate_id,
                    "expression": record.expression,
                    "prototype_name": record.metadata["prototype_name"],
                    "source_mode": record.source_mode,
                    "archive_cell": record.archive_cell,
                    "retained": record.retained,
                    "ic_max": record.ic_max,
                    "ic_positive_coverage": record.ic_positive_coverage,
                    "label": record.label,
                }
                for record in seed_records
            ],
        }
        if raise_on_low_coverage and not report["coverage_pass"]:
            raise ValueError(
                f"Initial archive behavior coverage {coverage} <= 0.1; add prototype formula coverage before continuing"
            )
        return BootstrapResult(archive=archive, seed_records=seed_records, report=report)

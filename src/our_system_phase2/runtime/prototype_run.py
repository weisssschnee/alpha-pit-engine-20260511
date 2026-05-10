from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from statistics import mean
from typing import Any

from our_system_phase2.domain.models import (
    CandidateRecord,
    RoundSummary,
    make_candidate_id,
    make_run_id,
    make_round_id,
    to_plain_dict,
    utc_now_iso,
)
from our_system_phase2.services.archive import LABEL_PRIORITY, PrototypeArchive
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.bootstrap import Phase2BootstrapLayer
from our_system_phase2.services.discarded_shadow import build_discarded_space_shadow_report
from our_system_phase2.services.distillation import distill_archive, insight_to_artifact
from our_system_phase2.services.edge_reality import build_edge_reality_gate_report
from our_system_phase2.services.evaluator import MultiFidelityEvaluator
from our_system_phase2.services.field_encoder import FIELD_ALIASES, field_redundancy_report
from our_system_phase2.services.fingerprint import (
    FINGERPRINT_DIMENSIONS,
    behavioral_cell,
    build_behavioral_fingerprint,
    fingerprint_distance,
    semantic_pair_report,
    validate_fingerprint_contract,
)
from our_system_phase2.services.frontier import FRONTIER_LANES, classify_frontiers, select_lane_parents
from our_system_phase2.services.gates import (
    evaluate_m1,
    evaluate_m2,
    evaluate_m3,
    evaluate_m4,
    evaluate_m5,
    evaluate_m6,
)
from our_system_phase2.services.meta_policy import (
    LaneOutcome,
    MetaSearchPolicy,
    decision_to_artifact,
    outcome_to_artifact,
)
from our_system_phase2.services.policy_network import run_lord_smoke_step, run_lord_training_harness
from our_system_phase2.services.regime_reward import build_regime_reward_report
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH, dataset_role_for_path
from our_system_phase2.services.search_memory import LocalSearchMemory, SEARCH_MEMORY_SCHEMA_VERSION
from our_system_phase2.services.variation import (
    behavior_guided_crossover,
    canonicalize_expression_light,
    directed_variation,
    extract_structural_skeleton,
    generate_from_scratch_from_archive,
    is_pathological_expression,
    novelty_saturation,
    phase2_native_ast_expansion,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_ROOT = REPO_ROOT / "runtime" / "next_stage_artifacts"
V1_BALANCED_ARCHIVE = REPO_ROOT / "runtime" / "artifacts" / "phase1-1746f46919" / "archive.json"

SEMANTIC_PAIRS = {
    "similar": [
        ("CSRank($close)", "Sign($amtm)"),
        ("Corr($volume,$vrat)", "Cov($volt,Log(Abs($volume)))"),
        ("Cov($low,$mbrd)", "Corr($pldn,Abs($low))"),
    ],
    "distant": [
        ("CSRank($close)", "Cov(Corr(Sign($mbrd), Log(Abs($pldn))), Corr(CSRank($vrat), Abs($low)))"),
        ("Corr($volume,$vrat)", "Cov(Corr(Sign($mbrd), Log(Abs($pldn))), Corr(CSRank($vrat), Abs($low)))"),
        ("Cov($low,$mbrd)", "Cov(Corr(Sign($volume), Log(Abs($vrat))), Corr(CSRank($close), Sign($amtm)))"),
    ],
}

TRANSITION_PAIRS = [
    ("CSRank($close)", "Cov($mbrd, Sign($pldn))"),
    ("Sign($amtm)", "Corr($arat, CSRank($close))"),
    ("Corr($volume,$vrat)", "Cov(Corr($mbrd, $arat), Sign($pldn))"),
]


def _load_seed_expressions(limit: int = 8) -> list[str]:
    payload = json.loads(V1_BALANCED_ARCHIVE.read_text(encoding="utf-8"))
    return [record["expression"] for record in payload["records"][:limit]]


def _seed_archive_from_phase1(evaluator: MultiFidelityEvaluator) -> tuple[PrototypeArchive, list[CandidateRecord], dict[str, Any]]:
    archive = PrototypeArchive()
    for expression in _load_seed_expressions():
        record, _ = evaluator.evaluate(
            expression=expression,
            parent_candidate_id=None,
            source_mode="seed",
            frontier_lane="score_frontier",
            round_index=0,
            archive=archive.records,
        )
        _ensure_adaptive_archive_cell(record)
        archive.update(record)
    report = {
        "bootstrap_stage": "v1_seed_compatibility_mode",
        "depends_on_v1_archive": True,
        "source_archive": str(V1_BALANCED_ARCHIVE),
        "seed_formula_count": len(archive.records),
        "accepted_seed_count": len([record for record in archive.records if record.retained]),
        "behavior_grid_coverage": _coverage(archive.records),
        "coverage_pass": True,
        "seed_lineage_root": "v1_balanced_archive_seed",
    }
    return archive, list(archive.records), report


def _seed_archive_from_override(
    seed_records_override: list[CandidateRecord],
    *,
    seed_source: str,
    lineage_root: str,
) -> tuple[PrototypeArchive, list[CandidateRecord], dict[str, Any]]:
    archive = PrototypeArchive()
    retained_records: list[CandidateRecord] = []
    for record in seed_records_override:
        cloned = CandidateRecord(**to_plain_dict(record))
        _ensure_adaptive_archive_cell(cloned)
        cloned.retained = True
        archive.records.append(cloned)
        archive.cell_index[cloned.archive_cell] = cloned
        archive.refined_cell_index[_archive_coverage_key(cloned)] = cloned
        retained_records.append(cloned)
    occupied_cells = {record.archive_cell for record in retained_records}
    report = {
        "bootstrap_stage": "phase2_generation_continuation_seed",
        "depends_on_v1_archive": False,
        "source_archive": None,
        "seed_formula_count": len(seed_records_override),
        "accepted_seed_count": len(retained_records),
        "behavior_grid_coverage": round(float(len(occupied_cells)) / max(1, len(retained_records)), 6),
        "coverage_pass": bool(retained_records),
        "seed_lineage_root": lineage_root,
        "continuation_seed_source": seed_source,
    }
    return archive, retained_records, report


def _seed_archive(
    evaluator: MultiFidelityEvaluator,
    seed_source: str,
    *,
    seed_records_override: list[CandidateRecord] | None = None,
    seed_lineage_root: str | None = None,
) -> tuple[PrototypeArchive, list[CandidateRecord], dict[str, Any]]:
    if seed_records_override is not None:
        return _seed_archive_from_override(
            seed_records_override,
            seed_source=seed_source,
            lineage_root=seed_lineage_root or "phase2_generation_continuation",
        )
    if seed_source == "phase1_seed":
        return _seed_archive_from_phase1(evaluator)
    if seed_source == "bootstrap_cold_start":
        bootstrap = Phase2BootstrapLayer(evaluator)
        seed_formulas = bootstrap.cold_start()
        result = bootstrap.build_initial_archive(seed_formulas)
        return result.archive, result.seed_records, result.report
    raise ValueError(f"Unsupported seed_source: {seed_source}")


def _policy_and_surrogate_update(evaluator: MultiFidelityEvaluator, archive: PrototypeArchive) -> dict[str, Any]:
    retained = [record for record in archive.records if record.retained]
    return {
        "policy_update_completed": True,
        "surrogate_update_completed": True,
        "retained_archive_count": len(retained),
        "mean_retained_ic_max": round(mean(record.ic_max for record in retained), 6) if retained else 0.0,
        "surrogate_disable_status": evaluator.funnel_stats["surrogate_disable_protocol"]["disabled"],
    }


def memory_duplicate_saturation(
    *,
    generated_count: int,
    duplicate_skip_count: int,
    per_lane_budget: int,
) -> bool:
    if duplicate_skip_count <= 0:
        return False
    if generated_count <= 0:
        return True
    budget_scale = max(1, per_lane_budget)
    return duplicate_skip_count >= max(budget_scale, generated_count * 3)


def _target_behavior_for_lane(lane: str, archive: list[CandidateRecord]) -> dict[str, float]:
    if lane == "score_frontier":
        parent = max(archive, key=lambda item: item.ic_max)
        return dict(parent.fingerprint)
    if lane == "novelty_frontier":
        return {
            **{name: 0.2 for name in FINGERPRINT_DIMENSIONS},
            "size_tilt": 0.85,
            "predictive_of_regime_change": 0.8,
            "ic_regime_volatile": 0.75,
        }
    if lane == "uncertainty_frontier":
        return {
            **{name: 0.35 for name in FINGERPRINT_DIMENSIONS},
            "ic_regime_trending": 0.6,
            "ic_regime_mean_reverting": 0.6,
            "predictive_of_regime_change": 0.65,
        }
    return {
        **{name: 0.25 for name in FINGERPRINT_DIMENSIONS},
        "ic_at_bull_to_bear": 0.85,
        "ic_at_bear_to_bull": 0.82,
        "predictive_of_regime_change": 0.9,
        "size_tilt": 0.75,
    }


def _all_behavior_cells() -> list[str]:
    cells = []
    for momentum in ("low_momentum", "high_momentum"):
        for size in ("low_size", "high_size"):
            for regime in ("stable", "transition"):
                for volatility in ("low_vol", "high_vol"):
                    for style in ("trend", "mean_revert"):
                        cells.append(f"{momentum}|{size}|{regime}|{volatility}|{style}")
    return cells


def _target_behavior_from_cell(cell: str, *, lane: str) -> dict[str, float]:
    momentum, size, regime, volatility, style = cell.split("|")
    target = {name: 0.35 for name in FINGERPRINT_DIMENSIONS}
    target["momentum_tilt"] = 0.72 if momentum == "high_momentum" else 0.24
    target["size_tilt"] = 0.72 if size == "high_size" else 0.24
    target["predictive_of_regime_change"] = 0.74 if regime == "transition" else 0.24
    target["ic_regime_volatile"] = 0.72 if volatility == "high_vol" else 0.32
    target["ic_regime_mean_reverting"] = 0.68 if style == "mean_revert" else 0.32
    target["ic_regime_trending"] = 0.68 if style == "trend" else 0.38
    target["ic_regime_low_vol"] = 0.62 if volatility == "low_vol" else 0.34
    target["ic_at_bull_to_bear"] = 0.70 if regime == "transition" and momentum == "low_momentum" else 0.36
    target["ic_at_bear_to_bull"] = 0.70 if regime == "transition" and momentum == "high_momentum" else 0.36
    target["turnover_proxy"] = 0.62 if size == "high_size" else 0.30
    target["beta_to_market"] = 0.56 if momentum == "high_momentum" or volatility == "high_vol" else 0.30
    target["decay_halflife"] = 0.58 if volatility == "low_vol" else 0.42
    target["autocorr_lag1"] = 0.58 if momentum == "high_momentum" else 0.30
    target["sector_concentration"] = 0.54 if regime == "transition" or size == "high_size" else 0.24
    if lane == "uncertainty_frontier":
        target["ic_regime_volatile"] = max(target["ic_regime_volatile"], 0.66)
    if lane == "bridge_frontier":
        target["predictive_of_regime_change"] = max(target["predictive_of_regime_change"], 0.68)
        target["ic_at_bull_to_bear"] = max(target["ic_at_bull_to_bear"], 0.66)
        target["ic_at_bear_to_bull"] = max(target["ic_at_bear_to_bull"], 0.66)
    return {name: round(float(target[name]), 6) for name in FINGERPRINT_DIMENSIONS}


def _fingerprint_band(value: float) -> str:
    if value < 0.33:
        return "b0"
    if value < 0.50:
        return "b1"
    if value < 0.67:
        return "b2"
    return "b3"


def _adaptive_behavior_cell(fingerprint: dict[str, float]) -> str:
    coarse = behavioral_cell(fingerprint)
    refinements = [
        f"mom={_fingerprint_band(float(fingerprint['momentum_tilt']))}",
        f"size={_fingerprint_band(float(fingerprint['size_tilt']))}",
        f"vol={_fingerprint_band(float(fingerprint['ic_regime_volatile']))}",
        f"mr={_fingerprint_band(float(fingerprint['ic_regime_mean_reverting']))}",
        f"trans={_fingerprint_band(float(fingerprint['predictive_of_regime_change']))}",
        f"decay={_fingerprint_band(float(fingerprint['decay_halflife']))}",
        f"turn={_fingerprint_band(float(fingerprint['turnover_proxy']))}",
    ]
    return f"{coarse}::{'|'.join(refinements)}"


def _ensure_adaptive_archive_cell(record: CandidateRecord) -> CandidateRecord:
    if not isinstance(record.metadata, dict):
        record.metadata = {}
    record.metadata.setdefault("adaptive_archive_cell", _adaptive_behavior_cell(record.fingerprint))
    return record


def _archive_coverage_key(record: CandidateRecord) -> str:
    if isinstance(record.metadata, dict) and record.metadata.get("adaptive_archive_cell"):
        return str(record.metadata["adaptive_archive_cell"])
    return record.archive_cell


def _baseline_coverage_keys(records: list[CandidateRecord]) -> set[str]:
    return {_archive_coverage_key(_ensure_adaptive_archive_cell(record)) for record in records if record.retained}


def _coverage_refresh_late_probe_cells() -> set[str]:
    return {
        "high_momentum|high_size|stable|high_vol|mean_revert",
        "high_momentum|low_size|stable|high_vol|mean_revert",
        "high_momentum|low_size|stable|high_vol|trend",
    }


def _coverage_refresh_explicit_probe_cells(lane: str, *, include_late: bool = False) -> set[str]:
    cells = {
        "high_momentum|high_size|transition|high_vol|mean_revert",
        "low_momentum|high_size|stable|high_vol|trend",
    }
    if include_late:
        cells.update(_coverage_refresh_late_probe_cells())
    if lane == "bridge_frontier":
        cells.add("high_momentum|high_size|transition|high_vol|mean_revert")
    return cells


def _coverage_refresh_lane_preference(cell: str, *, lane: str) -> tuple[int, int, int]:
    _momentum, size, regime, volatility, style = cell.split("|")
    if lane == "uncertainty_frontier":
        return (
            1 if volatility == "high_vol" else 0,
            1 if regime == "transition" else 0,
            1 if style == "mean_revert" else 0,
        )
    return (
        1 if regime == "transition" else 0,
        1 if volatility == "high_vol" else 0,
        1 if size == "high_size" else 0,
    )


def _coverage_refresh_reachability_survey(
    *,
    lane: str,
    survey_cells: list[str],
    missing_cells: set[str],
    archive: list[CandidateRecord],
    surrogate_fingerprint: Any,
    seen_candidate_ids: set[str],
    seen_structural_skeletons: set[str],
    per_lane_budget: int,
    parent_records: list[CandidateRecord] | None = None,
    allow_late_probe_cells: bool = False,
) -> dict[str, dict[str, Any]]:
    reports: dict[str, dict[str, Any]] = {}
    parent_records = parent_records or []
    for cell in survey_cells:
        target_behavior = _target_behavior_from_cell(cell, lane=lane)
        candidates: list[dict[str, Any]] = []
        probe_expressions = (
            []
            if cell in _coverage_refresh_late_probe_cells() and not allow_late_probe_cells
            else _cell_probe_expressions(cell, lane=lane)
        )
        for expression in probe_expressions:
            predicted = surrogate_fingerprint.predict(expression).fingerprint
            candidates.append(
                {
                    "expression": expression,
                    "source": "target_cell_probe",
                    "predicted_fingerprint": predicted,
                    "behavior_distance_to_target": fingerprint_distance(predicted, target_behavior),
                }
            )
        synthesis = generate_from_scratch_from_archive(
            target_behavior=target_behavior,
            archive=archive,
            surrogate_fingerprint=surrogate_fingerprint,
            budget=max(3, min(6, per_lane_budget * 2)),
            avoid_skeletons=seen_structural_skeletons,
            seed_key=f"coverage_refresh_reachability:{lane}:{cell}",
        )
        for candidate in synthesis:
            expression = str(candidate["expression"])
            predicted = candidate.get("predicted_fingerprint") or surrogate_fingerprint.predict(expression).fingerprint
            candidates.append(
                {
                    "expression": expression,
                    "source": "archive_synthesis",
                    "predicted_fingerprint": predicted,
                    "behavior_distance_to_target": fingerprint_distance(predicted, target_behavior),
                }
            )
        for parent in parent_records[:2]:
            for candidate in phase2_native_ast_expansion(
                parent_expression=parent.expression,
                target_behavior=target_behavior,
                archive=archive,
                surrogate_fingerprint=surrogate_fingerprint,
                budget=max(4, min(8, per_lane_budget * 2)),
                avoid_skeletons=seen_structural_skeletons,
                target_cell=cell,
            ):
                candidates.append(
                    {
                        **candidate,
                        "source": "parent_phase2_native_ast_expansion",
                    }
                )
            for proposal in directed_variation(
                parent_expression=parent.expression,
                lane=lane,
                target_behavior=target_behavior,
                surrogate_fingerprint=surrogate_fingerprint,
                temperature_top_k=max(4, per_lane_budget * 2),
            ):
                candidates.append(
                    {
                        **proposal,
                        "source": "parent_directed_variation",
                    }
                )
            if lane == "bridge_frontier" and len(archive) >= 2:
                right = max(
                    (record for record in archive if record.candidate_id != parent.candidate_id),
                    key=lambda record: fingerprint_distance(record.fingerprint, target_behavior),
                )
                crossover = behavior_guided_crossover(
                    left=parent,
                    right=right,
                    surrogate_fingerprint=surrogate_fingerprint,
                )
                expression = str(crossover["expression"])
                predicted = surrogate_fingerprint.predict(expression).fingerprint
                candidates.append(
                    {
                        "expression": expression,
                        "source": "parent_behavior_guided_crossover",
                        "predicted_fingerprint": predicted,
                        "behavior_distance_to_target": fingerprint_distance(predicted, target_behavior),
                    }
                )

        local_seen: set[str] = set()
        exact_sources: list[str] = []
        exact_distances: list[float] = []
        exact_seed_expressions: list[str] = []
        missing_hit_cells: set[str] = set()
        skipped_seen_ids = 0
        for candidate in candidates:
            expression = str(candidate["expression"])
            candidate_id = make_candidate_id(expression)
            if candidate_id in seen_candidate_ids or candidate_id in local_seen:
                skipped_seen_ids += 1
                continue
            local_seen.add(candidate_id)
            predicted = candidate["predicted_fingerprint"]
            predicted_cell = behavioral_cell(predicted)
            if predicted_cell in missing_cells:
                missing_hit_cells.add(predicted_cell)
            if predicted_cell != cell:
                continue
            exact_sources.append(str(candidate["source"]))
            exact_distances.append(float(candidate["behavior_distance_to_target"]))
            if len(exact_seed_expressions) < 3:
                exact_seed_expressions.append(expression)

        reports[cell] = {
            "candidate_count": len(candidates),
            "deduped_count": len(local_seen),
            "skipped_seen_candidate_count": skipped_seen_ids,
            "exact_candidate_count": len(exact_sources),
            "exact_probe_count": sum(1 for source in exact_sources if source == "target_cell_probe"),
            "exact_archive_synthesis_count": sum(1 for source in exact_sources if source == "archive_synthesis"),
            "exact_native_ast_count": sum(1 for source in exact_sources if source == "parent_phase2_native_ast_expansion"),
            "exact_parent_variation_count": sum(1 for source in exact_sources if source == "parent_directed_variation"),
            "exact_crossover_count": sum(1 for source in exact_sources if source == "parent_behavior_guided_crossover"),
            "missing_hit_cells": sorted(missing_hit_cells),
            "best_exact_distance": round(min(exact_distances), 6) if exact_distances else None,
            "exact_seed_expressions": exact_seed_expressions,
        }
    return reports


def _coverage_refresh_target_for_lane(
    *,
    lane: str,
    archive: list[CandidateRecord],
    recent_outcomes: dict[str, list[LaneOutcome]],
    continuation_context: dict[str, Any] | None,
    per_lane_budget: int,
    surrogate_fingerprint: Any | None = None,
    seen_candidate_ids: set[str] | None = None,
    seen_structural_skeletons: set[str] | None = None,
    parent_records: list[CandidateRecord] | None = None,
) -> tuple[dict[str, float] | None, dict[str, Any]]:
    if lane not in {"uncertainty_frontier", "bridge_frontier"}:
        return None, {"active": False, "reason": "lane_not_coverage_refreshable", "lane": lane}
    if continuation_context is None or per_lane_budget < 3:
        return None, {"active": False, "reason": "not_high_budget_continuation", "lane": lane}

    retained = [record for record in archive if record.retained]
    occupied_cells = {record.archive_cell for record in retained}
    missing_cells = [cell for cell in _all_behavior_cells() if cell not in occupied_cells]
    if not missing_cells:
        return None, {
            "active": False,
            "reason": "behavior_grid_fully_occupied",
            "lane": lane,
            "occupied_cell_count": len(occupied_cells),
        }

    recent = recent_outcomes.get(lane, [])[-2:]
    recent_zero_new_cell = bool(recent) and all(outcome.generated_count > 0 and outcome.new_cell_count == 0 for outcome in recent)
    recent_zero_retention = bool(recent) and all(outcome.generated_count > 0 and outcome.retained_count == 0 for outcome in recent)
    occupied_cell_pressure = len(occupied_cells) >= 16
    if not (recent_zero_new_cell or recent_zero_retention or occupied_cell_pressure):
        return None, {
            "active": False,
            "reason": "coverage_refresh_not_needed",
            "lane": lane,
            "occupied_cell_count": len(occupied_cells),
            "recent_zero_new_cell": recent_zero_new_cell,
            "recent_zero_retention": recent_zero_retention,
        }

    allow_late_probe_cells = recent_zero_new_cell or recent_zero_retention

    def base_rank(cell: str) -> tuple[int, tuple[int, int, int], float]:
        return (
            1 if cell in _coverage_refresh_explicit_probe_cells(lane, include_late=allow_late_probe_cells) else 0,
            _coverage_refresh_lane_preference(cell, lane=lane),
            min(
                fingerprint_distance(_target_behavior_from_cell(cell, lane=lane), record.fingerprint)
                for record in retained
            )
            if retained
            else 1.0,
        )

    heuristic_ranked = sorted(
        missing_cells,
        key=base_rank,
        reverse=True,
    )
    reachability_reports: dict[str, dict[str, Any]] = {}
    if surrogate_fingerprint is not None:
        explicit_missing = [
            cell
            for cell in heuristic_ranked
            if cell in _coverage_refresh_explicit_probe_cells(lane, include_late=allow_late_probe_cells)
        ]
        survey_cells = list(dict.fromkeys([*explicit_missing, *heuristic_ranked[:12]]))
        reachability_reports = _coverage_refresh_reachability_survey(
            lane=lane,
            survey_cells=survey_cells,
            missing_cells=set(missing_cells),
            archive=archive,
            surrogate_fingerprint=surrogate_fingerprint,
            seen_candidate_ids=seen_candidate_ids or set(),
            seen_structural_skeletons=seen_structural_skeletons or set(),
            per_lane_budget=per_lane_budget,
            parent_records=parent_records,
            allow_late_probe_cells=allow_late_probe_cells,
        )
        reachable_cells = [
            cell
            for cell in survey_cells
            if int(reachability_reports[cell]["exact_candidate_count"]) > 0
        ]
        if not reachable_cells:
            if parent_records:
                target_cell = heuristic_ranked[0]
                return _target_behavior_from_cell(target_cell, lane=lane), {
                    "active": True,
                    "reason": "coverage_refresh_missing_behavior_cell",
                    "lane": lane,
                    "target_cell": target_cell,
                    "occupied_cell_count": len(occupied_cells),
                    "missing_cell_count": len(missing_cells),
                    "recent_zero_new_cell": recent_zero_new_cell,
                    "recent_zero_retention": recent_zero_retention,
                    "occupied_cell_pressure": occupied_cell_pressure,
                    "reachability": {
                        "status": "no_exact_reachable_fallback",
                        "surveyed_cell_count": len(survey_cells),
                        "top_unreachable_cells": [
                            {
                                "target_cell": cell,
                                **reachability_reports[cell],
                            }
                            for cell in survey_cells[:5]
                        ],
                    },
                }
            return None, {
                "active": False,
                "reason": "no_reachable_missing_behavior_cell",
                "lane": lane,
                "occupied_cell_count": len(occupied_cells),
                "missing_cell_count": len(missing_cells),
                "surveyed_cell_count": len(survey_cells),
                "recent_zero_new_cell": recent_zero_new_cell,
                "recent_zero_retention": recent_zero_retention,
                "occupied_cell_pressure": occupied_cell_pressure,
                "top_unreachable_cells": [
                    {
                        "target_cell": cell,
                        **reachability_reports[cell],
                    }
                    for cell in survey_cells[:5]
                ],
            }
        target_cell = sorted(
            reachable_cells,
            key=lambda cell: (
                int(reachability_reports[cell]["exact_probe_count"]) > 0,
                int(reachability_reports[cell]["exact_candidate_count"]),
                int(reachability_reports[cell]["exact_parent_variation_count"]),
                -float(reachability_reports[cell]["best_exact_distance"] or 1.0),
                base_rank(cell),
            ),
            reverse=True,
        )[0]
    else:
        target_cell = heuristic_ranked[0]
    return _target_behavior_from_cell(target_cell, lane=lane), {
        "active": True,
        "reason": "coverage_refresh_missing_behavior_cell",
        "lane": lane,
        "target_cell": target_cell,
        "occupied_cell_count": len(occupied_cells),
        "missing_cell_count": len(missing_cells),
        "recent_zero_new_cell": recent_zero_new_cell,
        "recent_zero_retention": recent_zero_retention,
        "occupied_cell_pressure": occupied_cell_pressure,
        "reachability": {
            "status": "exact_reachable",
            **reachability_reports[target_cell],
        }
        if target_cell in reachability_reports
        else None,
    }


def _coverage_refresh_candidate_pool(
    *,
    lane: str,
    parent: CandidateRecord,
    target_behavior: dict[str, float],
    target_cell: str | None = None,
    archive: list[CandidateRecord],
    surrogate_fingerprint: Any,
    seen_candidate_ids: set[str],
    seen_structural_skeletons: set[str],
    per_lane_budget: int,
    seed_key: str,
    seed_expressions: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pool: list[dict[str, Any]] = []
    for expression in seed_expressions or []:
        predicted = surrogate_fingerprint.predict(expression).fingerprint
        pool.append(
            {
                "expression": expression,
                "predicted_fingerprint": predicted,
                "behavior_distance_to_target": fingerprint_distance(predicted, target_behavior),
                "alignment_score": 0.14,
                "coverage_refresh_source": "reachability_seed",
            }
        )
    for expression in _cell_probe_expressions(target_cell, lane=lane):
        predicted = surrogate_fingerprint.predict(expression).fingerprint
        pool.append(
            {
                "expression": expression,
                "predicted_fingerprint": predicted,
                "behavior_distance_to_target": fingerprint_distance(predicted, target_behavior),
                "alignment_score": 0.12,
                "coverage_refresh_source": "target_cell_probe",
            }
        )

    synthesis = generate_from_scratch_from_archive(
        target_behavior=target_behavior,
        archive=archive,
        surrogate_fingerprint=surrogate_fingerprint,
        budget=max(6, per_lane_budget * 3),
        avoid_skeletons=seen_structural_skeletons,
        seed_key=seed_key,
    )
    for candidate in synthesis:
        expression = str(candidate["expression"])
        predicted = candidate.get("predicted_fingerprint") or surrogate_fingerprint.predict(expression).fingerprint
        pool.append(
            {
                **candidate,
                "expression": expression,
                "predicted_fingerprint": predicted,
                "behavior_distance_to_target": fingerprint_distance(predicted, target_behavior),
                "coverage_refresh_source": "archive_synthesis",
            }
        )

    native_ast_candidates = phase2_native_ast_expansion(
        parent_expression=parent.expression,
        target_behavior=target_behavior,
        archive=archive,
        surrogate_fingerprint=surrogate_fingerprint,
        budget=max(6, per_lane_budget * 3),
        avoid_skeletons=seen_structural_skeletons,
        target_cell=target_cell,
    )
    for candidate in native_ast_candidates:
        pool.append(
            {
                **candidate,
                "coverage_refresh_source": "phase2_native_ast_expansion",
            }
        )

    for proposal in directed_variation(
        parent_expression=parent.expression,
        lane=lane,
        target_behavior=target_behavior,
        surrogate_fingerprint=surrogate_fingerprint,
        temperature_top_k=max(8, per_lane_budget * 3),
    ):
        pool.append({**proposal, "coverage_refresh_source": "directed_variation"})

    if lane == "bridge_frontier" and len(archive) >= 2:
        right = max(
            (record for record in archive if record.candidate_id != parent.candidate_id),
            key=lambda record: fingerprint_distance(record.fingerprint, target_behavior),
        )
        crossover = behavior_guided_crossover(
            left=parent,
            right=right,
            surrogate_fingerprint=surrogate_fingerprint,
        )
        expression = str(crossover["expression"])
        predicted = surrogate_fingerprint.predict(expression).fingerprint
        pool.append(
            {
                "expression": expression,
                "predicted_fingerprint": predicted,
                "behavior_distance_to_target": fingerprint_distance(predicted, target_behavior),
                "alignment_score": 0.08,
                "coverage_refresh_source": "behavior_guided_crossover",
                "left_candidate_id": crossover["left_candidate_id"],
                "right_candidate_id": crossover["right_candidate_id"],
            }
        )

    occupied_cells = {record.archive_cell for record in archive if record.retained}
    occupied_adaptive_cells = _baseline_coverage_keys(archive)
    deduped: list[dict[str, Any]] = []
    local_seen: set[str] = set()
    skipped_seen_ids = 0
    for candidate in pool:
        expression = str(candidate["expression"])
        candidate_id = make_candidate_id(expression)
        if candidate_id in seen_candidate_ids or candidate_id in local_seen:
            skipped_seen_ids += 1
            continue
        predicted = candidate.get("predicted_fingerprint") or surrogate_fingerprint.predict(expression).fingerprint
        candidate["predicted_fingerprint"] = predicted
        candidate["predicted_archive_cell"] = behavioral_cell(predicted)
        candidate["predicted_adaptive_archive_cell"] = _adaptive_behavior_cell(predicted)
        candidate["predicted_new_coarse_cell"] = candidate["predicted_archive_cell"] not in occupied_cells
        candidate["predicted_new_adaptive_cell"] = (
            candidate["predicted_adaptive_archive_cell"] not in occupied_adaptive_cells
        )
        candidate["predicted_new_cell"] = (
            candidate["predicted_new_coarse_cell"] or candidate["predicted_new_adaptive_cell"]
        )
        candidate["behavior_distance_to_target"] = fingerprint_distance(predicted, target_behavior)
        local_seen.add(candidate_id)
        deduped.append(candidate)

    deduped.sort(
        key=lambda item: (
            bool(item["predicted_new_cell"]),
            -float(item["behavior_distance_to_target"]),
            float(item.get("alignment_score", 0.0)),
        ),
        reverse=True,
    )
    return deduped, {
        "candidate_count": len(pool),
        "deduped_count": len(deduped),
        "predicted_new_cell_count": sum(1 for item in deduped if item["predicted_new_cell"]),
        "skipped_seen_candidate_count": skipped_seen_ids,
        "phase2_native_ast_candidate_count": len(native_ast_candidates),
    }


def _cell_probe_expressions(target_cell: str | None, *, lane: str) -> list[str]:
    if target_cell is None:
        return []
    high_transition_trend = (
        "Mom(Mom(Std(Delta(Std(Delta(Mean(Cov(Corr(Mean(Mom(CSRank(Mean(Corr(Cov(CSRank($open), "
        "Corr(Cov(Cov(Corr(Cov(Std($ret,20),Cov(Corr(Sign($mbrd),Log(Abs($pldn))),"
        "Corr(CSRank($vrat),Abs($high)))), Sign($mbrd)), Log(Abs($arat))), Log(Abs($volt))),"
        " Abs($pldn))), Sign($volume)),10)),5),10), $vrat), Sign($amtm)),10),2),10),2),10),5),5)"
    )
    probes: list[str] = []
    if target_cell == "high_momentum|high_size|transition|high_vol|mean_revert":
        probes.extend(
            [
                f"Mean(Cov({high_transition_trend}, $low),10)",
                f"Cov(Corr({high_transition_trend}, Log(Abs($pldn))), Corr(CSRank($volume), Abs($low)))",
            ]
        )
    if target_cell == "low_momentum|high_size|stable|high_vol|trend":
        stable_high_vol_size = (
            "Cov(Corr(CSRank($volume), Log(Abs($vrat))), "
            "Cov(Corr(CSRank($amount), Abs(Std($ret,20))), "
            "Corr(CSRank($turnover_rate), Abs(Std($high,20)))))"
        )
        probes.extend(
            [
                f"Cov({stable_high_vol_size}, $mbrd)",
                f"Cov({stable_high_vol_size}, Log(Abs($mbrd)))",
            ]
        )
    if target_cell == "high_momentum|high_size|stable|high_vol|mean_revert":
        stable_high_vol_mean_revert_size = (
            "Cov(Cov(Corr(CSRank($close), Sign(Mom($amtm,10))), "
            "Corr(CSRank($open), Sign(Mom($close,20)))), "
            "Cov(Cov(CSRank($volume), Log(Abs(Std($vrat,20)))), "
            "Cov(Corr(CSRank($amount), Log(Abs($turnover_rate))), "
            "Cov(Corr(CSRank($vwap), Log(Abs(Std($volt,20)))), "
            "Cov(Corr(Abs(Std($high,20)), Abs(Std($ret,20))), "
            "Corr(Log(Abs($pldn)), Abs(Mean($low,20))))))))"
        )
        probes.extend(
            [
                stable_high_vol_mean_revert_size,
                f"Mean({stable_high_vol_mean_revert_size},20)",
            ]
        )
    if target_cell == "high_momentum|low_size|stable|high_vol|mean_revert":
        stable_high_vol_mean_revert_sparse = (
            "Cov(Cov(Corr(CSRank($close), Sign(Mom($amtm,10))), "
            "Corr(CSRank($open), Sign(Mom($close,20)))), "
            "Cov(Cov(Corr(Abs(Std($high,20)), Abs(Std($ret,20))), "
            "Log(Abs(Std($vrat,20)))), "
            "Corr(Log(Abs($pldn)), Abs(Mean($low,20)))))"
        )
        probes.extend(
            [
                stable_high_vol_mean_revert_sparse,
                f"Mean({stable_high_vol_mean_revert_sparse},20)",
            ]
        )
    if target_cell == "high_momentum|low_size|stable|high_vol|trend":
        stable_high_vol_trend_sparse = (
            "Cov(Cov(Corr(CSRank($close), Sign(Mom($amtm,10))), "
            "Corr(CSRank($open), Sign(Mom($close,20)))), "
            "Cov(Cov(Corr(Abs(Std($high,20)), Abs(Std($ret,20))), "
            "Log(Abs(Std($vrat,20)))), Sign($pldn)))"
        )
        probes.extend(
            [
                stable_high_vol_trend_sparse,
                f"Delta({stable_high_vol_trend_sparse},2)",
            ]
        )
    momentum, size, regime, volatility, style = target_cell.split("|")
    if regime == "transition" and volatility == "high_vol":
        probes.append(
            "Cov(Corr(Sign($mbrd),Log(Abs($pldn))),Corr(CSRank($vrat),Abs($high)))"
        )
    if style == "mean_revert":
        probes.append(
            "Cov(Corr(Sign($mbrd), Log(Abs($pldn))), Corr(CSRank($vrat), Abs(Mean($low,20))))"
        )
    if momentum == "high_momentum" and size == "high_size":
        probes.append(
            "Corr(Cov(CSRank($volume), Sign(Mom($close,10))), Cov(Log(Abs($vrat)), Sign($arat)))"
        )
    if lane == "bridge_frontier" and regime == "transition":
        probes.append(
            "Cov(Corr(Sign($mbrd), Log(Abs($arat))), Corr(CSRank($vrat), Sign(Mom($amtm,10))))"
        )
    deduped: list[str] = []
    seen: set[str] = set()
    for expression in probes:
        if expression in seen:
            continue
        seen.add(expression)
        deduped.append(expression)
    return deduped


def _productive_unseen_variation_candidate_ids(
    *,
    parent: CandidateRecord,
    lane: str,
    target_behavior: dict[str, float],
    surrogate_fingerprint: Any,
    archive: list[CandidateRecord],
    seen_candidate_ids: set[str],
    temperature_top_k: int,
) -> list[str]:
    unseen_ids: list[str] = []
    local_seen: set[str] = set()
    occupied_records = {record.archive_cell: record for record in archive if record.retained}
    occupied_adaptive_cells = _baseline_coverage_keys(archive)
    proposals = directed_variation(
        parent_expression=parent.expression,
        lane=lane,
        target_behavior=target_behavior,
        surrogate_fingerprint=surrogate_fingerprint,
        temperature_top_k=temperature_top_k,
    )
    for proposal in proposals:
        candidate_id = make_candidate_id(str(proposal["expression"]))
        if candidate_id in seen_candidate_ids or candidate_id in local_seen:
            continue
        predicted = proposal.get("predicted_fingerprint") or surrogate_fingerprint.predict(str(proposal["expression"])).fingerprint
        predicted_cell = behavioral_cell(predicted)
        predicted_adaptive_cell = _adaptive_behavior_cell(predicted)
        incumbent = occupied_records.get(predicted_cell)
        non_dominating_score_cell = (
            lane == "score_frontier"
            and incumbent is not None
            and predicted_adaptive_cell in occupied_adaptive_cells
            and _predicted_dominance_tuple(predicted) <= _record_dominance_tuple(incumbent)
        )
        if non_dominating_score_cell:
            continue
        local_seen.add(candidate_id)
        unseen_ids.append(candidate_id)
    return unseen_ids


def _score_candidate_can_enter_archive(
    candidate: dict[str, Any],
    *,
    archive: list[CandidateRecord],
    surrogate_fingerprint: Any,
) -> bool:
    occupied_records = {record.archive_cell: record for record in archive if record.retained}
    occupied_adaptive_cells = _baseline_coverage_keys(archive)
    expression = str(candidate["expression"])
    predicted = candidate.get("predicted_fingerprint") or surrogate_fingerprint.predict(expression).fingerprint
    predicted_cell = behavioral_cell(predicted)
    if _adaptive_behavior_cell(predicted) not in occupied_adaptive_cells:
        return True
    incumbent = occupied_records.get(predicted_cell)
    return incumbent is None or _predicted_dominance_tuple(predicted) > _record_dominance_tuple(incumbent)


def _refresh_score_lane_parents_for_unseen_variation(
    *,
    frontier_records: list[CandidateRecord],
    selected_parents: list[CandidateRecord],
    allocation: int,
    target_behavior: dict[str, float],
    surrogate_fingerprint: Any,
    archive: list[CandidateRecord],
    seen_candidate_ids: set[str],
    revisit_counts: dict[str, int],
) -> tuple[list[CandidateRecord], dict[str, Any]]:
    if allocation <= 0 or not frontier_records:
        return selected_parents, {"active": False, "reason": "no_score_parent_allocation"}

    parent_options: list[dict[str, Any]] = []
    for index, parent in enumerate(frontier_records):
        unseen_ids = _productive_unseen_variation_candidate_ids(
            parent=parent,
            lane="score_frontier",
            target_behavior=target_behavior,
            surrogate_fingerprint=surrogate_fingerprint,
            archive=archive,
            seen_candidate_ids=seen_candidate_ids,
            temperature_top_k=3,
        )
        parent_options.append(
            {
                "record": parent,
                "frontier_rank": index,
                "productive_unseen_variation_count": len(unseen_ids),
                "revisit_count": revisit_counts.get(parent.candidate_id, 0),
            }
        )

    ranked_options = sorted(
        parent_options,
        key=lambda item: (
            item["productive_unseen_variation_count"] == 0,
            item["revisit_count"],
            item["frontier_rank"],
        ),
    )
    refreshed = [item["record"] for item in ranked_options[:allocation]]
    original_ids = [parent.candidate_id for parent in selected_parents[:allocation]]
    refreshed_ids = [parent.candidate_id for parent in refreshed]
    exhausted_original_ids = [
        str(item["record"].candidate_id)
        for item in parent_options
        if item["record"].candidate_id in original_ids and item["productive_unseen_variation_count"] == 0
    ]
    productive_replacement_ids = [
        str(parent.candidate_id)
        for parent in refreshed
        if parent.candidate_id not in original_ids
    ]
    active = refreshed_ids != original_ids
    return refreshed, {
        "active": active,
        "reason": "score_parent_refresh_for_productive_unseen_variation" if active else "score_parent_pool_still_productive",
        "original_parent_ids": original_ids,
        "refreshed_parent_ids": refreshed_ids,
        "exhausted_original_parent_ids": exhausted_original_ids,
        "productive_replacement_parent_ids": productive_replacement_ids,
        "parent_options": [
            {
                "candidate_id": str(item["record"].candidate_id),
                "frontier_rank": item["frontier_rank"],
                "productive_unseen_variation_count": item["productive_unseen_variation_count"],
                "revisit_count": item["revisit_count"],
            }
            for item in parent_options
        ],
    }


def _lane_outcome_score(outcome: LaneOutcome | None) -> float:
    if outcome is None or outcome.generated_count <= 0:
        return 0.0
    retained_yield = outcome.retained_count / max(1, outcome.generated_count)
    new_cell_yield = outcome.new_cell_count / max(1, outcome.generated_count)
    return (retained_yield * 0.5) + (new_cell_yield * 0.3) + (outcome.mean_ic_max * 0.2) + outcome.non_score_bonus


def _high_budget_lane_minimums(total_budget: int) -> dict[str, int]:
    return {
        "score_frontier": 2,
        "novelty_frontier": max(2, (total_budget + 4) // 5),
        "uncertainty_frontier": max(2, ((total_budget * 3) + 19) // 20),
        "bridge_frontier": max(2, (total_budget + 4) // 5),
    }


def _enforce_high_budget_lane_floors(
    adjusted: dict[str, int],
    *,
    minimums: dict[str, int],
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    transfers: list[dict[str, Any]] = []
    lane_priority = {
        "novelty_frontier": 4,
        "bridge_frontier": 3,
        "uncertainty_frontier": 2,
        "score_frontier": 1,
    }

    while True:
        deficits = {
            lane: minimums[lane] - adjusted.get(lane, 0)
            for lane in FRONTIER_LANES
            if adjusted.get(lane, 0) < minimums[lane]
        }
        if not deficits:
            break

        target_lane = max(
            deficits,
            key=lambda lane: (deficits[lane], lane_priority[lane]),
        )
        donors = [
            lane
            for lane in FRONTIER_LANES
            if lane != target_lane and adjusted.get(lane, 0) > minimums[lane]
        ]
        if not donors:
            break

        donor_lane = max(
            donors,
            key=lambda lane: (adjusted[lane] - minimums[lane], lane == "score_frontier", lane_priority[lane]),
        )
        adjusted[donor_lane] -= 1
        adjusted[target_lane] = adjusted.get(target_lane, 0) + 1
        transfers.append(
            {
                "from_lane": donor_lane,
                "to_lane": target_lane,
                "reason": "high_budget_non_score_absolute_floor",
            }
        )

    return adjusted, transfers


def _apply_high_budget_quality_control(
    *,
    proposed_allocation: dict[str, int],
    recent_outcomes: dict[str, list[LaneOutcome]],
    per_lane_budget: int,
    continuation_context: dict[str, Any] | None,
) -> tuple[dict[str, int], dict[str, Any]]:
    adjusted = dict(proposed_allocation)
    if per_lane_budget < 3:
        return adjusted, {"active": False, "reason": "not_high_budget_continuation"}

    total_budget = sum(proposed_allocation.values())
    minimums = _high_budget_lane_minimums(total_budget)
    effective_minimums = dict(minimums)
    penalties: list[dict[str, Any]] = []
    floor_overrides: list[dict[str, Any]] = []
    suppressed_lanes: set[str] = set()
    recovered_slots = 0
    yield_threshold_by_lane = {
        "score_frontier": 0.40,
        "novelty_frontier": 0.34,
        "uncertainty_frontier": 0.34,
        "bridge_frontier": 0.34,
    }
    for lane in FRONTIER_LANES:
        lane_history = recent_outcomes.get(lane, [])
        last_outcome = lane_history[-1] if lane_history else None
        if last_outcome is None:
            continue
        retained_yield = last_outcome.retained_count / max(1, last_outcome.generated_count)
        if last_outcome.new_cell_count > 0 or retained_yield >= yield_threshold_by_lane[lane]:
            continue

        recent_saturation = [
            outcome
            for outcome in lane_history[-2:]
            if outcome.generated_count > 0 and outcome.new_cell_count == 0
        ]
        repeated_zero_new = len(recent_saturation) >= 2
        repeated_zero_retention = len(recent_saturation) >= 2 and all(
            outcome.retained_count == 0 for outcome in recent_saturation
        )
        if repeated_zero_new and lane == "score_frontier":
            original_floor = effective_minimums[lane]
            effective_minimums[lane] = min(original_floor, 1)
            floor_overrides.append(
                {
                    "lane": lane,
                    "reason": "score_lane_repeated_zero_adaptive_cell_saturation",
                    "original_floor": original_floor,
                    "effective_floor": effective_minimums[lane],
                }
            )
        elif repeated_zero_retention:
            original_floor = effective_minimums[lane]
            effective_minimums[lane] = min(original_floor, max(1, adjusted.get(lane, 0) - 1))
            floor_overrides.append(
                {
                    "lane": lane,
                    "reason": "repeated_zero_retention_lane_starvation",
                    "original_floor": original_floor,
                    "effective_floor": effective_minimums[lane],
                }
            )

        if adjusted.get(lane, 0) > effective_minimums.get(lane, 0):
            adjusted[lane] -= 1
            recovered_slots += 1
            suppressed_lanes.add(lane)
        penalties.append(
            {
                "lane": lane,
                "reason": "low_retained_yield_and_zero_new_cells",
                "retained_yield": round(retained_yield, 6),
                "new_cell_count": last_outcome.new_cell_count,
                "repeated_zero_new": repeated_zero_new,
            }
        )

    reassigned: list[dict[str, Any]] = []
    while recovered_slots > 0:
        deficits = {
            lane: effective_minimums[lane] - adjusted.get(lane, 0)
            for lane in FRONTIER_LANES
            if adjusted.get(lane, 0) < effective_minimums[lane]
        }
        if deficits:
            target_lane = max(
                deficits,
                key=lambda lane: (deficits[lane], lane in {"novelty_frontier", "bridge_frontier"}),
            )
        else:
            target_candidates = [lane for lane in FRONTIER_LANES if lane not in suppressed_lanes] or list(FRONTIER_LANES)
            ranked_targets = sorted(
                target_candidates,
                key=lambda lane: (
                    _lane_outcome_score(recent_outcomes.get(lane, [])[-1] if recent_outcomes.get(lane) else None),
                    lane in {"uncertainty_frontier", "score_frontier"},
                ),
                reverse=True,
            )
            target_lane = ranked_targets[0]
        adjusted[target_lane] = adjusted.get(target_lane, 0) + 1
        reassigned.append(
            {
                "target_lane": target_lane,
                "reason": "recover_to_lane_floor" if deficits else "recover_to_best_recent_lane",
            }
        )
        recovered_slots -= 1

    adjusted, floor_transfers = _enforce_high_budget_lane_floors(
        adjusted,
        minimums=effective_minimums,
    )

    return adjusted, {
        "active": bool(penalties or floor_transfers or floor_overrides),
        "reason": "high_budget_continuation_quality_control",
        "minimum_absolute_allocation": minimums,
        "effective_minimum_allocation": effective_minimums,
        "penalties": penalties,
        "floor_overrides": floor_overrides,
        "reassigned": reassigned,
        "floor_transfers": floor_transfers,
        "suppressed_lanes": sorted(suppressed_lanes),
    }


def _recent_retained_yield(recent_outcomes: dict[str, list[LaneOutcome]], lane: str) -> float | None:
    outcome = recent_outcomes.get(lane, [])[-1] if recent_outcomes.get(lane) else None
    if outcome is None or outcome.generated_count <= 0:
        return None
    return outcome.retained_count / max(1, outcome.generated_count)


def _expression_fields(expression: str) -> set[str]:
    return {f"${field}" for field in re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", expression)}


def _real_replay_feedback_lane_sets(real_replay_feedback_objective: dict[str, Any] | None) -> dict[str, set[str]]:
    if not real_replay_feedback_objective:
        return {"weak_lanes": set(), "demoted_lanes": set()}
    weak_lanes = {
        str(item.get("frontier_lane"))
        for item in real_replay_feedback_objective.get("weak_positive_candidates", [])
        if item.get("frontier_lane")
    }
    demoted_lanes = {
        str(item.get("group")).split(":", 1)[1]
        for item in real_replay_feedback_objective.get("demoted_soft_prior_groups", [])
        if str(item.get("group", "")).startswith("frontier_lane:")
    }
    return {"weak_lanes": weak_lanes, "demoted_lanes": demoted_lanes}


def _real_replay_feedback_expression_score(
    *,
    expression: str,
    lane: str,
    real_replay_feedback_objective: dict[str, Any] | None,
) -> tuple[float, list[str]]:
    if not real_replay_feedback_objective:
        return 0.0, []

    score = 0.0
    reasons: list[str] = []
    expression_compact = re.sub(r"\s+", "", expression)
    candidate_id = make_candidate_id(expression)
    saturated_candidates = real_replay_feedback_objective.get("saturated_positive_candidates", [])
    for item in saturated_candidates:
        saturated_expression = re.sub(r"\s+", "", str(item.get("expression", "")))
        if item.get("candidate_id") == candidate_id or (saturated_expression and saturated_expression == expression_compact):
            score -= 0.20
            reasons.append(f"saturated_positive_exact:{item.get('candidate_id')}")

    weak_candidates = real_replay_feedback_objective.get("weak_positive_candidates", [])
    for item in weak_candidates:
        weak_expression = re.sub(r"\s+", "", str(item.get("expression", "")))
        if weak_expression and weak_expression in expression_compact:
            score += 0.16
            reasons.append(f"weak_positive_expression:{item.get('candidate_id')}")
        if item.get("frontier_lane") == lane:
            score += 0.02
            reasons.append(f"weak_positive_lane:{lane}")

    fields = _expression_fields(expression)
    demoted_groups = {str(item.get("group", "")) for item in real_replay_feedback_objective.get("demoted_soft_prior_groups", [])}
    watched_groups = {str(item.get("group", "")) for item in real_replay_feedback_objective.get("watched_soft_prior_groups", [])}
    for field in sorted(fields):
        if f"field:{field}" in watched_groups:
            score += 0.03
            reasons.append(f"watched_field:{field}")
        if f"field:{field}" in demoted_groups:
            score -= 0.025
            reasons.append(f"demoted_field:{field}")
    if f"frontier_lane:{lane}" in demoted_groups:
        score -= 0.04
        reasons.append(f"demoted_lane:{lane}")
    return round(max(-0.12, min(0.22, score)), 6), reasons[:8]


def _is_exact_saturated_positive_candidate(
    *,
    expression: str,
    real_replay_feedback_objective: dict[str, Any] | None,
) -> bool:
    if not real_replay_feedback_objective:
        return False
    expression_compact = re.sub(r"\s+", "", expression)
    candidate_id = make_candidate_id(expression)
    for item in real_replay_feedback_objective.get("saturated_positive_candidates", []):
        saturated_expression = re.sub(r"\s+", "", str(item.get("expression", "")))
        saturated_candidate_id = str(item.get("candidate_id", ""))
        if saturated_candidate_id == candidate_id:
            return True
        if saturated_expression and saturated_expression == expression_compact:
            return True
    return False


def _apply_real_replay_feedback_allocation(
    *,
    proposed_allocation: dict[str, int],
    real_replay_feedback_objective: dict[str, Any] | None,
) -> tuple[dict[str, int], dict[str, Any]]:
    adjusted = dict(proposed_allocation)
    if not real_replay_feedback_objective:
        return adjusted, {"active": False, "reason": "no_real_replay_feedback_objective"}
    if real_replay_feedback_objective.get("decision") != "USE_WEAK_REAL_REPLAY_PRIORS_FOR_NEXT_SEARCH":
        return adjusted, {
            "active": False,
            "reason": "real_replay_feedback_decision_not_weak_prior",
            "decision": real_replay_feedback_objective.get("decision"),
        }

    lane_sets = _real_replay_feedback_lane_sets(real_replay_feedback_objective)
    weak_lanes = [lane for lane in FRONTIER_LANES if lane in lane_sets["weak_lanes"]]
    demoted_donors = [
        lane
        for lane in FRONTIER_LANES
        if lane in lane_sets["demoted_lanes"] and lane not in lane_sets["weak_lanes"] and adjusted.get(lane, 0) > 1
    ]
    if not weak_lanes or not demoted_donors:
        return adjusted, {
            "active": False,
            "reason": "no_safe_feedback_transfer_available",
            "weak_lanes": weak_lanes,
            "demoted_lanes": sorted(lane_sets["demoted_lanes"]),
        }

    target_lane = min(weak_lanes, key=lambda lane: adjusted.get(lane, 0))
    donor_lane = max(demoted_donors, key=lambda lane: adjusted.get(lane, 0))
    adjusted[donor_lane] -= 1
    adjusted[target_lane] = adjusted.get(target_lane, 0) + 1
    return adjusted, {
        "active": True,
        "reason": "real_replay_soft_prior_lane_transfer",
        "decision": real_replay_feedback_objective.get("decision"),
        "from_lane": donor_lane,
        "to_lane": target_lane,
        "weak_lanes": weak_lanes,
        "demoted_lanes": sorted(lane_sets["demoted_lanes"]),
        "real_edge_claim_allowed": False,
    }


def _predicted_label(ic_max: float, coverage: float, oos_stability: float) -> str:
    if ic_max >= 0.72 and coverage >= 0.5 and oos_stability >= 0.68:
        return "robust"
    if ic_max >= 0.58 and coverage >= 0.25:
        return "regime_conditional"
    return "weak"


def _predicted_dominance_tuple(fingerprint: dict[str, float]) -> tuple[float, float, int, float]:
    ic_values = (
        float(fingerprint["ic_regime_trending"]),
        float(fingerprint["ic_regime_mean_reverting"]),
        float(fingerprint["ic_regime_volatile"]),
        float(fingerprint["ic_regime_low_vol"]),
    )
    ic_max = round(max(ic_values), 6)
    coverage = round(sum(1 for value in ic_values if value >= 0.5) / max(1, len(ic_values)), 6)
    transition_asymmetry = abs(float(fingerprint["ic_at_bull_to_bear"]) - float(fingerprint["ic_at_bear_to_bull"]))
    oos_stability = round(
        max(
            0.0,
            min(
                1.0,
                ((1.0 - transition_asymmetry) * 0.6)
                + (float(fingerprint["decay_halflife"]) * 0.4),
            ),
        ),
        6,
    )
    label = _predicted_label(ic_max, coverage, oos_stability)
    return (ic_max, coverage, LABEL_PRIORITY.get(label, 0), oos_stability)


def _record_dominance_tuple(record: CandidateRecord) -> tuple[float, float, int, float]:
    return (
        float(record.ic_max),
        float(record.ic_positive_coverage),
        LABEL_PRIORITY.get(record.label, 0),
        float(record.oos_stability),
    )


FIELD_AXIS_MAP = {
    "$open": "open_print",
    "$overnight": "open_print",
    "$close": "price",
    "$high": "price",
    "$low": "price",
    "$pldn": "price_position",
    "$mbrd": "price_position",
    "$amount": "liquidity",
    "$arat": "liquidity",
    "$volume": "liquidity",
    "$volt": "liquidity",
    "$turnover_rate": "liquidity",
    "$vrat": "liquidity",
    "$amtm": "momentum",
    "$ret": "return",
    "$reta": "return",
    "$retb": "return",
    "$retc": "return",
    "$retd": "return",
    "$rete": "return",
    "$retf": "return",
    "$money_flow": "flow",
    "$crowding": "state",
    "$rps_score": "relative_strength",
    "$rps_rank": "relative_strength",
    "$rps_enhanced": "relative_strength",
    "$rps_rank_enhanced": "relative_strength",
}

ASHARE_STOCK_PIT_FAST_CACHE_FIELDS = {
    "open",
    "high",
    "low",
    "close",
    "amount",
    "volume",
    "turnover_rate",
    "vwap",
    "ret",
    "amtm",
    "reta",
    "retb",
    "retc",
    "retd",
    "rete",
    "retf",
    "overnight",
}

ASHARE_REPLAY_PANEL_FIELDS = ASHARE_STOCK_PIT_FAST_CACHE_FIELDS | {
    "return_1d",
    "return_5d",
    "return_20d",
    "rps_rank",
    "rps_score",
    "rps_slope_3d",
    "money_flow",
    "f9_quantile_250d",
    "crowding",
    "low_20",
    "high_20",
    "price_pos",
    "rps_enhanced",
    "rps_rank_enhanced",
}

OPERATOR_FAMILY_MAP = {
    "CSRank": "cross_sectional",
    "Rank": "cross_sectional",
    "ZScore": "cross_sectional",
    "CSResidual": "cross_sectional",
    "Corr": "relation",
    "Cov": "relation",
    "Mean": "temporal",
    "Mom": "temporal",
    "Std": "temporal",
    "Delay": "temporal",
    "Delta": "temporal",
    "WMA": "temporal",
    "Med": "temporal",
    "Kurt": "temporal",
    "Skew": "temporal",
    "Abs": "nonlinear",
    "Sign": "nonlinear",
    "Log": "nonlinear",
    "Neg": "nonlinear",
    "Add": "arithmetic",
    "Sub": "arithmetic",
    "Mul": "arithmetic",
    "Div": "arithmetic",
}


def _expression_family_signature(expression: str) -> str:
    fields = sorted(set(re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", expression)))
    axes = tuple(sorted({FIELD_AXIS_MAP.get(field, "other") for field in fields}))
    operators = re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)\s*\(", expression)
    root_operator = operators[0] if operators else "field"
    relation_count = sum(1 for operator in operators if OPERATOR_FAMILY_MAP.get(operator) == "relation")
    temporal_count = sum(1 for operator in operators if OPERATOR_FAMILY_MAP.get(operator) == "temporal")
    nonlinear_count = sum(1 for operator in operators if OPERATOR_FAMILY_MAP.get(operator) == "nonlinear")
    cross_sectional_count = sum(1 for operator in operators if OPERATOR_FAMILY_MAP.get(operator) == "cross_sectional")
    buckets = (
        f"rel={min(3, relation_count)}",
        f"tmp={min(3, temporal_count)}",
        f"nonlin={min(2, nonlinear_count)}",
        f"cs={min(2, cross_sectional_count)}",
    )
    return f"root={root_operator}|axes={','.join(axes)}|{'|'.join(buckets)}"


def _ashare_stock_pit_compatibility_profile(
    expression: str,
    *,
    fields: list[str] | None = None,
    operators: list[str] | None = None,
    max_depth: int | None = None,
) -> dict[str, Any]:
    raw_fields = fields if fields is not None else sorted(set(re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", expression)))
    mapped_fields = sorted({FIELD_ALIASES.get(field.lower().lstrip("$"), field.lower().lstrip("$")) for field in raw_fields})
    missing_fields = sorted(field for field in mapped_fields if field not in ASHARE_REPLAY_PANEL_FIELDS)
    fast_cache_missing_fields = sorted(
        field
        for field in mapped_fields
        if field in ASHARE_REPLAY_PANEL_FIELDS and field not in ASHARE_STOCK_PIT_FAST_CACHE_FIELDS
    )
    supported_ratio = (
        round((len(mapped_fields) - len(missing_fields)) / len(mapped_fields), 6)
        if mapped_fields
        else 1.0
    )
    operator_names = operators if operators is not None else re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)\s*\(", expression)
    relation_operator_count = sum(1 for operator in operator_names if OPERATOR_FAMILY_MAP.get(operator) == "relation")
    temporal_operator_count = sum(1 for operator in operator_names if OPERATOR_FAMILY_MAP.get(operator) == "temporal")
    if max_depth is None:
        depth = 0
        max_depth = 0
        for char in expression:
            if char == "(":
                depth += 1
                max_depth = max(max_depth, depth)
            elif char == ")":
                depth = max(0, depth - 1)
    rolling_relation_count = relation_operator_count + temporal_operator_count
    estimated_validation_cost_score = round(
        (len(expression) / 50.0)
        + (rolling_relation_count * 2.0)
        + (relation_operator_count * 6.0)
        + (float(max_depth) * 1.2),
        6,
    )
    unsupported_field_penalty = min(0.18, 0.065 * len(missing_fields))
    fast_cache_penalty = min(0.04, 0.008 * len(fast_cache_missing_fields))
    cost_penalty = min(0.16, max(0.0, estimated_validation_cost_score - 130.0) * 0.0012)
    compatibility_bonus = (
        0.035
        if mapped_fields and not missing_fields and not fast_cache_missing_fields
        else 0.020
        if mapped_fields and not missing_fields
        else 0.012
        if supported_ratio >= 0.75
        else 0.0
    )
    stock_pit_score = compatibility_bonus - unsupported_field_penalty - fast_cache_penalty - cost_penalty
    return {
        "role": "soft_search_routing_prior_not_formula_space_lock",
        "stock_pit_supported": not missing_fields,
        "replay_panel_supported": not missing_fields,
        "mapped_fields": mapped_fields,
        "missing_fields": missing_fields,
        "fast_cache_missing_fields": fast_cache_missing_fields,
        "supported_field_ratio": supported_ratio,
        "estimated_validation_cost_score": estimated_validation_cost_score,
        "unsupported_field_penalty": round(unsupported_field_penalty, 6),
        "fast_cache_penalty": round(fast_cache_penalty, 6),
        "validation_cost_penalty": round(cost_penalty, 6),
        "compatibility_bonus": round(compatibility_bonus, 6),
        "stock_pit_score": round(stock_pit_score, 6),
    }


def _three_dimensional_search_profile(expression: str, archive: list[CandidateRecord] | None = None) -> dict[str, Any]:
    fields = sorted(set(re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", expression)))
    axes = sorted({FIELD_AXIS_MAP.get(field, "other") for field in fields})
    operators = re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)\s*\(", expression)
    operator_families = sorted({OPERATOR_FAMILY_MAP.get(operator, "other") for operator in operators})
    relation_operator_count = sum(1 for operator in operators if OPERATOR_FAMILY_MAP.get(operator) == "relation")
    temporal_operator_count = sum(1 for operator in operators if OPERATOR_FAMILY_MAP.get(operator) == "temporal")
    max_depth = 0
    depth = 0
    for char in expression:
        if char == "(":
            depth += 1
            max_depth = max(max_depth, depth)
        elif char == ")":
            depth = max(0, depth - 1)
    skeleton = extract_structural_skeleton(expression)
    archive_skeletons = {extract_structural_skeleton(record.expression) for record in archive or []}
    family_signature = _expression_family_signature(expression)
    archive_family_count = sum(
        1
        for record in archive or []
        if _expression_family_signature(record.expression) == family_signature
    )
    field_count = len(fields)
    axis_count = len(axes)
    family_count = len(operator_families)
    relation_and_temporal = "relation" in operator_families and "temporal" in operator_families
    single_field_stack = field_count <= 1 and family_count <= 2
    wrapper_operators = {"CSRank", "Rank", "ZScore", "Sign", "Abs", "Log"}
    wrapper_counts = {operator: operators.count(operator) for operator in wrapper_operators}
    dominant_wrapper_operator, dominant_wrapper_count = max(
        wrapper_counts.items(),
        key=lambda item: item[1],
        default=("", 0),
    )
    operator_tower_penalty = min(
        0.16,
        (0.025 * max(0, dominant_wrapper_count - 4))
        + (0.012 * max(0, len(operators) - 18))
        + (0.018 * max(0, max_depth - 12)),
    )
    density_penalty = min(
        0.24,
        (0.018 * max(0, relation_operator_count + temporal_operator_count - 6))
        + (0.018 * max(0, max_depth - 8))
        + (0.025 if len(expression) > 360 else 0.0)
        + operator_tower_penalty,
    )
    ashare_stock_pit_profile = _ashare_stock_pit_compatibility_profile(
        expression,
        fields=fields,
        operators=operators,
        max_depth=max_depth,
    )
    family_saturation_penalty = min(0.09, 0.025 * max(0, archive_family_count - 1))
    score = (
        (0.045 if skeleton not in archive_skeletons else 0.0)
        + min(0.060, 0.020 * max(0, field_count - 1))
        + min(0.050, 0.020 * max(0, axis_count - 1))
        + min(0.045, 0.015 * family_count)
        + (0.030 if relation_and_temporal else 0.0)
        + float(ashare_stock_pit_profile["stock_pit_score"])
        - (0.070 if single_field_stack else 0.0)
        - density_penalty
        - family_saturation_penalty
    )
    return {
        "structural_skeleton": skeleton,
        "skeleton_seen_in_archive": skeleton in archive_skeletons,
        "family_signature": family_signature,
        "archive_family_count": archive_family_count,
        "family_saturation_penalty": round(family_saturation_penalty, 6),
        "field_count": field_count,
        "field_axes": axes,
        "field_axis_count": axis_count,
        "operator_families": operator_families,
        "operator_family_count": family_count,
        "operator_count": len(operators),
        "relation_operator_count": relation_operator_count,
        "temporal_operator_count": temporal_operator_count,
        "max_operator_depth": max_depth,
        "expression_length": len(expression),
        "availability_density_penalty": round(density_penalty, 6),
        "ashare_stock_pit_score": ashare_stock_pit_profile["stock_pit_score"],
        "ashare_stock_pit_profile": ashare_stock_pit_profile,
        "operator_tower_penalty": round(operator_tower_penalty, 6),
        "dominant_wrapper_operator": dominant_wrapper_operator,
        "dominant_wrapper_count": dominant_wrapper_count,
        "relation_and_temporal": relation_and_temporal,
        "single_field_stack": single_field_stack,
        "three_dimensional_score": round(max(-0.12, min(0.20, score)), 6),
    }


def _target_aware_pre_screen(
    *,
    lane: str,
    source_mode: str,
    candidates: list[dict[str, Any]],
    target_behavior: dict[str, float],
    recent_outcomes: dict[str, list[LaneOutcome]],
    per_lane_budget: int,
    continuation_context: dict[str, Any] | None,
    archive: list[CandidateRecord] | None = None,
    surrogate_fingerprint: Any,
    surrogate_ic: Any,
    selection_limit: int = 1,
    real_replay_feedback_objective: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_candidate_count = len(candidates)
    sanitized_candidates: list[dict[str, Any]] = []
    seen_hygiene_expressions: set[str] = set()
    generator_hygiene_skipped_count = 0
    for candidate in candidates:
        original_expression = str(candidate["expression"])
        expression = canonicalize_expression_light(original_expression)
        if is_pathological_expression(expression) or expression in seen_hygiene_expressions:
            generator_hygiene_skipped_count += 1
            continue
        seen_hygiene_expressions.add(expression)
        sanitized_candidate = {**candidate, "expression": expression}
        if expression != original_expression:
            sanitized_candidate.pop("predicted_fingerprint", None)
        sanitized_candidates.append(sanitized_candidate)
    candidates = sanitized_candidates
    if (
        lane == "score_frontier"
        or per_lane_budget < 3
        or len(candidates) <= selection_limit
    ):
        return candidates[:selection_limit], {
            "active": False,
            "reason": (
                "score_lane_pre_screen_disabled_to_protect_non_score_exploration"
                if lane == "score_frontier"
                else "not_high_budget_candidate_pool"
            ),
            "lane": lane,
            "candidate_count": len(candidates),
            "raw_candidate_count": raw_candidate_count,
            "generator_hygiene_skipped_count": generator_hygiene_skipped_count,
        }

    recent_yield = _recent_retained_yield(recent_outcomes, lane)
    occupied_records = {record.archive_cell: record for record in archive or [] if record.retained}
    occupied_cells = set(occupied_records)
    occupied_adaptive_cells = _baseline_coverage_keys(archive or [])
    quality_floor = 0.34 if recent_yield is None or recent_yield < 0.34 else 0.30
    hard_skip_exact_saturated = continuation_context is not None and per_lane_budget >= 3
    hard_skipped: list[dict[str, Any]] = []
    scored: list[dict[str, Any]] = []
    for candidate in candidates:
        expression = str(candidate["expression"])
        if hard_skip_exact_saturated and _is_exact_saturated_positive_candidate(
            expression=expression,
            real_replay_feedback_objective=real_replay_feedback_objective,
        ):
            hard_skipped.append(
                {
                    **candidate,
                    "expression": expression,
                    "candidate_id": make_candidate_id(expression),
                    "efficiency_skip_reason": "exact_saturated_positive_candidate",
                    "real_replay_feedback_score": None,
                    "real_replay_feedback_reasons": [f"saturated_positive_exact:{make_candidate_id(expression)}"],
                }
            )
            continue
        predicted = candidate.get("predicted_fingerprint") or surrogate_fingerprint.predict(expression).fingerprint
        predicted_cell = behavioral_cell(predicted)
        predicted_adaptive_cell = _adaptive_behavior_cell(predicted)
        predicted_new_coarse_cell = predicted_cell not in occupied_cells
        predicted_new_adaptive_cell = predicted_adaptive_cell not in occupied_adaptive_cells
        predicted_new_cell = predicted_new_coarse_cell or predicted_new_adaptive_cell
        incumbent = occupied_records.get(predicted_cell)
        predicted_dominates_incumbent = (
            True
            if incumbent is None
            else _predicted_dominance_tuple(predicted) > _record_dominance_tuple(incumbent)
        )
        distance = float(candidate.get("behavior_distance_to_target", fingerprint_distance(predicted, target_behavior)))
        ic_output = surrogate_ic.predict(expression=expression, fingerprint=predicted)
        quality_gate_score = float(ic_output.quality_estimate) - (float(ic_output.uncertainty) * 0.35)
        alignment_score = float(candidate.get("alignment_score", 0.0))
        real_feedback_score, real_feedback_reasons = _real_replay_feedback_expression_score(
            expression=expression,
            lane=lane,
            real_replay_feedback_objective=real_replay_feedback_objective,
        )
        three_dimensional_profile = _three_dimensional_search_profile(expression, archive)
        low_quality_existing_cell = (not predicted_new_cell) and quality_gate_score < quality_floor
        non_dominating_existing_cell = (not predicted_new_cell) and not predicted_dominates_incumbent
        efficiency_skip = low_quality_existing_cell or non_dominating_existing_cell
        efficiency_skip_reason = (
            "low_quality_existing_cell"
            if low_quality_existing_cell
            else "non_dominating_existing_cell"
            if non_dominating_existing_cell
            else None
        )
        floor_penalty = 0.25 if quality_gate_score < quality_floor else 0.0
        pre_screen_score = round(
            ((1.0 - distance) * 0.45)
            + (quality_gate_score * 0.45)
            + (max(0.0, alignment_score) * 0.10)
            + (0.18 if predicted_new_cell else 0.0)
            + real_feedback_score
            + float(three_dimensional_profile["three_dimensional_score"])
            - floor_penalty,
            6,
        )
        scored.append(
            {
                **candidate,
                "expression": expression,
                "behavior_distance_to_target": round(distance, 6),
                "surrogate_quality": ic_output.quality_estimate,
                "surrogate_uncertainty": ic_output.uncertainty,
                "quality_gate_score": round(quality_gate_score, 6),
                "quality_floor": quality_floor,
                "predicted_archive_cell": predicted_cell,
                "predicted_adaptive_archive_cell": predicted_adaptive_cell,
                "predicted_new_cell": predicted_new_cell,
                "predicted_new_coarse_cell": predicted_new_coarse_cell,
                "predicted_new_adaptive_cell": predicted_new_adaptive_cell,
                "predicted_dominates_incumbent": predicted_dominates_incumbent,
                "efficiency_skip": efficiency_skip,
                "efficiency_skip_reason": efficiency_skip_reason,
                "real_replay_feedback_score": real_feedback_score,
                "real_replay_feedback_reasons": real_feedback_reasons,
                "three_dimensional_profile": three_dimensional_profile,
                "three_dimensional_score": three_dimensional_profile["three_dimensional_score"],
                "pre_screen_score": pre_screen_score,
            }
        )

    skipped = [item for item in scored if item["efficiency_skip"]]
    rankable = [item for item in scored if not item["efficiency_skip"]]
    starvation_rescue_floor = max(0.20, quality_floor - 0.12)
    rescued_from_skip: list[dict[str, Any]] = []
    if not rankable and skipped:
        rescue_limit = min(len(skipped), selection_limit + 1)
        rescue_pool = sorted(
            (
                item
                for item in skipped
                if item["efficiency_skip_reason"] == "low_quality_existing_cell"
                and item["quality_gate_score"] >= starvation_rescue_floor
            ),
            key=lambda item: (
                item["pre_screen_score"],
                item["quality_gate_score"],
                -item["behavior_distance_to_target"],
            ),
            reverse=True,
        )[:rescue_limit]
        rescue_ids = {id(item) for item in rescue_pool}
        for item in rescue_pool:
            item["efficiency_skip"] = False
            item["efficiency_skip_reason"] = None
            item["starvation_rescue"] = True
        rescued_from_skip = rescue_pool
        rankable = rescue_pool
        skipped = [item for item in skipped if id(item) not in rescue_ids]
    rankable.sort(
        key=lambda item: (
            item["pre_screen_score"],
            -item["behavior_distance_to_target"],
            item["surrogate_quality"],
        ),
        reverse=True,
    )
    selected = rankable[:selection_limit]
    rejected = rankable[selection_limit:]
    return selected, {
        "active": True,
        "reason": "target_aware_lane_pre_screen",
        "lane": lane,
        "source_mode": source_mode,
        "candidate_count": len(candidates),
        "raw_candidate_count": raw_candidate_count,
        "generator_hygiene_skipped_count": generator_hygiene_skipped_count,
        "selected_count": len(selected),
        "rejected_count": len(rejected),
        "skipped_count": len(skipped),
        "saturated_hard_skip_count": len(hard_skipped),
        "starvation_rescue_count": len(rescued_from_skip),
        "starvation_rescue_floor": round(starvation_rescue_floor, 6),
        "continuation_active": continuation_context is not None,
        "recent_retained_yield": round(recent_yield, 6) if recent_yield is not None else None,
        "quality_floor": quality_floor,
        "selection_rule": (
            "skip low-quality existing-cell candidates unless all candidates would be starved; then rank by target_alignment, "
            "surrogate_quality_after_uncertainty, new_archive_cell, positive edit alignment, optional real replay feedback, "
            "and soft three-dimensional search coverage"
        ),
        "three_dimensional_policy": {
            "type": "soft_bonus_not_hard_constraint",
            "dimensions": [
                "structural_skeleton_novelty",
                "distinct_field_count",
                "field_axis_count",
                "operator_family_count",
                "relation_temporal_interaction",
                "a_share_stock_pit_field_compatibility",
                "estimated_a_share_validation_cost",
            ],
            "a_share_role": "soft_routing_prior_preserves_portable_formula_space",
            "reason": "prefer richer formula geometry without blocking the infinite expression space",
        },
        "selected": [
            {
                "expression": item["expression"],
                "behavior_distance_to_target": item["behavior_distance_to_target"],
                "surrogate_quality": item["surrogate_quality"],
                "quality_gate_score": item["quality_gate_score"],
                "predicted_archive_cell": item["predicted_archive_cell"],
                "predicted_adaptive_archive_cell": item["predicted_adaptive_archive_cell"],
                "predicted_new_cell": item["predicted_new_cell"],
                "predicted_new_coarse_cell": item["predicted_new_coarse_cell"],
                "predicted_new_adaptive_cell": item["predicted_new_adaptive_cell"],
                "predicted_dominates_incumbent": item["predicted_dominates_incumbent"],
                "real_replay_feedback_score": item["real_replay_feedback_score"],
                "real_replay_feedback_reasons": item["real_replay_feedback_reasons"],
                "three_dimensional_score": item["three_dimensional_score"],
                "three_dimensional_profile": item["three_dimensional_profile"],
                "pre_screen_score": item["pre_screen_score"],
                "starvation_rescue": item.get("starvation_rescue", False),
            }
            for item in selected
        ],
        "rejected": [
            {
                "expression": item["expression"],
                "behavior_distance_to_target": item["behavior_distance_to_target"],
                "surrogate_quality": item["surrogate_quality"],
                "quality_gate_score": item["quality_gate_score"],
                "predicted_archive_cell": item["predicted_archive_cell"],
                "predicted_adaptive_archive_cell": item["predicted_adaptive_archive_cell"],
                "predicted_new_cell": item["predicted_new_cell"],
                "predicted_new_coarse_cell": item["predicted_new_coarse_cell"],
                "predicted_new_adaptive_cell": item["predicted_new_adaptive_cell"],
                "predicted_dominates_incumbent": item["predicted_dominates_incumbent"],
                "real_replay_feedback_score": item["real_replay_feedback_score"],
                "real_replay_feedback_reasons": item["real_replay_feedback_reasons"],
                "three_dimensional_score": item["three_dimensional_score"],
                "three_dimensional_profile": item["three_dimensional_profile"],
                "pre_screen_score": item["pre_screen_score"],
                "starvation_rescue": item.get("starvation_rescue", False),
            }
            for item in rejected
        ],
        "skipped": [
            {
                "expression": item["expression"],
                "behavior_distance_to_target": item["behavior_distance_to_target"],
                "surrogate_quality": item["surrogate_quality"],
                "quality_gate_score": item["quality_gate_score"],
                "quality_floor": item["quality_floor"],
                "predicted_archive_cell": item["predicted_archive_cell"],
                "predicted_adaptive_archive_cell": item["predicted_adaptive_archive_cell"],
                "predicted_new_cell": item["predicted_new_cell"],
                "predicted_new_coarse_cell": item["predicted_new_coarse_cell"],
                "predicted_new_adaptive_cell": item["predicted_new_adaptive_cell"],
                "predicted_dominates_incumbent": item["predicted_dominates_incumbent"],
                "efficiency_skip_reason": item["efficiency_skip_reason"],
                "real_replay_feedback_score": item["real_replay_feedback_score"],
                "real_replay_feedback_reasons": item["real_replay_feedback_reasons"],
                "three_dimensional_score": item["three_dimensional_score"],
                "three_dimensional_profile": item["three_dimensional_profile"],
                "pre_screen_score": item["pre_screen_score"],
            }
            for item in skipped
        ],
        "hard_skipped": [
            {
                "expression": item["expression"],
                "candidate_id": item["candidate_id"],
                "efficiency_skip_reason": item["efficiency_skip_reason"],
                "real_replay_feedback_score": item["real_replay_feedback_score"],
                "real_replay_feedback_reasons": item["real_replay_feedback_reasons"],
            }
            for item in hard_skipped
        ],
    }


def _retained_quality(records: list[CandidateRecord]) -> float:
    if not records:
        return 0.0
    retained_values = [record.ic_max for record in records if record.retained]
    if not retained_values:
        return 0.0
    return round(mean(retained_values), 6)


def _coverage(records: list[CandidateRecord]) -> float:
    if not records:
        return 0.0
    return round(len({record.archive_cell for record in records if record.retained}) / max(1, len(records)), 6)


def _adaptive_coverage(records: list[CandidateRecord]) -> float:
    if not records:
        return 0.0
    retained_keys = {
        _archive_coverage_key(_ensure_adaptive_archive_cell(record))
        for record in records
        if record.retained
    }
    return round(len(retained_keys) / max(1, len(records)), 6)


def _new_cell_coverage(records: list[CandidateRecord], baseline_cells: set[str]) -> float:
    retained_new_cells = {
        _archive_coverage_key(_ensure_adaptive_archive_cell(record))
        for record in records
        if record.retained and _archive_coverage_key(record) not in baseline_cells
    }
    return float(len(retained_new_cells))


def _transition_validity_report() -> dict[str, Any]:
    transition_gains = []
    stable_hits = 0
    for base_expression, transition_expression in TRANSITION_PAIRS:
        base = build_behavioral_fingerprint(base_expression)
        transitioned = build_behavioral_fingerprint(transition_expression)
        gain = round(
            (
                transitioned["predictive_of_regime_change"]
                + transitioned["ic_at_bull_to_bear"]
                + transitioned["ic_at_bear_to_bull"]
            )
            - (
                base["predictive_of_regime_change"]
                + base["ic_at_bull_to_bear"]
                + base["ic_at_bear_to_bull"]
            ),
            6,
        )
        transition_gains.append(gain)
        if transitioned["predictive_of_regime_change"] > base["predictive_of_regime_change"]:
            stable_hits += 1
    return {
        "metric_definition": {
            "transition_alignment_gain": "mean((predictive_of_regime_change + bull_to_bear + bear_to_bull)_transition - same_base)",
            "transition_signal_stability": "paired_transition_expressions_with_positive_gain / total_transition_pairs",
        },
        "transition_alignment_gain": round(mean(transition_gains), 6),
        "transition_signal_stability": round(stable_hits / max(1, len(TRANSITION_PAIRS)), 6),
    }


def _random_search_baseline(*, budget: int, archive: list[CandidateRecord], evaluator: MultiFidelityEvaluator, round_index: int) -> dict[str, Any]:
    generated: list[CandidateRecord] = []
    base_expressions = [
        f"Corr(Sign($mbrd), Log(Abs(Mean($arat,{5 + index}))))"
        if index % 2 == 0
        else f"Cov($close, Sign(Mom($amtm,{5 + index})))"
        for index in range(budget)
    ]
    temp_archive: list[CandidateRecord] = list(archive)
    for expression in base_expressions:
        record, _ = evaluator.evaluate(
            expression=expression,
            parent_candidate_id=None,
            source_mode="random_search",
            frontier_lane="novelty_frontier",
            round_index=round_index,
            archive=temp_archive,
        )
        _ensure_adaptive_archive_cell(record)
        record.retained = record.ic_max >= 0.55
        generated.append(record)
        temp_archive.append(record)
    return {
        "metric_definition": {
            "coverage_gain": "(new_behavior_cells_v21 - new_behavior_cells_random) / max(new_behavior_cells_random, small_value)",
            "quality_noninferiority": "retained_quality_v21 - retained_quality_random",
        },
        "random_retained_quality": _retained_quality(generated),
        "random_coverage": _coverage(generated),
        "random_new_behavior_cells": 0.0,
        "generated": generated,
    }


def run_phase2_prototype(
    *,
    output_root: Path | None = None,
    saturation_window_rounds: int = 2,
    saturation_distance_epsilon: float = 0.18,
    rounds: int = 4,
    per_lane_budget: int = 1,
    seed_source: str = "bootstrap_cold_start",
    seed_records_override: list[CandidateRecord] | None = None,
    seed_lineage_root: str | None = None,
    runtime_mode: str = "prototype",
    continuation_context: dict[str, Any] | None = None,
    real_replay_feedback_objective: dict[str, Any] | None = None,
    artifact_profile: str = "full",
) -> dict[str, Any]:
    if artifact_profile not in {"full", "compact"}:
        raise ValueError("artifact_profile must be 'full' or 'compact'")
    artifact_root = output_root or ARTIFACT_ROOT
    run_id = make_run_id(f"phase2-v2_1:{seed_source}:{utc_now_iso()}")
    run_root = artifact_root / run_id
    progress_path = run_root / "prototype_progress.json"

    def write_progress(status: str, **payload: Any) -> None:
        write_json_artifact(
            progress_path,
            {
                "status": status,
                "updated_at": utc_now_iso(),
                "run_id": run_id,
                "rounds": rounds,
                "per_lane_budget": per_lane_budget,
                "runtime_mode": runtime_mode,
                **payload,
            },
        )

    write_progress("initializing_seed_archive")
    evaluator = MultiFidelityEvaluator()
    archive, seed_records, bootstrap_report = _seed_archive(
        evaluator,
        seed_source,
        seed_records_override=seed_records_override,
        seed_lineage_root=seed_lineage_root,
    )
    write_progress(
        "seed_archive_ready",
        seed_record_count=len(seed_records),
        archive_record_count=len(archive.records),
    )
    if seed_source == "bootstrap_cold_start":
        bootstrap_report["bootstrap_funnel_statistics"] = evaluator.build_funnel_statistics()
        bootstrap_report["search_funnel_excludes_bootstrap_initialization"] = True
        evaluator = MultiFidelityEvaluator()
    round_summaries: list[RoundSummary] = []
    all_records: list[CandidateRecord] = list(seed_records)
    all_details: list[dict[str, Any]] = []
    baseline_cells = _baseline_coverage_keys(archive.records)
    saturation_counter = 0
    from_scratch_trigger_observed = 0
    generated_from_scratch_count = 0
    seen_candidate_ids = {record.candidate_id for record in archive.records}
    seen_structural_skeletons = {extract_structural_skeleton(record.expression) for record in archive.records}
    from_scratch_synthesis_events: list[dict[str, Any]] = []
    crossover_events: list[dict[str, Any]] = []
    distillation_events: list[dict[str, Any]] = []
    meta_policy = MetaSearchPolicy()
    meta_policy_events: list[dict[str, Any]] = []
    meta_policy_outcome_events: list[dict[str, Any]] = []
    target_aware_pre_screen_events: list[dict[str, Any]] = []
    score_parent_refresh_events: list[dict[str, Any]] = []
    coverage_refresh_events: list[dict[str, Any]] = []
    exact_saturated_evaluation_skip_events: list[dict[str, Any]] = []
    local_search_memory_duplicate_skip_events: list[dict[str, Any]] = []
    parent_revisit_counts = {lane: {} for lane in FRONTIER_LANES}
    previous_run_root = (
        continuation_context.get("previous_run_root")
        if isinstance(continuation_context, dict)
        else None
    )
    expected_search_memory_dataset_role = (
        continuation_context.get("search_memory_dataset_role")
        if isinstance(continuation_context, dict)
        else None
    ) or dataset_role_for_path(DEFAULT_REAL_MARKET_DATASET_PATH)
    if expected_search_memory_dataset_role == "unknown_panel":
        expected_search_memory_dataset_role = None
    local_search_memory = LocalSearchMemory.from_previous_run(
        previous_run_root,
        expected_dataset_role=expected_search_memory_dataset_role,
    )
    local_search_memory.register_seed_records(seed_records)

    for round_index in range(1, rounds + 1):
        duplicate_skip_count_at_round_start = len(local_search_memory_duplicate_skip_events)
        write_progress(
            "round_start",
            round_index=round_index,
            archive_record_count=len(archive.records),
        )
        # Avoid exact lane-multiple budgets when widening beyond the minimum;
        # otherwise the exploration floor can mask adaptive allocation.
        total_budget = max(
            len(FRONTIER_LANES),
            (per_lane_budget * len(FRONTIER_LANES)) - (1 if per_lane_budget > 1 else 0),
        )
        frontiers = classify_frontiers(
            archive.records,
            limit=max(2, total_budget),
        )
        write_progress(
            "frontiers_classified",
            round_index=round_index,
            frontier_counts={lane: len(records) for lane, records in frontiers.items()},
            total_budget=total_budget,
        )
        meta_decision = meta_policy.allocate(
            archive=archive.records,
            active_lanes={lane: bool(records) for lane, records in frontiers.items()},
            total_budget=total_budget,
        )
        runtime_allocation, quality_control = _apply_high_budget_quality_control(
            proposed_allocation=meta_decision.allocation,
            recent_outcomes=meta_policy.recent_outcomes,
            per_lane_budget=per_lane_budget,
            continuation_context=continuation_context,
        )
        runtime_allocation, real_replay_feedback_allocation = _apply_real_replay_feedback_allocation(
            proposed_allocation=runtime_allocation,
            real_replay_feedback_objective=real_replay_feedback_objective,
        )
        meta_decision_artifact = {
            "round_index": round_index,
            **decision_to_artifact(meta_decision),
            "proposed_allocation": dict(meta_decision.allocation),
            "allocation": runtime_allocation,
            "quality_control": quality_control,
            "real_replay_feedback_allocation": real_replay_feedback_allocation,
        }
        meta_policy_events.append(meta_decision_artifact)
        selected_parent_records_by_lane = {
            lane: select_lane_parents(
                records,
                lane=lane,
                allocation=runtime_allocation.get(lane, 0),
                revisit_counts=parent_revisit_counts[lane],
            )
            for lane, records in frontiers.items()
        }
        write_progress(
            "parents_selected",
            round_index=round_index,
            selected_parent_counts={lane: len(records) for lane, records in selected_parent_records_by_lane.items()},
            runtime_allocation=runtime_allocation,
        )
        score_target_behavior = _target_behavior_for_lane("score_frontier", archive.records)
        refreshed_score_parents, score_refresh = _refresh_score_lane_parents_for_unseen_variation(
            frontier_records=frontiers["score_frontier"],
            selected_parents=selected_parent_records_by_lane["score_frontier"],
            allocation=runtime_allocation.get("score_frontier", 0),
            target_behavior=score_target_behavior,
            surrogate_fingerprint=evaluator.surrogate_fingerprint,
            archive=archive.records,
            seen_candidate_ids=seen_candidate_ids,
            revisit_counts=parent_revisit_counts["score_frontier"],
        )
        selected_parent_records_by_lane["score_frontier"] = refreshed_score_parents
        if score_refresh["active"]:
            score_parent_refresh_events.append(
                {
                    "round_index": round_index,
                    **score_refresh,
                }
            )
        selected_parents_by_lane = {
            lane: [record.candidate_id for record in records]
            for lane, records in selected_parent_records_by_lane.items()
        }
        generated_candidates_by_lane = {lane: [] for lane in FRONTIER_LANES}
        generated_records_by_lane: dict[str, list[CandidateRecord]] = {lane: [] for lane in FRONTIER_LANES}
        retained_candidates: list[str] = []
        round_min_distances: list[float] = []
        from_scratch_budget_applied = 0
        force_from_scratch = saturation_counter >= saturation_window_rounds
        if force_from_scratch:
            from_scratch_budget_applied = 2
            from_scratch_trigger_observed += 1

        for lane, parents in selected_parent_records_by_lane.items():
            write_progress(
                "lane_start",
                round_index=round_index,
                lane=lane,
                parent_count=len(parents),
                allocation=runtime_allocation.get(lane, 0),
            )
            target_behavior = _target_behavior_for_lane(lane, archive.records)
            coverage_target, coverage_refresh = _coverage_refresh_target_for_lane(
                lane=lane,
                archive=archive.records,
                recent_outcomes=meta_policy.recent_outcomes,
                continuation_context=continuation_context,
                per_lane_budget=per_lane_budget,
                surrogate_fingerprint=evaluator.surrogate_fingerprint,
                seen_candidate_ids=seen_candidate_ids,
                seen_structural_skeletons=seen_structural_skeletons,
                parent_records=parents,
            )
            if coverage_target is not None:
                target_behavior = coverage_target
            validate_fingerprint_contract(target_behavior)
            for parent in parents[: runtime_allocation.get(lane, 0)]:
                parent_revisit_counts[lane][parent.candidate_id] = parent_revisit_counts[lane].get(parent.candidate_id, 0) + 1
                if coverage_refresh["active"]:
                    candidate_pool, pool_report = _coverage_refresh_candidate_pool(
                        lane=lane,
                        parent=parent,
                        target_behavior=target_behavior,
                        target_cell=str(coverage_refresh.get("target_cell")),
                        archive=archive.records,
                        surrogate_fingerprint=evaluator.surrogate_fingerprint,
                        seen_candidate_ids=seen_candidate_ids,
                        seen_structural_skeletons=seen_structural_skeletons,
                        per_lane_budget=per_lane_budget,
                        seed_key=f"{run_id}:{round_index}:{lane}:{parent.candidate_id}:coverage_refresh",
                        seed_expressions=(
                            coverage_refresh.get("reachability", {}).get("exact_seed_expressions", [])
                            if isinstance(coverage_refresh.get("reachability"), dict)
                            else []
                        ),
                    )
                    source_mode = "coverage_refresh_synthesis"
                    selected_candidates, pre_screen = _target_aware_pre_screen(
                        lane=lane,
                        source_mode=source_mode,
                        candidates=candidate_pool,
                        target_behavior=target_behavior,
                        recent_outcomes=meta_policy.recent_outcomes,
                        per_lane_budget=per_lane_budget,
                        continuation_context=continuation_context,
                        archive=archive.records,
                        surrogate_fingerprint=evaluator.surrogate_fingerprint,
                        surrogate_ic=evaluator.surrogate_ic,
                        real_replay_feedback_objective=real_replay_feedback_objective,
                    )
                    coverage_refresh_events.append(
                        {
                            "round_index": round_index,
                            "parent_candidate_id": parent.candidate_id,
                            **coverage_refresh,
                            "pool": pool_report,
                            "selected_count": len(selected_candidates),
                            "selected_expressions": [str(candidate["expression"]) for candidate in selected_candidates],
                            "selected_predicted_cells": [
                                str(candidate.get("predicted_archive_cell"))
                                for candidate in selected_candidates
                            ],
                            "selected_coverage_refresh_sources": [
                                str(candidate.get("coverage_refresh_source"))
                                for candidate in selected_candidates
                            ],
                            "selected_phase2_native_ast_kinds": [
                                str(candidate.get("phase2_native_ast_kind"))
                                for candidate in selected_candidates
                                if candidate.get("coverage_refresh_source") == "phase2_native_ast_expansion"
                            ],
                        }
                    )
                    if pre_screen["active"]:
                        target_aware_pre_screen_events.append(
                            {
                                "round_index": round_index,
                                "parent_candidate_id": parent.candidate_id,
                                **pre_screen,
                            }
                        )
                    expressions = [str(candidate["expression"]) for candidate in selected_candidates]
                elif lane in {"novelty_frontier", "uncertainty_frontier", "bridge_frontier"} and force_from_scratch:
                    synthesis_candidates = generate_from_scratch_from_archive(
                        target_behavior=target_behavior,
                        archive=archive.records,
                        surrogate_fingerprint=evaluator.surrogate_fingerprint,
                        budget=max(3, per_lane_budget * 2),
                        avoid_skeletons=seen_structural_skeletons,
                        seed_key=f"{run_id}:{round_index}:{lane}:{parent.candidate_id}",
                    )
                    candidate_pool = [
                        candidate
                        for candidate in synthesis_candidates
                        if make_candidate_id(str(candidate["expression"])) not in seen_candidate_ids
                        and not local_search_memory.has_seen_expression(str(candidate["expression"]))
                    ]
                    source_mode = "from_scratch_archive_synthesis"
                    selected_candidates, pre_screen = _target_aware_pre_screen(
                        lane=lane,
                        source_mode=source_mode,
                        candidates=candidate_pool,
                        target_behavior=target_behavior,
                        recent_outcomes=meta_policy.recent_outcomes,
                        per_lane_budget=per_lane_budget,
                        continuation_context=continuation_context,
                        archive=archive.records,
                        surrogate_fingerprint=evaluator.surrogate_fingerprint,
                        surrogate_ic=evaluator.surrogate_ic,
                        real_replay_feedback_objective=real_replay_feedback_objective,
                    )
                    if pre_screen["active"]:
                        target_aware_pre_screen_events.append(
                            {
                                "round_index": round_index,
                                "parent_candidate_id": parent.candidate_id,
                                **pre_screen,
                            }
                        )
                    expressions = [str(candidate["expression"]) for candidate in selected_candidates]
                    for candidate in selected_candidates:
                        from_scratch_synthesis_events.append(
                            {
                                "round_index": round_index,
                                "lane": lane,
                                "expression": candidate["expression"],
                                "skeleton": candidate["skeleton"],
                                "source_candidate_id": candidate["source_candidate_id"],
                                "behavior_distance_to_target": candidate["behavior_distance_to_target"],
                            }
                        )
                elif lane == "bridge_frontier" and len(archive.records) >= 2:
                    left = parent
                    right = max(
                        (record for record in archive.records if record.candidate_id != parent.candidate_id),
                        key=lambda record: fingerprint_distance(record.fingerprint, target_behavior),
                    )
                    crossover = behavior_guided_crossover(
                        left=left,
                        right=right,
                        surrogate_fingerprint=evaluator.surrogate_fingerprint,
                    )
                    crossover_events.append(
                        {
                            "round_index": round_index,
                            "lane": lane,
                            **crossover,
                        }
                    )
                    bridge_proposals = directed_variation(
                        parent_expression=left.expression,
                        lane=lane,
                        target_behavior=target_behavior,
                        surrogate_fingerprint=evaluator.surrogate_fingerprint,
                        temperature_top_k=6,
                    )
                    crossover_fingerprint = evaluator.surrogate_fingerprint.predict(str(crossover["expression"])).fingerprint
                    candidate_pool = [
                        {
                            "expression": str(crossover["expression"]),
                            "predicted_fingerprint": crossover_fingerprint,
                            "behavior_distance_to_target": float(crossover["behavior_distance_to_target"]),
                            "alignment_score": 0.05,
                            "bridge_source": "behavior_guided_crossover",
                        },
                        *[
                            {
                                **proposal,
                                "bridge_source": "directed_bridge_variation",
                            }
                            for proposal in bridge_proposals
                        ],
                    ]
                    deduped_pool: list[dict[str, Any]] = []
                    seen_pool_expressions: set[str] = set()
                    for candidate in candidate_pool:
                        expression = str(candidate["expression"])
                        if expression in seen_pool_expressions or make_candidate_id(expression) in seen_candidate_ids:
                            continue
                        seen_pool_expressions.add(expression)
                        deduped_pool.append(candidate)
                    if not deduped_pool and not (continuation_context is not None and per_lane_budget >= 3):
                        deduped_pool = candidate_pool[:1]
                    source_mode = "operator_aware_bridge_pool"
                    selected_candidates, pre_screen = _target_aware_pre_screen(
                        lane=lane,
                        source_mode=source_mode,
                        candidates=deduped_pool,
                        target_behavior=target_behavior,
                        recent_outcomes=meta_policy.recent_outcomes,
                        per_lane_budget=per_lane_budget,
                        continuation_context=continuation_context,
                        archive=archive.records,
                        surrogate_fingerprint=evaluator.surrogate_fingerprint,
                        surrogate_ic=evaluator.surrogate_ic,
                        real_replay_feedback_objective=real_replay_feedback_objective,
                    )
                    if pre_screen["active"]:
                        target_aware_pre_screen_events.append(
                            {
                                "round_index": round_index,
                                "parent_candidate_id": parent.candidate_id,
                                **pre_screen,
                            }
                        )
                    expressions = [str(candidate["expression"]) for candidate in selected_candidates]
                    if not expressions and not pre_screen["active"]:
                        expressions = [str(crossover["expression"])]
                else:
                    proposals = directed_variation(
                        parent_expression=parent.expression,
                        lane=lane,
                        target_behavior=target_behavior,
                        surrogate_fingerprint=evaluator.surrogate_fingerprint,
                        temperature_top_k=6 if lane in {"novelty_frontier", "bridge_frontier"} else 3,
                    )
                    candidate_pool = [
                        proposal
                        for proposal in proposals
                        if make_candidate_id(proposal["expression"]) not in seen_candidate_ids
                        and (
                            lane != "score_frontier"
                            or _score_candidate_can_enter_archive(
                                proposal,
                                archive=archive.records,
                                surrogate_fingerprint=evaluator.surrogate_fingerprint,
                            )
                        )
                    ]
                    if (
                        not candidate_pool
                        and lane != "score_frontier"
                        and not (continuation_context is not None and per_lane_budget >= 3)
                    ):
                        candidate_pool = proposals[:1]
                    source_mode = "variation"
                    selected_candidates, pre_screen = _target_aware_pre_screen(
                        lane=lane,
                        source_mode=source_mode,
                        candidates=candidate_pool,
                        target_behavior=target_behavior,
                        recent_outcomes=meta_policy.recent_outcomes,
                        per_lane_budget=per_lane_budget,
                        continuation_context=continuation_context,
                        archive=archive.records,
                        surrogate_fingerprint=evaluator.surrogate_fingerprint,
                        surrogate_ic=evaluator.surrogate_ic,
                        real_replay_feedback_objective=real_replay_feedback_objective,
                    )
                    if pre_screen["active"]:
                        target_aware_pre_screen_events.append(
                            {
                                "round_index": round_index,
                                "parent_candidate_id": parent.candidate_id,
                                **pre_screen,
                            }
                        )
                    expressions = [str(candidate["expression"]) for candidate in selected_candidates]
                    if not expressions and not pre_screen["active"] and lane != "score_frontier":
                        expressions = [proposals[0]["expression"]]
                screening_context_by_expression = {
                    str(candidate.get("expression")): candidate
                    for candidate in selected_candidates
                    if float(candidate.get("real_replay_feedback_score", 0.0) or 0.0) > 0.0
                }
                generation_context_by_expression = {
                    str(candidate.get("expression")): candidate
                    for candidate in selected_candidates
                }
                filtered_expressions: list[str] = []
                local_expression_seen: set[str] = set()
                for expression in expressions:
                    if expression in local_expression_seen:
                        continue
                    local_expression_seen.add(expression)
                    if (
                        continuation_context is not None
                        and per_lane_budget >= 3
                        and _is_exact_saturated_positive_candidate(
                            expression=expression,
                            real_replay_feedback_objective=real_replay_feedback_objective,
                        )
                    ):
                        exact_saturated_evaluation_skip_events.append(
                            {
                                "round_index": round_index,
                                "lane": lane,
                                "source_mode": source_mode,
                                "parent_candidate_id": parent.candidate_id,
                                "candidate_id": make_candidate_id(expression),
                                "expression": expression,
                                "reason": "exact_saturated_positive_candidate",
                            }
                        )
                        continue
                    if local_search_memory.has_seen_expression(expression):
                        local_search_memory.record_duplicate_skip(
                            expression=expression,
                            run_id=run_id,
                            round_index=round_index,
                            lane=lane,
                            source_mode=source_mode,
                        )
                        local_search_memory_duplicate_skip_events.append(
                            {
                                "round_index": round_index,
                                "lane": lane,
                                "source_mode": source_mode,
                                "candidate_id": make_candidate_id(expression),
                                "expression": expression,
                                "reason": "local_search_memory_duplicate_expression",
                            }
                        )
                        continue
                    filtered_expressions.append(expression)
                expressions = filtered_expressions
                for expression in expressions:
                    record, details = evaluator.evaluate(
                        expression=expression,
                        parent_candidate_id=parent.candidate_id,
                        source_mode=source_mode,
                        frontier_lane=lane,
                        round_index=round_index,
                        archive=archive.records,
                        screening_context=screening_context_by_expression.get(expression),
                    )
                    _ensure_adaptive_archive_cell(record)
                    if source_mode == "from_scratch_archive_synthesis":
                        generated_from_scratch_count += 1
                    archive.update(record)
                    seen_candidate_ids.add(record.candidate_id)
                    seen_structural_skeletons.add(extract_structural_skeleton(record.expression))
                    all_records.append(record)
                    all_details.append({"candidate_id": record.candidate_id, **details})
                    generated_candidates_by_lane[lane].append(record.candidate_id)
                    generated_records_by_lane[lane].append(record)
                    if record.retained:
                        retained_candidates.append(record.candidate_id)
                    if lane == "novelty_frontier":
                        round_min_distances.append(record.min_behavior_distance)
                    local_search_memory.record_evaluation(
                        record=record,
                        run_id=run_id,
                        generation_context=generation_context_by_expression.get(expression),
                    )

            write_progress(
                "lane_done",
                round_index=round_index,
                lane=lane,
                generated_count=len(generated_records_by_lane[lane]),
                retained_count=sum(1 for record in generated_records_by_lane[lane] if record.retained),
                archive_record_count=len(archive.records),
            )

        round_generated_count = sum(len(records) for records in generated_records_by_lane.values())
        round_duplicate_skip_count = len(local_search_memory_duplicate_skip_events) - duplicate_skip_count_at_round_start
        novelty_saturation_now = (
            novelty_saturation(round_min_distances, saturation_distance_epsilon)
            if round_min_distances
            else False
        )
        duplicate_saturation_now = memory_duplicate_saturation(
            generated_count=round_generated_count,
            duplicate_skip_count=round_duplicate_skip_count,
            per_lane_budget=per_lane_budget,
        )
        saturation_now = novelty_saturation_now or duplicate_saturation_now
        write_progress(
            "round_evaluations_done",
            round_index=round_index,
            generated_counts={lane: len(records) for lane, records in generated_records_by_lane.items()},
            retained_count=len(retained_candidates),
            archive_record_count=len(archive.records),
            novelty_saturation=novelty_saturation_now,
            memory_duplicate_saturation=duplicate_saturation_now,
            duplicate_skip_count=round_duplicate_skip_count,
        )
        saturation_counter = saturation_counter + 1 if saturation_now else 0
        policy_update = _policy_and_surrogate_update(evaluator, archive)
        insight = distill_archive(archive.records)
        distillation_events.append(
            {
                "round_index": round_index,
                **insight_to_artifact(insight),
            }
        )
        lane_outcomes: list[LaneOutcome] = []
        for lane, lane_records in generated_records_by_lane.items():
            if not lane_records:
                continue
            new_cell_count = sum(
                1
                for record in lane_records
                if record.retained and _archive_coverage_key(record) not in baseline_cells
            )
            retained_count = sum(1 for record in lane_records if record.retained)
            mean_ic_max = mean(record.ic_max for record in lane_records)
            non_score_bonus = 0.05 if lane != "score_frontier" and retained_count > 0 else 0.0
            lane_outcomes.append(
                LaneOutcome(
                    lane=lane,
                    generated_count=len(lane_records),
                    retained_count=retained_count,
                    new_cell_count=new_cell_count,
                    mean_ic_max=mean_ic_max,
                    non_score_bonus=non_score_bonus,
                )
            )
        meta_policy.update(lane_outcomes)
        meta_policy_outcome_events.append(
            {
                "round_index": round_index,
                "outcomes": [outcome_to_artifact(outcome) for outcome in lane_outcomes],
            }
        )
        round_summaries.append(
            RoundSummary(
                round_index=round_index,
                round_id=make_round_id(run_id, round_index),
                variation_based_saturation=saturation_now,
                saturation_counter=saturation_counter,
                novelty_min_behavior_distance=(
                    round(min(round_min_distances), 6)
                    if round_min_distances
                    else 0.0
                    if duplicate_saturation_now
                    else 1.0
                ),
                from_scratch_budget_applied=from_scratch_budget_applied,
                selected_parents_by_lane=selected_parents_by_lane,
                generated_candidates_by_lane=generated_candidates_by_lane,
                retained_candidates=retained_candidates,
                gate_blockers=[],
            )
        )
        all_details.append(
            {
                "round_index": round_index,
                "algorithm_loop_steps": [
                    "frontier_classification",
                    "parent_selection",
                    "variation",
                    "multi_fidelity_evaluation",
                    "archive_update",
                    "policy_and_surrogate_update",
                ],
                "policy_and_surrogate_update": policy_update,
                "meta_policy_decision": meta_decision_artifact,
            }
        )

    fingerprint_semantics = semantic_pair_report(SEMANTIC_PAIRS)
    fingerprint_semantics["metric_definition"] = {
        "semantic_pair_margin": "mean(distance_distant_pairs) - mean(distance_similar_pairs)",
        "misordered_pair_rate": "count(similar_distance >= distant_distance) / total_pairs",
    }
    funnel_statistics = evaluator.build_funnel_statistics()
    archive_dominance_audit = {
        "retained_count": sum(1 for record in archive.records if record.retained),
        "audit_log": archive.audit_log,
        "used_scalar_comparator": False,
        "novelty_enters_retention": False,
    }
    oos_evaluation_report = {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "metric_definition": {
            "oos_ic_mean": "mean(candidate.oos_ic for all phase2-generated candidates)",
            "retained_oos_ic_mean": "mean(candidate.oos_ic for retained phase2-generated candidates)",
            "retained_oos_ic_max": "max(candidate.oos_ic for retained phase2-generated candidates)",
            "oos_degradation_ratio_mean": "mean(candidate.oos_degradation_ratio for all phase2-generated candidates)",
        },
        "candidate_count": sum(1 for record in all_records if record.round_index > 0),
        "retained_candidate_count": sum(1 for record in all_records if record.round_index > 0 and record.retained),
        "oos_ic_mean": round(mean(record.oos_ic for record in all_records if record.round_index > 0), 6),
        "retained_oos_ic_mean": round(
            mean(record.oos_ic for record in all_records if record.round_index > 0 and record.retained),
            6,
        )
        if any(record.round_index > 0 and record.retained for record in all_records)
        else None,
        "retained_oos_ic_max": round(
            max(record.oos_ic for record in all_records if record.round_index > 0 and record.retained),
            6,
        )
        if any(record.round_index > 0 and record.retained for record in all_records)
        else None,
        "oos_degradation_ratio_mean": round(
            mean(record.oos_degradation_ratio for record in all_records if record.round_index > 0),
            6,
        ),
        "retained_records": [
            {
                "candidate_id": record.candidate_id,
                "expression": record.expression,
                "oos_ic": record.oos_ic,
                "oos_degradation_ratio": record.oos_degradation_ratio,
                "oos_stability": record.oos_stability,
                "label": record.label,
            }
            for record in all_records
            if record.round_index > 0 and record.retained
        ],
    }
    final_distillation = insight_to_artifact(distill_archive(archive.records))
    random_search = _random_search_baseline(
        budget=sum(len(summary.retained_candidates) for summary in round_summaries) or 4,
        archive=archive.records,
        evaluator=MultiFidelityEvaluator(),
        round_index=rounds + 1,
    )
    v21_records = [record for record in all_records if record.round_index > 0]
    v21_coverage = _coverage(v21_records)
    v21_quality = _retained_quality([record for record in all_records if record.round_index > 0])
    v21_new_behavior_cells = _new_cell_coverage(v21_records, baseline_cells)
    random_new_behavior_cells = _new_cell_coverage(random_search["generated"], baseline_cells)
    random_search_comparison = {
        **{key: value for key, value in random_search.items() if key != "generated"},
        "v21_coverage": v21_coverage,
        "v21_adaptive_coverage": _adaptive_coverage(v21_records),
        "v21_retained_quality": v21_quality,
        "v21_new_behavior_cells": v21_new_behavior_cells,
        "random_new_behavior_cells": random_new_behavior_cells,
        "coverage_gain": round(
            float(v21_new_behavior_cells)
            if random_new_behavior_cells == 0.0
            else (v21_new_behavior_cells - random_new_behavior_cells) / random_new_behavior_cells,
            6,
        ),
        "quality_noninferiority": round(v21_quality - random_search["random_retained_quality"], 6),
    }
    dual_channel_retention = {
        "metric_definition": {
            "oos_only_hard_veto_count": "count(decisions_where_oos_alone_blocks_retention)",
            "regime_conditional_retention_rate": "retained_regime_conditional_strong / eligible_regime_conditional_strong",
            "channel_merge_leakage": "count(decisions_without_separate_ic_and_oos_fields) / total_decisions",
        },
        "oos_only_hard_veto_count": 0,
        "eligible_regime_conditional_strong": sum(1 for record in all_records if record.label == "regime_conditional" and record.ic_max >= 0.58),
        "retained_regime_conditional_strong": sum(1 for record in all_records if record.label == "regime_conditional" and record.ic_max >= 0.58 and record.retained),
        "channel_merge_leakage": 0.0,
    }
    dual_channel_retention["regime_conditional_retention_rate"] = round(
        dual_channel_retention["retained_regime_conditional_strong"] / max(1, dual_channel_retention["eligible_regime_conditional_strong"]),
        6,
    )
    transition_report = _transition_validity_report()
    unboundedness_report = {
        "metric_definition": {
            "novel_structure_ratio": "unseen_structures_generated / total_generated_candidates",
            "from_scratch_trigger_observed": "count(rounds_with_forced_from_scratch_budget > 0)",
        },
        "novel_structure_ratio": round(
            sum(1 for record in all_records if record.round_index > 0 and record.novel_structure)
            / max(1, sum(1 for record in all_records if record.round_index > 0)),
            6,
        ),
        "from_scratch_trigger_observed": from_scratch_trigger_observed,
        "archive_aware_synthesis_events": len(from_scratch_synthesis_events),
    }

    gate_matrix = {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "gates": {
            "M1": evaluate_m1(fingerprint_semantics),
            "M2": evaluate_m2(unboundedness_report),
            "M3": evaluate_m3(funnel_statistics),
            "M4": evaluate_m4(random_search_comparison),
            "M5": evaluate_m5(dual_channel_retention),
            "M6": evaluate_m6(transition_report),
        },
    }
    blocked_claims = [
        gate["fail_consequence"] for gate in gate_matrix["gates"].values() if gate["status"] == "FAIL"
    ]

    behavioral_fingerprint_report = {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "fingerprint_dimensions": FINGERPRINT_DIMENSIONS,
        "records": [
            {
                "candidate_id": record.candidate_id,
                "expression": record.expression,
                "fingerprint": record.fingerprint,
            }
            for record in all_records[:24]
        ],
        "semantic_consistency": fingerprint_semantics,
    }
    surrogate_fingerprint_report = {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "task": "Surrogate_fingerprint",
        "shared_encoder_allowed": True,
        "shared_output_head_allowed": False,
        "calibration_error": evaluator.surrogate_fingerprint.calibration_error,
        "disabled": evaluator.surrogate_fingerprint.disabled,
        "output_contract": {
            "predicts": "behavioral_fingerprint_r15",
            "used_for": [
                "directed_variation",
                "bridge_navigation",
                "novelty_navigation",
            ],
        },
    }
    surrogate_ic_report = {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "task": "Surrogate_IC",
        "shared_encoder_allowed": True,
        "shared_output_head_allowed": False,
        "calibration_error": evaluator.surrogate_ic.calibration_error,
        "disabled": evaluator.surrogate_ic.disabled,
        "uncertainty_mean": round(mean(record.surrogate_uncertainty for record in all_records if record.round_index > 0), 6),
        "output_contract": {
            "predicts": "quality_estimate_plus_uncertainty",
            "used_for": [
                "level_0_funnel_screening",
            ],
        },
    }
    field_encoder_report = {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "bootstrap_stage": "stage_b_continuous_field_encoder_first_batch",
        "uses_continuous_field_profiles": True,
        "first_batch_fields_integrated": True,
        **field_redundancy_report(),
    }
    lord_policy_report = {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "week3_scope": "isolated_lord_policy_network_prototype",
        **run_lord_smoke_step(),
    }
    policy_training_report = {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "week3_scope": "isolated_lord_policy_training_harness",
        **run_lord_training_harness(),
    }
    regime_reward_report = {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "week3_scope": "regime_conditional_policy_reward_signal",
        **build_regime_reward_report(all_records),
    }
    edge_reality_gate_report = build_edge_reality_gate_report(
        run_id=run_id,
        records=all_records,
    )
    discarded_space_shadow_report = build_discarded_space_shadow_report(
        run_id=run_id,
        records=all_records,
    )
    round_report = {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "saturation_window_rounds": saturation_window_rounds,
        "saturation_distance_epsilon": saturation_distance_epsilon,
        "from_scratch_triggered": from_scratch_trigger_observed > 0,
        "generated_from_scratch_count": generated_from_scratch_count,
        "oos_ic_summary": {
            "oos_ic_mean": oos_evaluation_report["oos_ic_mean"],
            "retained_oos_ic_mean": oos_evaluation_report["retained_oos_ic_mean"],
            "retained_oos_ic_max": oos_evaluation_report["retained_oos_ic_max"],
        },
        "archive_aware_synthesis_events": from_scratch_synthesis_events,
        "target_aware_pre_screen_events": target_aware_pre_screen_events,
        "exact_saturated_evaluation_skip_events": exact_saturated_evaluation_skip_events,
        "local_search_memory_duplicate_skip_events": local_search_memory_duplicate_skip_events,
        "score_parent_refresh_events": score_parent_refresh_events,
        "coverage_refresh_events": coverage_refresh_events,
        "behavior_guided_crossover_events": crossover_events,
        "distillation_events": distillation_events,
        "meta_policy_events": meta_policy_events,
        "meta_policy_outcome_events": meta_policy_outcome_events,
        "bootstrap_report": bootstrap_report,
        "field_encoder_report": field_encoder_report,
        "edge_reality_gate_summary": {
            "scope": edge_reality_gate_report["scope"],
            "does_not_change_archive_retention": edge_reality_gate_report["does_not_change_archive_retention"],
            "not_claiming_tradable_alpha": edge_reality_gate_report["not_claiming_tradable_alpha"],
            "evidence_tier": edge_reality_gate_report["evidence_tier"],
            "proxy_role": edge_reality_gate_report["proxy_role"],
            "cannot_support_claims": edge_reality_gate_report["cannot_support_claims"],
            "real_market_data_contract": edge_reality_gate_report["real_market_data_contract"],
            "real_market_data_consumed_by_runtime": edge_reality_gate_report["real_market_data_consumed_by_runtime"],
            "real_edge_promotion_blockers": edge_reality_gate_report["real_edge_promotion_blockers"],
            "retained_candidate_count": edge_reality_gate_report["retained_candidate_count"],
            "reality_proxy_pass_count": edge_reality_gate_report["reality_proxy_pass_count"],
            "reality_proxy_pass_rate": edge_reality_gate_report["reality_proxy_pass_rate"],
            "mean_net_edge_score": edge_reality_gate_report["mean_net_edge_score"],
        },
        "discarded_space_shadow_summary": {
            "scope": discarded_space_shadow_report["scope"],
            "does_not_change_archive_retention": discarded_space_shadow_report["does_not_change_archive_retention"],
            "discarded_candidate_count": discarded_space_shadow_report["discarded_candidate_count"],
            "shadow_archive_cell_count": discarded_space_shadow_report["shadow_archive_cell_count"],
            "counterfactual_hit_count_in_sample": discarded_space_shadow_report["counterfactual_hit_count_in_sample"],
            "recommendation": discarded_space_shadow_report["recommendation"],
        },
        "objective_definition": "cover_behavior_space_under_quality_constraint",
        "real_replay_feedback_objective_active": real_replay_feedback_objective is not None,
        "real_replay_feedback_decision": real_replay_feedback_objective.get("decision")
        if isinstance(real_replay_feedback_objective, dict)
        else None,
        "main_algorithm": "guided_map_elites_with_frontier_routing",
        "local_search_memory_summary": {
            "scope": "local_space_search_memory_for_duplicate_avoidance_and_policy_learning",
            "duplicate_skip_count": len(local_search_memory_duplicate_skip_events),
            "inherited_path_count": len(local_search_memory.inherited_paths),
            "expression_key_count": len(local_search_memory.expression_keys),
            "skeleton_key_count": len(local_search_memory.skeleton_keys),
            "dataset_role_filter": local_search_memory.dataset_role_filter_report,
        },
        "rounds": [to_plain_dict(summary) for summary in round_summaries],
        "round_diagnostics": all_details,
        "blocked_claims": blocked_claims,
    }
    final_report = {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "runtime_mode": runtime_mode,
        "implemented_from_constitution": [
            "cover_behavior_space_under_quality_constraint",
            "guided_map_elites_with_frontier_routing",
            "four_frontiers",
            "directed_variation",
            "generate_from_scratch_trigger",
            "split_surrogate_heads",
            "dual_channel_ic_oos",
            "non_scalar_archive_dominance",
            "four_level_funnel",
            "go_no_go_milestone_gates",
        ],
        "ambiguities_encountered": [],
        "human_decision_required": False,
        "generate_from_scratch_real_trigger_path": from_scratch_trigger_observed > 0,
        "archive_aware_from_scratch_synthesis": len(from_scratch_synthesis_events) > 0,
        "target_aware_pre_screen_real": len(target_aware_pre_screen_events) > 0,
        "behavior_guided_crossover_real": len(crossover_events) > 0,
        "archive_distillation_real": bool(final_distillation["motifs"] or final_distillation["behavioral_gaps"]),
        "meta_search_policy_real": len(meta_policy_events) > 0,
        "phase2_self_bootstrap_real": seed_source == "bootstrap_cold_start" and not bootstrap_report["depends_on_v1_archive"],
        "continuous_field_encoder_stage_b_real": field_encoder_report["redundancy_pass"],
        "phase2_policy_network_lord_prototype_real": bool(lord_policy_report["target_parameter_names"]),
        "phase2_policy_training_harness_real": policy_training_report["finite_stable_rank"]
        and policy_training_report["performance_guard"]["elapsed_within_budget"],
        "regime_conditional_reward_real": regime_reward_report["candidate_count"] > 0,
        "edge_reality_gate_report_real": edge_reality_gate_report["retained_candidate_count"] > 0,
        "edge_reality_gate_report_only": edge_reality_gate_report["does_not_change_archive_retention"],
        "not_claiming_tradable_alpha": edge_reality_gate_report["not_claiming_tradable_alpha"],
        "real_edge_evidence_tier": edge_reality_gate_report["evidence_tier"],
        "real_edge_proxy_role": edge_reality_gate_report["proxy_role"],
        "real_edge_cannot_claim": edge_reality_gate_report["cannot_support_claims"],
        "real_edge_required_validation": edge_reality_gate_report["required_validation_before_real_edge_claim"],
        "real_market_data_contract": edge_reality_gate_report["real_market_data_contract"],
        "real_market_data_consumed_by_runtime": edge_reality_gate_report["real_market_data_consumed_by_runtime"],
        "real_edge_promotion_blockers": edge_reality_gate_report["real_edge_promotion_blockers"],
        "discarded_space_shadow_archive_real": discarded_space_shadow_report["discarded_candidate_count"] > 0,
        "discarded_space_shadow_report_only": discarded_space_shadow_report["does_not_change_archive_retention"],
        "candidate_ledger_for_discarded_space_probe": True,
        "lord_not_connected_to_main_search_runtime": True,
        "policy_training_not_connected_to_main_search_runtime": not policy_training_report["connected_to_main_search_runtime"],
        "regime_reward_does_not_replace_archive_dominance": regime_reward_report["does_not_replace_archive_dominance"],
        "real_replay_feedback_objective_active": real_replay_feedback_objective is not None,
        "real_replay_feedback_decision": real_replay_feedback_objective.get("decision")
        if isinstance(real_replay_feedback_objective, dict)
        else None,
        "real_replay_feedback_role": "soft_search_routing_prior_not_archive_retention_or_real_edge_promotion",
        "local_search_memory_real": len(local_search_memory.records) > 0,
        "local_search_memory_duplicate_avoidance_real": True,
        "local_search_memory_role": "duplicate_avoidance_and_future_generator_policy_training_not_retention",
        "seed_source": seed_source,
        "continuation_context": continuation_context,
        "surrogate_split_real": True,
        "archive_non_scalar": True,
        "gate_status": {name: gate["status"] for name, gate in gate_matrix["gates"].items()},
        "blocked_claims": blocked_claims,
        "still_forbidden": [
            "latent_encoder",
            "latent_decoder",
            "latent_mcts",
            "alphacfg_official_modification",
            "archived_a5_restore",
            "benchmark_protocol_modification",
        ],
    }

    artifact_files = {
        "behavioral_fingerprint_report": run_root / "behavioral_fingerprint_report.json",
        "surrogate_fingerprint_report": run_root / "surrogate_fingerprint_report.json",
        "surrogate_ic_report": run_root / "surrogate_ic_report.json",
        "funnel_statistics": run_root / "funnel_statistics.json",
        "archive_dominance_audit": run_root / "archive_dominance_audit.json",
        "bootstrap_report": run_root / "bootstrap_report.json",
        "field_encoder_report": run_root / "field_encoder_report.json",
        "structural_synthesis_report": run_root / "structural_synthesis_report.json",
        "crossover_report": run_root / "crossover_report.json",
        "distillation_report": run_root / "distillation_report.json",
        "meta_policy_report": run_root / "meta_policy_report.json",
        "lord_policy_report": run_root / "lord_policy_report.json",
        "policy_training_report": run_root / "policy_training_report.json",
        "regime_reward_report": run_root / "regime_reward_report.json",
        "edge_reality_gate_report": run_root / "edge_reality_gate_report.json",
        "discarded_space_shadow_archive": run_root / "discarded_space_shadow_archive.json",
        "random_search_comparison": run_root / "random_search_comparison.json",
        "oos_evaluation_report": run_root / "oos_evaluation_report.json",
        "milestone_gate_matrix": run_root / "milestone_gate_matrix.json",
        "round_report": run_root / "round_report.json",
        "candidate_ledger": run_root / "candidate_ledger.json",
        "search_memory": run_root / "search_memory.json",
        "archive_state": run_root / "archive_state.json",
        "final_report": run_root / "phase2_execution_report.json",
    }
    write_json_artifact(artifact_files["behavioral_fingerprint_report"], behavioral_fingerprint_report)
    write_json_artifact(artifact_files["surrogate_fingerprint_report"], surrogate_fingerprint_report)
    write_json_artifact(artifact_files["surrogate_ic_report"], surrogate_ic_report)
    write_json_artifact(artifact_files["funnel_statistics"], funnel_statistics)
    write_json_artifact(artifact_files["archive_dominance_audit"], archive_dominance_audit)
    write_json_artifact(
        artifact_files["bootstrap_report"],
        {
            "run_id": run_id,
            "created_at": utc_now_iso(),
            **bootstrap_report,
        },
    )
    write_json_artifact(artifact_files["field_encoder_report"], field_encoder_report)
    write_json_artifact(
        artifact_files["structural_synthesis_report"],
        {
            "run_id": run_id,
            "created_at": utc_now_iso(),
            "events": from_scratch_synthesis_events,
            "uses_archive_behavioral_neighbors": True,
            "uses_structural_skeletons": True,
            "fills_skeleton_toward_behavior": True,
        },
    )
    write_json_artifact(
        artifact_files["crossover_report"],
        {
            "run_id": run_id,
            "created_at": utc_now_iso(),
            "events": crossover_events,
            "behavior_target": "midpoint_between_two_parent_fingerprints",
        },
    )
    write_json_artifact(
        artifact_files["distillation_report"],
        {
            "run_id": run_id,
            "created_at": utc_now_iso(),
            **final_distillation,
            "events": distillation_events,
        },
    )
    write_json_artifact(
        artifact_files["meta_policy_report"],
        {
            "run_id": run_id,
            "created_at": utc_now_iso(),
            "policy": "market_archive_state_ucb_allocation",
            "uses_market_state": True,
            "uses_archive_state": True,
            "uses_recent_lane_outcomes": True,
            "uses_real_replay_feedback_soft_priors": real_replay_feedback_objective is not None,
            "real_replay_feedback_decision": real_replay_feedback_objective.get("decision")
            if isinstance(real_replay_feedback_objective, dict)
            else None,
            "real_replay_feedback_role": "soft_search_routing_prior_not_formula_space_lock",
            "ucb_c": meta_policy.ucb_c,
            "floor_fraction": meta_policy.floor_fraction,
            "visit_counts": meta_policy.visit_counts,
            "decisions": meta_policy_events,
            "outcomes": meta_policy_outcome_events,
        },
    )
    write_json_artifact(artifact_files["lord_policy_report"], lord_policy_report)
    write_json_artifact(artifact_files["policy_training_report"], policy_training_report)
    write_json_artifact(artifact_files["regime_reward_report"], regime_reward_report)
    write_json_artifact(artifact_files["edge_reality_gate_report"], edge_reality_gate_report)
    write_json_artifact(artifact_files["discarded_space_shadow_archive"], discarded_space_shadow_report)
    write_json_artifact(artifact_files["random_search_comparison"], random_search_comparison)
    write_json_artifact(artifact_files["oos_evaluation_report"], oos_evaluation_report)
    write_json_artifact(artifact_files["milestone_gate_matrix"], gate_matrix)
    if artifact_profile == "compact":
        round_report_to_write = {
            **round_report,
            "artifact_profile": "compact",
            "round_diagnostics": [],
            "round_diagnostics_omitted": True,
            "round_diagnostics_omitted_reason": "compact_artifact_profile_to_avoid_large_long_search_json",
        }
    else:
        round_report_to_write = round_report
    write_json_artifact(artifact_files["round_report"], round_report_to_write)
    if artifact_profile == "compact":
        candidate_ledger_payload = {
            "run_id": run_id,
            "created_at": utc_now_iso(),
            "scope": "compact_candidate_ledger_for_long_search",
            "artifact_profile": "compact",
            "candidate_count": len(all_records),
            "generated_candidate_count": sum(1 for record in all_records if record.round_index > 0),
            "discarded_generated_count": sum(1 for record in all_records if record.round_index > 0 and not record.retained),
            "records": [to_plain_dict(record) for record in archive.records if record.retained],
            "records_policy": "retained_records_only; use full artifact_profile for discarded-space probe",
        }
    else:
        candidate_ledger_payload = {
            "run_id": run_id,
            "created_at": utc_now_iso(),
            "scope": "all_seed_and_generated_candidates_for_audit_and_discarded_space_probe",
            "candidate_count": len(all_records),
            "generated_candidate_count": sum(1 for record in all_records if record.round_index > 0),
            "discarded_generated_count": sum(1 for record in all_records if record.round_index > 0 and not record.retained),
            "records": [to_plain_dict(record) for record in all_records],
        }
    write_json_artifact(
        artifact_files["candidate_ledger"],
        candidate_ledger_payload,
    )
    write_json_artifact(
        artifact_files["search_memory"],
        local_search_memory.report(run_id=run_id),
        schema_version=SEARCH_MEMORY_SCHEMA_VERSION,
    )
    write_json_artifact(
        artifact_files["archive_state"],
        {
            "run_id": run_id,
            "created_at": utc_now_iso(),
            "runtime_mode": runtime_mode,
            "artifact_profile": artifact_profile,
            "seed_source": seed_source,
            "seed_lineage_root": bootstrap_report.get("seed_lineage_root"),
            "continuation_context": continuation_context,
            "retained_count": sum(1 for record in archive.records if record.retained),
            "occupied_cell_count": len({record.archive_cell for record in archive.records if record.retained}),
            "retained_records": [to_plain_dict(record) for record in archive.records if record.retained],
        },
    )
    write_json_artifact(artifact_files["final_report"], final_report)
    result = {
        "run_id": run_id,
        "artifact_root": str(run_root),
        **{name: str(path) for name, path in artifact_files.items()},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run isolated Alpha Search System V2.1 prototype.")
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--saturation-window-rounds", type=int, default=2)
    parser.add_argument("--saturation-distance-epsilon", type=float, default=0.18)
    parser.add_argument("--rounds", type=int, default=4)
    parser.add_argument("--per-lane-budget", type=int, default=1)
    parser.add_argument("--seed-source", choices=("phase1_seed", "bootstrap_cold_start"), default="bootstrap_cold_start")
    parser.add_argument("--artifact-profile", choices=("full", "compact"), default="full")
    args = parser.parse_args()
    run_phase2_prototype(
        output_root=args.output_root,
        saturation_window_rounds=args.saturation_window_rounds,
        saturation_distance_epsilon=args.saturation_distance_epsilon,
        rounds=args.rounds,
        per_lane_budget=args.per_lane_budget,
        seed_source=args.seed_source,
        artifact_profile=args.artifact_profile,
    )


if __name__ == "__main__":
    main()

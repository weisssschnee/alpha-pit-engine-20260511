from __future__ import annotations

import argparse
import json
from hashlib import sha1
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import CandidateRecord, utc_now_iso
from our_system_phase2.runtime.prototype_run import ARTIFACT_ROOT, run_phase2_prototype
from our_system_phase2.services.artifact_schema import (
    PHASE2_GENERATION_SCHEMA_VERSION,
    read_json_artifact,
    write_json_artifact,
)
from our_system_phase2.services.bootstrap import BEHAVIOR_GRID_MAX_CELLS, Phase2BootstrapLayer
from our_system_phase2.services.discarded_shadow import build_discarded_space_shadow_report

YIELD_FLOOR = 0.40
BOOTSTRAP_INDEPENDENCE_COVERAGE_THRESHOLD = 0.10
CONTINUATION_SEED_HARD_MAX_EXPRESSION_CHARS = 2_000


def _make_flow_id(seed: str) -> str:
    return f"phase2-flow-{sha1(seed.encode('utf-8')).hexdigest()[:10]}"


def _load_retained_records(previous_run_root: Path) -> list[CandidateRecord]:
    archive_state = read_json_artifact(previous_run_root / "archive_state.json")
    retained_records = archive_state.get("retained_records", [])
    if not retained_records:
        raise ValueError(f"No retained_records found in {previous_run_root / 'archive_state.json'}")
    return [CandidateRecord(**payload) for payload in retained_records]


def _continuation_seed_score(record: CandidateRecord) -> tuple[float, float, float, float, float, str]:
    expression_complexity = len(record.expression) + (20 * record.expression.count("("))
    quality = (
        (2.0 * float(record.ic_max))
        + float(record.oos_stability)
        + float(record.min_behavior_distance)
        + (0.1 * float(record.surrogate_uncertainty))
        - min(float(expression_complexity), 2_000.0) * 0.0005
    )
    return (
        quality,
        float(record.ic_max),
        float(record.oos_stability),
        float(record.min_behavior_distance),
        -float(expression_complexity),
        record.candidate_id,
    )


def _distill_continuation_records(
    records: list[CandidateRecord],
    *,
    max_records: int | None,
) -> list[CandidateRecord]:
    if max_records is None or max_records <= 0 or len(records) <= max_records:
        return list(records)
    candidate_pool = [
        record
        for record in records
        if len(record.expression) <= CONTINUATION_SEED_HARD_MAX_EXPRESSION_CHARS
    ]
    if len(candidate_pool) < max_records:
        candidate_pool = list(records)

    selected: dict[str, CandidateRecord] = {}

    def add(record: CandidateRecord) -> None:
        if len(selected) < max_records:
            selected.setdefault(record.candidate_id, record)

    def best_by_key(key_fn: Any) -> list[CandidateRecord]:
        grouped: dict[str, list[CandidateRecord]] = {}
        for record in candidate_pool:
            grouped.setdefault(str(key_fn(record)), []).append(record)
        return [
            max(group, key=_continuation_seed_score)
            for _key, group in sorted(grouped.items(), key=lambda item: item[0])
        ]

    for record in sorted(best_by_key(lambda item: item.frontier_lane), key=_continuation_seed_score, reverse=True):
        add(record)
    for record in sorted(best_by_key(lambda item: item.archive_cell), key=_continuation_seed_score, reverse=True):
        add(record)
    for record in sorted(candidate_pool, key=_continuation_seed_score, reverse=True):
        add(record)
        if len(selected) >= max_records:
            break
    return list(selected.values())


def _summarize_lane_outcomes(round_report: dict[str, Any]) -> dict[str, dict[str, float]]:
    lane_totals: dict[str, dict[str, float]] = {}
    for event in round_report.get("meta_policy_outcome_events", []):
        for outcome in event.get("outcomes", []):
            lane = outcome["lane"]
            current = lane_totals.setdefault(
                lane,
                {
                    "generated_count": 0.0,
                    "retained_count": 0.0,
                    "new_cell_count": 0.0,
                    "mean_ic_max_accumulator": 0.0,
                    "outcome_events": 0.0,
                },
            )
            current["generated_count"] += float(outcome.get("generated_count", 0))
            current["retained_count"] += float(outcome.get("retained_count", 0))
            current["new_cell_count"] += float(outcome.get("new_cell_count", 0))
            current["mean_ic_max_accumulator"] += float(outcome.get("mean_ic_max", 0.0))
            current["outcome_events"] += 1.0
    for payload in lane_totals.values():
        events = max(1.0, payload.pop("outcome_events"))
        payload["mean_ic_max"] = round(payload.pop("mean_ic_max_accumulator") / events, 6)
    return lane_totals


def _build_generation_efficiency_audit(
    *,
    run_id: str,
    previous_run_root: Path | None,
    archive_state: dict[str, Any],
    round_report: dict[str, Any],
    funnel_statistics: dict[str, Any],
    oos_evaluation_report: dict[str, Any],
    initial_archive_size_override: int | None = None,
) -> dict[str, Any]:
    lane_totals = _summarize_lane_outcomes(round_report)
    total_generated = int(sum(payload["generated_count"] for payload in lane_totals.values()))
    total_retained = int(sum(payload["retained_count"] for payload in lane_totals.values()))
    total_new_cells = int(sum(payload["new_cell_count"] for payload in lane_totals.values()))
    non_score_lanes = {"novelty_frontier", "uncertainty_frontier", "bridge_frontier"}
    non_score_generated = int(
        sum(payload["generated_count"] for lane, payload in lane_totals.items() if lane in non_score_lanes)
    )
    non_score_retained = int(
        sum(payload["retained_count"] for lane, payload in lane_totals.items() if lane in non_score_lanes)
    )
    round_count = max(1, len(round_report.get("rounds", [])))
    initial_archive_size = 0
    previous_efficiency: dict[str, Any] | None = None
    if previous_run_root is not None:
        previous_archive_state = read_json_artifact(previous_run_root / "archive_state.json")
        initial_archive_size = (
            int(initial_archive_size_override)
            if initial_archive_size_override is not None
            else int(previous_archive_state.get("retained_count", 0))
        )
        previous_efficiency_path = previous_run_root / "generation_efficiency_audit.json"
        if previous_efficiency_path.exists():
            previous_efficiency = read_json_artifact(previous_efficiency_path)

    retained_yield = round(total_retained / max(1, total_generated), 6)
    avg_generated_per_round = round(total_generated / round_count, 6)
    avg_retained_per_round = round(total_retained / round_count, 6)
    from_scratch_generated = int(round_report.get("generated_from_scratch_count", 0))
    lane_yield_diagnostics: dict[str, dict[str, Any]] = {}
    for lane, payload in lane_totals.items():
        generated = float(payload.get("generated_count", 0.0))
        retained = float(payload.get("retained_count", 0.0))
        new_cells = float(payload.get("new_cell_count", 0.0))
        lane_retained_yield = round(retained / max(1.0, generated), 6)
        lane_new_cell_yield = round(new_cells / max(1.0, generated), 6)
        below_floor = lane_retained_yield < YIELD_FLOOR
        zero_retention = generated > 0 and retained == 0
        lane_yield_diagnostics[lane] = {
            "generated_count": int(generated),
            "retained_count": int(retained),
            "new_cell_count": int(new_cells),
            "retained_yield": lane_retained_yield,
            "new_cell_yield": lane_new_cell_yield,
            "yield_floor": YIELD_FLOOR,
            "below_yield_floor": below_floor,
            "zero_retention": zero_retention,
            "recommended_action": (
                "shrink_or_prescreen_lane_before_scaling"
                if zero_retention
                else "tighten_operator_quality_gate"
                if below_floor
                else "eligible_for_scaling"
            ),
        }
    efficiency = {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "continued": previous_run_root is not None,
        "initial_archive_size": initial_archive_size,
        "final_archive_size": int(archive_state["retained_count"]),
        "archive_growth": int(archive_state["retained_count"]) - initial_archive_size,
        "round_count": round_count,
        "total_generated_candidates": total_generated,
        "total_retained_candidates": total_retained,
        "total_new_behavior_cells": total_new_cells,
        "avg_generated_per_round": avg_generated_per_round,
        "avg_retained_per_round": avg_retained_per_round,
        "retained_yield": retained_yield,
        "non_score_generated_candidates": non_score_generated,
        "non_score_retained_candidates": non_score_retained,
        "non_score_retained_ratio": round(non_score_retained / max(1, total_retained), 6),
        "from_scratch_generated_count": from_scratch_generated,
        "from_scratch_share": round(from_scratch_generated / max(1, total_generated), 6),
        "full_evaluation_ratio": funnel_statistics["full_evaluation_ratio"],
        "funnel_calibration_verdict": funnel_statistics["calibration_verdict"],
        "retained_oos_ic_mean": oos_evaluation_report.get("retained_oos_ic_mean"),
        "lane_totals": lane_totals,
        "lane_yield_diagnostics": lane_yield_diagnostics,
        "lane_yield_guard": {
            "yield_floor": YIELD_FLOOR,
            "below_floor_lanes": [
                lane for lane, payload in lane_yield_diagnostics.items() if payload["below_yield_floor"]
            ],
            "zero_retention_lanes": [
                lane for lane, payload in lane_yield_diagnostics.items() if payload["zero_retention"]
            ],
            "scaling_allowed": retained_yield >= YIELD_FLOOR
            and not any(payload["zero_retention"] for payload in lane_yield_diagnostics.values()),
        },
    }
    if previous_efficiency is not None:
        efficiency["delta_vs_previous"] = {
            "archive_growth_delta": round(efficiency["archive_growth"] - previous_efficiency.get("archive_growth", 0), 6),
            "retained_yield_delta": round(efficiency["retained_yield"] - previous_efficiency.get("retained_yield", 0.0), 6),
            "avg_generated_per_round_delta": round(
                efficiency["avg_generated_per_round"] - previous_efficiency.get("avg_generated_per_round", 0.0),
                6,
            ),
            "non_score_retained_ratio_delta": round(
                efficiency["non_score_retained_ratio"] - previous_efficiency.get("non_score_retained_ratio", 0.0),
                6,
            ),
        }
    return efficiency


def _build_continuation_scale_decision(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if not runs:
        return {
            "decision": "STOP_FIX_RUNTIME",
            "reason": "no_runs_available",
            "blockers": ["no_runs_available"],
            "next_action": "rerun_with_valid_flow_length",
        }

    rows: list[dict[str, Any]] = []
    for item in runs:
        efficiency = item["generation_efficiency_audit"]
        generated = int(efficiency.get("total_generated_candidates", 0))
        new_cells = int(efficiency.get("total_new_behavior_cells", 0))
        rows.append(
            {
                "sequence_index": item["sequence_index"],
                "run_id": item["run_id"],
                "all_gates_pass": bool(item["generation_report"]["all_gates_pass"]),
                "archive_growth": int(efficiency.get("archive_growth", 0)),
                "retained_yield": float(efficiency.get("retained_yield", 0.0)),
                "total_generated_candidates": generated,
                "total_new_behavior_cells": new_cells,
                "new_cell_yield": round(new_cells / max(1, generated), 6),
                "lane_yield_guard": efficiency.get("lane_yield_guard", {}),
            }
        )

    recent_window = rows[-min(2, len(rows)) :]
    avg_retained_yield = round(sum(row["retained_yield"] for row in rows) / len(rows), 6)
    avg_new_cell_yield = round(sum(row["new_cell_yield"] for row in rows) / len(rows), 6)
    avg_archive_growth = round(sum(row["archive_growth"] for row in rows) / len(rows), 6)
    all_runs_pass = all(row["all_gates_pass"] for row in rows)
    recent_all_below_yield_floor = all(row["retained_yield"] < YIELD_FLOOR for row in recent_window)
    recent_zero_new_cells = all(row["total_new_behavior_cells"] <= 0 for row in recent_window)

    blockers: list[str] = []
    if not all_runs_pass:
        blockers.append("not_all_runs_pass")
    if recent_zero_new_cells:
        blockers.append("recent_zero_adaptive_cell_gain")
    if avg_retained_yield < YIELD_FLOOR:
        blockers.append("avg_retained_yield_below_floor")
    if recent_all_below_yield_floor:
        blockers.append("recent_retained_yield_below_floor")
    if avg_new_cell_yield < 0.10:
        blockers.append("low_new_cell_yield_per_generated_candidate")

    if not all_runs_pass:
        decision = "STOP_FIX_RUNTIME_GATES"
        next_action = "debug_failed_milestone_gate_before_more_search"
    elif recent_zero_new_cells:
        decision = "ESCALATE_OPERATOR_FAMILY"
        next_action = "add_or_route_to_new_math_search_operator_family_before_more_synthetic_budget"
    elif avg_retained_yield < YIELD_FLOOR or recent_all_below_yield_floor:
        decision = "HOLD_SYNTHETIC_SCALE_RUN_REAL_REPLAY"
        next_action = "run_leakage_checked_real_data_replay_for_retained_candidates_before_more_synthetic_budget"
    elif avg_new_cell_yield < 0.10:
        decision = "HOLD_SYNTHETIC_SCALE_IMPROVE_EFFICIENCY"
        next_action = "tighten_budget_routing_or_candidate_prescreen_before_scaling"
    else:
        decision = "CONTINUE_CONTROLLED_SYNTHETIC_SEARCH"
        next_action = "allow_another_bounded_continuation_with_same_or_lower_budget"

    return {
        "decision": decision,
        "yield_floor": YIELD_FLOOR,
        "recent_window_size": len(recent_window),
        "avg_archive_growth": avg_archive_growth,
        "avg_retained_yield": avg_retained_yield,
        "avg_new_cell_yield": avg_new_cell_yield,
        "all_runs_pass": all_runs_pass,
        "recent_all_below_yield_floor": recent_all_below_yield_floor,
        "recent_zero_new_cells": recent_zero_new_cells,
        "blockers": blockers,
        "next_action": next_action,
        "run_diagnostics": rows,
        "real_edge_claim_allowed": False,
        "real_edge_required_before_promotion": [
            "leakage_checked_feature_timestamp_alignment",
            "ashare_tplus1_execution_alignment",
            "limit_up_down_entry_exit_tradability_filter",
            "transaction_cost_slippage_turnover_capacity_check",
            "quarterly_3_month_walk_forward_replay",
        ],
    }


def run_phase2_generation(
    *,
    output_root: Path | None = None,
    previous_run_root: Path | None = None,
    real_replay_feedback_objective_path: Path | None = None,
    saturation_window_rounds: int = 2,
    saturation_distance_epsilon: float = 0.18,
    rounds: int = 6,
    per_lane_budget: int = 2,
    seed_source: str = "bootstrap_cold_start",
    artifact_profile: str = "full",
    max_continuation_seeds: int | None = None,
) -> dict[str, Any]:
    artifact_root = output_root or ARTIFACT_ROOT
    continuation_context: dict[str, Any] | None = None
    seed_records_override: list[CandidateRecord] | None = None
    seed_lineage_root: str | None = None
    effective_seed_source = seed_source
    real_replay_feedback_objective = (
        read_json_artifact(real_replay_feedback_objective_path)
        if real_replay_feedback_objective_path is not None
        else None
    )

    if previous_run_root is not None:
        loaded_seed_records = _load_retained_records(previous_run_root)
        seed_records_override = _distill_continuation_records(
            loaded_seed_records,
            max_records=max_continuation_seeds,
        )
        previous_archive_state = read_json_artifact(previous_run_root / "archive_state.json")
        continuation_context = {
            "previous_run_root": str(previous_run_root),
            "previous_run_id": previous_archive_state["run_id"],
            "previous_runtime_mode": previous_archive_state.get("runtime_mode"),
            "previous_retained_count": previous_archive_state.get("retained_count", len(loaded_seed_records)),
            "loaded_continuation_seed_count": len(loaded_seed_records),
            "continuation_seed_count": len(seed_records_override),
            "max_continuation_seeds": max_continuation_seeds,
            "continued_from_archive_state": True,
            "continuation_seed_policy": "frontier_cell_score_distillation"
            if max_continuation_seeds is not None and len(seed_records_override) < len(loaded_seed_records)
            else "full_retained_archive",
        }
        effective_seed_source = "phase2_generation_continuation"
        seed_lineage_root = previous_archive_state.get("seed_lineage_root") or previous_archive_state["run_id"]

    write_json_artifact(
        artifact_root / "generation_launch_progress.json",
        {
            "status": "entering_prototype",
            "created_at": utc_now_iso(),
            "previous_run_root": str(previous_run_root) if previous_run_root else None,
            "rounds": rounds,
            "per_lane_budget": per_lane_budget,
            "artifact_profile": artifact_profile,
            "max_continuation_seeds": max_continuation_seeds,
            "continuation_context": continuation_context,
            "seed_record_count": len(seed_records_override) if seed_records_override is not None else None,
            "real_replay_feedback_active": real_replay_feedback_objective is not None,
        },
        schema_version=PHASE2_GENERATION_SCHEMA_VERSION,
    )

    result = run_phase2_prototype(
        output_root=artifact_root,
        saturation_window_rounds=saturation_window_rounds,
        saturation_distance_epsilon=saturation_distance_epsilon,
        rounds=rounds,
        per_lane_budget=per_lane_budget,
        seed_source=effective_seed_source,
        seed_records_override=seed_records_override,
        seed_lineage_root=seed_lineage_root,
        runtime_mode="generation",
        continuation_context=continuation_context,
        real_replay_feedback_objective=real_replay_feedback_objective,
        artifact_profile=artifact_profile,
    )

    run_root = Path(result["artifact_root"])
    archive_state = read_json_artifact(run_root / "archive_state.json")
    final_report = read_json_artifact(run_root / "phase2_execution_report.json")
    round_report = read_json_artifact(run_root / "round_report.json")
    funnel_statistics = read_json_artifact(run_root / "funnel_statistics.json")
    gate_matrix = read_json_artifact(run_root / "milestone_gate_matrix.json")
    oos_evaluation_report = read_json_artifact(run_root / "oos_evaluation_report.json")

    continuation_manifest = {
        "run_id": result["run_id"],
        "created_at": utc_now_iso(),
        "runtime_mode": "generation",
        "previous_run_root": str(previous_run_root) if previous_run_root else None,
        "previous_run_id": continuation_context["previous_run_id"] if continuation_context else None,
        "continued": previous_run_root is not None,
        "previous_retained_count": continuation_context["previous_retained_count"] if continuation_context else None,
        "initial_archive_size": continuation_context["continuation_seed_count"] if continuation_context else archive_state["retained_count"],
        "final_archive_size": archive_state["retained_count"],
        "round_count": len(round_report["rounds"]),
        "retained_delta": archive_state["retained_count"]
        - (continuation_context["continuation_seed_count"] if continuation_context else 0),
        "max_continuation_seeds": max_continuation_seeds,
        "continuation_seed_policy": continuation_context["continuation_seed_policy"] if continuation_context else None,
    }
    efficiency_audit = _build_generation_efficiency_audit(
        run_id=result["run_id"],
        previous_run_root=previous_run_root,
        archive_state=archive_state,
        round_report=round_report,
        funnel_statistics=funnel_statistics,
        oos_evaluation_report=oos_evaluation_report,
        initial_archive_size_override=continuation_context["continuation_seed_count"] if continuation_context else None,
    )
    generation_report = {
        "run_id": result["run_id"],
        "created_at": utc_now_iso(),
        "runtime_mode": "generation",
        "continued": previous_run_root is not None,
        "generation_goal": "phase2_longer_horizon_isolated_runtime",
        "seed_source": effective_seed_source,
        "per_lane_budget": per_lane_budget,
        "rounds": rounds,
        "artifact_profile": artifact_profile,
        "max_continuation_seeds": max_continuation_seeds,
        "continuation_seed_count": continuation_context["continuation_seed_count"] if continuation_context else None,
        "continuation_seed_policy": continuation_context["continuation_seed_policy"] if continuation_context else None,
        "real_replay_feedback_objective_path": str(real_replay_feedback_objective_path)
        if real_replay_feedback_objective_path
        else None,
        "real_replay_feedback_decision": real_replay_feedback_objective.get("decision")
        if isinstance(real_replay_feedback_objective, dict)
        else None,
        "real_replay_feedback_active": real_replay_feedback_objective is not None,
        "archive_retained_count": archive_state["retained_count"],
        "occupied_cell_count": archive_state["occupied_cell_count"],
        "from_scratch_triggered": round_report["from_scratch_triggered"],
        "generated_from_scratch_count": round_report["generated_from_scratch_count"],
        "funnel_calibration_verdict": funnel_statistics["calibration_verdict"],
        "full_evaluation_ratio": funnel_statistics["full_evaluation_ratio"],
        "generation_efficiency": {
            "archive_growth": efficiency_audit["archive_growth"],
            "retained_yield": efficiency_audit["retained_yield"],
            "avg_generated_per_round": efficiency_audit["avg_generated_per_round"],
            "non_score_retained_ratio": efficiency_audit["non_score_retained_ratio"],
        },
        "gate_status": {name: gate["status"] for name, gate in gate_matrix["gates"].items()},
        "all_gates_pass": all(gate["status"] == "PASS" for gate in gate_matrix["gates"].values()),
        "final_report_runtime_mode": final_report["runtime_mode"],
        "continuation_manifest": continuation_manifest,
    }

    result["continuation_manifest"] = str(run_root / "continuation_manifest.json")
    result["generation_report"] = str(run_root / "generation_report.json")
    result["generation_efficiency_audit"] = str(run_root / "generation_efficiency_audit.json")
    write_json_artifact(
        run_root / "continuation_manifest.json",
        continuation_manifest,
        schema_version=PHASE2_GENERATION_SCHEMA_VERSION,
    )
    write_json_artifact(
        run_root / "generation_report.json",
        generation_report,
        schema_version=PHASE2_GENERATION_SCHEMA_VERSION,
    )
    write_json_artifact(
        run_root / "generation_efficiency_audit.json",
        efficiency_audit,
        schema_version=PHASE2_GENERATION_SCHEMA_VERSION,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def run_phase2_generation_flow(
    *,
    output_root: Path | None = None,
    flow_length: int = 3,
    initial_previous_run_root: Path | None = None,
    real_replay_feedback_objective_path: Path | None = None,
    saturation_window_rounds: int = 2,
    saturation_distance_epsilon: float = 0.18,
    rounds: int = 6,
    per_lane_budget: int = 2,
    seed_source: str = "bootstrap_cold_start",
    artifact_profile: str = "full",
    max_continuation_seeds: int | None = None,
) -> dict[str, Any]:
    if flow_length < 1:
        raise ValueError("flow_length must be >= 1")
    artifact_root = output_root or ARTIFACT_ROOT
    flow_id = _make_flow_id(f"{utc_now_iso()}:{flow_length}:{per_lane_budget}:{rounds}")
    flow_root = artifact_root / flow_id
    previous_run_root = initial_previous_run_root
    runs: list[dict[str, Any]] = []

    for index in range(1, flow_length + 1):
        generation = run_phase2_generation(
            output_root=flow_root,
            previous_run_root=previous_run_root,
            real_replay_feedback_objective_path=real_replay_feedback_objective_path,
            saturation_window_rounds=saturation_window_rounds,
            saturation_distance_epsilon=saturation_distance_epsilon,
            rounds=rounds,
            per_lane_budget=per_lane_budget,
            seed_source=seed_source if previous_run_root is None else "bootstrap_cold_start",
            artifact_profile=artifact_profile,
            max_continuation_seeds=max_continuation_seeds,
        )
        current_run_root = Path(generation["artifact_root"])
        generation_report = read_json_artifact(current_run_root / "generation_report.json")
        efficiency_audit = read_json_artifact(current_run_root / "generation_efficiency_audit.json")
        runs.append(
            {
                "sequence_index": index,
                "run_id": generation["run_id"],
                "artifact_root": generation["artifact_root"],
                "generation_report": generation_report,
                "generation_efficiency_audit": efficiency_audit,
            }
        )
        previous_run_root = current_run_root

    summary = {
        "flow_id": flow_id,
        "created_at": utc_now_iso(),
        "flow_length": flow_length,
        "runtime_mode": "generation_flow",
        "artifact_profile": artifact_profile,
        "max_continuation_seeds": max_continuation_seeds,
        "input_previous_run_root": str(initial_previous_run_root) if initial_previous_run_root else None,
        "real_replay_feedback_objective_path": str(real_replay_feedback_objective_path)
        if real_replay_feedback_objective_path
        else None,
        "runs": [
            {
                "sequence_index": item["sequence_index"],
                "run_id": item["run_id"],
                "archive_growth": item["generation_efficiency_audit"]["archive_growth"],
                "retained_yield": item["generation_efficiency_audit"]["retained_yield"],
                "avg_generated_per_round": item["generation_efficiency_audit"]["avg_generated_per_round"],
                "non_score_retained_ratio": item["generation_efficiency_audit"]["non_score_retained_ratio"],
                "all_gates_pass": item["generation_report"]["all_gates_pass"],
            }
            for item in runs
        ],
        "final_run_id": runs[-1]["run_id"],
        "all_runs_pass": all(item["generation_report"]["all_gates_pass"] for item in runs),
        "archive_growth_trend": [item["generation_efficiency_audit"]["archive_growth"] for item in runs],
        "retained_yield_trend": [item["generation_efficiency_audit"]["retained_yield"] for item in runs],
        "non_score_retained_ratio_trend": [
            item["generation_efficiency_audit"]["non_score_retained_ratio"] for item in runs
        ],
        "continuation_scale_decision": _build_continuation_scale_decision(runs),
    }
    summary_path = flow_root / "multi_run_generation_summary.json"
    write_json_artifact(
        summary_path,
        summary,
        schema_version=PHASE2_GENERATION_SCHEMA_VERSION,
    )
    result = {
        "flow_id": flow_id,
        "artifact_root": str(flow_root),
        "multi_run_generation_summary": str(summary_path),
        "run_roots": [item["artifact_root"] for item in runs],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def _select_best_budget(profiles: list[dict[str, Any]]) -> str | None:
    eligible = [
        profile
        for profile in profiles
        if profile["all_runs_pass"] and float(profile.get("avg_retained_yield", 0.0)) >= YIELD_FLOOR
    ]
    if not eligible:
        return None
    ranked = sorted(
        eligible,
        key=lambda item: (
            item["avg_non_score_retained_ratio"],
            item["avg_retained_yield"],
            item["avg_archive_growth"],
            -item["avg_generated_per_round"],
        ),
        reverse=True,
    )
    return str(ranked[0]["budget"])


def run_phase2_budget_profile_comparison(
    *,
    output_root: Path | None = None,
    budgets: list[int] | None = None,
    real_replay_feedback_objective_path: Path | None = None,
    flow_length: int = 2,
    rounds: int = 4,
    seed_source: str = "bootstrap_cold_start",
    artifact_profile: str = "full",
    max_continuation_seeds: int | None = None,
    saturation_window_rounds: int = 2,
    saturation_distance_epsilon: float = 0.18,
) -> dict[str, Any]:
    artifact_root = output_root or ARTIFACT_ROOT
    profile_budgets = budgets or [1, 2, 3]
    comparison_id = f"phase2-budget-{sha1(f'{utc_now_iso()}:{profile_budgets}:{flow_length}:{rounds}'.encode('utf-8')).hexdigest()[:10]}"
    comparison_root = artifact_root / comparison_id
    profiles: list[dict[str, Any]] = []

    for budget in profile_budgets:
        flow_result = run_phase2_generation_flow(
            output_root=comparison_root,
            flow_length=flow_length,
            real_replay_feedback_objective_path=real_replay_feedback_objective_path,
            rounds=rounds,
            per_lane_budget=budget,
            seed_source=seed_source,
            artifact_profile=artifact_profile,
            max_continuation_seeds=max_continuation_seeds,
            saturation_window_rounds=saturation_window_rounds,
            saturation_distance_epsilon=saturation_distance_epsilon,
        )
        flow_summary = read_json_artifact(Path(flow_result["multi_run_generation_summary"]))
        final_run_root = Path(flow_result["run_roots"][-1])
        final_efficiency = read_json_artifact(final_run_root / "generation_efficiency_audit.json")
        avg_archive_growth = round(
            sum(flow_summary["archive_growth_trend"]) / max(1, len(flow_summary["archive_growth_trend"])),
            6,
        )
        avg_retained_yield = round(
            sum(flow_summary["retained_yield_trend"]) / max(1, len(flow_summary["retained_yield_trend"])),
            6,
        )
        avg_non_score_retained_ratio = round(
            sum(flow_summary["non_score_retained_ratio_trend"])
            / max(1, len(flow_summary["non_score_retained_ratio_trend"])),
            6,
        )
        per_run_yield_floor_warnings = [
            {
                "sequence_index": run["sequence_index"],
                "run_id": run["run_id"],
                "retained_yield": run["retained_yield"],
            }
            for run in flow_summary["runs"]
            if float(run["retained_yield"]) < YIELD_FLOOR
        ]
        yield_floor_pass = avg_retained_yield >= YIELD_FLOOR
        selection_blockers = []
        if not flow_summary["all_runs_pass"]:
            selection_blockers.append("not_all_runs_pass")
        if not yield_floor_pass:
            selection_blockers.append("avg_retained_yield_below_floor")
        profile = {
            "budget": budget,
            "flow_id": flow_summary["flow_id"],
            "flow_length": flow_summary["flow_length"],
            "all_runs_pass": flow_summary["all_runs_pass"],
            "avg_archive_growth": avg_archive_growth,
            "avg_retained_yield": avg_retained_yield,
            "avg_non_score_retained_ratio": avg_non_score_retained_ratio,
            "yield_floor": YIELD_FLOOR,
            "yield_floor_pass": yield_floor_pass,
            "min_run_retained_yield": min(flow_summary["retained_yield_trend"]),
            "per_run_yield_floor_warnings": per_run_yield_floor_warnings,
            "selection_eligible": not selection_blockers,
            "selection_blockers": selection_blockers,
            "avg_generated_per_round": final_efficiency["avg_generated_per_round"],
            "total_generated_candidates": final_efficiency["total_generated_candidates"],
            "total_retained_candidates": final_efficiency["total_retained_candidates"],
            "full_evaluation_ratio": final_efficiency["full_evaluation_ratio"],
            "funnel_calibration_verdict": final_efficiency["funnel_calibration_verdict"],
            "final_run_id": flow_summary["final_run_id"],
            "final_run_root": str(final_run_root),
        }
        profiles.append(profile)

    comparison = {
        "comparison_id": comparison_id,
        "created_at": utc_now_iso(),
        "runtime_mode": "generation_budget_profiles",
        "budgets": profile_budgets,
        "flow_length": flow_length,
        "rounds": rounds,
        "artifact_profile": artifact_profile,
        "profiles": profiles,
        "real_replay_feedback_objective_path": str(real_replay_feedback_objective_path)
        if real_replay_feedback_objective_path
        else None,
        "best_budget": _select_best_budget(profiles),
        "yield_floor": YIELD_FLOOR,
        "yield_floor_policy": "budget profile eligibility requires avg_retained_yield >= yield_floor; per-run misses are warnings",
        "selection_rule": (
            "eligible profiles must all_runs_pass and avg_retained_yield >= yield_floor; then rank by "
            "avg_non_score_retained_ratio, avg_retained_yield, avg_archive_growth, lower avg_generated_per_round"
        ),
    }

    comparison_path = comparison_root / "budget_profile_comparison.json"
    write_json_artifact(
        comparison_path,
        comparison,
        schema_version=PHASE2_GENERATION_SCHEMA_VERSION,
    )
    result = {
        "comparison_id": comparison_id,
        "artifact_root": str(comparison_root),
        "budget_profile_comparison": str(comparison_path),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def run_phase2_bootstrap_independence_precheck(
    *,
    output_root: Path | None = None,
    variants_per_prototype: int = 4,
) -> dict[str, Any]:
    artifact_root = output_root or ARTIFACT_ROOT
    precheck_id = f"phase2-bootstrap-precheck-{sha1(f'{utc_now_iso()}:{variants_per_prototype}'.encode('utf-8')).hexdigest()[:10]}"
    precheck_root = artifact_root / precheck_id
    bootstrap = Phase2BootstrapLayer()
    seed_formulas = bootstrap.cold_start(variants_per_prototype=variants_per_prototype)
    bootstrap_result = bootstrap.build_initial_archive(seed_formulas, raise_on_low_coverage=False)
    bootstrap_report = bootstrap_result.report
    behavior_cell_count = len(bootstrap_report["occupied_behavior_cells"])
    coverage = round(behavior_cell_count / BEHAVIOR_GRID_MAX_CELLS, 6)
    decision = (
        "direct_bootstrap_independence"
        if coverage > BOOTSTRAP_INDEPENDENCE_COVERAGE_THRESHOLD
        else "prototype_formula_family_expansion_first"
    )
    precheck_report = {
        "precheck_id": precheck_id,
        "created_at": utc_now_iso(),
        "runtime_mode": "bootstrap_independence_precheck",
        "assumption": "simulate disconnecting V1 archive seeds by using Phase2 bootstrap cold_start only",
        "depends_on_v1_archive": bootstrap_report["depends_on_v1_archive"],
        "variants_per_prototype": variants_per_prototype,
        "prototype_family_count": len(bootstrap_report["prototype_names"]),
        "generated_formula_count": bootstrap_report["seed_formula_count"],
        "legal_formula_count": bootstrap_report["accepted_seed_count"],
        "rejected_formula_count": bootstrap_report["rejected_seed_count"],
        "behavior_grid_max_cells": BEHAVIOR_GRID_MAX_CELLS,
        "occupied_behavior_cell_count": behavior_cell_count,
        "occupied_behavior_cells": bootstrap_report["occupied_behavior_cells"],
        "behavior_grid_coverage": coverage,
        "decision_threshold": BOOTSTRAP_INDEPENDENCE_COVERAGE_THRESHOLD,
        "coverage_pass": coverage > BOOTSTRAP_INDEPENDENCE_COVERAGE_THRESHOLD,
        "step4_decision": decision,
        "step4_rule": "if coverage > 10% do Bootstrap independence; otherwise expand prototype formula families first",
        "bootstrap_report": bootstrap_report,
    }
    report_path = precheck_root / "bootstrap_independence_precheck.json"
    write_json_artifact(
        report_path,
        precheck_report,
        schema_version=PHASE2_GENERATION_SCHEMA_VERSION,
    )
    result = {
        "precheck_id": precheck_id,
        "artifact_root": str(precheck_root),
        "bootstrap_independence_precheck": str(report_path),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def run_phase2_discarded_space_probe(
    *,
    run_root: Path,
    sample_limit: int = 32,
) -> dict[str, Any]:
    """Report-only reverse experiment for edge hiding in rejected candidates.

    This does not change archive retention. It asks whether candidates discarded
    by behavior-cell dominance would have looked more tradeable under the same
    friction-aware proxy used by the retained edge reality report.
    """
    ledger_path = run_root / "candidate_ledger.json"
    if not ledger_path.exists():
        raise ValueError(f"candidate_ledger.json not found in {run_root}")

    ledger = read_json_artifact(ledger_path)
    generated = [
        CandidateRecord(**payload)
        for payload in ledger.get("records", [])
        if int(payload.get("round_index", 0)) > 0
    ]
    report = {
        **build_discarded_space_shadow_report(
            run_id=ledger["run_id"],
            records=generated,
            sample_limit=sample_limit,
        ),
        "runtime_mode": "discarded_space_reverse_probe",
        "candidate_ledger": str(ledger_path),
    }
    report["interpretation"] = (
        "investigate_discarded_space_before_tightening_archive_dominance"
        if report["counterfactual_hit_count_in_sample"] > 0
        else "no_discarded_edge_proxy_found_in_sample"
    )
    report_path = run_root / "discarded_space_probe.json"
    write_json_artifact(
        report_path,
        report,
        schema_version=PHASE2_GENERATION_SCHEMA_VERSION,
    )
    result = {
        "run_id": ledger["run_id"],
        "artifact_root": str(run_root),
        "discarded_space_probe": str(report_path),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run isolated Alpha Search System V2.1 generation runtime.")
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--previous-run-root", type=Path, default=None)
    parser.add_argument("--probe-run-root", type=Path, default=None)
    parser.add_argument("--flow-length", type=int, default=1)
    parser.add_argument("--budget-profiles", type=int, nargs="*", default=None)
    parser.add_argument("--bootstrap-independence-precheck", action="store_true")
    parser.add_argument("--discarded-space-probe", action="store_true")
    parser.add_argument("--discarded-sample-limit", type=int, default=32)
    parser.add_argument("--real-replay-feedback-objective", type=Path, default=None)
    parser.add_argument("--variants-per-prototype", type=int, default=4)
    parser.add_argument("--saturation-window-rounds", type=int, default=2)
    parser.add_argument("--saturation-distance-epsilon", type=float, default=0.18)
    parser.add_argument("--rounds", type=int, default=6)
    parser.add_argument("--per-lane-budget", type=int, default=2)
    parser.add_argument("--seed-source", choices=("phase1_seed", "bootstrap_cold_start"), default="bootstrap_cold_start")
    parser.add_argument("--artifact-profile", choices=("full", "compact"), default="full")
    parser.add_argument("--max-continuation-seeds", type=int, default=None)
    args = parser.parse_args()
    if args.discarded_space_probe:
        probe_root = args.probe_run_root or args.previous_run_root
        if probe_root is None:
            raise ValueError("--discarded-space-probe requires --probe-run-root or --previous-run-root")
        run_phase2_discarded_space_probe(
            run_root=probe_root,
            sample_limit=args.discarded_sample_limit,
        )
    elif args.bootstrap_independence_precheck:
        run_phase2_bootstrap_independence_precheck(
            output_root=args.output_root,
            variants_per_prototype=args.variants_per_prototype,
        )
    elif args.budget_profiles and len(args.budget_profiles) > 1:
        run_phase2_budget_profile_comparison(
            output_root=args.output_root,
            budgets=args.budget_profiles,
            real_replay_feedback_objective_path=args.real_replay_feedback_objective,
            flow_length=args.flow_length,
            rounds=args.rounds,
            seed_source=args.seed_source,
            artifact_profile=args.artifact_profile,
            max_continuation_seeds=args.max_continuation_seeds,
            saturation_window_rounds=args.saturation_window_rounds,
            saturation_distance_epsilon=args.saturation_distance_epsilon,
        )
    elif args.flow_length > 1:
        run_phase2_generation_flow(
            output_root=args.output_root,
            flow_length=args.flow_length,
            initial_previous_run_root=args.previous_run_root,
            real_replay_feedback_objective_path=args.real_replay_feedback_objective,
            saturation_window_rounds=args.saturation_window_rounds,
            saturation_distance_epsilon=args.saturation_distance_epsilon,
            rounds=args.rounds,
            per_lane_budget=args.per_lane_budget,
            seed_source=args.seed_source,
            artifact_profile=args.artifact_profile,
            max_continuation_seeds=args.max_continuation_seeds,
        )
    else:
        run_phase2_generation(
            output_root=args.output_root,
            previous_run_root=args.previous_run_root,
            real_replay_feedback_objective_path=args.real_replay_feedback_objective,
            saturation_window_rounds=args.saturation_window_rounds,
            saturation_distance_epsilon=args.saturation_distance_epsilon,
            rounds=args.rounds,
            per_lane_budget=args.per_lane_budget,
            seed_source=args.seed_source,
            artifact_profile=args.artifact_profile,
            max_continuation_seeds=args.max_continuation_seeds,
        )


if __name__ == "__main__":
    main()
